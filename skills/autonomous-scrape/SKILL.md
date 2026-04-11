---
name: autonomous-scrape
description: Run the full AI-driven scraping loop - the LLM generates a config, executes it, validates results, and repairs the config if extraction fails. Use this when you want to scrape a site with zero human configuration.
---

## What This Skill Does

Implements a closed-loop autonomous scraping workflow:

1. Fetch the target URL and summarise its HTML structure
2. LLM generates a scraper config with CSS selectors and field definitions
3. Execute the scraper with the generated config
4. LLM validates results - checks for empty fields, wrong values, 0 records
5. If validation fails, LLM repairs the config and retries (up to N attempts)
6. Save results to JSON

No human writes selectors. No human inspects the HTML. The loop runs until data is extracted or the retry limit is reached.

## Preconditions

- Python environment active (`uv sync` or `pip install -r requirements.txt`)
- LLM backend configured in `.env` (see `generate-config` skill for setup)
- For CSR/JavaScript-rendered sites: `playwright install chromium`
- For demo sites: `cd demo-sites && docker compose up -d`

## Steps

**Scrape a marketplace (SSR):**

```bash
python agents/autonomous_scraper.py --url http://localhost:8001 --site marketplace
```

**Scrape a job board (SSR):**

```bash
python agents/autonomous_scraper.py --url http://localhost:8003 --site jobboard
```

**Use a pre-built config (skips generation step):**

```bash
python agents/autonomous_scraper.py --config configs/shopsphere-ssr.json
```

**From Python:**

```python
import asyncio
from agents.autonomous_scraper import autonomous_scrape

results = asyncio.run(autonomous_scrape(
    url="http://localhost:8001",
    site_type="marketplace",
    max_retries=3
))
print(f"Extracted {len(results)} records")
```

## Output

Results saved to JSON in the repo root:

```
marketplace-ssr_results.json
jobboard-ssr_results.json
```

Each file contains a list of structured records:

```json
[
  {
    "name": "Wireless Headphones",
    "price": "$89.99",
    "rating": "4.5",
    "in_stock": "In Stock"
  }
]
```

## Repair Loop

When extracted results fail validation (0 records, missing fields, or garbled values), the agent runs a repair cycle:

```
Attempt 1: generate config -> run -> validate -> FAIL (0 records)
Attempt 2: LLM sees failure reason -> repairs selectors -> run -> validate -> PASS
```

The LLM receives the failure reason and the original HTML summary on each repair attempt. Typical issues it fixes: wrong selector class names, missing `link_prefix`, incorrect `retrieve` type.

## Adapting for Your Own Agent

Run the loop programmatically and handle results yourself:

```python
import asyncio
from agents.config_generator import generate_config
from agents.autonomous_scraper import run, validate_results

async def my_scrape(url):
    config = generate_config(url)
    results = await run(url, config, max_items=50)
    failure = validate_results(results, config)
    if failure:
        # handle failure: repair config, retry, or escalate
        pass
    return results

results = asyncio.run(my_scrape("https://target.com"))
```

To drive the repair loop with your own LLM or your own retry logic, see `skills/integrate/SKILL.md`.

## SSR vs CSR

| Flag | Site type | Rendering |
|------|-----------|-----------|
| `--site marketplace` + port 8001 | ShopSphere SSR | Static fetch |
| `--site marketplace` + port 8002 | ShopSphere CSR | Playwright |
| `--site jobboard` + port 8003 | JobHive SSR | Static fetch |
| `--site jobboard` + port 8004 | JobHive CSR | Playwright |

The agent auto-detects whether Playwright is needed via `render_mode: "auto"`.
