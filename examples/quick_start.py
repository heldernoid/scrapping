"""
Quick start example: scrape ShopSphere SSR with a hand-written config.

Run from the repo root:
    python examples/quick_start.py

Prerequisites:
    uv sync
    cd demo-sites && docker compose up -d
"""

import asyncio
import json
import httpx
from bs4 import BeautifulSoup

# ---- Config ----------------------------------------------------------------

CONFIG = {
    "render_mode": "static",
    "sources": [
        {
            "url_template": "http://localhost:8001/products?page={n}",
            "pagination": {
                "start": 1,
                "step": 1,
                "max_pages": 10,
                "stop_condition": "no_results",
            },
        }
    ],
    "listing": {
        "link_selector": ".product-card a.product-link",
        "link_prefix": "http://localhost:8001",
    },
    "fields": {
        "title":    {"selector": "h1.product-title",        "retrieve": "plaintext"},
        "price":    {"selector": "span.price-amount",       "retrieve": "plaintext"},
        "rating":   {"selector": "[data-rating]",           "retrieve": "attr", "attr": "data-rating"},
        "category": {"selector": ".product-category-badge", "retrieve": "plaintext"},
        "in_stock":      {"selector": ".stock-status",        "retrieve": "plaintext"},
        "image":         {"selector": "img.product-image-main","retrieve": "attr", "attr": "src"},
        "gallery_images":{"selector": "img.gallery-image",     "retrieve": "attr", "attr": "src",
                          "multiple": True},
    },
}

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

# ---- Engine ----------------------------------------------------------------

def extract_fields(soup: BeautifulSoup, fields: dict) -> dict:
    record = {}
    for name, spec in fields.items():
        selector = spec.get("selector")
        retrieve = spec.get("retrieve", "plaintext")
        attr = spec.get("attr")
        multiple = spec.get("multiple", False)

        if not selector:
            continue

        if multiple:
            elements = soup.select(selector)
            if retrieve == "plaintext":
                record[name] = [el.get_text(strip=True) for el in elements]
            elif retrieve == "attr":
                record[name] = [el.get(attr) for el in elements if el.get(attr)]
            else:
                record[name] = [el.get_text(strip=True) for el in elements]
        else:
            element = soup.select_one(selector)
            if element is None:
                record[name] = None
            elif retrieve == "plaintext":
                record[name] = element.get_text(strip=True)
            elif retrieve == "attr":
                record[name] = element.get(attr)
            elif retrieve == "regexp":
                import re
                text = element.get_text(strip=True)
                match = re.search(spec.get("pattern", "(.*)"), text)
                record[name] = match.group(1) if match else None

    return record


async def collect_listing_links(
    client: httpx.AsyncClient,
    source: dict,
    listing: dict,
) -> list[str]:
    template = source["url_template"]
    pagination = source.get("pagination", {})
    start = pagination.get("start", 1)
    step = pagination.get("step", 1)
    max_pages = pagination.get("max_pages", 10)
    link_selector = listing.get("link_selector", "a")
    link_prefix = listing.get("link_prefix", "")

    all_links = []

    for page_num in range(max_pages):
        n = start + page_num * step
        url = template.replace("{n}", str(n))

        print(f"  Fetching listing page: {url}")
        resp = await client.get(url)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.select(link_selector)

        if not links:
            print(f"  No links found on page {n} - stopping pagination")
            break

        for link in links:
            href = link.get("href", "")
            if href.startswith("/"):
                href = link_prefix + href
            all_links.append(href)

        await asyncio.sleep(0.1)  # Polite delay

    return all_links


async def scrape(config: dict, max_items: int = 10) -> list[dict]:
    listing = config.get("listing", {})
    fields = config.get("fields", {})
    results = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        # Collect detail page links
        all_links = []
        for source in config.get("sources", []):
            links = await collect_listing_links(client, source, listing)
            all_links.extend(links)

        all_links = all_links[:max_items]
        print(f"\nCollected {len(all_links)} product links")

        # Fetch and extract from each detail page
        semaphore = asyncio.Semaphore(4)

        async def fetch_detail(url: str) -> dict | None:
            async with semaphore:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None
                soup = BeautifulSoup(resp.text, "lxml")
                record = extract_fields(soup, fields)
                record["url"] = url
                return record

        tasks = [fetch_detail(url) for url in all_links]
        raw_results = await asyncio.gather(*tasks)
        results = [r for r in raw_results if r]

    return results


# ---- Main ------------------------------------------------------------------

async def main():
    print("ShopSphere SSR Quick Start Scraper")
    print("=" * 40)
    print()

    # Check the site is reachable
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=5) as client:
            resp = await client.get("http://localhost:8001/products")
            if resp.status_code != 200:
                print(f"ERROR: ShopSphere SSR returned HTTP {resp.status_code}")
                print("Make sure the demo sites are running: cd demo-sites && docker compose up -d")
                return
    except httpx.ConnectError:
        print("ERROR: Cannot connect to http://localhost:8001")
        print("Make sure the demo sites are running: cd demo-sites && docker compose up -d")
        return

    print("Collecting products (up to 10)...")
    print()

    results = await scrape(CONFIG, max_items=10)

    print()
    print(f"Scraped {len(results)} products:")
    print()

    for i, product in enumerate(results, 1):
        in_stock_text = product.get("in_stock", "")
        in_stock = "Yes" if in_stock_text == "In Stock" else "No"
        print(f"{i:2}. {product.get('title', 'N/A')}")
        print(f"     Price: {product.get('price', 'N/A')} | "
              f"Rating: {product.get('rating', 'N/A')} | "
              f"Category: {product.get('category', 'N/A')} | "
              f"In Stock: {in_stock}")

    print()
    print("Full JSON output:")
    print(json.dumps(results[:2], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
