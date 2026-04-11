/**
 * ShopSphere CSR - Product detail renderer
 * Extracts slug from the URL path and fetches product data from /api/products/<slug>
 */

(function () {
  "use strict";

  const app = document.getElementById("app");

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }

  function getSlug() {
    // Path: /products/<slug>
    const parts = window.location.pathname.split("/");
    return parts[parts.length - 1] || "";
  }

  async function render() {
    const slug = getSlug();
    if (!slug) {
      app.innerHTML = `<div class="error-page"><h1>No product specified</h1></div>`;
      return;
    }

    try {
      const resp = await fetch(`/api/products/${encodeURIComponent(slug)}`);
      if (!resp.ok) {
        app.innerHTML = `<div class="error-page"><h1>Product not found</h1><a href="/" class="btn btn-primary">Back</a></div>`;
        return;
      }

      const p = await resp.json();
      document.title = `${p.name} - ShopSphere`;

      const specRows = Object.entries(p.specs || {})
        .map(([k, v]) => `<tr><td class="spec-key">${esc(k)}</td><td class="spec-value">${esc(v)}</td></tr>`)
        .join("");

      const tags = (p.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join("");

      app.innerHTML = `
        <nav class="breadcrumb">
          <a href="/">Products</a>
          <span>/</span>
          <a href="/?category=${encodeURIComponent(p.category)}">${esc(p.category)}</a>
          <span>/</span>
          <span>${esc(p.name)}</span>
        </nav>

        <div class="product-detail" data-product-id="${esc(p.id)}">
          <div class="product-detail-layout">
            <div class="product-image-large">
              <img class="product-image-main"
                   src="https://picsum.photos/seed/${esc(p.slug)}/600/380"
                   alt="${esc(p.name)}">
              <span class="product-category-badge large">${esc(p.category)}</span>
              <div class="product-gallery">
                <img class="gallery-image" src="https://picsum.photos/seed/${esc(p.slug)}-alt1/200/150" alt="View 2" loading="lazy">
                <img class="gallery-image" src="https://picsum.photos/seed/${esc(p.slug)}-alt2/200/150" alt="View 3" loading="lazy">
                <img class="gallery-image" src="https://picsum.photos/seed/${esc(p.slug)}-alt3/200/150" alt="View 4" loading="lazy">
              </div>
            </div>

            <div class="product-detail-info">
              <h1 class="product-title">${esc(p.name)}</h1>

              <div class="product-rating-row">
                <span class="rating-value" data-rating="${esc(p.rating)}">${esc(p.rating)}</span>
                <span class="rating-label">/ 5.0</span>
                <span class="review-count">(${p.review_count.toLocaleString()} customer reviews)</span>
              </div>

              <div class="product-price-box">
                <span class="price-label">Price:</span>
                <span class="price-amount">$${parseFloat(p.price).toFixed(2)}</span>
              </div>

              <div class="availability ${p.in_stock ? "available" : "unavailable"}">
                <span class="stock-status">${p.in_stock ? "In Stock" : "Out of Stock"}</span>
              </div>

              <div class="product-tags">${tags}</div>

              <div class="product-actions">
                <button class="btn btn-primary btn-large" ${!p.in_stock ? "disabled" : ""}>
                  Add to Cart
                </button>
              </div>
            </div>
          </div>

          <div class="product-details-section">
            <div class="description-block">
              <h2>Description</h2>
              <p class="product-description-full">${esc(p.description)}</p>
            </div>
            <div class="specs-block">
              <h2>Specifications</h2>
              <table class="specs-table"><tbody>${specRows}</tbody></table>
            </div>
          </div>
        </div>`;

    } catch (err) {
      app.innerHTML = `<div class="error-page"><h1>Error loading product</h1><p>${esc(err.message)}</p></div>`;
    }
  }

  render();
})();
