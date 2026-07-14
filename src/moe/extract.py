"""Per-format extraction → a normalized :class:`~moe.models.Document`.

Every extractor preserves the citation backbone: title, author, heading path, and (for
PDFs) page numbers. Heavy parser libraries are imported lazily inside each extractor."""

from __future__ import annotations

import re
from pathlib import Path

from moe.models import Document, Section, SourceFormat

_EXT_MAP = {
    ".pdf": SourceFormat.pdf,
    ".epub": SourceFormat.epub,
    ".mobi": SourceFormat.mobi,
    ".azw": SourceFormat.mobi,
    ".azw3": SourceFormat.mobi,
    ".htm": SourceFormat.html,
    ".html": SourceFormat.html,
    ".md": SourceFormat.markdown,
    ".markdown": SourceFormat.markdown,
    ".txt": SourceFormat.text,
}


def detect_format(origin: str, explicit: SourceFormat | None = None) -> SourceFormat:
    if explicit:
        return explicit
    if origin.startswith(("http://", "https://")):
        # A URL with a document extension is that document; otherwise treat as an article.
        ext = Path(origin.split("?")[0]).suffix.lower()
        return _EXT_MAP.get(ext, SourceFormat.html)
    ext = Path(origin).suffix.lower()
    if ext not in _EXT_MAP:
        raise ValueError(f"unsupported file type: {ext or origin!r}")
    return _EXT_MAP[ext]


def extract(
    data: bytes,
    origin: str,
    fmt: SourceFormat,
    source_id: str,
    *,
    title: str | None = None,
    author: str | None = None,
) -> Document:
    dispatch = {
        SourceFormat.pdf: _extract_pdf,
        SourceFormat.epub: _extract_epub,
        SourceFormat.mobi: _extract_mobi,
        SourceFormat.html: _extract_html,
        SourceFormat.markdown: _extract_markdown,
        SourceFormat.text: _extract_text,
    }
    doc = dispatch[fmt](data, origin)
    if title:
        doc.title = title
    if author:
        doc.author = author
    doc.source_id = source_id
    if not doc.title:
        doc.title = Path(origin).stem or origin
    # drop empty sections
    doc.sections = [s for s in doc.sections if s.text.strip()]
    return doc


# --------------------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------------------
def _extract_pdf(data: bytes, origin: str) -> Document:
    import fitz  # PyMuPDF

    pdf = fitz.open(stream=data, filetype="pdf")
    meta = pdf.metadata or {}
    toc = pdf.get_toc()  # [[level, title, page], ...] (1-indexed pages)

    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    toc_by_page: dict[int, list[tuple[int, str]]] = {}
    for level, htitle, page in toc:
        toc_by_page.setdefault(page, []).append((level, htitle))

    for pno in range(pdf.page_count):
        page = pdf.load_page(pno)
        # advance heading stack for any TOC entries starting on this page
        for level, htitle in toc_by_page.get(pno + 1, []):
            heading_stack = [(lvl, t) for lvl, t in heading_stack if lvl < level]
            heading_stack.append((level, htitle))

        text = page.get_text("text")
        if not text.strip():
            try:  # scanned page → OCR fallback (needs Tesseract available to MuPDF)
                text = page.get_textpage_ocr(flags=0, full=True).extractText()
            except Exception:  # noqa: BLE001
                text = ""
        if not text.strip():
            continue
        sections.append(
            Section(
                heading_path=[t for _, t in heading_stack],
                text=text,
                page_start=pno + 1,
                page_end=pno + 1,
            )
        )
    return Document(
        source_id="",
        title=(meta.get("title") or "").strip() or None,
        author=(meta.get("author") or "").strip() or None,
        fmt=SourceFormat.pdf,
        sections=sections,
    )


