"""
Config Generator Agent

Given a URL, fetches the page, extracts the HTML structure,
and asks the LLM to produce a valid bylgja-format scraper config.

Usage:
  python agents/config_generator.py http://localhost:8001/products
  python agents/config_generator.py http://localhost:8003/jobs
"""
import sys
import json
import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel

from llm import chat

console = Console()


# ---- HTML summariser ----

def summarise_html(html: str, max_elements: int = 60) -> str:
    """
    Extract a compact structural summary of the page for the LLM.
    Full HTML is too large; we want just enough structure to write selectors.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove scripts and styles
    for tag in soup(["script", "style", "meta", "link", "noscript"]):
        tag.decompose()

    lines = []
    seen_selectors = set()

    def walk(el, depth: int = 0):
        if len(lines) >= max_elements:
            return
        if not hasattr(el, "name") or not el.name:
            return

        indent = "  " * depth
        classes = " ".join(el.get("class", []))
        attrs = ""
        if classes:
            attrs += f' class="{classes}"'
        for attr in ("id", "href", "data-product-id", "data-job-id", "data-rating", "data-testid"):
            val = el.get(attr)
            if val:
                attrs += f' {attr}="{val}"'

        tag_id = f"{el.name}.{classes}"
        if tag_id not in seen_selectors:
            seen_selectors.add(tag_id)
            text_preview = el.get_text(strip=True)[:60]
            if text_preview:
                lines.append(f"{indent}<{el.name}{attrs}> {text_preview!r}")
            else:
                lines.append(f"{indent}<{el.name}{attrs}>")

        for child in el.children:
            walk(child, depth + 1)

    walk(soup.body or soup, 0)
    return "\n".join(lines)


# ---- LLM prompt ----

SYSTEM_PROMPT = """You are an expert web scraping engineer. You analyse HTML page structure
and produce scraper configuration in JSON format.

The config schema (use ONLY these top-level keys - do not invent others):
{
  "name": "string",
  "description": "string",
  "render_mode": "static" | "playwright" | "auto",
  "sources": [
    {
      "url_template": "URL with {n} placeholder for page number",
      "index_type": "page",
      "pagination": {
        "start": 1,
        "step": 1,
        "max_pages": 20,
        "stop_condition": "no_results"
      }
    }
  ],
  "listing": {
    "link_selector": "CSS selector for the <a> links to detail pages on the listing page",
    "link_prefix": "base URL to prepend to relative hrefs (e.g. http://localhost:8001)"
  },
  "fields": {
    "field_name": {
      "selector": "CSS selector (must match elements on the DETAIL page, not the listing page)",
      "retrieve": "plaintext" | "attr" | "regexp" | "regexpall",
      "attr": "attribute name (only for retrieve=attr)",
      "pattern": "regex pattern (only for retrieve=regexp)",
      "multiple": false
    }
  }
}

Critical rules:
- Output ONLY valid JSON. No markdown fences, no commentary.
- Do NOT add keys that are not in the schema above (no detail_fields, no extra sections).
- render_mode MUST be "static" if the HTML summary contains product cards, job listings,
  or other content elements. Only use "playwright" if the body is nearly empty (CSR shell).
- fields selectors must target the DETAIL page (e.g. h1.product-title, .price-amount),
  NOT the listing page cards. The engine navigates listing links to detail pages first.
- For job boards include: title, company, location, salary, job_type, tags.
- For marketplaces include: title, price, rating, category, in_stock, image.
- For boolean-like fields (in_stock, availability) use retrieve=plaintext on the
  text element (e.g. span.stock-status returns "In Stock") - never retrieve the
  class attribute of a container div.
"""

USER_TEMPLATE = """Analyse this site starting from URL: {url}

Is CSR (nearly empty body): {is_csr}
Listing page visible text chars: {text_len}

LISTING PAGE HTML structure (use for link_selector and url_template only):
{html_summary}

DETAIL PAGE HTML structure (use this for fields selectors):
{detail_summary}

Raw listing page HTML preview (first 1500 chars):
{raw_preview}

Produce the scraper config JSON now."""


# ---- Main ----

def generate_config(url: str) -> dict:
    console.print(f"\n[bold blue]Fetching listing page[/bold blue] {url}")

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
    except Exception as e:
        console.print(f"[red]Fetch failed: {e}[/red]")
        sys.exit(1)

    # Detect if CSR (almost no content in body)
    soup = BeautifulSoup(html, "lxml")
    visible_text = soup.get_text(strip=True)
    is_csr = len(visible_text) < 200

    if is_csr:
        console.print("[yellow]Page appears CSR - setting render_mode=playwright[/yellow]")

    listing_summary = summarise_html(html)
    raw_preview = html[:1500]

    # Fetch a sample detail page so the LLM can see detail-page selectors
    detail_summary = ""
    try:
        first_link = soup.select_one("a[href*='/product'], a[href*='/job'], a[href*='/item']")
        if not first_link:
            first_link = soup.select_one("article a, .card a, li a")
        if first_link:
            href = first_link.get("href", "")
            if href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            if href.startswith("http"):
                console.print(f"[bold blue]Fetching sample detail page[/bold blue] {href}")
                with httpx.Client(timeout=15, follow_redirects=True) as client:
                    detail_resp = client.get(href, headers={"User-Agent": "Mozilla/5.0"})
                detail_summary = summarise_html(detail_resp.text, max_elements=80)
                console.print(f"[dim]Detail page summary ({len(detail_summary.splitlines())} lines)[/dim]")
    except Exception as e:
        console.print(f"[dim]Could not fetch detail page: {e}[/dim]")

    console.print(f"[dim]Listing page summary ({len(listing_summary.splitlines())} lines)[/dim]")
    console.print("[bold blue]Asking LLM to generate config...[/bold blue]")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(
            url=url,
            is_csr=is_csr,
            text_len=len(visible_text),
            html_summary=listing_summary,
            raw_preview=raw_preview,
            detail_summary=detail_summary or "(not available - use listing structure to infer)",
        )},
    ]

    raw = chat(messages, temperature=0.1, max_tokens=2048)

    # Strip markdown fences if LLM wrapped the JSON anyway
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        config = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]LLM returned invalid JSON: {e}[/red]")
        console.print(raw)
        sys.exit(1)

    # Hard-enforce correct render_mode based on actual page content
    if is_csr:
        config["render_mode"] = "playwright"
    elif len(visible_text) > 500:
        # Page clearly has content - static fetch is sufficient
        config["render_mode"] = "static"

    # Strip non-standard top-level keys the LLM sometimes invents
    allowed_keys = {"name", "description", "render_mode", "sources", "listing", "fields"}
    for key in list(config.keys()):
        if key not in allowed_keys:
            del config[key]

    return config


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[red]Usage: python config_generator.py <url>[/red]")
        sys.exit(1)

    url = sys.argv[1]
    config = generate_config(url)

    console.print(Panel(
        Syntax(json.dumps(config, indent=2), "json", theme="monokai"),
        title="[bold green]Generated Scraper Config[/bold green]",
    ))

    # Save to file
    out_file = "generated_config.json"
    with open(out_file, "w") as f:
        json.dump(config, f, indent=2)
    console.print(f"\n[green]Saved to {out_file}[/green]")
