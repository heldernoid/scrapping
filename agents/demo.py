"""
Full autonomous scraping demo.

Demonstrates the complete pipeline:
  1. Start with a URL (no prior knowledge)
  2. AI generates a scraper config
  3. Scraper executes (static or Playwright)
  4. AI validates the results
  5. Results saved to JSON

Works with the demo sites at localhost:8001-8004.
Start them first: cd demo-sites && docker compose up -d

Usage:
  python agents/demo.py --demo marketplace-ssr
  python agents/demo.py --demo marketplace-csr
  python agents/demo.py --demo jobboard-ssr
  python agents/demo.py --demo jobboard-csr
  python agents/demo.py --demo compare   # Show SSR vs CSR side-by-side
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path

import httpx

# Resolve paths relative to the repo root regardless of CWD
REPO_ROOT = Path(__file__).parent.parent
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.table import Table

console = Console()

DEMOS = {
    "marketplace-ssr": {
        "url": "http://localhost:8001",
        "config": REPO_ROOT / "configs/shopsphere-ssr.json",
        "description": "ShopSphere (server-side rendered) - BeautifulSoup works directly",
    },
    "marketplace-csr": {
        "url": "http://localhost:8002",
        "config": REPO_ROOT / "configs/shopsphere-csr.json",
        "description": "ShopSphere (client-side rendered) - Playwright required",
    },
    "jobboard-ssr": {
        "url": "http://localhost:8003",
        "config": REPO_ROOT / "configs/jobhive-ssr.json",
        "description": "JobHive (server-side rendered) - BeautifulSoup works directly",
    },
    "jobboard-csr": {
        "url": "http://localhost:8004",
        "config": REPO_ROOT / "configs/jobhive-csr.json",
        "description": "JobHive (client-side rendered) - Playwright required",
    },
}


def check_sites_running() -> dict[str, bool]:
    status = {}
    for name, demo in DEMOS.items():
        try:
            resp = httpx.get(demo["url"], timeout=3)
            status[name] = resp.status_code == 200
        except Exception:
            status[name] = False
    return status


def show_site_status():
    status = check_sites_running()
    table = Table(title="Demo Site Status")
    table.add_column("Site")
    table.add_column("URL")
    table.add_column("Status")
    for name, demo in DEMOS.items():
        ok = status.get(name, False)
        table.add_row(
            name,
            demo["url"],
            "[green]Running[/green]" if ok else "[red]Not running[/red]",
        )
    console.print(table)
    return status


async def demo_compare():
    """Show the fundamental SSR vs CSR difference."""
    console.print(Panel(
        "Comparing what a static scraper sees on SSR vs CSR sites",
        title="[bold]SSR vs CSR Comparison[/bold]",
    ))

    pairs = [
        ("ShopSphere SSR", "http://localhost:8001/products", "ShopSphere CSR", "http://localhost:8002/products"),
        ("JobHive SSR", "http://localhost:8003/jobs", "JobHive CSR", "http://localhost:8004/jobs"),
    ]

    for ssr_name, ssr_url, csr_name, csr_url in pairs:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                ssr_resp = await client.get(ssr_url, headers={"User-Agent": "Mozilla/5.0"})
                csr_resp = await client.get(csr_url, headers={"User-Agent": "Mozilla/5.0"})

            ssr_soup = BeautifulSoup(ssr_resp.text, "lxml")
            csr_soup = BeautifulSoup(csr_resp.text, "lxml")

            ssr_cards = len(ssr_soup.select(".product-card, .job-card"))
            csr_cards = len(csr_soup.select(".product-card, .job-card"))
            ssr_text = len(ssr_soup.get_text(strip=True))
            csr_text = len(csr_soup.get_text(strip=True))

            console.print(f"\n[bold]{ssr_name} vs {csr_name}[/bold]")
            table = Table(show_header=True)
            table.add_column("Metric")
            table.add_column(ssr_name, style="green")
            table.add_column(csr_name, style="yellow")
            table.add_row("Visible text (chars)", str(ssr_text), str(csr_text))
            table.add_row("Cards found by BS4", str(ssr_cards), str(csr_cards))
            table.add_row("Needs Playwright?", "No", "Yes")
            console.print(table)

        except Exception as e:
            console.print(f"[red]Error fetching {ssr_url} or {csr_url}: {e}[/red]")

    console.print(Panel(
        "SSR sites: static HTTP request returns full product/job data in HTML.\n"
        "CSR sites: static HTTP request returns only <div id='app'> - empty shell.\n"
        "The config field render_mode='playwright' triggers a headless browser fetch.",
        title="[bold yellow]Key Insight[/bold yellow]",
    ))


async def run_demo(demo_name: str, max_items: int = 5):
    if demo_name not in DEMOS:
        console.print(f"[red]Unknown demo: {demo_name}. Choose from: {list(DEMOS.keys())}[/red]")
        return

    demo = DEMOS[demo_name]
    console.print(Panel(demo["description"], title=f"[bold blue]{demo_name}[/bold blue]"))

    # Load config
    with open(demo["config"]) as f:
        config = json.load(f)

    console.print(f"Config: [cyan]{config['name']}[/cyan] | Mode: [cyan]{config['render_mode']}[/cyan]")

    if config["render_mode"] == "playwright":
        console.print(
            "[yellow]Note: This site requires Playwright. "
            "Ensure playwright-service is running at localhost:3001 "
            "or playwright Python package is installed.[/yellow]"
        )

    # Import and run
    from autonomous_scraper import run, display_results, validate_results
    results = await run(demo["url"], config, max_items=max_items)
    display_results(results, config)

    if results:
        feedback = validate_results(results, config)
        console.print(Panel(feedback, title="[yellow]AI Quality Check[/yellow]"))
        with open(f"{demo_name}_results.json", "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"[green]Saved to {demo_name}_results.json[/green]")
    else:
        console.print("[red]No results extracted. Check that the demo site is running.[/red]")


async def main():
    parser = argparse.ArgumentParser(description="Autonomous scraping demo")
    parser.add_argument("--demo", choices=list(DEMOS.keys()) + ["compare", "status"],
                        required=True, help="Which demo to run")
    parser.add_argument("--max-items", type=int, default=5, help="Max items to scrape")
    args = parser.parse_args()

    if args.demo == "status":
        show_site_status()
        return

    if args.demo == "compare":
        await demo_compare()
        return

    status = check_sites_running()
    site_url = DEMOS[args.demo]["url"]
    site_name = args.demo
    if not status.get(site_name):
        console.print(f"[red]Site not running: {site_url}[/red]")
        console.print("[yellow]Start demo sites with: cd demo-sites && docker compose up -d[/yellow]")
        sys.exit(1)

    await run_demo(args.demo, max_items=args.max_items)


if __name__ == "__main__":
    asyncio.run(main())
