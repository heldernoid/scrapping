# Chapter 5: Fields, Transforms, and Extraction Types

A CSS selector finds an element. What you do with that element - the retrieval method and any transformations applied - determines the quality of the extracted data. A price stored as `"$1,999.00"` is not the same as `1999.00`. A date displayed as "3 days ago" is not the same as `"2024-01-15"`. This chapter covers every extraction method in the JSON config and how to handle the gap between display format and data format.

## The Field Extraction Pipeline

Every field in a config goes through the same pipeline:

1. **Select**: Find the element(s) using the CSS selector
2. **Retrieve**: Extract the raw value from the element
3. **Transform**: Apply post-processing (optional)
4. **Store**: Place the value in the output record

The `retrieve` type controls step 2. Everything else is handled by the engine.

## Retrieve Types

### `plaintext`

Extracts all text content from the element and its descendants, with leading/trailing whitespace stripped.

```json
"title": {"selector": "h1.product-title", "retrieve": "plaintext"}
```

```python
# Equivalent Python
element.get_text(strip=True)
```

Works for most text content. If the element contains nested elements with text, their content is concatenated: `<p>Price: <span>$19.99</span></p>` becomes `"Price: $19.99"`.

Use `plaintext` when the element's entire text content is the value, or when nested elements only add formatting (bold, italic, spans) that you want to ignore.

### `attr`

Extracts a named attribute from the element.

```json
"url":    {"selector": "a.product-link", "retrieve": "attr", "attr": "href"},
"rating": {"selector": "[data-rating]",  "retrieve": "attr", "attr": "data-rating"},
"image":  {"selector": "img.product-img","retrieve": "attr", "attr": "src"}
```

```python
# Equivalent Python
element.get("href")
element.get("data-rating")
```

Common attributes to extract:

- `href` from `<a>` elements (URLs, relative links)
- `src` from `<img>`, `<video>`, `<audio>` (media URLs)
- `data-*` attributes (machine-readable structured data)
- `value` from `<input>`, `<option>` (form field values)
- `content` from `<meta>` tags (page metadata)

### `regexp`

Applies a regular expression to the element's text content. Returns the first capture group.

```json
"price": {
  "selector": ".product-price",
  "retrieve": "regexp",
  "pattern": "\\$([\\d,]+\\.?\\d*)"
}
```

```python
import re
text = element.get_text(strip=True)  # "$1,999.00"
match = re.search(r"\$([\d,]+\.?\d*)", text)
value = match.group(1) if match else None  # "1,999.00"
```

The `regexp` type is the right choice when:

- The element mixes the value with surrounding text: `"Price: $19.99 (was $29.99)"`
- You need a specific part of compound text: `"Engineering - Senior - Remote"`
- The element contains display formatting you want to strip

A critical point: the pattern is a JSON string, so backslashes must be doubled. The Python pattern `\d` becomes `\\d` in JSON.

### `regexpall`

Like `regexp`, but returns a list of all capture group matches rather than just the first.

```json
"all_prices": {
  "selector": ".price-history",
  "retrieve": "regexpall",
  "pattern": "\\$([\\d,]+)"
}
```

```python
matches = re.findall(r"\$([\d,]+)", text)  # ["1,999", "2,499", "1,799"]
```

Use `regexpall` when a single element contains multiple values of the same type - a price history, a list of phone numbers, a series of dates embedded in text.

### `multiple`

The `multiple` flag (combinable with any retrieve type) extracts the value from every element matching the selector, returning a list.

```json
"tags": {
  "selector": ".skill-tag",
  "retrieve": "plaintext",
  "multiple": true
}
```

```python
elements = soup.select(".skill-tag")
values = [el.get_text(strip=True) for el in elements]
# ["Python", "Django", "PostgreSQL", "Docker"]
```

Without `multiple`, only the first matching element is used. With `multiple`, all matches are collected into a list.

Use `multiple` for:

