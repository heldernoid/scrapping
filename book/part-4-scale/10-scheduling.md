# Chapter 10: Scheduling and Orchestration

A scraper that runs once is a script. A scraper that runs on schedule is a data pipeline. The difference is not technical sophistication but operational discipline: the scraper must run reliably, at the right frequency, with visibility into its execution, and with the ability to recover from failures.

This chapter covers scheduling patterns, from simple cron jobs to the config-driven scheduling approach that the bylgja engine uses.

## Scheduling Requirements

A production scraping schedule has five requirements:

**Regularity**: The scraper runs at a defined frequency - hourly, daily, weekly. Data consumers depend on freshness; missing a scheduled run means stale data.

**Reliability**: If a run fails (network error, site change, rate limit), the failure is logged and the next run is attempted at the scheduled time. A failed run does not cause all subsequent runs to be skipped.

**Idempotency**: Running a scraper twice produces the same result as running it once. The scraper overwrites existing records rather than appending duplicates. This makes missed runs safe to re-run manually.

**Visibility**: Operators can see which scrapers ran, when, how long they took, and whether they succeeded or failed. Invisible failures are the worst kind.

**Rate-awareness**: The schedule respects site rate limits. Scraping a site hourly when the data changes daily wastes resources and risks blocking.

## The Config as Schedule Specification

The JSON config is extended with scheduling information:

```json
{
  "render_mode": "static",
  "schedule": {
    "cron": "0 6 * * *",
    "timezone": "UTC",
    "enabled": true,
    "max_items": 500,
    "priority": "normal"
  },
  "sources": [...],
  "listing": {...},
  "fields": {...}
}
```

The `schedule.cron` field uses standard cron syntax. `"0 6 * * *"` means "at 6:00 AM every day". The scheduler reads all configs, finds enabled schedules, and dispatches runs at the appropriate times.

Common scheduling patterns:

| Cron expression | Runs |
|-----------------|------|
| `"0 * * * *"` | Every hour at minute 0 |
| `"*/15 * * * *"` | Every 15 minutes |
| `"0 6 * * *"` | Daily at 6:00 AM |
| `"0 6 * * 1"` | Every Monday at 6:00 AM |
| `"0 6 1 * *"` | First day of each month at 6:00 AM |

## Simple Scheduling with APScheduler

For a self-contained Python scraper, APScheduler provides cron scheduling without external dependencies:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import json
from pathlib import Path

async def run_config(config_path: str):
    config = json.loads(Path(config_path).read_text())
    print(f"Running scraper for {config_path}")
    results = await scrape(config)
    print(f"Scraped {len(results)} items")

async def main():
    scheduler = AsyncIOScheduler()

    configs_dir = Path("configs")
    for config_file in configs_dir.glob("*.json"):
        config = json.loads(config_file.read_text())
        schedule = config.get("schedule", {})

        if schedule.get("enabled", False):
            cron_expr = schedule["cron"]
            # Parse "0 6 * * *" into CronTrigger fields
            minute, hour, day, month, day_of_week = cron_expr.split()
            trigger = CronTrigger(
                minute=minute, hour=hour,
                day=day, month=month,
                day_of_week=day_of_week,
                timezone=schedule.get("timezone", "UTC")
            )
            scheduler.add_job(
                run_config,
                trigger=trigger,
                args=[str(config_file)],
                id=config_file.stem,
                name=f"Scraper: {config_file.stem}",
                replace_existing=True,
            )
            print(f"Scheduled {config_file.stem}: {cron_expr}")

    scheduler.start()

    try:
        await asyncio.Event().wait()  # Run forever
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

asyncio.run(main())
```

This scheduler:
- Reads all JSON configs from the `configs/` directory
- Schedules each enabled config according to its cron expression
- Runs scrape jobs using asyncio (compatible with async fetch functions)
- Continues running until interrupted

## Cron-Based Scheduling (System Level)

For simpler cases, Linux cron handles scheduling without Python overhead:

```cron
# /etc/cron.d/scrapers

# ShopSphere daily at 3 AM
0 3 * * * hm /home/hm/Documents/coding/scrapping/.venv/bin/python \
  /home/hm/Documents/coding/scrapping/agents/autonomous_scraper.py \
  --config configs/shopsphere-ssr.json \
  >> /var/log/scrapers/shopsphere-ssr.log 2>&1

