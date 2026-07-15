"""Author-time knowledge build: raw materials → curated, cited markdown + an INDEX.

For each source in the roster we run :func:`moe.extract.extract` (PyMuPDF / ebooklib /
trafilatura / markdown) to get a normalized :class:`~moe.models.Document`, then write one
markdown file per source (front-matter + sectioned text carrying heading path + page range)
plus a per-expert ``INDEX.md``. No chunking, embeddings, or database — this is the whole
"retrieval index": files an agent greps and reads."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.request import Request, urlopen

from moe.extract import detect_format, extract
from moe.models import Document, Section, content_hash, make_source_id, slugify
from moe.roster import ExpertSpec, MaterialSpec


def expert_dir(slug: str, root: Path) -> Path:
    return root / "experts" / slug


def knowledge_dir(slug: str, root: Path) -> Path:
    return expert_dir(slug, root) / "knowledge"


# --------------------------------------------------------------------------------------
# Fetch + extract
# --------------------------------------------------------------------------------------
def _read_material(mat: MaterialSpec, root: Path) -> bytes:
    if mat.url:
        req = Request(mat.url, headers={"User-Agent": "moe-knowledge-builder"})
        with urlopen(req, timeout=60) as resp:  # noqa: S310 — operator-provided URL
            return resp.read()
    p = (root / mat.path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"material not found: {mat.path}")
    return p.read_bytes()


def _document_for(mat: MaterialSpec, root: Path) -> Document:
    data = _read_material(mat, root)
    fmt = detect_format(mat.origin)
    sid = make_source_id(mat.origin, content_hash(data))
    return extract(data, mat.origin, fmt, sid, title=mat.title, author=mat.author)


# --------------------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------------------
def _page_suffix(sec: Section) -> str:
    if sec.page_start is None:
        return ""
    if sec.page_end and sec.page_end != sec.page_start:
        return f" (p. {sec.page_start}–{sec.page_end})"
    return f" (p. {sec.page_start})"


def _heading_label(sec: Section) -> str:
    return " › ".join(sec.heading_path) if sec.heading_path else "(untitled section)"


def _fmt_size(chars: int) -> str:
    return f"{chars / 1000:.1f}k chars" if chars >= 1000 else f"{chars} chars"


def _preview(text: str) -> str:
    """First *substantive* line — a topical hint for the grep/read step. Skips short label stems
    (e.g. "Knowledge of:", "Skills in:") that head list-structured docs and would otherwise make
    every preview identical, and drops a leading bullet marker."""
    for line in text.splitlines():
        s = " ".join(line.split())
        if not s or (s.endswith(":") and len(s) <= 24):
            continue
        s = re.sub(r"^[-*+]\s+", "", s).strip()
        if any(c.isalnum() for c in s):  # skip lone bullets / punctuation-only lines
            return s[:77] + "…" if len(s) > 78 else s
    return ""


def _yaml_escape(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_source_md(doc: Document, origin: str) -> str:
    fm = [
        "---",
        f"title: {_yaml_escape(doc.title or 'Untitled')}",
    ]
    if doc.author:
        fm.append(f"author: {_yaml_escape(doc.author)}")
    fm += [
        f"origin: {_yaml_escape(doc.url or origin)}",
        f"format: {doc.fmt.value}",
        f"source_id: {doc.source_id}",
        f"sections: {len(doc.sections)}",
        "---",
        "",
        f"# {doc.title or 'Untitled'}",
        "",
    ]
    body: list[str] = []
    for sec in doc.sections:
        body.append(f"## {_heading_label(sec)}{_page_suffix(sec)}")
        body.append("")
        body.append(sec.text.strip())
        body.append("")
    return "\n".join(fm) + "\n".join(body).rstrip() + "\n"


def render_index_md(expert: ExpertSpec, entries: list[dict]) -> str:
    out = [
        f"# {expert.name} — knowledge index",
        "",
        f"_Consult this index, then grep/read the files below to answer "
        f"{expert.name} questions. Always cite: source title · section · page._",
        "",
    ]
    if not entries:
        out.append("_No sources built yet._")
        return "\n".join(out) + "\n"
    for e in entries:
        out.append(f"## {e['title']}  →  `{e['file']}`")
        for sec in e["sections"]:
            line = f"- {sec['label']}  ·  {_fmt_size(sec['chars'])}"
            if sec["preview"]:
                line += f'  ·  "{sec["preview"]}"'
            out.append(line)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------------------
# Build one expert
# --------------------------------------------------------------------------------------
def build_expert_knowledge(expert: ExpertSpec, root: Path) -> dict:
    kdir = knowledge_dir(expert.slug, root)
    kdir.mkdir(parents=True, exist_ok=True)
    # clear stale generated files (keep nothing but what we regenerate)
    for old in kdir.glob("*.md"):
        old.unlink()

    entries: list[dict] = []
    used: set[str] = set()
    total_sections = 0
    for mat in expert.materials:
        doc = _document_for(mat, root)
        base = slugify(doc.title or Path(mat.origin).stem or "source") or "source"
        slug = base
        i = 2
        while slug in used:
            slug, i = f"{base}-{i}", i + 1
        used.add(slug)
        fname = f"{slug}.md"
        (kdir / fname).write_text(render_source_md(doc, mat.origin))
        entries.append(
            {
                "title": doc.title or "Untitled",
                "file": fname,
                "sections": [
                    {
                        "label": f"{_heading_label(s)}{_page_suffix(s)}",
                        "chars": len(s.text),
                        "preview": _preview(s.text),
                    }
                    for s in doc.sections
                ],
            }
        )
        total_sections += len(doc.sections)

    (kdir / "INDEX.md").write_text(render_index_md(expert, entries))
    return {"expert": expert.name, "sources": len(entries), "sections": total_sections}
