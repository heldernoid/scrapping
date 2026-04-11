# Chapter 6: Pagination Architecture

Without pagination support, a scraper collects one page of results. For a job board with 400 listings across 40 pages, you get 10. For a marketplace with 10,000 products across 1,000 pages, you get 10. Pagination is not an edge case; it is the primary mechanism by which large datasets are surfaced through web interfaces.

This chapter covers every major pagination pattern, how to detect which one a site uses, and how the JSON config encodes each pattern declaratively.

## Why Pagination Exists

Pagination exists because serving 10,000 records in a single HTTP response is impractical: the response is too large, rendering is slow, the user interface becomes unusable. Pagination divides the dataset into pages and presents them one at a time.

The mechanism by which the server knows which page to serve is encoded in the URL or request body. The variation in how this encoding works produces the different pagination patterns you encounter in practice.

## Pattern 1: Page-Number Offset

The simplest and most common pattern. The URL contains a `?page=N` parameter (or equivalent: `?p=N`, `?pg=N`, `?_pgn=N`, `?paged=N`).

```
https://jobs.example.com/listings?page=1
https://jobs.example.com/listings?page=2
https://jobs.example.com/listings?page=3
```

The config encodes this as:

```json
{
  "url_template": "https://jobs.example.com/listings?page={n}",
  "pagination": {
    "start": 1,
    "step": 1,
    "max_pages": 100,
    "stop_condition": "no_results"
  }
}
```

The engine generates URLs by substituting `{n}` with `start`, `start+step`, `start+2*step`, up to `max_pages` URLs. The `stop_condition: no_results` halts pagination when a page returns no links. Since the job board only has 4 pages, the engine stops at page 5 automatically.

**Variants:**
- `?page=0` indexing: `start: 0`
- Path-based: `/listings/page/3/` use `url_template: "https://example.com/listings/page/{n}/"`
- Query parameter combinations: `?page=2&per_page=50`

## Pattern 2: Numeric Item Offset

Instead of page numbers, some sites use raw item offsets: "start from item 0", "start from item 20", "start from item 40". Craigslist uses this pattern. eBay's search API uses it. Many older e-commerce engines use it.

```
https://example.com/search?s=0&count=20
https://example.com/search?s=20&count=20
https://example.com/search?s=40&count=20
```

Config:

```json
{
  "url_template": "https://example.com/search?s={n}&count=20",
  "pagination": {
    "start": 0,
    "step": 20,
    "max_pages": 500,
    "stop_condition": "no_results"
  }
}
```

The `step: 20` means each URL advances by 20 items: `s=0`, `s=20`, `s=40`. The math is identical to page-number pagination; only the URL parameter semantics differ.

## Pattern 3: "Next Page" Link Traversal

Some sites do not use predictable URL patterns. Instead, each page contains a link to the next page. The URL of page 3 might be `?cursor=abc123` with no obvious relationship to page 2's URL `?cursor=xyz789`.

```html
<nav class="pagination">
  <a href="/jobs?after=eyJpZCI6MTAwfQ" class="next-link">Next</a>
</nav>
```

This pattern requires a different traversal approach: follow the next link until no next link exists:

```python
def scrape_follow_next(start_url: str, next_selector: str, item_selector: str):
    current_url = start_url
    all_items = []

    while current_url:
        soup = fetch_and_parse(current_url)
        items = soup.select(item_selector)
        all_items.extend(items)

        next_el = soup.select_one(next_selector)
        href = next_el.get("href") if next_el else None
        current_url = make_absolute(href, current_url) if href else None

    return all_items
```

The JSON config does not natively support this pattern (it assumes pre-generatable URLs). When you encounter it, either implement custom pagination logic or treat each page's next-link href as the source for the following iteration.

## Pattern 4: API Cursor Pagination

REST APIs often implement cursor-based pagination, a pattern designed to be stable under concurrent writes:

```
GET /api/jobs?limit=20
Response: { "jobs": [...], "next_cursor": "eyJpZCI6MjB9", "has_next": true }

GET /api/jobs?limit=20&cursor=eyJpZCI6MjB9
Response: { "jobs": [...], "next_cursor": "eyJpZCI6NDB9", "has_next": true }

GET /api/jobs?limit=20&cursor=eyJpZCI6NDB9
Response: { "jobs": [...], "next_cursor": null, "has_next": false }
```

The cursor is typically a base64-encoded pointer into the dataset (often a record ID). Unlike page numbers, cursors do not skip items if records are added or removed between pages.

For API pagination, the config approach requires either a direct API config (listing the API endpoint in `sources` with the JSON response structure) or custom agent code that handles the cursor loop. The bylgja engine supports direct API fetching when the source URL returns JSON rather than HTML.

## Pattern 5: Infinite Scroll

Infinite scroll is pagination without pagination UI. As the user scrolls toward the bottom of the page, JavaScript detects the position and fetches the next batch of items, appending them to the existing list. There is no "Next" button. There is no visible page number.

From a scraping perspective, infinite scroll is CSR pagination: the data is loaded via JavaScript API calls. The approaches:

**Option A: Find the API.** The infinite scroll triggers API calls. Open DevTools, Network tab, filter XHR, scroll down. You will see API calls like `GET /api/feed?offset=20`. Call that API directly. This is almost always cleaner than using Playwright to scroll.

