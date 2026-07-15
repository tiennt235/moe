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
    # Normalize for cheap, precise agent reads: drop empty sections, strip source boilerplate
    # (legal/front-back matter that is not the work), then bound section size by sub-splitting
    # oversized sections on the source's own enumeration.
    doc.sections = [s for s in doc.sections if s.text.strip()]
    doc.sections = _strip_boilerplate(doc.sections, fmt)
    doc.sections = _dedupe_heading_prefix(doc.sections)
    doc.sections = _split_oversized(doc.sections)
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
# Post-extraction normalization: strip boilerplate, bound section size
# --------------------------------------------------------------------------------------
# Largest a single knowledge section should get before we sub-split it. Above this an agent
# would have to read a whole chapter to cite one passage; below it a read is one citable unit.
# ~6k chars ≈ 1.5k tokens.
MAX_SECTION_CHARS = 6000

# Editorial back-matter that is a division of long-form *published works* (books). Matched
# against *any* element of a section's heading path (case-insensitive), so sub-sections such as
# "GLOSSARY › Paragraphs with First Lines" are dropped with their parent. Only applied to book
# formats (see ``_BOOK_FORMATS``): in web/doc formats these words are inline callouts — e.g. an
# AWS doc's "**Note**" that trafilatura renders as a heading — and carry real content, so
# stripping them there silently deletes prose.
_BOILERPLATE_HEADINGS = {
    "notes", "note", "glossary", "appendix", "index", "bibliography", "footnotes",
    "endnotes", "colophon", "contents", "table of contents", "transcriber's note",
    "transcriber's notes",
}
_BOOK_FORMATS = {
    SourceFormat.pdf, SourceFormat.epub, SourceFormat.mobi, SourceFormat.text,
}
_GUTENBERG_START = re.compile(r"\*\*\*\s*START OF TH(?:E|IS) PROJECT GUTENBERG[^*]*\*\*\*", re.I)
_GUTENBERG_END = re.compile(r"\*\*\*\s*END OF TH(?:E|IS) PROJECT GUTENBERG[^*]*\*\*\*", re.I)
# A line beginning with a roman-numeral or arabic enumerator ("I.", "42.") — the natural
# citation unit of enumerated works (e.g. Meditations verses). Anchored to the line start so
# indented continuation lines never match.
_ENUM_RE = re.compile(r"^(?P<label>[IVXLCDM]{1,7}|\d{1,3})\.\s", re.M)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_boilerplate(heading_path: list[str], *, editorial: bool) -> bool:
    for h in heading_path:
        leaf = _clean(h).lower()
        if "project gutenberg" in leaf:  # header block + "THE FULL PROJECT GUTENBERG LICENSE"
            return True
        if editorial and leaf.rstrip(":.").strip() in _BOILERPLATE_HEADINGS:
            return True
    return False


def _trim_gutenberg(text: str) -> str:
    """For plain-text sources the legal wrapper is inline; keep only the work between markers."""
    m = _GUTENBERG_START.search(text)
    if m:
        text = text[m.end() :]
    m = _GUTENBERG_END.search(text)
    if m:
        text = text[: m.start()]
    return text


def _strip_boilerplate(sections: list[Section], fmt: SourceFormat) -> list[Section]:
    editorial = fmt in _BOOK_FORMATS
    out: list[Section] = []
    for s in sections:
        if _is_boilerplate(s.heading_path, editorial=editorial):
            continue
        s.text = _trim_gutenberg(s.text).strip()
        if s.text:
            out.append(s)
    return out


def _dedupe_heading_prefix(sections: list[Section]) -> list[Section]:
    """Drop the leading heading elements shared by *every* section — typically the page's H1,
    which repeats on each child line of the INDEX and each citation while carrying no
    discriminating signal (the source title already supplies that context). Only strips a truly
    common prefix, so multi-chapter works (each chapter distinct) are untouched; a section that
    would be left empty keeps its last element."""
    paths = [s.heading_path for s in sections if s.heading_path]
    if len(paths) < 2:
        return sections
    common = 0
    shortest = min(len(p) for p in paths)
    while common < shortest and len({p[common] for p in paths}) == 1:
        common += 1
    if common == 0:
        return sections
    for s in sections:
        if s.heading_path:
            s.heading_path = s.heading_path[common:] or s.heading_path[-1:]
    return sections


def _sub(sec: Section, extra: str, text: str) -> Section:
    """A child section that inherits ``sec``'s heading path (plus ``extra``) and page range."""
    return Section(
        heading_path=[*sec.heading_path, extra] if extra else list(sec.heading_path),
        text=text.strip(),
        page_start=sec.page_start,
        page_end=sec.page_end,
    )


def _split_oversized(sections: list[Section]) -> list[Section]:
    out: list[Section] = []
    for sec in sections:
        out.extend([sec] if len(sec.text) <= MAX_SECTION_CHARS else _split_one(sec))
    return out


def _split_one(sec: Section) -> list[Section]:
    text = sec.text
    marks = list(_ENUM_RE.finditer(text))
    if len(marks) >= 2:  # enumerated: pack consecutive items into ≤MAX chunks, anchor by range
        parts: list[Section] = []
        pre = text[: marks[0].start()].strip()
        if pre:
            parts.append(_sub(sec, "", pre))
        bounds = [m.start() for m in marks] + [len(text)]
        labels = [m.group("label") for m in marks]
        i, n = 0, len(marks)
        while i < n:
            j = i
            while j + 1 < n and (bounds[j + 1] - bounds[i]) <= MAX_SECTION_CHARS:
                j += 1
            label = labels[i] if i == j else f"{labels[i]}–{labels[j]}"
            parts.append(_sub(sec, label, text[bounds[i] : bounds[j + 1]]))
            i = j + 1
        return parts
    return _split_by_size(sec)  # unenumerated prose: pack paragraphs into ≤MAX "part N" chunks


def _split_by_size(sec: Section) -> list[Section]:
    # Split on the coarsest boundary that actually subdivides the text: blank-line paragraphs,
    # then single newlines (EPUB/HTML prose), then sentence ends; hard-slice only if nothing
    # else works. Then greedily pack units into ≤MAX chunks.
    text = sec.text
    sep = ""
    units = [text]
    for pat, s in ((r"\n\s*\n", "\n\n"), (r"\n", "\n"), (r"(?<=[.!?])\s+", " ")):
        parts = re.split(pat, text)
        if len(parts) > 1:
            units, sep = parts, s
            break
    else:
        units = [text[i : i + MAX_SECTION_CHARS] for i in range(0, len(text), MAX_SECTION_CHARS)]

    chunks: list[Section] = []
    buf: list[str] = []
    size = 0
    for u in units:
        if buf and size + len(u) > MAX_SECTION_CHARS:
            chunks.append(_sub(sec, f"part {len(chunks) + 1}", sep.join(buf)))
            buf, size = [], 0
        buf.append(u)
        size += len(u) + len(sep)
    if buf:
        chunks.append(_sub(sec, f"part {len(chunks) + 1}", sep.join(buf)))
    return chunks if len(chunks) > 1 else [sec]


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
            # Join inline children with a space, else nested tags concatenate ("ofMeditations").
            stack.append((level, _clean(el.get_text(" ", strip=True))))
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
