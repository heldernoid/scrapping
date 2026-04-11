# Chapter 12: Change Detection and Alerts

A scraper that runs on schedule but never tells you when something important changes is a passive data collector. Adding change detection transforms it into an active intelligence system: when prices drop, when jobs matching your criteria appear, when a site restructures and the scraper breaks, you know immediately.

This chapter covers change detection patterns, alert conditions, and notification delivery.

## What to Detect

Change detection falls into two categories:

**Data changes**: The extracted data itself changed. A price dropped. A job listing was posted. A product went out of stock. These are expected changes - the data is supposed to evolve.

**Scraper health changes**: The scraper is no longer extracting data correctly. Zero items scraped. Required fields consistently null. HTTP error rate increasing. These are unexpected changes that indicate a problem.

Both are worth alerting on, but they require different responses. Data changes are the point of the scraper. Health changes require intervention.

## Detecting Data Changes

Compare the new extraction against the previous extraction to find what changed:

```python
async def detect_changes(
    new_records: list[dict],
    db_path: str
) -> dict:
    changes = {
        "new": [],      # Records not in the previous run
        "removed": [],  # Records in the previous run but not this one
        "modified": []  # Records that exist in both but with different values
    }

    import sqlite3, json
    conn = sqlite3.connect(db_path)

    previous = {
        row["slug"]: json.loads(row["raw"])
        for row in conn.execute("SELECT slug, raw FROM products").fetchall()
    }
    current = {r["slug"]: r for r in new_records}

    # New records
    for slug, record in current.items():
        if slug not in previous:
            changes["new"].append(record)

    # Removed records
    for slug in previous:
        if slug not in current:
            changes["removed"].append(previous[slug])

    # Modified records
    for slug in set(previous) & set(current):
        prev = previous[slug]
        curr = current[slug]

        diffs = {}
        for field in ["price", "rating", "in_stock", "review_count"]:
            if prev.get(field) != curr.get(field):
                diffs[field] = {"before": prev.get(field), "after": curr.get(field)}

        if diffs:
            changes["modified"].append({"slug": slug, "title": curr.get("title"), "diffs": diffs})

    conn.close()
    return changes
```

## Price Change Alerts

Price changes are the most commonly monitored data change. A simple threshold alert:

```python
def filter_significant_price_changes(
    modified: list[dict],
    threshold_pct: float = 10.0
) -> list[dict]:
    significant = []
    for item in modified:
        diffs = item.get("diffs", {})
        if "price" in diffs:
            before = diffs["price"]["before"]
            after = diffs["price"]["after"]
            if before and after:
                change_pct = abs(after - before) / before * 100
                if change_pct >= threshold_pct:
                    significant.append({
                        **item,
                        "price_change_pct": round((after - before) / before * 100, 1)
                    })
    return significant
```

A 10% price change threshold avoids alerting on trivial fluctuations while catching meaningful changes. Adjust to match your use case.

## Scraper Health Monitoring

Data quality checks that run after each scrape:

```python
def check_scraper_health(results: list[dict], config: dict) -> list[str]:
    issues = []

    # Check item count
    if len(results) == 0:
        issues.append("CRITICAL: Zero items scraped - selectors may be broken")
        return issues  # No point checking further

    expected_min = config.get("health", {}).get("min_items", 5)
    if len(results) < expected_min:
        issues.append(f"WARNING: Only {len(results)} items scraped (expected >= {expected_min})")

    # Check field completeness
    required_fields = config.get("health", {}).get("required_fields", [])
    for field in required_fields:
        null_count = sum(1 for r in results if r.get(field) is None)
        null_pct = null_count / len(results) * 100
        if null_pct > 20:
            issues.append(
                f"WARNING: Field '{field}' is null in {null_pct:.0f}% of records "
                f"({null_count}/{len(results)})"
            )

    # Check for suspiciously uniform values (extraction bug symptom)
    spot_fields = ["price", "title"]
    for field in spot_fields:
        values = [r.get(field) for r in results if r.get(field)]
        if values and len(set(values)) == 1 and len(values) > 3:
            issues.append(
                f"WARNING: Field '{field}' has the same value in all {len(values)} records - "
                f"possible selector bug"
            )

    return issues
```

The health check configuration lives in the config JSON:

