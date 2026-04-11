# Chapter 7: Static Fetching with httpx

Static fetching is the baseline: send an HTTP GET request, receive an HTML response, parse it. No browser, no JavaScript execution, no waiting for dynamic content. When it works - when the server returns all the data you need in the initial HTML response - it is the fastest, cheapest, and most reliable approach.

This chapter covers the static fetching layer: the HTTP client, parsing, character encoding, request configuration, and rate limiting.

## The httpx Library

`httpx` is a modern Python HTTP client that supports both synchronous and asynchronous usage, HTTP/2, and a clean API. It is the right tool for scraping because:

- **Async support**: `httpx.AsyncClient` integrates with `asyncio`, enabling concurrent fetching without threads
- **HTTP/2**: Many modern sites serve faster over HTTP/2; httpx negotiates the protocol automatically
- **Connection pooling**: A single `AsyncClient` instance reuses connections across requests to the same host
- **Timeout control**: Per-request and per-client timeouts prevent hanging requests

Basic usage:

```python
import httpx
from bs4 import BeautifulSoup

response = httpx.get("http://localhost:8001/products")
soup = BeautifulSoup(response.text, "lxml")
cards = soup.select("article.product-card")
print(f"Found {len(cards)} products")
```

## The User-Agent Header

Many web servers check the `User-Agent` header and block requests that identify as automated clients. A missing `User-Agent` (the default in most HTTP clients) or a value like `python-httpx/0.27.0` is a signal that the request is not from a real browser.

Always set a realistic `User-Agent`:

```python
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

response = httpx.get(url, headers=HEADERS)
```

For most sites, a standard Chrome or Firefox user agent string is sufficient. Sites with more sophisticated bot detection require additional headers (Accept, Accept-Language, Accept-Encoding) to match what a browser would send.

## Async Fetching for Concurrency

Scraping multiple pages sequentially is slow. Fetching them concurrently is fast. `httpx.AsyncClient` enables concurrent fetching within a single asyncio event loop:

```python
import asyncio
import httpx
from bs4 import BeautifulSoup

async def fetch(client, url):
    response = await client.get(url)
    return response.text

async def fetch_all(urls):
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        tasks = [fetch(client, url) for url in urls]
        return await asyncio.gather(*tasks)

# Fetch 10 product pages concurrently
urls = [f"http://localhost:8001/products/{slug}" for slug in slugs]
pages = asyncio.run(fetch_all(urls))
```

`asyncio.gather()` runs all coroutines concurrently but within a single thread. The concurrency is IO-bound: while waiting for one HTTP response, the event loop processes other tasks.

## Controlling Concurrency

Launching 500 concurrent requests to a single server is not polite, and often counterproductive - the server may rate-limit or ban the client. Control concurrency with a semaphore:

```python
async def scrape_products(slugs):
    semaphore = asyncio.Semaphore(4)  # Max 4 concurrent requests

    async def fetch_one(slug):
        async with semaphore:
            async with httpx.AsyncClient(headers=HEADERS) as client:
                resp = await client.get(f"http://localhost:8001/products/{slug}")
                return resp.text

    pages = await asyncio.gather(*[fetch_one(slug) for slug in slugs])
    return pages
```

A semaphore limit of 4-8 concurrent requests to a single host is usually safe. For commercial sites, 1-2 is more appropriate.

## Character Encoding

Web pages declare their character encoding in the HTML or HTTP headers. Getting the encoding wrong produces garbled text for non-ASCII content - prices with currency symbols, product names with accented characters, job titles with dashes.

`httpx` reads the Content-Type header for encoding information, but it can be wrong or missing. BeautifulSoup can detect encoding from the HTML `<meta charset>` tag.

The safest approach: use `chardet` or `charset-normalizer` to detect encoding from the raw bytes:

```python
def decode_response(response):
    # Try the encoding httpx detected
    try:
        return response.text
    except UnicodeDecodeError:
        # Fall back to detection from raw bytes
        import charset_normalizer
        result = charset_normalizer.from_bytes(response.content).best()
        return str(result) if result else response.content.decode("utf-8", errors="replace")
```

For sites that consistently use UTF-8 (most modern sites), this complexity is unnecessary. But for older sites or international content, encoding issues are common.

## Timeouts

A request that never completes blocks the entire scraping pipeline. Always set explicit timeouts:

