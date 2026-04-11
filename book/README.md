# Autonomous Scraping: The JSON-Config Approach

**A technical book on modern web scraping - from static HTML extraction to AI-driven autonomous data collection.**

---

## Table of Contents

### Part 1: Foundations

| Chapter | Title | Key concepts |
|---------|-------|-------------|
| [1](part-1-foundations/01-why-scraping.md) | Why Scraping | Data as infrastructure, use cases, when scraping is the right tool |
| [2](part-1-foundations/02-rendering-landscape.md) | The Rendering Landscape | SSR vs. CSR, how browsers build the DOM, curl vs. what you see |
| [3](part-1-foundations/03-json-config-contract.md) | The JSON Config Contract | Config schema, sources, listing, fields, render_mode |

### Part 2: Extraction

| Chapter | Title | Key concepts |
|---------|-------|-------------|
| [4](part-2-extraction/04-selectors.md) | CSS Selectors as a Query Language | Selector vocabulary, stability, debugging |
| [5](part-2-extraction/05-fields-and-transforms.md) | Fields, Transforms, and Extraction Types | plaintext, attr, regexp, regexpall, multiple, batch_fields, stage |
| [6](part-2-extraction/06-pagination.md) | Pagination Architecture | Page offset, item offset, next-link, cursor, infinite scroll |

### Part 3: Rendering

| Chapter | Title | Key concepts |
|---------|-------|-------------|
| [7](part-3-rendering/07-static-fetching.md) | Static Fetching with httpx | Async client, headers, timeouts, concurrency |
| [8](part-3-rendering/08-playwright.md) | Playwright for Dynamic Content | Browser automation, wait strategies, concurrency, API interception |
| [9](part-3-rendering/09-auto-fallback.md) | The Auto-Fallback Engine | Probe selector, static-first strategy, mode caching |

### Part 4: Scale

| Chapter | Title | Key concepts |
|---------|-------|-------------|
| [10](part-4-scale/10-scheduling.md) | Scheduling and Orchestration | APScheduler, cron, task queues, frequency guidelines |
| [11](part-4-scale/11-storage.md) | Storage Patterns | SQLite, PostgreSQL, dual-database, upsert, change tracking |
| [12](part-4-scale/12-alerts.md) | Change Detection and Alerts | Data change detection, health monitoring, alert delivery |

### Part 5: AI Agents

| Chapter | Title | Key concepts |
|---------|-------|-------------|
| [13](part-5-ai-agents/13-config-as-language.md) | Config as Language for AI Agents | LLM config generation, repair loop, AI as config author |
| [14](part-5-ai-agents/14-autonomous-agents.md) | Autonomous Scraping Agents | Full autonomous loop, evaluation, repair, config registry |
| [15](part-5-ai-agents/15-mcp.md) | MCP and the Tool-First Paradigm | FastMCP, tool design, exposing scraping as AI-accessible tools |

### [Epilogue](16-epilogue.md)

The scraping stack as infrastructure; where to take it next.

---

## How to Read This Book

**If you are new to web scraping**, read Parts 1-3 in order. Part 1 builds the conceptual foundation; Part 2 covers the extraction mechanics; Part 3 explains rendering modes and the fetching layer.

**If you have scraped before but not used a config-driven approach**, start with Chapter 3 (The JSON Config Contract) and Chapter 6 (Pagination Architecture), then move to Part 5.

**If you are interested in AI-driven scraping**, Parts 4-5 and the epilogue are the core material. Chapter 13 (Config as Language) is the conceptual bridge between traditional scraping and AI-assisted automation.

**If you want to run the code first**, follow the Quick Start in the repository README:

```bash
uv sync
cd demo-sites && docker compose up -d
jupyter notebook notebooks/
```

The notebooks mirror the book chapters and contain all code examples in runnable form.

---

## The Demo Sites

Every code example runs against one or more of the four demo sites included in this repository:

| Site | Port | Rendering | Test with |
|------|------|-----------|-----------|
| ShopSphere SSR | 8001 | Flask + Jinja2 | `httpx` only |
| ShopSphere CSR | 8002 | JavaScript + API | Playwright required |
| JobHive SSR | 8003 | Flask + Jinja2 | `httpx` only |
| JobHive CSR | 8004 | JavaScript + API | Playwright required |

The SSR and CSR versions of each site have identical data and identical rendered DOM. CSS selectors that work on ShopSphere SSR work identically on ShopSphere CSR after Playwright renders the page.

This design is intentional: it isolates the rendering mode decision from the extraction logic, making both independently testable.

---

## License

Book content: Creative Commons Attribution 4.0. You may share and adapt with attribution.

Code: MIT License. Use freely in commercial and non-commercial projects.
