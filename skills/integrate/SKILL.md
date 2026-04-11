---
name: integrate
description: Embed this repo's scraping primitives into your own autonomous agent. Use this when you want to call the scraping engine programmatically - not via CLI - and drive the generate/execute/repair loop from your own code with your own LLM.
---

## What This Skill Does

Documents the importable Python API so external agents can use this repo as a scraping library. You get three layers:

- **`agents/llm.py`** - thin LLM client (swap in your own)
- **`agents/config_generator.py`** - HTML summariser + config generator
- **`agents/autonomous_scraper.py`** - fetcher, parser, validator, runner

## Minimal Working Example

10 lines to go from URL to structured data:

```python
import asyncio, sys
sys.path.insert(0, "/path/to/scrapping/agents")

from config_generator import generate_config
from autonomous_scraper import run

# 1. LLM generates config from page structure
config = generate_config("https://target-site.com/listings")

# 2. Execute the scrape
results = asyncio.run(run("https://target-site.com/listings", config, max_items=50))

print(results)  # list of dicts, one per record
```

## Full API Reference

### `agents/llm.py`

```python
from llm import chat, get_backend, get_model, get_client
```

| Function | Signature | Returns |
|----------|-----------|---------|
| `chat` | `(messages: list[dict], temperature=0.2, max_tokens=4096)` | `str` - assistant reply |
| `get_backend` | `()` | `"openrouter"` or `"ollama"` |
| `get_model` | `()` | model name string |
| `get_client` | `()` | `OpenAI` client instance |

### `agents/config_generator.py`

```python
from config_generator import generate_config, summarise_html
```

| Function | Signature | Returns |
|----------|-----------|---------|
| `summarise_html` | `(html: str, max_elements=60)` | compact HTML structure string for LLM |
| `generate_config` | `(url: str)` | `dict` - full scraper config |

### `agents/autonomous_scraper.py`

```python
from autonomous_scraper import (
    fetch_static, fetch_playwright,
    select, extract_field, scrape_detail_page,
    generate_urls, validate_results, run
)
```

| Function | Signature | Returns |
|----------|-----------|---------|
| `fetch_static` | `async (url: str, headers=None)` | `str` - HTML |
| `fetch_playwright` | `async (url: str)` | `str` - HTML after JS execution |
| `select` | `(soup, selector: str)` | list of BS4 tags |
| `extract_field` | `(soup, name: str, cfg: dict)` | `(name, value)` tuple |
| `scrape_detail_page` | `(html: str, config: dict)` | `dict` - one record |
| `generate_urls` | `(source: dict)` | `list[str]` - paginated URLs |
| `validate_results` | `(results: list[dict], config: dict)` | `str` - failure reason or `""` |
| `run` | `async (url: str, config: dict, max_items=20)` | `list[dict]` - all records |

## Plug In Your Own LLM

The `chat()` function in `llm.py` is the only LLM call site. Replace it with your own:

```python
import agents.llm as llm

def my_chat(messages, temperature=0.2, max_tokens=4096):
    # call your own LLM here
    return my_llm_client.complete(messages)

llm.chat = my_chat  # monkey-patch before importing config_generator
```

Or set environment variables to use a different OpenAI-compatible endpoint:

```python
import os
os.environ["LLM_BACKEND"] = "ollama"
os.environ["OLLAMA_BASE_URL"] = "http://my-llm-server:11434/v1"
os.environ["OLLAMA_MODEL"] = "llama3.1:70b"
```

## Build Your Own Repair Loop

`validate_results` returns an empty string on success, or a failure reason string. Use it to drive retries:

```python
import asyncio
from config_generator import generate_config, summarise_html
from autonomous_scraper import run, validate_results, fetch_static
from llm import chat

async def scrape_with_repair(url: str, max_retries: int = 3):
    config = generate_config(url)

    for attempt in range(max_retries):
        results = await run(url, config, max_items=20)
        failure = validate_results(results, config)

        if not failure:
            return results  # success

        # Ask LLM to repair the config
        html = await fetch_static(url)
        structure = summarise_html(html)
        repair_prompt = f"""
The scraper config failed: {failure}

Page structure:
{structure}

Current config:
{config}

Return a corrected config JSON only.
"""
        import json
        response = chat([{"role": "user", "content": repair_prompt}])
        config = json.loads(response)

    return results  # return whatever we have after max retries

results = asyncio.run(scrape_with_repair("https://target-site.com/listings"))
```

## Embed the MCP Server in Your Agent System

If your agent supports MCP (Claude Desktop, Claude Code, any MCP client), point it at the server:

```python
# Start as subprocess from your agent
import subprocess
proc = subprocess.Popen(
    ["python", "/path/to/scrapping/agents/mcp_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE
)
# Then connect your MCP client to proc.stdin / proc.stdout
```

Or register it directly in your agent config - see `skills/mcp-scraping/SKILL.md`.

## Config Schema Reference

```json
{
  "render_mode": "static | playwright | auto",
  "sources": [
    {
      "url_template": "https://site.com/page/{n}",
      "pagination": {"start": 1, "step": 1, "max_pages": 10}
    }
  ],
  "listing": {
    "link_selector": "a.item-link",
    "link_prefix": "https://site.com"
  },
  "fields": {
    "field_name": {
      "selector": "css-selector",
      "retrieve": "plaintext | html | attr:NAME | regexp",
      "pattern": "regex with one capture group (regexp only)",
      "multiple": false
    }
  }
}
```

`render_mode: "auto"` tries static fetch first; falls back to Playwright if the extracted record count is 0.