# --------------------------------------------------------------------------------------
# EPUB
# --------------------------------------------------------------------------------------
def _extract_epub(data: bytes, origin: str) -> Document:
    import io

    from ebooklib import ITEM_DOCUMENT, epub

    book = epub.read_epub(io.BytesIO(data))
    title = _first(book.get_metadata("DC", "title"))
    author = _first(book.get_metadata("DC", "creator"))

    sections: list[Section] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        sections.extend(_html_to_sections(item.get_content()))
    return Document(
        source_id="", title=title, author=author, fmt=SourceFormat.epub, sections=sections
    )


def _extract_mobi(data: bytes, origin: str) -> Document:
    """MOBI/AZW → EPUB via Calibre's ``ebook-convert`` (if installed), then reuse EPUB."""
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("ebook-convert"):
        raise RuntimeError(
            "MOBI ingestion requires Calibre's 'ebook-convert' on PATH "
            "(install calibre, or convert to EPUB/PDF first)."
        )
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.mobi"
        dst = Path(td) / "out.epub"
        src.write_bytes(data)
        subprocess.run(
            ["ebook-convert", str(src), str(dst)], check=True, capture_output=True
        )
        doc = _extract_epub(dst.read_bytes(), origin)
    doc.fmt = SourceFormat.mobi
    return doc


# --------------------------------------------------------------------------------------
# HTML / web article
# --------------------------------------------------------------------------------------
def _extract_html(data: bytes, origin: str) -> Document:
    import trafilatura

    html = data.decode("utf-8", errors="replace")
    md = trafilatura.extract(
        html, output_format="markdown", with_metadata=False, favor_precision=True
    )
    meta = trafilatura.extract_metadata(html)
    title = getattr(meta, "title", None)
    author = getattr(meta, "author", None)
    url = getattr(meta, "url", None) or (origin if origin.startswith("http") else None)
    if md:
        sections = _markdown_to_sections(md)
    else:  # fall back to raw text if main-content extraction failed
        sections = _html_to_sections(data)
    doc = Document(
        source_id="", title=title, author=author, fmt=SourceFormat.html, sections=sections
    )
    doc.url = url
    return doc


# --------------------------------------------------------------------------------------
# Markdown / plain text
# --------------------------------------------------------------------------------------
def _extract_markdown(data: bytes, origin: str) -> Document:
    text = data.decode("utf-8", errors="replace")
    return Document(
        source_id="", title=None, fmt=SourceFormat.markdown,
        sections=_markdown_to_sections(text),
    )


def _extract_text(data: bytes, origin: str) -> Document:
    text = data.decode("utf-8", errors="replace")
    return Document(
        source_id="", title=None, fmt=SourceFormat.text,
        sections=[Section(heading_path=[], text=text)],
    )


# --------------------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _markdown_to_sections(md: str) -> list[Section]:
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush() -> None:
        if buf and "".join(buf).strip():
            sections.append(
                Section(heading_path=[t for _, t in stack], text="\n".join(buf).strip())
            )
        buf.clear()

    for line in md.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            stack = [(lvl, t) for lvl, t in stack if lvl < level]
            stack.append((level, m.group(2).strip()))
        else:
            buf.append(line)
    flush()
    return sections or [Section(heading_path=[], text=md.strip())]


def _html_to_sections(content: bytes | str) -> list[Section]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            sections.append(Section(heading_path=[t for _, t in stack], text=text))
        buf.clear()

    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        if el.name and el.name[0] == "h" and el.name[1:].isdigit():
            flush()
            level = int(el.name[1:])
            stack = [(lvl, t) for lvl, t in stack if lvl < level]
            stack.append((level, el.get_text(strip=True)))
        else:
            txt = el.get_text(" ", strip=True)
            if txt:
                buf.append(txt)
    flush()
    if not sections:  # no structure at all → dump body text
        body = soup.get_text("\n", strip=True)
        if body:
            sections = [Section(heading_path=[], text=body)]
    return sections


def _first(meta_list) -> str | None:
    if meta_list and meta_list[0]:
        val = meta_list[0][0] if isinstance(meta_list[0], (tuple, list)) else meta_list[0]
        return str(val).strip() or None
    return None
