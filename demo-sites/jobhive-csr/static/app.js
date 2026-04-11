/**
 * JobHive CSR - Job listing renderer
 * Fetches jobs from /api/jobs and builds the DOM entirely via JavaScript.
 */

(function () {
  "use strict";

  const app = document.getElementById("app");

  function getParams() {
    const p = new URLSearchParams(window.location.search);
    return {
      page: parseInt(p.get("page") || "1", 10),
      department: p.get("department") || "",
      remote: p.get("remote") || "",
    };
  }

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }

  function fmt(n) {
    return Number(n).toLocaleString("en-US");
  }

  function slugify(str) {
    return str.toLowerCase().replace(/\s+/g, "-");
  }

  function renderJobCard(j) {
    const tags = (j.requirements || []).slice(0, 4)
      .map(r => `<span class="tag">${esc(r)}</span>`).join("");
    return `
      <article class="job-card" data-job-id="${esc(j.id)}">
        <div class="job-card-header">
          <div class="job-card-main">
            <img class="company-logo"
                 src="https://picsum.photos/seed/${slugify(j.company)}/48/48"
                 alt="${esc(j.company)} logo"
                 loading="lazy">
            <div>
              <h2 class="job-title">
                <a href="/jobs/${esc(j.slug)}" class="job-link">${esc(j.title)}</a>
              </h2>
              <div class="job-company">${esc(j.company)}</div>
            </div>
          </div>
          <div class="job-badges">
            <span class="badge badge-remote">${esc(j.remote)}</span>
            <span class="badge badge-type">${esc(j.type)}</span>
          </div>
        </div>
        <div class="job-meta">
          <span class="job-location">${esc(j.location)}</span>
          <span class="job-salary">$${fmt(j.salary_min)} - $${fmt(j.salary_max)}</span>
          <span class="job-experience">${esc(j.experience)}</span>
          <span class="job-posted">${j.posted_days_ago}d ago</span>
        </div>
        <p class="job-description">${esc(j.description.substring(0, 140))}...</p>
        <div class="job-tags">${tags}</div>
        <a href="/jobs/${esc(j.slug)}" class="btn btn-outline">View Job</a>
      </article>`;
  }

  function renderPagination(page, totalPages, department, remote) {
    if (totalPages <= 1) return "";
    const extra = [
      department ? `department=${encodeURIComponent(department)}` : "",
      remote ? `remote=${encodeURIComponent(remote)}` : "",
    ].filter(Boolean).join("&");
    const sep = extra ? "&" : "";
    let html = `<nav class="pagination">`;
    if (page > 1) html += `<a href="?page=${page - 1}${sep}${extra}" class="pagination-btn">Previous</a>`;
    for (let p = 1; p <= totalPages; p++) {
      html += `<a href="?page=${p}${sep}${extra}" class="pagination-btn ${p === page ? "active" : ""}">${p}</a>`;
    }
    if (page < totalPages) html += `<a href="?page=${page + 1}${sep}${extra}" class="pagination-btn">Next</a>`;
    html += `</nav>`;
    return html;
  }

  function renderSidebar(filters, activeDept, activeRemote) {
    const deptLinks = [`<li><a href="/" class="category-link ${!activeDept ? "active" : ""}">All Departments</a></li>`];
    (filters.departments || []).forEach(d => {
      deptLinks.push(`<li><a href="/?department=${encodeURIComponent(d)}" class="category-link ${activeDept === d ? "active" : ""}">${esc(d)}</a></li>`);
    });
    const remoteLinks = [`<li><a href="/" class="category-link ${!activeRemote ? "active" : ""}">All Types</a></li>`];
    (filters.remote_options || []).forEach(r => {
      remoteLinks.push(`<li><a href="/?remote=${encodeURIComponent(r)}" class="category-link ${activeRemote === r ? "active" : ""}">${esc(r)}</a></li>`);
    });
    return `
      <aside class="sidebar">
        <div class="filter-group">
          <h3 class="sidebar-title">Department</h3>
          <ul class="category-list">${deptLinks.join("")}</ul>
        </div>
        <div class="filter-group" style="margin-top:20px">
          <h3 class="sidebar-title">Work Type</h3>
          <ul class="category-list">${remoteLinks.join("")}</ul>
        </div>
      </aside>`;
  }

  async function render() {
    const { page, department, remote } = getParams();

    try {
      const params = new URLSearchParams({ page });
      if (department) params.set("department", department);
      if (remote) params.set("remote", remote);

      const [jobData, filterData] = await Promise.all([
        fetch(`/api/jobs?${params}`).then(r => r.json()),
        fetch("/api/filters").then(r => r.json()),
      ]);

      const cards = (jobData.jobs || []).map(renderJobCard).join("");
      const sidebar = renderSidebar(filterData, department, remote);
      const pagination = renderPagination(jobData.page, jobData.total_pages, department, remote);

      document.title = `Jobs (Page ${jobData.page}) - JobHive`;

      app.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">Open Positions
            <span class="page-count">(${jobData.total_items} jobs)</span>
          </h1>
        </div>
        <div class="layout-sidebar">
          ${sidebar}
          <div class="main-content">
            <div class="job-list" data-testid="job-list">${cards}</div>
            ${pagination}
          </div>
        </div>`;

    } catch (err) {
      app.innerHTML = `<div class="error-page"><h1>Error loading jobs</h1><p>${esc(err.message)}</p></div>`;
    }
  }

  render();
})();