- Tags, categories, skills lists
- Multiple images
- Multiple authors or contributors
- Feature lists on product pages

## Handling Units and Formatting

Raw extracted values often contain formatting intended for humans, not machines. Common patterns and their handling:

**Currency amounts:**

```json
"price_raw": {"selector": ".price", "retrieve": "plaintext"}
// Extracted: "$1,999.00"

"price_numeric": {
  "selector": ".price",
  "retrieve": "regexp",
  "pattern": "\\$([\\d,\\.]+)"
}
// Extracted: "1,999.00" (still a string; remove comma in post-processing)
```

**Percentage values:**

```json
"discount": {
  "selector": ".discount-badge",
  "retrieve": "regexp",
  "pattern": "(\\d+)%"
}
// From "Save 25%" -> "25"
```

**Salary ranges:**

```json
"salary_min": {
  "selector": ".salary-range",
  "retrieve": "regexp",
  "pattern": "\\$([\\d,]+)\\s*[-to]"
},
"salary_max": {
  "selector": ".salary-range",
  "retrieve": "regexp",
  "pattern": "[-to]\\s*\\$([\\d,]+)"
}
// From "$80,000 - $120,000" -> min="80,000", max="120,000"
```

**Ratings (text vs. attribute):**

```json
// If rating is in an attribute (clean):
"rating": {"selector": "[data-rating]", "retrieve": "attr", "attr": "data-rating"}
// Extracted: "4.8"

// If rating is in text (needs regexp):
"rating": {
  "selector": ".star-rating",
  "retrieve": "regexp",
  "pattern": "([\\d\\.]+) out of 5"
}
// From "4.8 out of 5 stars" -> "4.8"
```

## Extracting Images

Images are attributes, not text. The `attr` retrieve type with `attr: "src"` extracts image URLs from `<img>` tags.

### Single Image

The main product or hero image on a detail page:

```json
"image": {
  "selector": "img.product-image-main",
  "retrieve": "attr",
  "attr": "src"
}
```

```python
# Equivalent
element = soup.select_one("img.product-image-main")
src = element.get("src") if element else None
# "https://picsum.photos/seed/macbook-pro-14/600/380"
```

### Image Gallery

A product detail page with multiple gallery images uses `multiple: true`:

```json
"gallery_images": {
  "selector": "img.gallery-image",
  "retrieve": "attr",
  "attr": "src",
  "multiple": true
}
```

Result:

```json
{
  "gallery_images": [
    "https://picsum.photos/seed/macbook-pro-14-alt1/200/150",
    "https://picsum.photos/seed/macbook-pro-14-alt2/200/150",
    "https://picsum.photos/seed/macbook-pro-14-alt3/200/150"
  ]
}
```

This is exactly `retrieve: attr` with `multiple: true` - the same pattern used for extracting lists of tags or requirements, applied to `src` attributes instead of text content.

### Listing-Page Thumbnail vs. Detail-Page Image

On listing pages, product cards typically show a smaller thumbnail. On detail pages, a full-resolution image appears alongside a gallery. Both use the same pattern, targeting different selectors:

```json
// In the listing config (from the card, not the detail page)
"thumbnail": {
  "selector": "img.product-image",
  "retrieve": "attr",
  "attr": "src"
}

// In the detail config (from the detail page)
"image": {
  "selector": "img.product-image-main",
  "retrieve": "attr",
  "attr": "src"
},
"gallery_images": {
  "selector": "img.gallery-image",
  "retrieve": "attr",
  "attr": "src",
  "multiple": true
}
```

### Company and Hero Images

Job boards often show a company logo and a hero banner image alongside each listing. These follow the same pattern:

```json
"company_image": {
  "selector": "img.company-logo-lg",
  "retrieve": "attr",
  "attr": "src"
},
"hero_image": {
  "selector": "img.job-hero-image",
  "retrieve": "attr",
  "attr": "src"
}
```

