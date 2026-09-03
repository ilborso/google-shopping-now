"""Google Shopping Now — Apify Actor.

Interroga l'API di Scrape.do per Google Shopping Search e salva nel
Dataset di Apify esclusivamente i singoli elementi dell'array
"shopping_results", come record piatti (senza array o oggetti radice).
"""

import asyncio
import os
from typing import Any, Dict, Optional

import httpx
from apify import Actor

# Scrape.do Google Shopping endpoint
API_URL = "https://api.scrape.do/plugin/google/shopping"

# Request configuration
REQUEST_TIMEOUT = 60  # seconds – Shopping queries can be slower


async def main() -> None:
    """Main entry point of the Actor."""
    async with Actor:
        Actor.log.info("=" * 60)
        Actor.log.info("GOOGLE SHOPPING NOW ACTOR STARTED")
        Actor.log.info("=" * 60)

        # ── 1. Read and validate Scrape.do token ────────────────────
        token = (
            os.environ.get("SCRAPE_DO_TOKEN", "").strip()
            or os.environ.get("SCRAPE_DO_API_KEY", "").strip()
        )
        if not token:
            await Actor.fail(
                status_message=(
                    "Missing Scrape.do API token. "
                    "Please set the SCRAPE_DO_TOKEN (or SCRAPE_DO_API_KEY) "
                    "environment variable in the Actor settings."
                )
            )
            return  # unreachable, but keeps the type checker happy

        # ── 2. Read and validate Actor input ────────────────────────
        input_data: Dict[str, Any] = await Actor.get_input() or {}

        query: Optional[str] = input_data.get("query")
        if not query or not str(query).strip():
            await Actor.fail(
                status_message=(
                    "The 'query' input parameter is required. "
                    "Please provide a search query (e.g. 'laptop')."
                )
            )
            return

        query = str(query).strip()

        # Optional parameters
        min_price: Optional[int] = input_data.get("min_price")
        max_price: Optional[int] = input_data.get("max_price")
        sort_by: Optional[int] = input_data.get("sort_by")
        free_shipping: bool = bool(input_data.get("free_shipping", False))
        on_sale: bool = bool(input_data.get("on_sale", False))
        hl: str = input_data.get("hl") or "en"
        gl: str = input_data.get("gl") or "us"
        google_domain: str = input_data.get("google_domain") or "google.com"

        raw_max_results = input_data.get("max_results")
        max_results: Optional[int] = None
        if raw_max_results is not None:
            try:
                max_results = int(raw_max_results)
                if max_results <= 0:
                    max_results = None
            except (ValueError, TypeError):
                max_results = None

        Actor.log.info(
            f"Configuration — query={query!r}, hl={hl}, gl={gl}, "
            f"google_domain={google_domain}, min_price={min_price}, "
            f"max_price={max_price}, sort_by={sort_by}, "
            f"free_shipping={free_shipping}, on_sale={on_sale}, "
            f"max_results={max_results}"
        )

        # ── 3. Build query parameters (only defined values) ─────────
        params: Dict[str, Any] = {
            "token": token,
            "query": query,
            "hl": hl,
            "gl": gl,
            "google_domain": google_domain,
        }

        if min_price is not None:
            params["min_price"] = int(min_price)
        if max_price is not None:
            params["max_price"] = int(max_price)
        if sort_by is not None:
            params["sort_by"] = int(sort_by)
        if free_shipping:
            params["free_shipping"] = "true"
        if on_sale:
            params["on_sale"] = "true"

        # ── 4. Make the API request ─────────────────────────────────
        Actor.log.info(f"Requesting {API_URL} ...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    API_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
        except httpx.TimeoutException:
            await Actor.fail(
                status_message=(
                    f"Request timed out after {REQUEST_TIMEOUT}s. "
                    "The Scrape.do API did not respond in time."
                )
            )
            return
        except httpx.NetworkError as exc:
            await Actor.fail(
                status_message=f"Network error while contacting Scrape.do API: {exc}"
            )
            return

        Actor.log.info(f"Response status: {response.status_code}")

        # Handle rate limiting (HTTP 429)
        if response.status_code == 429:
            await Actor.fail(
                status_message=(
                    "Scrape.do API returned HTTP 429 (Too Many Requests). "
                    "You have exceeded your rate limit. Please wait and try again."
                )
            )
            return

        if response.status_code >= 400:
            body_preview = response.text[:500] if response.text else "(empty body)"
            await Actor.fail(
                status_message=(
                    f"Scrape.do API returned HTTP {response.status_code}. "
                    f"Response: {body_preview}"
                )
            )
            return

        # ── 5. Parse response ───────────────────────────────────────
        try:
            data: Dict[str, Any] = response.json()
        except Exception as exc:
            await Actor.fail(
                status_message=f"Failed to parse JSON from Scrape.do API response: {exc}"
            )
            return

        shopping_results = data.get("shopping_results", [])

        if not isinstance(shopping_results, list):
            Actor.log.warning(
                "The 'shopping_results' key is not a list. "
                f"Got type: {type(shopping_results).__name__}. Wrapping in a list."
            )
            shopping_results = [shopping_results] if shopping_results else []

        Actor.log.info(f"Extracted {len(shopping_results)} products from 'shopping_results'")

        if not shopping_results:
            Actor.log.warning(
                "No shopping results found. The query may have returned "
                "zero products, or the response structure may have changed."
            )
            # Log available top-level keys for debugging
            Actor.log.info(f"Available response keys: {list(data.keys())}")

        # ── 6. Apply max_results limit ──────────────────────────────
        if max_results is not None and len(shopping_results) > max_results:
            Actor.log.info(
                f"Limiting results to max_results={max_results} "
                f"(from {len(shopping_results)})"
            )
            shopping_results = shopping_results[:max_results]

        # ── 7. Push to Dataset (flat records only) ──────────────────
        if shopping_results:
            Actor.log.info("Pushing shopping results as individual records to Dataset")
            await Actor.push_data(shopping_results)
            Actor.log.info(f"Pushed {len(shopping_results)} product records to Dataset")
        else:
            Actor.log.info("Nothing to push — Dataset will remain empty for this run.")

        # ── 7. Done ─────────────────────────────────────────────────
        Actor.log.info("=" * 60)
        Actor.log.info("ACTOR COMPLETED SUCCESSFULLY")
        Actor.log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
