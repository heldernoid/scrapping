"""
ShopSphere CSR - Client-Side Rendered marketplace demo.

The server only serves:
  - Static HTML shell at / (empty <div id="app">)
  - JSON API at /api/*

All product content is rendered by JavaScript in the browser.
Scraping with BeautifulSoup on the raw HTML response returns nothing useful.
Playwright (headless browser) is required to see actual content.

Run: flask run --port 8002
"""
import os
from flask import Flask, jsonify, request, send_from_directory, abort
from data import get_page, get_by_slug, PRODUCTS

app = Flask(__name__, static_folder="static", static_url_path="")


# ---- Static HTML shell routes ----

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/products")
def products_page():
    # SPA: all routes serve the same shell; JS handles routing
    return send_from_directory("static", "index.html")


@app.route("/products/<slug>")
def product_page(slug):
    # Still serve the shell - JS will load the product data
    return send_from_directory("static", "product.html")


# ---- JSON API ----

@app.route("/api/products")
def api_products():
    page = int(request.args.get("page", 1))
    category = request.args.get("category", "")

    if category:
        filtered = [p for p in PRODUCTS if p["category"].lower() == category.lower()]
        per_page = 10
        start = (page - 1) * per_page
        items = filtered[start:start + per_page]
        total_pages = (len(filtered) + per_page - 1) // per_page
        return jsonify({
            "products": items,
            "page": page,
            "total_pages": total_pages,
            "total_items": len(filtered),
            "has_next": page < total_pages,
            "has_prev": page > 1,
        })

    data = get_page(page)
    return jsonify({
        "products": data["items"],
        "page": data["page"],
        "total_pages": data["total_pages"],
        "total_items": data["total_items"],
        "has_next": data["has_next"],
        "has_prev": data["has_prev"],
    })


@app.route("/api/products/<slug>")
def api_product(slug):
    product = get_by_slug(slug)
    if not product:
        return jsonify({"error": "Not found"}), 404
    return jsonify(product)


@app.route("/api/categories")
def api_categories():
    cats = sorted(set(p["category"] for p in PRODUCTS))
    return jsonify({"categories": cats})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002, debug=False)
