/**
 * ShopSphere CSR - Product listing renderer
 *
 * This script:
 * 1. Reads the current page number from URL params
 * 2. Fetches products from /api/products
 * 3. Builds and injects the DOM entirely via JavaScript
 *
 * Static scrapers see only the empty <div id="app"> shell.
 * A headless browser (Playwright) running this script sees the full product grid.
 */

(function () {
  "use strict";

  const app = document.getElementById("app");

  function getParams() {
    const p = new URLSearchParams(window.location.search);
    return {
      page: parseInt(p.get("page") || "1", 10),
      category: p.get("category") || "",
    };
  }

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }

  function renderStars(rating) {
    return `${rating}/5`;
  }

  function renderProductCard(p) {
    return `
      <article class="product-card" data-product-id="${esc(p.id)}">
        <div class="product-image-wrapper">
          <img class="product-image"
               src="https://picsum.photos/seed/${esc(p.slug)}/400/200"
               alt="${esc(p.name)}"
               loading="lazy">
          <span class="product-category-badge">${esc(p.category)}</span>
        </div>
        <div class="product-card-body">
          <h2 class="product-name">
            <a href="/products/${esc(p.slug)}" class="product-link">${esc(p.name)}</a>
          </h2>
          <div class="product-meta">
            <span class="product-price">$${parseFloat(p.price).toFixed(2)}</span>
            <span class="product-rating" data-rating="${esc(p.rating)}">${renderStars(p.rating)}</span>
            <span class="product-reviews">(${p.review_count.toLocaleString()} reviews)</span>
          </div>
          <div class="product-stock ${p.in_stock ? "in-stock" : "out-of-stock"}">
            ${p.in_stock ? "In Stock" : "Out of Stock"}
          </div>
          <p class="product-description">${esc(p.description.substring(0, 120))}...</p>
          <a href="/products/${esc(p.slug)}" class="btn btn-primary">View Details</a>
        </div>
      </article>`;
  }

  function renderPagination(page, totalPages, category) {
    if (totalPages <= 1) return "";
    const catParam = category ? `&category=${encodeURIComponent(category)}` : "";
    let html = `<nav class="pagination" aria-label="Product pages">`;
    if (page > 1) {
      html += `<a href="?page=${page - 1}${catParam}" class="pagination-btn">Previous</a>`;
    }
    for (let p = 1; p <= totalPages; p++) {
      html += `<a href="?page=${p}${catParam}" class="pagination-btn ${p === page ? "active" : ""}">${p}</a>`;
    }
    if (page < totalPages) {
      html += `<a href="?page=${page + 1}${catParam}" class="pagination-btn">Next</a>`;
    }
    html += `</nav>`;
    return html;
  }

  function renderSidebar(categories, activeCategory) {
    const links = [`<li><a href="/" class="category-link ${!activeCategory ? "active" : ""}">All Products</a></li>`];
    categories.forEach(cat => {
      const active = activeCategory === cat ? "active" : "";
      links.push(`<li><a href="/?category=${encodeURIComponent(cat)}" class="category-link ${active}">${esc(cat)}</a></li>`);
    });
    return `
      <aside class="sidebar">
        <h3 class="sidebar-title">Categories</h3>
        <ul class="category-list">${links.join("")}</ul>
      </aside>`;
  }

  async function loadCategories() {
    const resp = await fetch("/api/categories");
    const data = await resp.json();
    return data.categories || [];
  }

  async function loadProducts(page, category) {
    const params = new URLSearchParams({ page });
    if (category) params.set("category", category);
    const resp = await fetch(`/api/products?${params}`);
    return resp.json();
  }

  async function render() {
    const { page, category } = getParams();

    try {
      const [data, categories] = await Promise.all([
        loadProducts(page, category),
        loadCategories(),
      ]);

      const cards = (data.products || []).map(renderProductCard).join("");
      const sidebar = renderSidebar(categories, category);
      const pagination = renderPagination(data.page, data.total_pages, category);

      document.title = `Products (Page ${data.page}) - ShopSphere`;

      app.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">Products
            <span class="page-count">(${data.total_items} items)</span>
          </h1>
        </div>
        <div class="layout-sidebar">
          ${sidebar}
          <div class="main-content">
            <div class="product-grid" data-testid="product-grid">
              ${cards}
            </div>
            ${pagination}
          </div>
        </div>`;
    } catch (err) {
      app.innerHTML = `<div class="error-page"><h1>Error loading products</h1><p>${esc(err.message)}</p></div>`;
    }
  }

  render();
})();
