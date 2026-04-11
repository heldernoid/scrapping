---
name: generate-config
description: Use an LLM to automatically generate a scraper config from a URL. Use this when you have a target URL and a list of fields to extract but no existing config. The LLM inspects the page structure and writes the JSON config for you.
---

## What This Skill Does

Fetches a URL, summarises its HTML structure, and asks an LLM to produce a valid scraper config with correct CSS selectors and field definitions. The generated config can be saved and reused.

## Preconditions

- Python environment active (`uv sync` or `pip install -r requirements.txt`)
- LLM backend configured - set one of:
  - `LLM_BACKEND=openrouter` + `OPENROUTER_API_KEY=sk-or-...` in `.env`
  - `LLM_BACKEND=ollama` + Ollama running locally (`ollama serve`)
- For JavaScript-rendered sites: `playwright install chromium`

## Steps

**Option A - command line:**

```bash
python agents/config_generator.py http://localhost:8001/products
```

Prints the generated config as JSON. Redirect to save it:

```bash
python agents/config_generator.py http://localhost:8001/products > my_config.json
```

**Option B - from Python:**

```python
from agents.config_generator import generate_config

config = generate_config("http://localhost:8001/products")
print(config)
```

**Option C - with field hints** (improves accuracy):

```python
from agents.config_generator import generate_config

config = generate_config(
    "http://localhost:8001/products",
    fields=["name", "price", "rating", "in_stock"]
)
```

## Output

A scraper config dict ready to pass to `run_scrape`:

```json
{
  "render_mode": "static",
  "sources": [{"url_template": "http://localhost:8001/products?page={n}",
               "pagination": {"start": 1, "step": 1, "max_pages": 10}}],
  "listing": {"link_selector": "a.product-link",
              "link_prefix": "http://localhost:8001"},
  "fields": {
    "name":     {"selector": "h1.product-title",  "retrieve": "plaintext"},
    "price":    {"selector": ".price-amount",     "retrieve": "plaintext"},
    "rating":   {"selector": ".star-rating",      "retrieve": "attr:data-score"},
    "in_stock": {"selector": ".stock-status",     "retrieve": "plaintext"}
  }
}
```

## LLM Backend Configuration

Copy `.env.example` to `.env` and set your backend:

```bash
# OpenRouter (cloud, many model choices)
LLM_BACKEND=openrouter
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL=mistralai/ministral-3b   # or any OpenRouter model

# Ollama (local, no API key needed)
LLM_BACKEND=ollama
OLLAMA_MODEL=ministral-3:14b
```

## Adapting for Your Own Agent

Swap the LLM by patching `llm.chat` before importing `config_generator`:

```python
import agents.llm as llm

def my_llm(messages, **kwargs):
    return my_own_client.complete(messages)

llm.chat = my_llm

from agents.config_generator import generate_config
config = generate_config("https://target.com")
```

Or use `summarise_html` alone to get the page structure as a string, then pass it to your own LLM with your own prompt:

```python
import asyncio
from agents.autonomous_scraper import fetch_static
from agents.config_generator import summarise_html

html = asyncio.run(fetch_static("https://target.com"))
structure = summarise_html(html)
# pass `structure` to your own LLM
```

For the full API reference, see `skills/integrate/SKILL.md`.

## Notes

- If the generated config produces 0 results, use the `autonomous-scrape` skill which includes an automatic repair loop
- The LLM sees a structural summary of the HTML, not the full source - this keeps token usage low
