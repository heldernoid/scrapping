"""
Scraper MCP Server

Exposes the scraping toolkit as MCP tools so any MCP-compatible AI agent
(Claude Desktop, Claude Code, etc.) can autonomously discover and scrape websites.

Tools exposed:
  - fetch_page_structure(url)       Fetches a URL and returns its HTML structure summary
  - generate_scraper_config(url)    LLM generates a scraper config from page structure
  - test_selector(url, selector)    Tests a CSS selector against a URL
  - run_scrape(config_json, max)    Executes a scrape with the given config
  - load_config(config_name)        Loads one of the pre-built demo configs

Run:
  python agents/mcp_server.py

Then connect from Claude Desktop via STDIO, or use:
  mcp dev agents/mcp_server.py
"""
import json
import asyncio
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

from config_generator import generate_config, summarise_html
from autonomous_scraper import (
    fetch_static, scrape_detail_page, generate_urls, select, run
)

mcp = FastMCP("scraper")

CONFIGS_DIR = Path(__file__).parent.parent / "configs"


# ---- Tool 1: Fetch page structure ----

@mcp.tool()
async def fetch_page_structure(url: str) -> str:
    """
    Fetch a URL and return a compact structural summary of its HTML.
    Use this to understand the page layout before generating a scraper config.
    Returns a simplified tag tree showing class names, data attributes, and text previews.
    """
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(strip=True)
        is_csr = len(text) < 200

        summary = summarise_html(html, max_elements=80)
        result = {
            "url": url,
            "status_code": resp.status_code,
            "is_csr": is_csr,
            "csr_note": "Page appears client-side rendered - use render_mode=playwright" if is_csr else "",
            "structure": summary,
            "visible_text_length": len(text),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url})


# ---- Tool 2: Generate scraper config ----

@mcp.tool()
async def generate_scraper_config(url: str) -> str:
    """
    Analyse a URL and generate a complete bylgja-format scraper config.
    The config specifies: pagination URLs, link selectors, and field extractors.
    Returns a JSON object ready to pass to run_scrape().
    """
    try:
        config = generate_config(url)
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---- Tool 3: Test a CSS selector ----

@mcp.tool()
async def test_selector(url: str, selector: str, render_mode: str = "static") -> str:
    """
    Test a CSS selector against a live URL.
    Returns the count of matched elements and text previews of the first 5.
    Use render_mode='playwright' for JavaScript-rendered pages.

    Args:
        url: The page URL to test against
        selector: CSS selector to test (e.g. "a.product-link", "h1.job-title")
        render_mode: 'static' or 'playwright'
    """
    try:
        if render_mode == "playwright":
            from autonomous_scraper import fetch_playwright
            html = await fetch_playwright(url)
        else:
            html = await fetch_static(url)

        soup = BeautifulSoup(html, "lxml")
        elements = select(soup, selector)

        previews = []
        for el in elements[:5]:
            text = el.get_text(strip=True)[:80]
            href = el.get("href", "")
            previews.append({"text": text, "href": href})

        return json.dumps({
            "url": url,
            "selector": selector,
            "render_mode": render_mode,
            "count": len(elements),
            "previews": previews,
            "note": "No matches found" if not elements else f"{len(elements)} elements matched",
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---- Tool 4: Run a scrape ----

@mcp.tool()
async def run_scrape(config_json: str, max_items: int = 10) -> str:
    """
    Execute a scrape using a bylgja-format config JSON string.
    Returns a JSON array of scraped records.

    Args:
        config_json: Complete scraper config as a JSON string
        max_items: Maximum number of items to scrape (default 10, max 50)
    """
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid config JSON: {e}"})

    max_items = min(max_items, 50)

    try:
        sources = config.get("sources", [])
        if not sources:
            return json.dumps({"error": "Config has no sources"})

        base_url = sources[0].get("url_template", "").replace("{n}", "1").split("?")[0]
        results = await run(base_url, config, max_items=max_items)

        return json.dumps({
            "count": len(results),
            "config_name": config.get("name", "unnamed"),
            "render_mode": config.get("render_mode", "auto"),
            "records": results,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---- Tool 5: Load a pre-built demo config ----

@mcp.tool()
def load_config(config_name: str) -> str:
    """
    Load one of the pre-built demo site configs.
    Available configs: shopsphere-ssr, shopsphere-csr, jobhive-ssr, jobhive-csr

    Args:
        config_name: Name of the config file without .json extension
    """
    config_path = CONFIGS_DIR / f"{config_name}.json"
    if not config_path.exists():
        available = [p.stem for p in CONFIGS_DIR.glob("*.json")]
        return json.dumps({
            "error": f"Config '{config_name}' not found",
            "available": available,
        })
    with open(config_path) as f:
        config = json.load(f)
    return json.dumps(config, indent=2)


# ---- Tool 6: Compare SSR vs CSR ----

@mcp.tool()
async def compare_rendering(ssr_url: str, csr_url: str) -> str:
    """
    Fetch both an SSR and CSR version of a site and compare what a static scraper sees.
    Demonstrates why Playwright is needed for CSR sites.

    Args:
        ssr_url: URL of the server-side rendered version
        csr_url: URL of the client-side rendered version
    """
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            ssr_resp = await client.get(ssr_url, headers={"User-Agent": "Mozilla/5.0"})
            csr_resp = await client.get(csr_url, headers={"User-Agent": "Mozilla/5.0"})

        ssr_soup = BeautifulSoup(ssr_resp.text, "lxml")
        csr_soup = BeautifulSoup(csr_resp.text, "lxml")

        ssr_text = ssr_soup.get_text(strip=True)
        csr_text = csr_soup.get_text(strip=True)

        ssr_links = len(ssr_soup.select("a[href]"))
        csr_links = len(csr_soup.select("a[href]"))

        ssr_items = len(ssr_soup.select(".product-card, .job-card"))
        csr_items = len(csr_soup.select(".product-card, .job-card"))

        return json.dumps({
            "ssr": {
                "url": ssr_url,
                "visible_text_chars": len(ssr_text),
                "links_found": ssr_links,
                "cards_found": ssr_items,
                "scrapeable_without_js": True,
            },
            "csr": {
                "url": csr_url,
                "visible_text_chars": len(csr_text),
                "links_found": csr_links,
                "cards_found": csr_items,
                "scrapeable_without_js": False,
                "note": "CSR requires Playwright. Static fetch returns only the empty HTML shell.",
            },
            "verdict": (
                "SSR: direct scraping works. "
                "CSR: JavaScript must execute first - use render_mode=playwright in config."
            ),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