**Option B: Playwright scrolling.** When the API is not accessible (requires complex auth or dynamic tokens), use Playwright to scroll and collect:

```python
async def scrape_infinite_scroll(url: str, item_selector: str) -> list:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")

        all_items = []
        previous_count = 0

        for _ in range(20):  # Max 20 scroll cycles
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)  # Wait for new content

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            items = soup.select(item_selector)
            current_count = len(items)

            if current_count == previous_count:
                break  # No new items loaded - end of content

            previous_count = current_count

        await browser.close()
        return soup.select(item_selector)
```

## Stop Conditions

Every pagination loop needs a reliable termination condition. Without one, your scraper runs indefinitely against a site that returns empty pages after the last valid page.

**`no_results` (default):** Stop when the link selector matches zero elements. This is the most reliable general-purpose stop condition:

```json
"stop_condition": "no_results"
```

Most sites return an empty listing page (with a "No results" message) or redirect to page 1 when you exceed the last page. Either way, the link count drops to zero.

**`last_page_text`:** Stop when a specific string appears in the page HTML. Useful when a site shows an empty state message rather than an empty page:

```json
"stop_condition": "last_page_text",
"last_page_text": "End of results"
```

**`max_pages` only:** Set a conservative `max_pages` limit and rely on it as the stop condition. This is less elegant but works when the site's behavior at the end of pagination is unpredictable:

```json
{
  "start": 1,
  "step": 1,
  "max_pages": 50
}
```

**HTTP status codes:** The engine should treat 404 and 400 responses as pagination end, regardless of stop condition setting. Many sites return 404 for pages beyond the last.

## Detecting the Pagination Pattern

When approaching a new site, identify the pagination pattern before writing the config:

1. Navigate to a listing page. Look at the URL.
2. Click "Next" or page 2. Look at the URL again.
3. What changed? A `?page=N` parameter? A different parameter? The path?

If the URL is unreadable (a cursor token), look in the page HTML for the pagination links. The `href` attributes on "Next" and numbered page links reveal the URL pattern.

If there are no pagination links and the content loads as you scroll, you are dealing with infinite scroll. Open the Network tab to find the API calls.

## The URL Template

The config's `url_template` is designed to capture any linear URL pattern where one variable value changes across pages. The `{n}` placeholder is replaced with the computed value for each page.

For complex URLs that combine page number with other parameters (category filter, sort order), include those parameters in the template:

```json
{
  "url_template": "https://marketplace.example.com/search?q=laptop&condition=new&page={n}&sort=price_asc",
  "pagination": {"start": 1, "step": 1, "max_pages": 50, "stop_condition": "no_results"}
}
```

The static parameters (query, condition, sort) are baked into the template. The page number is the only variable.

## Polite Crawling

Pagination means many requests to the same server. Sending 100 requests as fast as possible is inconsiderate and often counterproductive: the server rate-limits you, returns errors, or bans your IP.

The bylgja engine inserts a small delay between requests:

```python
await asyncio.sleep(0.1)  # 100ms between listing pages
```

For production scrapers against commercial sites, a delay of 1-3 seconds between requests is more appropriate. Some sites publish their crawl rate guidelines in `robots.txt`. Respect them.

Rate limiting also applies at the detail-page level. If a listing page yields 20 product URLs, fetching all 20 concurrently is 20 simultaneous requests. A bounded concurrency pool (4-8 workers) is a better approach:

```python
semaphore = asyncio.Semaphore(4)

async def fetch_detail(url):
    async with semaphore:
        return await fetch_and_extract(url)

# Fetch all detail pages with max 4 concurrent requests
results = await asyncio.gather(*[fetch_detail(url) for url in detail_urls])
```

## The Demo Sites as Pagination Test Cases

The four demo sites demonstrate different facets of pagination:

**ShopSphere SSR and CSR** both have 5 pages of 10 products each. The stop condition triggers on page 6 when the link selector returns 0 elements. Testing a config against ShopSphere verifies that both pagination URL generation and stop condition detection work correctly.

**JobHive SSR and CSR** have 4 pages of 10 jobs each. Jobs are organized by department (Engineering, Data, Product, Operations), making them useful for testing multi-source configs where each source covers one department.

Running a config against both the SSR and CSR versions of the same site is a useful test: the selectors should work identically, only the `render_mode` differs.

## Apply This

**1. Determine the URL pattern before writing code.** Open DevTools, navigate three pages, and compare the URLs. Write down the pattern. The template writes itself once you see it.

**2. Set `max_pages` conservatively.** If you think a site has 50 pages, set `max_pages: 100`. Running an extra 50 empty-result requests is cheap; missing pages because your limit was too low is a data quality problem.

**3. Always use a stop condition in addition to `max_pages`.** Belt and suspenders. `max_pages` is your hard ceiling; `stop_condition` is your adaptive termination.

**4. Test pagination separately from extraction.** Before writing field selectors, verify that your URL template generates the right URLs and that the stop condition triggers at the right page. This isolates pagination bugs from extraction bugs.

**5. Monitor for pagination drift.** Sites occasionally change the number of items per page. If you were scraping 20 items per page and the site switches to 25, your offset-based config will miss items and return duplicates near page boundaries. Add a check that total scraped items equals the expected total.
