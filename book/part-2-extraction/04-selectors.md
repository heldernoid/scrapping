# Chapter 4: CSS Selectors as a Query Language

A scraper is only as precise as its selectors. The CSS selector is the primary tool for targeting elements in HTML documents. BeautifulSoup's `select()` and `select_one()` methods accept any CSS selector string and return matching elements, giving you the full expressive power of CSS as a programmatic query language.

This chapter is a complete reference to CSS selectors in a scraping context. Every example runs against the ShopSphere and JobHive demo sites.

## Why CSS Selectors

Before CSS selectors became the standard approach, scrapers often used XPath. XPath is more expressive - it can traverse upward in the DOM, count text nodes separately from elements, and handle XML namespaces. CSS selectors cannot do any of these things.

CSS selectors win on three grounds: they are shorter to write, they are familiar to anyone who has written CSS, and they are sufficient for 95% of scraping tasks. The remaining 5% where XPath excels (navigating upward from a known element, for instance) can usually be solved by a different traversal strategy: find the container instead of navigating up from the child.

## The Selector Vocabulary

### Type, Class, and ID

The three fundamental selectors:

```python
# All h2 elements
soup.select("h2")

# Elements with class 'product-card'
soup.select(".product-card")

# Element with id 'pagination'
soup.select("#pagination")
```

In practice, class selectors are the most useful. Modern web applications assign descriptive classes to semantic elements: `.product-card`, `.job-listing`, `.price-amount`. These classes are stable across page instances and are designed to be targeted by CSS rules, which makes them reliable for scraping.

ID selectors are less useful on listing pages because IDs must be unique per page - there can only be one `#product-123`. On detail pages, IDs like `#product-title` or `#price-display` are useful for targeting unique page elements.

### Combining Selectors

Selectors can be combined to increase specificity:

```python
# Type AND class (element must be both)
soup.select("article.product-card")

# Multiple classes (element must have all of them)
soup.select(".product-card.featured")

# Comma-separated: either selector matches
soup.select("a.product-link, a.next-page")
```

The type+class combination is the most reliable pattern for listing pages. `article.product-card` matches `<article class="product-card">` but not `<div class="product-card">`. When you can see the actual HTML, use the element type to reduce false matches.

### Descendant and Child Selectors

```python
# Descendant: h2 anywhere inside .product-card
soup.select(".product-card h2")

# Direct child: only immediate children
soup.select(".product-card > .product-info")

# Adjacent sibling: .price immediately after .name
soup.select(".product-name + .product-price")
```

Descendant selectors (space between selectors) are the most common. Child selectors (`>`) are useful when element types are reused at multiple nesting levels and you need to target a specific depth.

### Attribute Selectors

```python
# Has the attribute (regardless of value)
soup.select("[data-rating]")

# Exact value match
soup.select("[data-category='laptops']")

# Contains substring
soup.select("[class*='price']")

# Starts with
soup.select("[href^='/products/']")

# Ends with
soup.select("[href$='.pdf']")
```

Attribute selectors are particularly useful for:

- **Data attributes**: `data-*` attributes often carry machine-readable values that are cleaner than parsing display text
- **URL patterns**: `[href^='/jobs/']` selects links to job detail pages
- **Input types**: `input[type='checkbox']`

The `data-rating` pattern from the ShopSphere site is a good example: the rating is stored as `data-rating="4.8"` on the container element, making it directly extractable without parsing the display text.

### Pseudo-Classes for Structure

```python
# First and last child
soup.select("tr:first-child")
soup.select("tr:last-child")

# Nth child (1-indexed)
soup.select("td:nth-child(2)")  # Second column

# Not a specific type
soup.select("div:not(.hidden)")
```

Structural pseudo-classes are most useful for tables. When a specs table has two columns (key and value), `td:nth-child(1)` extracts all keys and `td:nth-child(2)` extracts all values. This is cleaner than iterating over rows manually.

## Practical Selector Strategies

### The Inspection Workflow

Before writing any selectors, inspect the target page. In a browser:

1. Right-click the element you want to extract
2. Select "Inspect" (or equivalent)
3. Examine the element's tag, classes, and attributes
4. Look at the surrounding structure: what container holds all items of this type?

The questions to answer:

- What element type and class uniquely identifies each item on a listing page?
- On a detail page, what selectors target each data field?
- Are there data attributes that carry machine-readable versions of display values?

### Choosing Stable Selectors

Not all selectors are equally stable. Selectors based on content position (`:nth-child(3)`) break when the page structure changes. Selectors based on generated class names (`div.css-a1b2c3`) break on every CSS rebuild.

Prefer selectors in this order of stability:

1. **Semantic classes**: `.product-name`, `.job-title`, `.price-amount` - designed to identify content
2. **Data attributes**: `[data-product-id]`, `[data-rating]` - machine-readable, explicit
3. **Element+class combinations**: `h1.product-title`, `span.salary` - specific, stable
4. **Attribute patterns**: `[href^='/products/']` - based on URL structure, stable
5. **Structural positions**: `tr:nth-child(2) td:nth-child(1)` - breaks on layout changes

Avoid:

- Long descendant chains: `.container .wrapper .card .body .title` breaks on any intermediate change
- Generated class names with hashes
- Positional selectors for non-tabular content

### Extracting Links from Listing Pages

The most common listing page operation is collecting links to detail pages. The target: every link that leads to a product or job detail page.

