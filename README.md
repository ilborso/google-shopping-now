# Google Shopping Now

An Apify Actor that fetches Google Shopping search results and saves each product as an individual record in an Apify Dataset.

## What does this Actor do?

This Actor:
1. Accepts a search query and optional filters (price range, sorting, shipping, sale, localization)
2. Extracts only the shopping results without ads. It pushes each product as a flat record to the Apify Dataset

Perfect for price monitoring, competitor analysis, product research, e-commerce intelligence, and market comparisons.

## Why use Google Shopping Now?

- **Flat product records** — Each product is stored as an individual Dataset row, ready for export
- **Flexible filtering** — Filter by price range, free shipping, on sale, and sorting
- **Localization support** — Choose language, country, and Google domain
- **Clean output** — No root wrappers, no `search_parameters`, no `ads`, no `filters` — just products
- **Production-ready** — Robust error handling with descriptive failure messages and rate limit detection
- **Sponsored products are ignored.** — We don' return sponsored products

## Input Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | **Yes** | — | Search query (e.g. `"laptop"`, `"wireless headphones"`) |
| `min_price` | integer | No | — | Minimum price filter |
| `max_price` | integer | No | — | Maximum price filter |
| `sort_by` | integer | No | — | Sort order: `0` = relevance, `1` = price low→high, `2` = price high→low |
| `free_shipping` | boolean | No | `false` | Show only products with free shipping |
| `on_sale` | boolean | No | `false` | Show only products currently on sale |
| `max_results` | integer | No | — | Maximum number of products to return (empty = all) |
| `hl` | string | No | `"en"` | Host language code (e.g. `en`, `it`, `de`, `fr`) |
| `gl` | string | No | `"us"` | Country perspective (ISO 3166-1 alpha-2, e.g. `us`, `gb`, `de`) |
| `google_domain` | string | No | `"google.com"` | Google domain to query (e.g. `google.it`, `google.de`) |

### Example Scenarios

| Description | JSON Input |
|:---|:---|
| Search laptops in the US | `{"query": "laptop"}` |
| Cheap headphones, price low to high | `{"query": "headphones", "max_price": 50, "sort_by": 1}` |
| On-sale sneakers with free shipping | `{"query": "sneakers", "free_shipping": true, "on_sale": true}` |
| Search in Italy, Italian language | `{"query": "smartphone", "hl": "it", "gl": "it", "google_domain": "google.it"}` |
| Premium monitors, $500–$1500 | `{"query": "monitor 4k", "min_price": 500, "max_price": 1500}` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SCRAPE_DO_TOKEN` | **Yes** | Your Scrape.do API token |
| `SCRAPE_DO_API_KEY` | Alternative | Alternative name for the same token |

Set the token in the Actor's **Environment Variables** settings on the Apify platform.

## Example Input

```json
{
    "query": "laptop",
    "min_price": 300,
    "max_price": 1000,
    "sort_by": 1,
    "free_shipping": true,
    "hl": "en",
    "gl": "us",
    "google_domain": "google.com"
}
```

## Output

Each product from the `shopping_results` array is pushed as an individual flat record to the Apify Dataset. No root objects, no `search_parameters`, no `ads`, no `filters`.

```json
[
  {
    "position": 1,
    "title": "Lenovo IdeaPad 3 15.6\" Laptop",
    "price": "$349.99",
    "extracted_price": 349.99,
    "old_price": "$449.99",
    "extracted_old_price": 449.99,
    "source": "Best Buy",
    "rating": 4.5,
    "reviews": 1234,
    "delivery": "Free delivery by Fri, Sep 5",
    "badge": "Sale",
    "thumbnail": "https://encrypted-tbn0.gstatic.com/shopping?q=...",
    "link": "https://www.bestbuy.com/site/lenovo-ideapad-3/...",
    "product_id": "abc123xyz"
  },
  {
    "position": 2,
    "title": "HP Pavilion 15.6\" Touch-Screen Laptop",
    "price": "$499.00",
    "extracted_price": 499.0,
    "source": "Amazon.com",
    "rating": 4.3,
    "reviews": 876,
    "delivery": "Free shipping",
    "thumbnail": "https://encrypted-tbn0.gstatic.com/shopping?q=...",
    "link": "https://www.amazon.com/HP-Pavilion/dp/...",
    "product_id": "def456uvw"
  }
]
```

> **Note**: The exact fields returned depend on what Google Shopping provides for each product. Fields like `old_price`, `extracted_old_price`, `badge`, and `delivery` may not be present for every item.

## Dataset Views

The Actor provides two pre-configured views in the Apify Dataset:

| View | Description | Key Fields |
|------|-------------|------------|
| **Shopping Results** | Compact overview | title, price, source, rating, reviews, link, thumbnail |
| **Full Product Details** | All available fields | All of the above + old_price, delivery, badge, product_id, position |

## Error Handling

The Actor fails gracefully with descriptive messages for:

| Scenario | Behavior |
|----------|----------|
| Missing API token | `Actor.fail()` with instructions to set `SCRAPE_DO_TOKEN` |
| Missing query | `Actor.fail()` with instructions to provide a search query |
| HTTP 429 (rate limit) | `Actor.fail()` with rate limit exceeded message |
| HTTP 4xx/5xx errors | `Actor.fail()` with status code and response preview |
| Network timeout | `Actor.fail()` with timeout duration |
| Invalid JSON response | `Actor.fail()` with parse error details |
| Empty results | Warning log with available response keys for debugging |
