---
name: scrape-url
description: Scrape structured data from a URL using a declarative JSON config. Use this when you have a scraper config (or can load one) and want to extract data from a website into structured JSON records.
---

## What This Skill Does

Executes a scraper config against one or more URLs and returns structured JSON records. The config controls rendering mode (static HTTP or headless browser), field selectors, pagination, and transforms - no custom Python needed.

## Preconditions

- Python environment is active (`uv sync` or `pip install -r requirements.txt`)
- For CSR/JavaScript-rendered sites: `playwright install chromium`
- For the demo sites: `cd demo-sites && docker compose up -d`

## Config Shape

```json
{
  "render_mode": "static",
  "sources": [{"url_template": "https://example.com/listings?page={n}",
               "pagination": {"start": 1, "step": 1, "max_pages": 5}}],
  "listing": {"link_selector": "a.item-link", "link_prefix": "https://example.com"},
  "fields": {
    "title":  {"selector": "h1.title",   "retrieve": "plaintext"},
    "price":  {"selector": ".price",     "retrieve": "regexp", "pattern": "([\\d.]+)"},
    "tags":   {"selector": ".tag",       "retrieve": "plaintext", "multiple": true}
  }
}
```

`render_mode` options: `"static"` (httpx), `"playwright"` (headless browser), `"auto"` (tries static first, falls back to Playwright).

## Steps

**Option A - use a pre-built demo config:**

```bash
python examples/quick_start.py
```

Pre-built configs are in `configs/`:
- `configs/shopsphere-ssr.json` - product marketplace (server-side rendered)
- `configs/shopsphere-csr.json` - product marketplace (client-side rendered)
- `configs/jobhive-ssr.json`    - job board (server-side rendered)
- `configs/jobhive-csr.json`    - job board (client-side rendered)

**Option B - run a config file directly:**

```python
import asyncio, json
from agents.autonomous_scraper import run_scrape

config = json.load(open("configs/shopsphere-ssr.json"))
results = asyncio.run(run_scrape(config))
print(results)
```

**Option C - pass a config dict inline:**

```python
import asyncio
from agents.autonomous_scraper import run_scrape

config = {
    "render_mode": "static",
    "sources": [{"url_template": "http://localhost:8001/products?page={n}",
                 "pagination": {"start": 1, "step": 1, "max_pages": 3}}],
    "listing": {"link_selector": "a.product-link",
                "link_prefix": "http://localhost:8001"},
    "fields": {
        "name":  {"selector": "h1.product-title", "retrieve": "plaintext"},
        "price": {"selector": ".price-amount",    "retrieve": "plaintext"}
    }
}
results = asyncio.run(run_scrape(config))
```

## Output

A list of dicts, one per scraped record:

```json
[
  {"name": "Wireless Headphones", "price": "$89.99"},
  {"name": "USB-C Hub",           "price": "$34.99"}
]
```

## Field `retrieve` Options

| Value | What it extracts |
|-------|-----------------|
| `plaintext` | Visible text content |
| `html` | Raw inner HTML |
| `attr:NAME` | Value of attribute NAME (e.g. `attr:href`) |
| `regexp` | First capture group of `pattern` against text |

## Adapting for Your Own Agent

Import `run` directly for lower-level control:

```python
import asyncio
from agents.autonomous_scraper import run

results = asyncio.run(run(url="https://target.com", config=my_config, max_items=100))
```

`run` handles both static and Playwright fetching based on `config["render_mode"]`. For the full API including repair loop, see `skills/integrate/SKILL.md`.
