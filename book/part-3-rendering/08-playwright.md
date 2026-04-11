# Chapter 8: Playwright for Dynamic Content

When a site loads its content through JavaScript rather than returning it in the initial HTML response, static fetching returns an empty shell. Playwright solves this by operating a real browser: it downloads the page, executes JavaScript, waits for the DOM to stabilize, and returns the fully rendered HTML.

This chapter covers Playwright's integration with the scraping engine: launching browsers, navigating pages, waiting for content, and extracting data from the rendered DOM.

## Why Playwright Over Selenium

Playwright is the modern choice for browser automation. Compared to Selenium:

- **Async-native**: Playwright's Python API is designed for asyncio
- **Auto-wait**: Playwright waits for elements to be visible before interacting, reducing flaky tests
- **Network interception**: Playwright can intercept and modify network requests
- **Multiple browsers**: Chromium, Firefox, and WebKit (Safari engine) with a single API
- **Faster**: Playwright's protocol is more efficient than the WebDriver protocol used by Selenium

For scraping, the key advantage is async support - `async with async_playwright()` integrates naturally with the async scraping engine.

## Basic Playwright Fetch

The minimal pattern: launch a browser, navigate to a URL, wait for the page to load, and return the HTML.

```python
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def fetch_playwright(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")

        html = await page.content()
        await browser.close()
        return html

# Use exactly like fetch_static
html = await fetch_playwright("http://localhost:8002/products")
soup = BeautifulSoup(html, "lxml")
cards = soup.select("article.product-card")
print(f"Found {len(cards)} products")  # 10 products, unlike with static fetch
```

`wait_until="networkidle"` tells Playwright to wait until no network requests have been made for 500 milliseconds. This is the standard approach for CSR sites: wait until the JavaScript has finished fetching data and rendering the DOM.

## The `wait_until` Options

Different pages need different wait strategies:

```python
# "load": Wait for the load event (DOMContentLoaded + all resources)
await page.goto(url, wait_until="load")

# "domcontentloaded": Wait for initial HTML parse only (faster, before images)
await page.goto(url, wait_until="domcontentloaded")

# "networkidle": Wait until no network requests for 500ms (most thorough)
await page.goto(url, wait_until="networkidle")

# "commit": Return as soon as navigation started (rarely useful for scraping)
await page.goto(url, wait_until="commit")
```

For CSR sites that fetch data immediately on load, `networkidle` is the right choice. For sites with aggressive analytics, advertisements, or chat widgets that continuously make network requests, `networkidle` never triggers - use `load` and add an explicit wait instead:

```python
await page.goto(url, wait_until="load")
await page.wait_for_selector(".product-card", timeout=10000)  # Wait up to 10s for first card
```

## Waiting for Specific Content

Instead of waiting for a time condition, wait for a specific element that indicates the content is ready:

```python
async def fetch_playwright_with_probe(url: str, probe_selector: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="load")

        # Wait for the first product card to appear
        await page.wait_for_selector(probe_selector, timeout=15000)

        html = await page.content()
        await browser.close()
        return html

html = await fetch_playwright_with_probe(
    "http://localhost:8002/products",
    probe_selector=".product-card"
)
```

This is more reliable than `networkidle` because it directly checks for the content you need. If the selector never appears within the timeout, Playwright raises `TimeoutError` - a clear signal that the fetch failed.

## Reusing Browser Instances

Launching a new browser for every URL is expensive. A single Playwright browser can serve multiple pages through a browser context:

```python
async def scrape_csr_site(urls: list[str]) -> list[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )

        results = []
        for url in urls:
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle")
            html = await page.content()
            await page.close()
            results.append(html)

        await browser.close()
        return results
```

Each `context.new_page()` creates a new tab. Pages within the same context share cookies and storage but run independently. Closing each page after use prevents memory from growing unbounded across large scraping runs.

## Concurrency with Playwright

Multiple pages can run concurrently in the same browser context:

```python
async def fetch_parallel(urls: list[str], max_concurrent: int = 3) -> list[str]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        async def fetch_one(url):
            async with semaphore:
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="networkidle")
                    html = await page.content()
                    return html
                finally:
                    await page.close()

        results = await asyncio.gather(*[fetch_one(url) for url in urls])
        await browser.close()
        return results
```

More than 3-5 concurrent Playwright pages can strain memory and CPU. Each browser page is a full rendering process. Test with your target machine's resource constraints.

## User Agent and Browser Fingerprint