### Relative vs. Absolute URLs

Image `src` attributes can be relative (`/images/product.jpg`) or absolute (`https://cdn.example.com/product.jpg`). Your scraper should always produce absolute URLs:

```python
from urllib.parse import urljoin

def make_absolute(base_url: str, src: str) -> str:
    if not src:
        return None
    if src.startswith(("http://", "https://", "//")):
        return src
    return urljoin(base_url, src)

# In the extraction loop:
record["image"] = make_absolute(page_url, record.get("image"))
record["gallery_images"] = [
    make_absolute(page_url, url)
    for url in (record.get("gallery_images") or [])
]
```

The demo sites use Picsum Photos with absolute URLs (`https://picsum.photos/seed/{slug}/...`), so this is not an issue there. For production scrapers, always verify whether image URLs are relative or absolute before storing them.

### Lazy-Loaded Images

Some sites use `data-src` instead of `src` for lazy-loaded images. The actual URL is in the data attribute; `src` contains a placeholder or is empty:

```html
<img class="product-image" src="/placeholder.gif" data-src="/images/product.jpg" loading="lazy">
```

Target `data-src` instead of `src`:

```json
"image": {
  "selector": "img.product-image",
  "retrieve": "attr",
  "attr": "data-src"
}
```

For sites that lazy-load images via JavaScript, static fetching may capture only the placeholder. Playwright will trigger the lazy loading if images are within the viewport, but may miss images lower on the page unless scroll behavior is triggered.

## The `batch_fields` Pattern

Some pages present structured data as key-value tables. A product specification table might look like:

```html
<table class="specs-table">
  <tr><td>Processor</td><td>Apple M3 Pro</td></tr>
  <tr><td>RAM</td><td>18 GB</td></tr>
  <tr><td>Storage</td><td>512 GB SSD</td></tr>
</table>
```

Extracting each row as a separate field would require knowing all possible spec names in advance - impractical for sites with variable specs.

The `batch_fields` config extracts the entire table as a dictionary:

```json
"specs": {
  "selector": "table.specs-table tr",
  "retrieve": "batch_fields",
  "key_selector": "td:nth-child(1)",
  "value_selector": "td:nth-child(2)"
}
```

Result:

```json
{
  "specs": {
    "Processor": "Apple M3 Pro",
    "RAM": "18 GB",
    "Storage": "512 GB SSD"
  }
}
```

The engine iterates over each `tr` element, extracts the text of the first `td` as the key and the second `td` as the value.

## Temp Fields (the `_` Prefix)

Sometimes you need an intermediate value that is used in computation but should not appear in the final output. Config fields whose names start with `_` are temp fields.

A common use case: a product page shows stock status as a class name rather than text. You want to extract a boolean `in_stock` value, but the raw element has `class="stock-status in-stock"` or `class="stock-status out-of-stock"`.

```json
"_stock_classes": {
  "selector": ".stock-status",
  "retrieve": "attr",
  "attr": "class"
},
"in_stock": {
  "retrieve": "stage",
  "expression": "'in-stock' in (_stock_classes or '')"
}
```

`_stock_classes` extracts the class string but is dropped from the final record. `in_stock` uses it as input to a computed expression.

## The `stage` Retrieve Type

The `stage` type evaluates a Python expression in a sandboxed environment. The expression has access to all previously extracted fields in the current record.

```json
"title_slug": {
  "retrieve": "stage",
  "expression": "title.lower().replace(' ', '-') if title else None"
}
```

```json
"salary_midpoint": {
  "retrieve": "stage",
  "expression": "(int(salary_min.replace(',','')) + int(salary_max.replace(',',''))) // 2 if salary_min and salary_max else None"
}
```

Stage expressions run after all selector-based fields have been extracted, so they can reference any field in the current record.

The sandbox restricts what the expression can do: no imports, no file system access, no network calls. Expressions are limited to string manipulation, arithmetic, and simple conditionals - exactly the operations needed for data normalization.

