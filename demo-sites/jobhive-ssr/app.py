"""
JobHive SSR - Server-Side Rendered job board demo.

Content is fully rendered in HTML by the server (Jinja2 templates).
BeautifulSoup can parse the raw HTTP response directly - no JavaScript needed.

Run: flask run --port 8003
"""
from flask import Flask, render_template, request, abort
from data import get_page, get_by_slug, JOBS

app = Flask(__name__)


@app.route("/")
@app.route("/jobs")
def listing():
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

    departments = sorted(set(j["department"] for j in JOBS))
    remote_options = sorted(set(j["remote"] for j in JOBS))

    return render_template(
        "index.html",
        jobs=filtered[start:start + per_page],
        page=page,
        total_pages=total_pages,
        total_items=len(filtered),
        has_next=page < total_pages,
        has_prev=page > 1,
        departments=departments,
        remote_options=remote_options,
        active_department=department,
        active_remote=remote,
    )


@app.route("/jobs/<slug>")
def job_detail(slug):
    job = get_by_slug(slug)
    if not job:
        abort(404)
    return render_template("job.html", job=job)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003, debug=False)
