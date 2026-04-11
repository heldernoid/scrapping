# Chapter 11: Storage Patterns for Scraped Data

Scraped data has a shape that challenges conventional storage choices. Product records have variable schemas: a laptop has CPU and RAM specs; a headphone has driver size and impedance. Job listings vary across companies: some have salary ranges, some have only "competitive". Review counts change daily. Prices change hourly.

The right storage approach depends on what you do with the data after scraping. This chapter covers the main patterns: SQLite for exploration, PostgreSQL for production relational data, and the dual-database pattern (relational + document store) for structured-plus-variable data.

## The Scraped Record Shape

A scraped record has two parts:

**Core fields**: Title, URL, price, rating - consistent across all records of the same type. These map naturally to relational columns.

**Variable fields**: Specs, features, tags, custom attributes - vary per record. A MacBook Pro has `"Processor"`, `"RAM"`, `"Storage"`. A desk lamp has `"Wattage"`, `"Bulb Type"`, `"Cord Length"`.

Relational databases handle core fields well. Variable fields require either a JSON column, a key-value table, or a document store.

## SQLite for Development and Small Datasets

SQLite requires no infrastructure and works perfectly for development, testing, and datasets under a few million records.

```python
import sqlite3
import json
from datetime import datetime

def create_schema(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            slug        TEXT UNIQUE NOT NULL,
            title       TEXT,
            price       REAL,
            rating      REAL,
            category    TEXT,
            in_stock    INTEGER,
            tags        TEXT,  -- JSON array
            specs       TEXT,  -- JSON object
            url         TEXT,
            scraped_at  TEXT,
            raw         TEXT   -- Full JSON record
        )
    """)
    conn.commit()
    conn.close()

def upsert_product(db_path: str, product: dict):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO products (slug, title, price, rating, category, in_stock,
                              tags, specs, url, scraped_at, raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            price = excluded.price,
            rating = excluded.rating,
            category = excluded.category,
            in_stock = excluded.in_stock,
            tags = excluded.tags,
            specs = excluded.specs,
            scraped_at = excluded.scraped_at,
            raw = excluded.raw
    """, (
        product.get("slug"),
        product.get("title"),
        product.get("price"),
        product.get("rating"),
        product.get("category"),
        product.get("in_stock"),
        json.dumps(product.get("tags", [])),
        json.dumps(product.get("specs", {})),
        product.get("url"),
        datetime.utcnow().isoformat(),
        json.dumps(product),
    ))
    conn.commit()
    conn.close()
```

The `ON CONFLICT(slug) DO UPDATE` clause is the upsert - if a product with that slug already exists, update it rather than failing. This makes scrape runs idempotent.

Store the full `raw` JSON record alongside the normalized columns. The raw record is your audit trail: if the extraction logic changes and you need to re-derive a field, the raw data is already stored.

## PostgreSQL for Production

PostgreSQL handles the same patterns at production scale, with better concurrency, real foreign keys, and the `JSONB` column type for efficient querying of JSON data.

```python
import asyncpg
import json
from datetime import datetime

async def upsert_product(pool: asyncpg.Pool, product: dict):
    await pool.execute("""
        INSERT INTO products (slug, title, price, rating, category, in_stock,
                              tags, specs, url, scraped_at, raw)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (slug) DO UPDATE SET
            title = EXCLUDED.title,
            price = EXCLUDED.price,
            rating = EXCLUDED.rating,
            category = EXCLUDED.category,
            in_stock = EXCLUDED.in_stock,
            tags = EXCLUDED.tags,
            specs = EXCLUDED.specs,
            scraped_at = EXCLUDED.scraped_at,
            raw = EXCLUDED.raw
    """,
        product.get("slug"),
        product.get("title"),
        product.get("price"),
        product.get("rating"),
        product.get("category"),
        product.get("in_stock"),
        json.dumps(product.get("tags", [])),  # JSONB
        json.dumps(product.get("specs", {})), # JSONB
        product.get("url"),
        datetime.utcnow(),
        json.dumps(product),
    )
```

PostgreSQL's `JSONB` type allows querying inside JSON fields:

```sql
-- Find all products with RAM >= 16GB in their specs
SELECT title, price FROM products
WHERE specs->>'RAM' ILIKE '%16%'
   OR specs->>'RAM' ILIKE '%32%';

-- Find products with a specific tag
SELECT title FROM products
WHERE tags @> '["Laptops"]'::jsonb;
```

## The Dual-Database Pattern

For high-volume scraping where the schema varies significantly across record types, a dual-database approach provides the best of both worlds:

**Relational database (PostgreSQL or SQLite)**: Core structured fields - slug, title, price, rating, URL, scraped_at. These are consistent and queryable with SQL.