# JobHive every 6 hours
0 */6 * * * hm /home/hm/Documents/coding/scrapping/.venv/bin/python \
  /home/hm/Documents/coding/scrapping/agents/autonomous_scraper.py \
  --config configs/jobhive-ssr.json \
  >> /var/log/scrapers/jobhive-ssr.log 2>&1
```

System cron is reliable (it is the OS scheduler), but lacks visibility into run status, run history, and failure notifications. For a small number of scrapers, it is appropriate. For 20+ scrapers, a proper task queue (Celery, Redis Queue) provides better observability.

## Task Queue Architecture

For production scale, a task queue separates scheduling (determining when a scraper runs) from execution (running it):

```
Scheduler (cron trigger or APScheduler)
    |
    | Enqueues task: "run config X"
    v
Task Queue (Redis)
    |
    | Worker picks up task
    v
Worker Process (runs the scraper)
    |
    | Writes results
    v
Storage (SQLite, PostgreSQL, MongoDB)
```

Celery with Redis is a common stack:

```python
# tasks.py
from celery import Celery
import json
from pathlib import Path

app = Celery("scrapers", broker="redis://localhost:6379/0")

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_scraper(self, config_path: str):
    try:
        config = json.loads(Path(config_path).read_text())
        import asyncio
        results = asyncio.run(scrape(config))
        return {"status": "success", "items": len(results)}
    except Exception as exc:
        raise self.retry(exc=exc)

# Schedule in celery beat
app.conf.beat_schedule = {
    "shopsphere-daily": {
        "task": "tasks.run_scraper",
        "schedule": crontab(hour=3, minute=0),
        "args": ["configs/shopsphere-ssr.json"],
    },
}
```

The task queue approach provides:
- **Retry logic**: Failed tasks are automatically retried
- **Visibility**: Celery Flower dashboard shows task history, duration, failures
- **Horizontal scaling**: Add more workers to process tasks in parallel
- **Priority queues**: High-priority scrapers run ahead of low-priority ones

## Scheduling Frequency Guidelines

How often to scrape depends on how often the data changes:

| Data type | Changes | Recommended frequency |
|-----------|---------|----------------------|
| Job listings | Several times daily | Every 4-6 hours |
| Product prices | Multiple times daily | Hourly or every 2 hours |
| Product inventory | Hourly or less | Every 30-60 minutes |
| Product catalog | Weekly (new items) | Daily |
| Review counts | Daily | Daily or twice daily |

Scraping more frequently than the data changes wastes resources and burdens the target site. Scraping less frequently means stale data. Monitor the change rate of your target data and adjust the schedule accordingly.

## Handling Schedule Drift

A scraper that takes 20 minutes to run should not be scheduled every 15 minutes. Schedule frequency must account for run duration:

```python
@app.task(bind=True)
def run_scraper(self, config_name: str):
    # Check if a run is already in progress for this config
    lock_key = f"scraper_lock:{config_name}"
    if not redis.set(lock_key, "1", nx=True, ex=3600):
        print(f"Scraper {config_name} already running, skipping")
        return

    try:
        results = asyncio.run(scrape(config_name))
        return results
    finally:
        redis.delete(lock_key)
```

The Redis lock prevents concurrent runs of the same scraper. If the previous run has not finished when the next scheduled run triggers, the new run is skipped.

## Apply This

**1. Make every scrape run idempotent.** Use upsert semantics when writing to storage: update the record if it exists, insert it if it does not. Running a scraper twice should not double the data.

**2. Log run start, completion, and failure.** At minimum: timestamp, config name, item count, duration, and error if applicable. These logs are your primary debugging tool when a scheduled scrape silently stops working.

**3. Set run duration limits.** A scraper that hangs indefinitely blocks the worker. Set a maximum run time and kill the job if it exceeds it.

**4. Monitor for zero-item runs.** A scraper that completes without errors but returns 0 items is silent data loss. Alert on this condition: it usually means the site changed its structure and the selectors are no longer matching.

**5. Test the schedule locally before deploying.** Use APScheduler's `.run_job()` to trigger a scheduled job immediately rather than waiting for the cron time. Verify the job executes correctly before scheduling it.