Headless browsers have detectable characteristics. Sites with anti-bot measures check:

- The `User-Agent` string (headless Chromium reports itself)
- JavaScript properties like `navigator.webdriver` (set to `true` in automated browsers)
- Canvas and WebGL fingerprints
- Timing patterns

For most scraping targets, setting a realistic user agent is sufficient:

```python
context = await browser.new_context(
    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    viewport={"width": 1920, "height": 1080},
)
```

For sites with more sophisticated detection, Playwright Extra and the `stealth` plugin can hide automation signals. These are beyond the scope of this book but are well-documented in the Playwright ecosystem.

## Extracting Data Inside the Browser

Sometimes it is more efficient to extract data using JavaScript inside the browser rather than exporting the full HTML to Python:

```python
# Execute JavaScript in the browser context and return the result
products = await page.evaluate("""
    () => {
        return Array.from(document.querySelectorAll('.product-card')).map(card => ({
            name: card.querySelector('h2.product-name')?.textContent.trim(),
            price: card.querySelector('.price-amount')?.textContent.trim(),
            url: card.querySelector('a.product-link')?.href,
        }));
    }
""")
# products is a Python list of dicts, returned by JSON serialization
print(products[0])
# {'name': 'MacBook Pro 14"', 'price': '$1,999.00', 'url': 'http://localhost:8002/products/macbook-pro-14'}
```

`page.evaluate()` runs JavaScript synchronously in the page context and returns the result, automatically deserializing JSON-compatible values.

This approach is faster than exporting full HTML when you need only a subset of data, and avoids the HTML parsing step entirely. The downside: the extraction logic is in JavaScript, which is less convenient than Python for complex transforms.

## Intercepting API Calls

CSR sites fetch their data from APIs. Instead of scraping the rendered DOM, you can intercept the API calls directly:

```python
async def intercept_api(url: str) -> list[dict]:
    api_responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Register a route handler that intercepts API calls
        async def handle_route(route):
            response = await route.fetch()
            body = await response.json()
            if "products" in body:
                api_responses.append(body)
            await route.fulfill(response=response)

        await page.route("**/api/products*", handle_route)
        await page.goto(url, wait_until="networkidle")
        await browser.close()

    # All captured API responses
    return api_responses
```

When the JavaScript on the page calls `/api/products?page=1`, the route handler captures the response. The data arrives as clean JSON, bypassing HTML parsing entirely.

This is often the most efficient approach for CSR sites: let the browser load the page (which triggers the API calls), capture the API responses, and skip HTML extraction entirely.

## Playwright in the Config Engine

The config's `render_mode` field controls which fetch path the engine uses:

```json
{
  "render_mode": "static",
  ...
}
```

```json
{
  "render_mode": "playwright",
  ...
}
```

The engine resolves `render_mode` to a fetch function:

```python
async def fetch_page(url: str, render_mode: str, probe_selector: str = None) -> str:
    if render_mode == "static":
        return await fetch_static(url)
    elif render_mode == "playwright":
        return await fetch_playwright(url, probe_selector)
    elif render_mode == "auto":
        return await fetch_auto(url, probe_selector)  # Chapter 9
    else:
        raise ValueError(f"Unknown render_mode: {render_mode}")
```

The rest of the engine - pagination, field extraction, storage - is identical regardless of render mode. The only difference is which function fetches the HTML. The same CSS selectors that work on ShopSphere SSR work on ShopSphere CSR after Playwright renders the page.

## Apply This

**1. Install Playwright's browsers before running.** `playwright install chromium` downloads the Chromium binary that Playwright uses. Without this step, the browser launch fails.

**2. Default to `wait_until="networkidle"` for CSR sites, but have a fallback.** If `networkidle` never fires (due to background requests), use `wait_until="load"` combined with `wait_for_selector(probe)` to wait for specific content.

**3. Close pages after use.** Accumulating open pages in a long-running browser context leaks memory. Close each page when you are done with it.

**4. Consider API interception before DOM scraping.** If the site is CSR, find the API calls in the browser's Network tab. Intercepting the API directly may be simpler and faster than scraping the rendered DOM.

**5. Test both SSR and CSR configs with the same selectors.** The demo sites are designed to verify this: `configs/shopsphere-ssr.json` and `configs/shopsphere-csr.json` use identical CSS selectors. Only `render_mode` differs. If your selectors work on the SSR site, they should work identically on the CSR site once Playwright has rendered it.
