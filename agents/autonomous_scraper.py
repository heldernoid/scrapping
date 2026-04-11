"""
Autonomous Scraping Agent

Demonstrates the full AI-driven scraping loop:
1. Receive a target URL and fields to extract
2. LLM generates a scraper config from the page structure
3. Execute the scraper using the config (static or Playwright)
4. LLM validates/interprets results and flags issues
5. Save structured data to JSON

Usage:
  python agents/autonomous_scraper.py --url http://localhost:8001 --site marketplace
  python agents/autonomous_scraper.py --url http://localhost:8003 --site jobboard
  python agents/autonomous_scraper.py --config configs/jobhive-ssr.json
"""
import sys
import json
import asyncio
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from llm import chat
from config_generator import generate_config

console = Console()


# ---- Static fetcher ----

async def fetch_static(url: str, headers: dict | None = None) -> str:
    default_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AutonomousScraper/1.0)",
        "Accept": "text/html,*/*;q=0.9",
    }
    if headers:
        default_headers.update(headers)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers=default_headers)
        resp.raise_for_status()
    return resp.text


# ---- Playwright fetcher (optional) ----

async def fetch_playwright(url: str) -> str:
    """
    Fetch via Playwright. Requires Playwright service running at localhost:3001
    OR uses playwright Python library directly.
    """
    # Try local Playwright service first (bylgja architecture)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "http://localhost:3001/fetch",
                json={"url": url},
            )
            data = resp.json()
            if data.get("html"):
                return data["html"]
    except Exception:
        pass

    # Fall back to playwright Python library
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        raise RuntimeError(f"Playwright failed: {e}")


# ---- Field extractor (simplified bylgja-compatible) ----

import re

def select(soup, selector: str):
    try:
        return soup.select(selector)
    except Exception:
        return []

def extract_field(soup, field_name: str, field_cfg: dict) -> tuple:
    selector = field_cfg.get("selector")
    retrieve = field_cfg.get("retrieve", "plaintext")
    multiple = field_cfg.get("multiple", False)
    attr = field_cfg.get("attr")
    pattern = field_cfg.get("pattern")

    if not selector:
        return None, "no selector"

    try:
        elements = select(soup, selector)
        if not elements:
            return None, f"selector '{selector}' matched nothing"

        def get_val(el):
            if retrieve == "attr":
                return el.get(attr) if attr else None
            text = el.get_text(separator=" ", strip=True)
            if retrieve == "regexp" and pattern:
                m = re.search(pattern, text)
                return m.group(1) if m and m.lastindex else (m.group(0) if m else None)
            if retrieve == "regexpall" and pattern:
                return re.findall(pattern, text)
            return text

        if multiple:
            return [get_val(el) for el in elements if get_val(el) is not None], None
        return get_val(elements[0]), None
    except Exception as e:
        return None, str(e)


def scrape_detail_page(html: str, config: dict) -> dict:
    soup = BeautifulSoup(html, "lxml")
    fields = config.get("fields", {})
    result = {}
    errors = {}
    for name, cfg in fields.items():
        val, err = extract_field(soup, name, cfg)
        result[name] = val
        if err:
            errors[name] = err
    result["_errors"] = errors
    return result


# ---- Pagination URL generator ----

def generate_urls(source: dict) -> list[str]:
    template = source.get("url_template", "")
    pagination = source.get("pagination", {})
    start = pagination.get("start", 1)
    step = pagination.get("step", 1)
    max_pages = pagination.get("max_pages", 5)
    return [template.replace("{n}", str(start + i * step)) for i in range(max_pages)]


# ---- LLM result validator ----

def validate_results(results: list[dict], config: dict) -> str:
    sample = results[:3]
    messages = [
        {"role": "system", "content": (
            "You are a data quality analyst for web scraping. "
            "Given scraped records and the config used, identify: "
            "1) Missing critical fields, 2) Malformed values, 3) Extraction errors. "
            "Be brief (under 150 words)."
        )},
        {"role": "user", "content": (
            f"Config fields: {list(config.get('fields', {}).keys())}\n\n"
            f"Sample records ({len(sample)} of {len(results)}):\n"
            f"{json.dumps(sample, indent=2)}"
        )},
    ]
    return chat(messages, temperature=0.1, max_tokens=512)


# ---- Main orchestration ----