```python
# Separate timeouts for different phases
timeout = httpx.Timeout(
    connect=5.0,   # Connection establishment
    read=30.0,     # Reading the response
    write=5.0,     # Sending the request
    pool=5.0       # Acquiring a connection from the pool
)

async with httpx.AsyncClient(timeout=timeout, headers=HEADERS) as client:
    response = await client.get(url)
```

A 30-second read timeout handles slow servers and large pages without blocking indefinitely. Adjust based on the target site's behavior.

## Handling HTTP Errors

Not every request succeeds. Handle HTTP errors explicitly:

```python
async def safe_fetch(client, url):
    try:
        response = await client.get(url)
        response.raise_for_status()  # Raises for 4xx/5xx responses
        return response.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None  # Product deleted - skip
        elif e.response.status_code == 429:
            # Rate limited - backoff and retry
            await asyncio.sleep(5)
            return await safe_fetch(client, url)
        else:
            raise
    except httpx.RequestError:
        # Network error - connection refused, DNS failure, etc.
        return None
```

For pagination, a 404 on a page URL typically means you have exceeded the last page - a valid stop condition. For detail pages, a 404 means the item no longer exists.

## Detecting CSR Pages

Before proceeding with a static scrape, verify that the page actually contains the expected content. A CSR page returns an HTML shell - very little text, no product or job content. Detecting this early avoids wasted time extracting nothing.

```python
def is_csr(html: str, probe_selector: str = None) -> bool:
    soup = BeautifulSoup(html, "lxml")

    # Heuristic 1: Very little visible text suggests a JS-only shell
    if len(soup.get_text(strip=True)) < 200:
        return True

    # Heuristic 2: Probe for a specific element that should be present
    if probe_selector and not soup.select_one(probe_selector):
        return True

    return False
```

The probe selector approach is more reliable: if the product cards are not in the static HTML, the page is CSR regardless of how much text appears in navigation and footer elements.

## The Static Fetcher in the Config Engine

The config-driven scraper wraps all of this into a single `fetch_static` function:

```python
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

async def fetch_static(url: str) -> str:
    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=httpx.Timeout(connect=5, read=30, write=5, pool=5),
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
```

`follow_redirects=True` handles sites that redirect HTTP to HTTPS, or redirect to a canonical URL. Without this, redirects return a 301/302 response body (usually an empty HTML redirect page) rather than the target content.

## Rate Limiting

Between requests to the same host, insert a delay. This is both polite and practical - aggressive scraping triggers rate limits that slow the scraper more than a small sleep would.

```python
async def scrape_pages(urls, delay=0.5):
    results = []
    async with httpx.AsyncClient(headers=HEADERS) as client:
        for url in urls:
            html = await fetch_static_with_client(client, url)
            results.append(html)
            await asyncio.sleep(delay)
    return results
```

For listing pages, a delay of 0.1 to 0.5 seconds is usually sufficient. For detail pages on commercial sites, 1-3 seconds is more appropriate. Check `robots.txt` for explicit crawl delay guidelines.

## When Static Fetching Fails

The engine falls back to Playwright when static fetching is insufficient. The signals that static fetching has failed:

1. The probe selector returns no elements on the fetched HTML
2. The fetched HTML contains a loading indicator (`.loading`, "Please wait...")
3. The visible text length is below a threshold
4. The page explicitly requires JavaScript (meta redirect, error message)

These signals are evaluated in the auto-fallback logic, covered in Chapter 9. The important point here: `fetch_static` is designed to fail fast and return the raw HTML - the decision to escalate to Playwright is made by the engine, not the fetcher.

## Apply This

**1. Reuse a single `AsyncClient` across requests to the same host.** Creating a new client for each request forfeits connection pooling. Create the client once, pass it to all fetch functions.

**2. Set timeouts explicitly.** The default timeout in httpx is 5 seconds - too short for slow pages, but better than no timeout. Set read timeout to 30 seconds and connection timeout to 5 seconds.

**3. Check the actual fetched HTML before debugging selectors.** Before assuming a selector is wrong, verify the content is in the HTML at all. Print `response.text[:2000]` and look for the element you are targeting.

**4. Use `follow_redirects=True`.** Most scraping targets redirect somewhere - HTTP to HTTPS, trailing slash normalization, canonical URL enforcement. Without following redirects, you extract nothing from redirect responses.

**5. Respect `robots.txt` and rate limits.** Check `https://example.com/robots.txt` for crawl delay and disallowed paths. Respecting these is both ethical and practical - sites that actively disallow scraping have defenses that a crawl delay instruction is only the first line of.