Use `stage` for:

- Combining or deriving fields from other extracted values
- Type coercion (string to int, string to float)
- Computing slugs, canonical forms, or normalized values
- Boolean flags derived from text values

## Field Ordering

Within a config, fields are processed in the order they are defined. This matters for `stage` fields that depend on earlier fields: a `stage` field must come after the fields it references.

```json
"fields": {
  "title": {"selector": "h1", "retrieve": "plaintext"},
  "price_raw": {"selector": ".price", "retrieve": "plaintext"},
  "price": {
    "retrieve": "stage",
    "expression": "float(price_raw.replace('$','').replace(',','')) if price_raw else None"
  }
}
```

If `price` were defined before `price_raw`, the stage expression would fail because `price_raw` would not yet be in scope.

## Null Handling

When a selector matches nothing, the field value is `null` (Python `None`). This is the correct behavior: missing data should be explicitly null, not an empty string or a default value.

Stage expressions receive `None` for missing fields. Always guard against `None`:

```python
# Wrong: raises AttributeError when price_raw is None
float(price_raw.replace('$', ''))

# Right: returns None if price_raw is missing
float(price_raw.replace('$', '').replace(',', '')) if price_raw else None
```

## Practical Field Configuration: ShopSphere Product

The complete field configuration for a ShopSphere product detail page demonstrates all the extraction types working together:

```json
"fields": {
  "title":         {"selector": "h1.product-title",          "retrieve": "plaintext"},
  "price_str":     {"selector": "span.price-amount",         "retrieve": "plaintext"},
  "rating":        {"selector": "[data-rating]",             "retrieve": "attr", "attr": "data-rating"},
  "review_count":  {"selector": ".review-count",             "retrieve": "regexp", "pattern": "(\\d+) review"},
  "category":      {"selector": ".product-category-badge",   "retrieve": "plaintext"},
  "in_stock":      {"selector": ".stock-status",             "retrieve": "plaintext"},
  "description":   {"selector": ".product-description-full", "retrieve": "plaintext"},
  "tags":          {"selector": "span.tag",                  "retrieve": "plaintext", "multiple": true},
  "image":         {"selector": "img.product-image-main",    "retrieve": "attr", "attr": "src"},
  "gallery_images":{"selector": "img.gallery-image",         "retrieve": "attr", "attr": "src", "multiple": true},
  "specs":         {
    "selector": "table.specs-table tr",
    "retrieve": "batch_fields",
    "key_selector": "td.spec-key",
    "value_selector": "td.spec-value"
  },
  "price": {
    "retrieve": "stage",
    "expression": "float(price_str.replace('$','').replace(',','')) if price_str else None"
  }
}
```

Each field uses the appropriate retrieval type for its source: plaintext for text, attr for data attributes, regexp for embedded values, multiple for lists, batch_fields for tables, and stage for derived values.

## Apply This

**1. Match the retrieve type to the source, not the desired output type.** If the price is in plain text, use `plaintext` and convert in a `stage` field. Do not try to make `regexp` do double duty as retrieval and conversion.

**2. Use data attributes when they exist.** A `data-price="1999.00"` attribute is always cleaner than parsing `"$1,999.00"` from display text. Inspect the HTML before assuming text is the only option.

**3. Normalize early, use `stage` for derived values.** Extract the raw value faithfully, then normalize it. Keep the raw value if debugging will be needed (call it `price_raw`), and compute the normalized version separately.

**4. Test regexp patterns against real values.** Copy the actual text content from the page and test your regexp against it in a Python REPL before encoding it in the config. `re.search(pattern, actual_text)` is faster than debugging config failures.

**5. Guard against None in all stage expressions.** Every stage expression that operates on a field value should check that the value is not None before calling string methods on it. Null-safety in expressions prevents silent failures on pages where a field is genuinely absent.
