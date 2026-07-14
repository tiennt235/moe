# Supported material formats

Each material is either a local file (`path:`) or a fetched URL (`url:`). The builder runs the
extractor at build time, which produces cleaned, sectioned markdown with citation anchors
(title, author, heading path, and page numbers for PDFs).

## Formats

- **PDF** (`.pdf`): text + table of contents become sections with page numbers. Scanned PDFs
  fall back to OCR if Tesseract is available to MuPDF.
- **EPUB** (`.epub`): chapters become sections; title/author come from EPUB metadata.
- **MOBI / AZW / AZW3**: converted to EPUB first via Calibre's `ebook-convert` (must be on
  PATH); otherwise convert to EPUB/PDF beforehand.
- **HTML / web article** (`.htm`, `.html`, or a URL with no document extension): main content is
  extracted with trafilatura; title/author/url come from page metadata.
- **Markdown / text** (`.md`, `.markdown`, `.txt`): passed through; markdown headings become the
  section structure.

## path vs url

- `path:` — a repo-relative file. Place local sources under `experts/<slug>/materials/` so they
  are committed alongside the expert.
- `url:` — fetched at build time. Prefer **stable, canonical** URLs (project Gutenberg text
  files, official docs, standards pages). A URL ending in `.pdf`/`.epub` is treated as that
  document; any other URL is treated as an HTML article.

Always set `title:` (and `author:` when known) on each material — it makes citations readable
and gives the knowledge file a clean name.

## Prefer structured formats for good citations

Citations are only as granular as the source's structure. The extractor makes sections from
**headings** (PDF bookmarks, EPUB chapters, HTML/markdown headings). A **plain `.txt` file has
no headings**, so it collapses into a single section and citations degrade to document-level.

So for books, **prefer EPUB or PDF over plain `.txt`.** For Project Gutenberg specifically,
use the `.epub` edition (e.g. `.../cache/epub/2680/pg2680.epub`), not `pg2680.txt` — the EPUB
sections cleanly by book/chapter (e.g. "THE FOURTH BOOK"), giving real citation anchors. Only
fall back to `.txt` when no structured edition exists, and note the coarser citations if so.