```python
# Pattern 1: Link is the card itself
links = soup.select("a.product-card[href]")

# Pattern 2: Link is inside the card (most common)
links = soup.select(".product-card a.product-link")

# Pattern 3: Link is the heading
links = soup.select("h2.product-name a")

# Pattern 4: URL pattern matching
links = [a for a in soup.select("a[href]")
         if a["href"].startswith("/products/")]
```

The ShopSphere listing page uses pattern 2: `<article class="product-card">` contains `<a class="product-link" href="/products/macbook-pro-14">`.

Always verify you are not including navigation links, pagination links, or sidebar links. Test the selector count against what you see on the page.

### Extracting Data from Detail Pages

On a detail page, each field has its own selector:

```python
product = fetch("http://localhost:8001/products/macbook-pro-14")

title    = product.select_one("h1.product-title").get_text(strip=True)
price    = product.select_one("span.price-amount").get_text(strip=True)
rating   = product.select_one("[data-rating]")["data-rating"]
category = product.select_one(".product-category-badge").get_text(strip=True)
in_stock = "in-stock" in product.select_one(".stock-status")["class"]
```

Notice the different retrieval methods:

- `.get_text(strip=True)` for text content
- `["attribute"]` or `.get("attribute")` for attribute values
- Class membership check for boolean flags

### Handling Optional Elements

Not every field appears on every page. A product might have no sale price. A job might have no salary listed. Selectors that find nothing return an empty list or `None`.

```python
# select_one returns None if not found
el = soup.select_one(".sale-price")
sale_price = el.get_text(strip=True) if el else None

# select returns empty list if not found
tags = [el.get_text(strip=True) for el in soup.select(".tag-badge")]
# tags = [] if none found
```

The JSON config handles this automatically: fields that match nothing produce `null` in the output.

## Debugging Selectors

When a selector returns nothing, the problem is usually one of:

**Wrong class name.** Class names look similar but differ by a character. Inspect the actual HTML rather than guessing.

**Whitespace in class names.** `class="product card"` means two classes: `product` and `card`. The selector `.product.card` (no space) targets elements with both classes. `.product card` (with space) targets a `card` inside a `product`, which is different.

**Nested document fragments.** Some sites use `<template>` elements or shadow DOM. BeautifulSoup cannot see inside these.

**The page is CSR.** If `curl`ing the page returns different HTML than the browser shows, JavaScript is building the DOM. BeautifulSoup is working on the pre-JavaScript HTML, which does not contain the elements you are trying to select.

To diagnose selector failures:

```python
def debug_selector(soup, selector):
    elements = soup.select(selector)
    print(f"Selector: {selector!r}")
    print(f"Count: {len(elements)}")
    for el in elements[:3]:
        print(f"  Tag: {el.name}, Classes: {el.get('class', [])}")
        print(f"  Text: {el.get_text(strip=True)[:60]!r}")
    return elements
```

## The `select_one` vs `select` Choice

`select_one` returns the first matching element or `None`. `select` returns all matching elements as a list.

Use `select_one` when:
- You expect exactly one element (page title, price, description)
- You want the first of multiple matches (featured product)

Use `select` when:
- You expect multiple elements (product cards, job listings, tags, images)
- You want to verify count before extracting

## CSS Selector Quick Reference

| Selector | Matches |
|----------|---------|
| `div` | All `<div>` elements |
| `.price` | Elements with class `price` |
| `#main` | Element with id `main` |
| `span.price` | `<span>` with class `price` |
| `.a.b` | Elements with BOTH classes `a` and `b` |
| `div p` | `<p>` anywhere inside `<div>` |
| `div > p` | `<p>` that is a direct child of `<div>` |
| `h2 + p` | `<p>` immediately following `<h2>` |
| `[href]` | Any element with an `href` attribute |
| `[href="/jobs"]` | `href` is exactly `/jobs` |
| `[class*="price"]` | Class attribute contains the string `price` |
| `[href^="/products/"]` | `href` starts with `/products/` |
| `[href$=".pdf"]` | `href` ends with `.pdf` |
| `a, button` | Either `<a>` or `<button>` |
| `li:first-child` | `<li>` that is the first child of its parent |
| `li:last-child` | `<li>` that is the last child of its parent |
| `td:nth-child(2)` | Second `<td>` in its parent row |
| `div:not(.hidden)` | `<div>` that does not have class `hidden` |

## Apply This

**1. Test selectors interactively before encoding them in configs.** Use a Python REPL with BeautifulSoup to test selectors against live pages. Print element counts and preview text before committing to a config.

**2. Select containers, not children.** On listing pages, select the containing element for each item (`.product-card`, `.job-listing`), then extract fields from within each container. This is more reliable than selecting all titles across the page, all prices, and trying to match them up.

**3. Prefer data attributes for structured data.** When a rating is shown as stars graphically, look for `data-rating` or similar on the container. Numeric values stored in data attributes are easier to extract than parsing display text.

**4. Document selector failures.** When a selector returns nothing, print the actual HTML of the suspected parent element. The problem is usually visible immediately: a class name with a typo, an extra wrapper element, or evidence that the page is CSR.

**5. Keep selectors minimal.** The selector `.product-card h2.product-name a` is more specific than `a`, but less brittle than `.main-content .products-grid .product-card .card-body h2.product-name > a`. Remove ancestor selectors that are not adding discrimination power.