```json
{
  "render_mode": "static",
  "health": {
    "min_items": 10,
    "required_fields": ["title", "price", "url"]
  },
  "sources": [...],
  "fields": {...}
}
```

## Alert Delivery

Alerts are only useful if they reach someone who can act on them. The delivery mechanism depends on your operational setup.

**Log-based alerts** (simplest): Write alerts to a log file and monitor the log.

```python
import logging

logger = logging.getLogger("scraper.alerts")
handler = logging.FileHandler("scraper-alerts.log")
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

def alert(level: str, message: str):
    if level == "critical":
        logger.critical(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)
```

**Email alerts**: Send an email when issues are detected.

```python
import smtplib
from email.message import EmailMessage

def send_email_alert(subject: str, body: str, to: str, smtp_host: str):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "scraper-alerts@yourdomain.com"
    msg["To"] = to
    msg.set_content(body)

    with smtplib.SMTP(smtp_host) as smtp:
        smtp.send_message(msg)
```

**Webhook alerts**: Post to a Slack channel, a Discord server, or any HTTP endpoint.

```python
import httpx

async def send_webhook_alert(webhook_url: str, message: str):
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={"text": message})

# Slack example
await send_webhook_alert(
    os.environ["SLACK_WEBHOOK_URL"],
    f":warning: Scraper health check failed:\n{chr(10).join(issues)}"
)
```

## Composing the Alert Pipeline

The alert pipeline runs after each scrape:

```python
async def run_with_alerts(config: dict, db_path: str, webhook_url: str):
    # Run the scrape
    results = await scrape(config)

    # Check health
    health_issues = check_scraper_health(results, config)
    if health_issues:
        await send_webhook_alert(
            webhook_url,
            f"Scraper health issues detected:\n" + "\n".join(f"- {i}" for i in health_issues)
        )

    # Detect data changes
    if results:
        changes = await detect_changes(results, db_path)

        if changes["new"]:
            await send_webhook_alert(
                webhook_url,
                f"{len(changes['new'])} new items found"
            )

        significant_price_changes = filter_significant_price_changes(changes["modified"])
        if significant_price_changes:
            lines = []
            for item in significant_price_changes[:5]:
                pct = item["price_change_pct"]
                before = item["diffs"]["price"]["before"]
                after = item["diffs"]["price"]["after"]
                sign = "+" if pct > 0 else ""
                lines.append(f"  {item['title']}: ${before} -> ${after} ({sign}{pct}%)")
            await send_webhook_alert(
                webhook_url,
                f"Price changes detected:\n" + "\n".join(lines)
            )

    # Store the new results
    for record in results:
        upsert_product(db_path, record)
```

## Alert Fatigue

Alerts lose their value if they fire too often. Alert fatigue sets in when operators start ignoring alerts because most are noise. Prevent it:

**Threshold everything.** A 1% price change is noise. A 10% price change is signal. A scraper returning 9 items instead of 10 is noise. A scraper returning 0 items is a critical failure.

**Suppress repeated alerts.** If a scraper has been returning zero items for three runs, alert once per day, not once per run. Implement a cooldown period for recurring alerts.

**Categorize by severity.** Critical issues (zero items, multiple field failures) require immediate attention. Warnings (count slightly below expected, one field occasionally null) can wait for the daily digest.

**Alert on recovery too.** When a failed scraper starts working again, alert. Recovery confirmation closes the loop and prevents unnecessary investigation.

## Apply This

**1. Monitor zero-item runs above all else.** A scraper that returns zero items and reports success is the worst kind of failure. Treat it as a critical alert that requires immediate investigation.

**2. Define health expectations in the config.** The `min_items` and `required_fields` health configuration belongs in the config JSON alongside the extraction logic. When the config changes, the health expectations change with it.

**3. Alert on data changes that matter, not all changes.** Implement thresholds for what constitutes a significant change before alerting. Small fluctuations are expected; large changes warrant attention.

**4. Test your alerts.** Add a `--dry-run` mode that runs the change detection and health checks but sends alerts to stdout instead of the actual destination. Test this after any change to the alert pipeline.

**5. Log everything, alert selectively.** All health checks and change detection should write to logs. Only a subset of those log events should trigger alerts. The log is for debugging; the alert is for action.
