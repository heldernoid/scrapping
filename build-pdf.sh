#!/usr/bin/env bash
# build-pdf.sh – compile the book to PDF using pandoc + pdflatex
# Run from the repo root: ./build-pdf.sh
set -euo pipefail

OUT="${1:-autonomous-scraping-book.pdf}"

echo "Building $OUT …"

pandoc \
  --metadata-file=dev-book/metadata.yaml \
  book/part-1-foundations/01-why-scraping.md \
  book/part-1-foundations/02-rendering-landscape.md \
  book/part-1-foundations/03-json-config-contract.md \
  book/part-2-extraction/04-selectors.md \
  book/part-2-extraction/05-fields-and-transforms.md \
  book/part-2-extraction/06-pagination.md \
  book/part-3-rendering/07-static-fetching.md \
  book/part-3-rendering/08-playwright.md \
  book/part-3-rendering/09-auto-fallback.md \
  book/part-4-scale/10-scheduling.md \
  book/part-4-scale/11-storage.md \
  book/part-4-scale/12-alerts.md \
  book/part-5-ai-agents/13-config-as-language.md \
  book/part-5-ai-agents/14-autonomous-agents.md \
  book/part-5-ai-agents/15-mcp.md \
  book/16-epilogue.md \
  book/17-references.md \
  -o "$OUT" \
  --from=markdown+rebase_relative_paths \
  --pdf-engine=pdflatex \
  --include-in-header=dev-book/latex-header.tex \
  --top-level-division=chapter \
  -V documentclass=report \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  --toc \
  --toc-depth=2 \
  --highlight-style=tango

echo "Done → $OUT ($(du -h "$OUT" | cut -f1))"
