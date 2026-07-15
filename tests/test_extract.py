import pytest

from moe.extract import (
    MAX_SECTION_CHARS,
    _html_to_sections,
    _strip_boilerplate,
    detect_format,
    extract,
)
from moe.knowledge import _preview, render_index_md
from moe.models import Section, SourceFormat
from moe.roster import ExpertSpec


def _md(text: str):
    return extract(text.encode(), "t.md", SourceFormat.markdown, "sid")


def test_detect_format():
    assert detect_format("book.pdf") == SourceFormat.pdf
    assert detect_format("notes.md") == SourceFormat.markdown
    assert detect_format("https://example.com/post") == SourceFormat.html
    assert detect_format("https://example.com/a.pdf") == SourceFormat.pdf
    with pytest.raises(ValueError):
        detect_format("mystery.xyz")


def test_markdown_headings():
    doc = extract(b"# Title\n## Sub\nBody text here.", "x.md", SourceFormat.markdown, "sid")
    assert any("Sub" in s.heading_path for s in doc.sections)


def test_html_main_content():
    html = (
        b"<html><head><title>Doc</title></head><body>"
        b"<h1>Heading</h1><p>" + b"Meaningful sentence. " * 20 + b"</p></body></html>"
    )
    doc = extract(html, "http://x/y", SourceFormat.html, "sid")
    assert doc.sections
    assert "Meaningful sentence" in " ".join(s.text for s in doc.sections)


def test_text_fallback_title():
    doc = extract(b"just some text", "readme.txt", SourceFormat.text, "sid")
    assert doc.title == "readme"  # falls back to origin stem


# --------------------------------------------------------------------------------------
# Post-extraction normalization (boilerplate, headings, size-bounded sections, INDEX)
# --------------------------------------------------------------------------------------
def test_gutenberg_license_stripped_for_any_format():
    doc = _md("# The Work\nReal content here.\n# THE FULL PROJECT GUTENBERG LICENSE\nlegal\n")
    heads = [" › ".join(s.heading_path) for s in doc.sections]
    assert "THE FULL PROJECT GUTENBERG LICENSE" not in heads  # legal boilerplate always dropped
    assert "The Work" in heads


def test_editorial_backmatter_stripped_for_books_kept_for_web():
    # Books: NOTES/GLOSSARY are back-matter divisions → dropped.
    book = [
        Section(heading_path=["NOTES"], text="endnotes"),
        Section(heading_path=["Chapter 1"], text="real content."),
    ]
    assert [s.heading_path for s in _strip_boilerplate(book, SourceFormat.epub)] == [["Chapter 1"]]

    # Web docs: an inline "Note" callout (e.g. AWS docs) is real content → kept. Regression for
    # the bug where AWS pages opening with a **Note** lost their prose.
    web = [
        Section(heading_path=["Model Monitor", "Note"], text="Important caveat about access."),
        Section(heading_path=["Model Monitor", "Overview"], text="How it works."),
    ]
    kept = [s.heading_path for s in _strip_boilerplate(web, SourceFormat.html)]
    assert ["Model Monitor", "Note"] in kept


def test_gutenberg_inline_markers_trim_plain_text():
    doc = extract(
        b"front matter\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nthe work\n"
        b"*** END OF THE PROJECT GUTENBERG EBOOK X ***\nlegal footer",
        "t.txt",
        SourceFormat.text,
        "sid",
    )
    body = "\n".join(s.text for s in doc.sections)
    assert "the work" in body
    assert "front matter" not in body and "legal footer" not in body


def test_html_heading_joins_inline_children():
    secs = _html_to_sections(b"<h2>The <i>Enchiridion</i> By<b>EPICTETUS</b></h2><p>Body.</p>")
    label = secs[0].heading_path[-1]
    assert "ByEPICTETUS" not in label  # the concatenation bug this fix removes
    assert "Enchiridion" in label and "EPICTETUS" in label


def test_oversized_enumerated_section_splits_with_range_anchors():
    verses = "\n".join(f"{i}. " + "word " * 60 for i in range(1, 60))
    doc = _md("# THE FOURTH BOOK\n" + verses)

    assert len(doc.sections) > 1  # the ~18k-char book is broken up
    assert all(s.heading_path[0] == "THE FOURTH BOOK" for s in doc.sections)
    # one enumerated item may exceed the cap, but a chunk stops within one item of it
    assert all(len(s.text) <= MAX_SECTION_CHARS * 2 for s in doc.sections)
    assert any("–" in s.heading_path[-1] for s in doc.sections)  # e.g. "1–15"


def test_oversized_unenumerated_prose_splits_into_parts():
    doc = _md("# Introduction\n" + ("A long sentence of prose. " * 400))
    assert len(doc.sections) > 1
    assert all(s.heading_path[-1].startswith("part ") for s in doc.sections)


def test_common_heading_prefix_is_stripped():
    # Every section sits under the same H1 → that prefix carries no signal and is dropped.
    doc = _md("# The Exam Guide\n## Domain 1\nfirst.\n## Domain 2\nsecond.\n")
    labels = [s.heading_path for s in doc.sections]
    assert labels == [["Domain 1"], ["Domain 2"]]


def test_common_prefix_not_stripped_when_chapters_differ():
    # No shared leading element (each book is top-level) → nothing to strip.
    doc = _md("## THE FIRST BOOK\na.\n## THE SECOND BOOK\nb.\n")
    leaves = [s.heading_path[0] for s in doc.sections]
    assert leaves == ["THE FIRST BOOK", "THE SECOND BOOK"]


def test_preview_skips_label_stems_and_bullets():
    assert _preview("Knowledge of:\n- Data formats and ingestion mechanisms") == (
        "Data formats and ingestion mechanisms"
    )
    assert _preview("Real sentence up front.") == "Real sentence up front."
    # lone-bullet / punctuation-only first line is skipped, not shown as the preview
    assert _preview("-\nActual content follows here.") == "Actual content follows here."


def test_index_shows_size_and_preview():
    expert = ExpertSpec(name="x", description="d")
    entries = [
        {
            "title": "T",
            "file": "t.md",
            "sections": [{"label": "Ch 1", "chars": 1500, "preview": "Hello world"}],
        }
    ]
    idx = render_index_md(expert, entries)
    assert "1.5k chars" in idx
    assert '"Hello world"' in idx
