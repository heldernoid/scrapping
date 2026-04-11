/**
 * JobHive CSR - Job detail renderer
 */

(function () {
  "use strict";

  const app = document.getElementById("app");

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

  function getSlug() {
    const parts = window.location.pathname.split("/");
    return parts[parts.length - 1] || "";
  }

  async function render() {
    const slug = getSlug();
    if (!slug) {
      app.innerHTML = `<div class="error-page"><h1>No job specified</h1></div>`;
      return;
    }

    try {
      const resp = await fetch(`/api/jobs/${encodeURIComponent(slug)}`);
      if (!resp.ok) {
        app.innerHTML = `<div class="error-page"><h1>Job not found</h1><a href="/" class="btn btn-primary">Browse Jobs</a></div>`;
        return;
      }

      const j = await resp.json();
      document.title = `${j.title} at ${j.company} - JobHive`;

      const reqs = (j.requirements || []).map(r => `<li class="requirement-item">${esc(r)}</li>`).join("");
      const benefits = (j.benefits || []).map(b => `<li class="benefit-item">${esc(b)}</li>`).join("");

      app.innerHTML = `
        <nav class="breadcrumb">
          <a href="/">Jobs</a>
          <span>/</span>
          <a href="/?department=${encodeURIComponent(j.department)}">${esc(j.department)}</a>
          <span>/</span>
          <span>${esc(j.title)}</span>
        </nav>

        <div class="job-hero">
          <img class="job-hero-image"
               src="https://picsum.photos/seed/${esc(j.slug)}-hero/900/220"
               alt="${esc(j.company)} workplace">
        </div>

        <div class="job-detail" data-job-id="${esc(j.id)}">
          <div class="job-detail-header">
            <div class="job-detail-title-block">
              <div class="job-detail-company-row">
                <img class="company-logo company-logo-lg"
                     src="https://picsum.photos/seed/${slugify(j.company)}/64/64"
                     alt="${esc(j.company)} logo">
                <div>
                  <h1 class="job-detail-title">${esc(j.title)}</h1>
                  <div class="job-detail-company">${esc(j.company)}</div>
                </div>
              </div>
            </div>
            <div class="job-detail-badges">
              <span class="badge badge-remote">${esc(j.remote)}</span>
              <span class="badge badge-type">${esc(j.type)}</span>
              <span class="badge badge-dept">${esc(j.department)}</span>
            </div>
          </div>

          <div class="job-detail-meta-grid">
            <div class="meta-item">
              <span class="meta-label">Location</span>
              <span class="meta-value job-location">${esc(j.location)}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Salary Range</span>
              <span class="meta-value salary-range">$${fmt(j.salary_min)} - $${fmt(j.salary_max)}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Experience</span>
              <span class="meta-value">${esc(j.experience)}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Posted</span>
              <span class="meta-value">${j.posted_days_ago} days ago</span>
            </div>
          </div>

          <div class="job-detail-body">
            <section class="job-section">
              <h2>About the Role</h2>
              <p class="job-description-full">${esc(j.description)}</p>
            </section>
            <section class="job-section">
              <h2>Requirements</h2>
              <ul class="requirements-list">${reqs}</ul>
            </section>
            <section class="job-section">
              <h2>Benefits</h2>
              <ul class="benefits-list">${benefits}</ul>
            </section>
          </div>

          <div class="job-apply-box">
            <button class="btn btn-primary btn-large">Apply Now</button>
            <p class="apply-note">Job ID: <code>${esc(j.id)}</code></p>
          </div>
        </div>`;

    } catch (err) {
      app.innerHTML = `<div class="error-page"><h1>Error</h1><p>${esc(err.message)}</p></div>`;
    }
  }

  render();
})();
