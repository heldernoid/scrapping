---
name: mcp-scraping
description: Expose the scraping toolkit as MCP tools so any MCP-compatible AI agent can autonomously discover, configure, and execute web scrapes. Use this to connect Claude Desktop, Claude Code, or any MCP client to the scraping engine.
---

## What This Skill Does

Starts an MCP server that exposes 6 scraping tools over STDIO. Any MCP-compatible agent (Claude Desktop, Claude Code, Cursor, etc.) can then call these tools to scrape websites without leaving the conversation.

## Exposed Tools

| Tool | What it does |
|------|-------------|
| `fetch_page_structure(url)` | Fetches a URL and returns a compact HTML structure summary |
| `generate_scraper_config(url)` | LLM generates a scraper config from the page structure |
| `test_selector(url, selector)` | Tests a CSS selector and returns matching text |
| `run_scrape(config_json, max_results)` | Executes a scrape with the given config JSON string |
| `load_config(config_name)` | Loads a pre-built demo config by name |
| `list_configs()` | Lists all available pre-built configs |

## Preconditions

- Python environment active (`uv sync` or `pip install -r requirements.txt`)
- LLM backend configured in `.env` (needed for `generate_scraper_config`)
- For demo sites: `cd demo-sites && docker compose up -d`

## Steps

**Start the MCP server:**

```bash
python agents/mcp_server.py
```

Or using the MCP dev inspector:

```bash
mcp dev agents/mcp_server.py
```

**Connect from Claude Desktop** - add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "scraper": {
      "command": "python",
      "args": ["/path/to/scrapping/agents/mcp_server.py"]
    }
  }
}
```

**Connect from Claude Code:**

```bash
claude mcp add scraper python /path/to/scrapping/agents/mcp_server.py
```

## Typical Agent Workflow

Once connected, an agent can scrape a site in 3 tool calls:

```
1. fetch_page_structure("http://localhost:8001/products")
   -> Returns HTML structure summary

2. generate_scraper_config("http://localhost:8001/products")
   -> Returns JSON config string

3. run_scrape(config_json=<config from step 2>, max_results=20)
   -> Returns list of extracted records as JSON string
```

## Pre-built Config Names

Pass these to `load_config()`:

| Name | Site |
|------|------|
| `shopsphere-ssr` | Product marketplace, server-side rendered |
| `shopsphere-csr` | Product marketplace, client-side rendered |
| `jobhive-ssr` | Job board, server-side rendered |
| `jobhive-csr` | Job board, client-side rendered |

Example:

```
load_config("jobhive-ssr")
-> Returns the full config JSON string ready for run_scrape
```

## Adapting for Your Own Agent

Add new tools to the MCP server by editing `agents/mcp_server.py`:

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("scraper")

@mcp.tool()
async def my_custom_tool(url: str, my_param: str) -> str:
    # your logic here
    return json.dumps({"result": "..."})
```

Or embed the server as a subprocess and connect your own MCP client to its STDIO pipes:

```python
import subprocess
proc = subprocess.Popen(
    ["python", "/path/to/scrapping/agents/mcp_server.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE
)
```

For calling the underlying scraping functions directly (without MCP), see `skills/integrate/SKILL.md`.

## Notes

- All tools return JSON strings (MCP requires string returns)
- `run_scrape` accepts either a JSON string or a dict
- The server runs over STDIO - it does not bind to a network port
- See `agents/mcp_server.py` for full tool implementations