**Document store (MongoDB or a JSON file store)**: The complete raw record with all variable fields. Query by slug to retrieve the full document.

```python
# Write core fields to PostgreSQL
await pg_pool.execute(
    "INSERT INTO products (slug, title, price, rating, scraped_at) VALUES ($1,$2,$3,$4,$5)"
    " ON CONFLICT (slug) DO UPDATE SET title=$2, price=$3, rating=$4, scraped_at=$5",
    product["slug"], product["title"], product.get("price"),
    product.get("rating"), datetime.utcnow()
)

# Write full document to MongoDB
await mongo_collection.replace_one(
    {"slug": product["slug"]},
    {**product, "scraped_at": datetime.utcnow()},
    upsert=True
)
```

Use PostgreSQL when you need: aggregate queries (average price by category), filtering on multiple fields, joins across tables.

Use MongoDB when you need: the full variable-schema document, flexible querying of nested fields, rapid iteration when the schema is still evolving.

## Change Tracking

Scraped data changes. Prices go up and down. Items go in and out of stock. Job listings expire. Tracking these changes over time requires more than upsert - it requires versioned records.

The simplest approach: a `price_history` table alongside the current `products` table.

```sql
CREATE TABLE products (
    slug        TEXT PRIMARY KEY,
    title       TEXT,
    price       REAL,
    in_stock    BOOLEAN,
    scraped_at  TIMESTAMPTZ
);

CREATE TABLE price_history (
    id         SERIAL PRIMARY KEY,
    slug       TEXT REFERENCES products(slug),
    price      REAL,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);
```

When upserting a product, check if the price changed before inserting a history record:

```python
async def upsert_with_history(pool, product):
    async with pool.acquire() as conn:
        # Get current price
        row = await conn.fetchrow(
            "SELECT price FROM products WHERE slug = $1",
            product["slug"]
        )

        current_price = row["price"] if row else None
        new_price = product.get("price")

        # Upsert the main record
        await conn.execute("""
            INSERT INTO products (slug, title, price, in_stock, scraped_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                title = EXCLUDED.title,
                price = EXCLUDED.price,
                in_stock = EXCLUDED.in_stock,
                scraped_at = NOW()
        """, product["slug"], product["title"], new_price, product.get("in_stock"))

        # Record price change
        if current_price != new_price and new_price is not None:
            await conn.execute(
                "INSERT INTO price_history (slug, price) VALUES ($1, $2)",
                product["slug"], new_price
            )
```

## File-Based Storage for Simple Cases

For development and small-scale extraction, JSON files are sometimes the right choice:

```python
import json
from pathlib import Path
from datetime import datetime

def save_results(results: list[dict], output_dir: str, run_id: str):
    output_path = Path(output_dir) / f"{run_id}.json"
    output_path.write_text(json.dumps({
        "run_id": run_id,
        "scraped_at": datetime.utcnow().isoformat(),
        "count": len(results),
        "records": results,
    }, indent=2))
    return output_path
```

File-based storage is simple to inspect, easy to move between systems, and does not require database infrastructure. The downside: no indexing, no query capability, no deduplication. Use it for one-off extractions and prototyping.

## Schema Evolution

Scraped schemas change. The target site adds a field you want. It removes a field you were extracting. The config changes to match.

For relational storage, schema evolution requires migrations: `ALTER TABLE products ADD COLUMN discount_pct REAL`. For MongoDB or JSON storage, schema evolution is free - new fields simply appear in new documents.

The pragmatic approach for long-lived scraping projects: use a relational table for the queryable core fields and evolve them with explicit migrations. Store the full raw document in a JSON column or document store so that new fields are always available for retrospective analysis, even before you added them to the schema.

## Apply This

**1. Always upsert, never insert.** Use `ON CONFLICT ... DO UPDATE` in SQL or `replace_one(upsert=True)` in MongoDB. Idempotent writes mean you can re-run any scrape without worrying about duplicates.

**2. Store the raw record alongside normalized fields.** A `raw JSONB` or `raw TEXT` column containing the full extracted JSON is free insurance. When the extraction logic changes, you can re-derive normalized fields from the raw record without re-scraping.

**3. Track changes that matter.** Price history and stock status history are the most common valuable time series in product scraping. Implement change tracking from the start; retrofitting it to an existing dataset is painful.

**4. Use SQLite for development.** No infrastructure, no config, just a file. Swap in PostgreSQL for production by changing the connection string. The SQL dialect differences are minimal.

**5. Index your primary lookup fields.** `slug` (or whatever unique identifier you use for deduplication) must be indexed. Query fields like `category` and `in_stock` benefit from indexes once the dataset grows beyond a few hundred thousand records.
