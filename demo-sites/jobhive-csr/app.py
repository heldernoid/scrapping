"""
JobHive CSR - Client-Side Rendered job board demo.

The server only serves:
  - Static HTML shell at / (empty <div id="app">)
  - JSON API at /api/*

All job content is rendered by JavaScript in the browser.
Scraping with BeautifulSoup on the raw HTML response returns nothing useful.
Playwright (headless browser) is required to see actual content.

Run: flask run --port 8004
"""
from flask import Flask, jsonify, request, send_from_directory
from data import get_page, get_by_slug, JOBS

app = Flask(__name__, static_folder="static", static_url_path="")


# ---- Static HTML shell routes ----

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/jobs")
def jobs_page():
    # SPA: all routes serve the same shell; JS handles routing
    return send_from_directory("static", "index.html")


@app.route("/jobs/<slug>")
def job_page(slug):
    return send_from_directory("static", "job.html")


# ---- JSON API ----

@app.route("/api/jobs")
def api_jobs():
    page = int(request.args.get("page", 1))
    department = request.args.get("department", "")
    remote = request.args.get("remote", "")

    filtered = JOBS
    if department:
        filtered = [j for j in filtered if j["department"].lower() == department.lower()]
    if remote:
        filtered = [j for j in filtered if j["remote"].lower() == remote.lower()]

    per_page = 10
    start = (page - 1) * per_page
    total_pages = (len(filtered) + per_page - 1) // per_page

    return jsonify({
        "jobs": filtered[start:start + per_page],
        "page": page,
        "total_pages": total_pages,
        "total_items": len(filtered),
        "has_next": page < total_pages,
        "has_prev": page > 1,
    })


@app.route("/api/jobs/<slug>")
def api_job(slug):
    job = get_by_slug(slug)
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify(job)


@app.route("/api/filters")
def api_filters():
    return jsonify({
        "departments": sorted(set(j["department"] for j in JOBS)),
        "remote_options": sorted(set(j["remote"] for j in JOBS)),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004, debug=False)
