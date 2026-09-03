"""Google Shopping Now — Apify Actor.

Interroga l'API di Scrape.do per Google Shopping Search e salva nel
Dataset di Apify esclusivamente i singoli elementi dell'array
"shopping_results", come record piatti (senza array o oggetti radice).
"""

import asyncio
import os
import traceback
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
        Actor.log.info("Step 1: Reading Scrape.do API token from environment...")
        token = (
            os.environ.get("SCRAPE_DO_TOKEN", "").strip()
            or os.environ.get("SCRAPE_DO_API_KEY", "").strip()
        )
        if not token:
            msg = (
                "Missing Scrape.do API token. "
                "Please set the SCRAPE_DO_TOKEN (or SCRAPE_DO_API_KEY) "
                "environment variable in the Actor settings."
            )
            Actor.log.info(f"ERROR: {msg}")
            await Actor.fail(status_message=msg)
            return  # unreachable, but keeps the type checker happy

        Actor.log.info("Token found (length=%d, starts with '%s...')", len(token), token[:4])

        # ── 2. Read and validate Actor input ────────────────────────
        Actor.log.info("Step 2: Reading Actor input...")
        input_data: Dict[str, Any] = await Actor.get_input() or {}
        Actor.log.info(f"Raw input received: {input_data}")

        query: Optional[str] = input_data.get("query")
        if not query or not str(query).strip():
            msg = (
                "The 'query' input parameter is required. "
                "Please provide a search query (e.g. 'laptop')."
            )
            Actor.log.info(f"ERROR: {msg}")
            await Actor.fail(status_message=msg)
            return

        query = str(query).strip()
        Actor.log.info(f"Search query: {query!r}")

        # Optional parameters
        Actor.log.info("Step 2b: Parsing optional parameters...")
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
                    Actor.log.info(f"max_results={raw_max_results} is <= 0, ignoring limit")
                    max_results = None
            except (ValueError, TypeError) as exc:
                Actor.log.info(f"ERROR parsing max_results={raw_max_results!r}: {exc}. Ignoring limit.")
                max_results = None

        Actor.log.info(
            f"Configuration — query={query!r}, hl={hl}, gl={gl}, "
            f"google_domain={google_domain}, min_price={min_price}, "
            f"max_price={max_price}, sort_by={sort_by}, "
            f"free_shipping={free_shipping}, on_sale={on_sale}, "
            f"max_results={max_results}"
        )

        # ── 3. Build query parameters (only defined values) ─────────
        Actor.log.info("Step 3: Building API query parameters...")
        params: Dict[str, Any] = {
            "token": token,
            "q": query,
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

        # Log params without the token for security
        safe_params = {k: v for k, v in params.items() if k != "token"}
        Actor.log.info(f"Query parameters (token hidden): {safe_params}")

        # ── 4. Make the API request ─────────────────────────────────
        Actor.log.info(f"Step 4: Sending GET request to {API_URL} (timeout={REQUEST_TIMEOUT}s)...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    API_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
        except httpx.TimeoutException as exc:
            msg = (
                f"Request timed out after {REQUEST_TIMEOUT}s. "
                "The Scrape.do API did not respond in time."
            )
            Actor.log.info(f"ERROR: {msg}")
            Actor.log.info(f"Exception details: {exc}")
            Actor.log.info(f"Traceback:\n{traceback.format_exc()}")
            await Actor.fail(status_message=msg)
            return
        except httpx.NetworkError as exc:
            msg = f"Network error while contacting Scrape.do API: {exc}"
            Actor.log.info(f"ERROR: {msg}")
            Actor.log.info(f"Traceback:\n{traceback.format_exc()}")
            await Actor.fail(status_message=msg)
            return
        except Exception as exc:
            msg = f"Unexpected error during HTTP request: {type(exc).__name__}: {exc}"
            Actor.log.info(f"ERROR: {msg}")
            Actor.log.info(f"Traceback:\n{traceback.format_exc()}")
            await Actor.fail(status_message=msg)
            return

        Actor.log.info(f"Response received — HTTP {response.status_code}")
        Actor.log.info(f"Response headers: {dict(response.headers)}")
        Actor.log.info(f"Response body length: {len(response.text)} chars")

        # Handle rate limiting (HTTP 429)
        if response.status_code == 429:
            msg = (
                "Scrape.do API returned HTTP 429 (Too Many Requests). "
                "You have exceeded your rate limit. Please wait and try again."
            )
            Actor.log.info(f"ERROR: {msg}")
            Actor.log.info(f"Response body: {response.text[:1000]}")
            await Actor.fail(status_message=msg)
            return

        if response.status_code >= 400:
            body_preview = response.text[:1000] if response.text else "(empty body)"
            msg = (
                f"Scrape.do API returned HTTP {response.status_code}. "
                f"Response: {body_preview}"
            )
            Actor.log.info(f"ERROR: {msg}")
            await Actor.fail(status_message=msg)
            return

        Actor.log.info(f"HTTP {response.status_code} — OK")

        # ── 5. Parse response ───────────────────────────────────────
        Actor.log.info("Step 5: Parsing JSON response...")
        try:
            data: Dict[str, Any] = response.json()
        except Exception as exc:
            msg = f"Failed to parse JSON from Scrape.do API response: {exc}"
            Actor.log.info(f"ERROR: {msg}")
            Actor.log.info(f"Raw response (first 1000 chars): {response.text[:1000]}")
            Actor.log.info(f"Traceback:\n{traceback.format_exc()}")
            await Actor.fail(status_message=msg)
            return

        Actor.log.info(f"JSON parsed successfully — top-level keys: {list(data.keys())}")

        # Log presence of other keys for debugging
        for key in data.keys():
            if key == "shopping_results":
                continue
            value = data[key]
            if isinstance(value, list):
                Actor.log.info(f"  Key '{key}': list with {len(value)} items (ignored)")
            elif isinstance(value, dict):
                Actor.log.info(f"  Key '{key}': dict with keys {list(value.keys())} (ignored)")
            else:
                Actor.log.info(f"  Key '{key}': {type(value).__name__} = {str(value)[:200]} (ignored)")

        shopping_results = data.get("shopping_results", [])

        if not isinstance(shopping_results, list):
            Actor.log.info(
                f"INFO: 'shopping_results' is not a list — got {type(shopping_results).__name__}. "
                "Wrapping in a list."
            )
            shopping_results = [shopping_results] if shopping_results else []

        Actor.log.info(f"Extracted {len(shopping_results)} products from 'shopping_results'")

        if not shopping_results:
            Actor.log.info(
                "INFO: No shopping results found. The query may have returned "
                "zero products, or the response structure may have changed."
            )
            Actor.log.info(f"Available response keys: {list(data.keys())}")
            Actor.log.info(f"Full response (first 2000 chars): {response.text[:2000]}")
        else:
            # Log a sample product for debugging
            Actor.log.info(f"Sample product (first result): {shopping_results[0]}")

        # ── 6. Apply max_results limit ──────────────────────────────
        if max_results is not None and len(shopping_results) > max_results:
            Actor.log.info(
                f"Step 6: Limiting results to max_results={max_results} "
                f"(from {len(shopping_results)})"
            )
            shopping_results = shopping_results[:max_results]
        else:
            Actor.log.info(f"Step 6: No limit applied — returning all {len(shopping_results)} results")

        # ── 7. Push to Dataset (flat records only) ──────────────────
        if shopping_results:
            Actor.log.info(f"Step 7: Pushing {len(shopping_results)} product records to Dataset...")
            try:
                await Actor.push_data(shopping_results)
                Actor.log.info(f"Successfully pushed {len(shopping_results)} records to Dataset")
            except Exception as exc:
                msg = f"Failed to push data to Dataset: {type(exc).__name__}: {exc}"
                Actor.log.info(f"ERROR: {msg}")
                Actor.log.info(f"Traceback:\n{traceback.format_exc()}")
                await Actor.fail(status_message=msg)
                return
        else:
            Actor.log.info("Step 7: Nothing to push — Dataset will remain empty for this run.")

        # ── 8. Done ─────────────────────────────────────────────────
        Actor.log.info("=" * 60)
        Actor.log.info("ACTOR COMPLETED SUCCESSFULLY")
        Actor.log.info(f"Total products in Dataset: {len(shopping_results)}")
        Actor.log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
