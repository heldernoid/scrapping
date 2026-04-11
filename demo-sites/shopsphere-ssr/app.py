"""
ShopSphere SSR - Server-Side Rendered marketplace demo.

Content is fully rendered in HTML by the server (Jinja2 templates).
BeautifulSoup can parse the raw HTTP response directly - no JavaScript needed.

Run: flask run --port 8001
"""
from flask import Flask, render_template, request, abort
from data import get_page, get_by_slug, PRODUCTS

app = Flask(__name__)


@app.route("/")
@app.route("/products")
def listing():
    page = int(request.args.get("page", 1))
    category = request.args.get("category", "")

    if category:
        from data import PRODUCTS as ALL
        filtered = [p for p in ALL if p["category"].lower() == category.lower()]
        per_page = 10
        start = (page - 1) * per_page
        data = {
            "items": filtered[start:start + per_page],
            "page": page,
            "total_pages": (len(filtered) + per_page - 1) // per_page,
            "total_items": len(filtered),
            "has_next": page < (len(filtered) + per_page - 1) // per_page,
            "has_prev": page > 1,
        }
    else:
        data = get_page(page)

    categories = sorted(set(p["category"] for p in PRODUCTS))
    return render_template(
        "index.html",
        products=data["items"],
        page=data["page"],
        total_pages=data["total_pages"],
        total_items=data["total_items"],
        has_next=data["has_next"],
        has_prev=data["has_prev"],
        categories=categories,
        active_category=category,
    )


@app.route("/products/<slug>")
def product_detail(slug):
    product = get_by_slug(slug)
    if not product:
        abort(404)
    return render_template("product.html", product=product)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=False)