async def run(url: str, config: dict, max_items: int = 20) -> list[dict]:
    render_mode = config.get("render_mode", "auto")
    sources = config.get("sources", [])
    listing = config.get("listing", {})
    link_selector = listing.get("link_selector", "")
    link_prefix = listing.get("link_prefix", "")

    all_results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        for source in sources:
            urls = generate_urls(source)
            task = progress.add_task(f"Crawling {len(urls)} pages...", total=len(urls))

            for page_url in urls:
                if len(all_results) >= max_items:
                    break

                progress.update(task, description=f"Fetching {page_url}")

                try:
                    if render_mode == "playwright":
                        html = await fetch_playwright(page_url)
                    else:
                        html = await fetch_static(page_url)
                except Exception as e:
                    console.print(f"[red]  Fetch error: {page_url} - {e}[/red]")
                    continue

                soup = BeautifulSoup(html, "lxml")
                links = select(soup, link_selector)

                if not links:
                    console.print(f"[yellow]  No links found at {page_url} - stopping pagination[/yellow]")
                    break

                seen_urls: set[str] = set()
                detail_urls = []
                for el in links:
                    href = el.get("href", "")
                    if href.startswith("http"):
                        full = href
                    elif href:
                        full = link_prefix.rstrip("/") + "/" + href.lstrip("/")
                    else:
                        continue
                    if full not in seen_urls:
                        seen_urls.add(full)
                        detail_urls.append(full)

                progress.update(task, description=f"Scraping {len(detail_urls)} items from page...")

                for detail_url in detail_urls[:max_items]:
                    if len(all_results) >= max_items:
                        break
                    try:
                        if render_mode == "playwright":
                            detail_html = await fetch_playwright(detail_url)
                        else:
                            detail_html = await fetch_static(detail_url)

                        record = scrape_detail_page(detail_html, config)
                        record["source_url"] = detail_url
                        all_results.append(record)
                    except Exception as e:
                        console.print(f"[red]  Detail error: {detail_url} - {e}[/red]")

                progress.advance(task)

    return all_results


def display_results(results: list[dict], config: dict):
    if not results:
        console.print("[red]No results extracted.[/red]")
        return

    field_names = [k for k in config.get("fields", {}).keys() if not k.startswith("_")]
    display_fields = field_names[:6]  # Show max 6 columns

    table = Table(title=f"Scraped {len(results)} records", show_header=True)
    table.add_column("#", style="dim", width=4)
    for f in display_fields:
        table.add_column(f, max_width=30, overflow="fold")

    for i, r in enumerate(results[:15], 1):
        row = [str(i)]
        for f in display_fields:
            val = r.get(f, "")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val[:3])
            row.append(str(val)[:60] if val else "")
        table.add_row(*row)

    console.print(table)


async def main():
    parser = argparse.ArgumentParser(description="Autonomous scraping agent")
    parser.add_argument("--url", help="Target URL to auto-configure and scrape")
    parser.add_argument("--config", help="Path to existing config JSON file")
    parser.add_argument("--max-items", type=int, default=20, help="Max items to scrape")
    parser.add_argument("--output", default=str(REPO_ROOT / "scraped_results.json"), help="Output JSON file")
    parser.add_argument("--no-validate", action="store_true", help="Skip LLM result validation")
    args = parser.parse_args()

    if not args.url and not args.config:
        console.print("[red]Provide --url or --config[/red]")
        sys.exit(1)

    # Load or generate config
    if args.config:
        config_path = Path(args.config)
        with open(config_path) as f:
            config = json.load(f)
        console.print(f"[green]Loaded config: {config.get('name', config_path.name)}[/green]")
    else:
        console.print(f"[bold]Generating config for:[/bold] {args.url}")
        config = generate_config(args.url)

    console.print(Panel(
        f"Name: {config.get('name', 'unnamed')}\n"
        f"Mode: {config.get('render_mode', 'auto')}\n"
        f"Fields: {list(config.get('fields', {}).keys())}",
        title="Config Summary",
    ))

    # Run scrape
    console.print("\n[bold blue]Starting autonomous scrape...[/bold blue]")
    results = await run(args.url or config.get("sources", [{}])[0].get("url_template", ""),
                        config, max_items=args.max_items)

    # Display
    display_results(results, config)

    # LLM validation
    if not args.no_validate and results:
        console.print("\n[bold blue]LLM validating results...[/bold blue]")
        feedback = validate_results(results, config)
        console.print(Panel(feedback, title="[yellow]Quality Assessment[/yellow]"))

    # Save
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    console.print(f"\n[green]Saved {len(results)} records to {args.output}[/green]")


if __name__ == "__main__":
    asyncio.run(main())
