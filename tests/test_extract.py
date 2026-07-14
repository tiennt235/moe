import pytest

from moe.ingest.extract import detect_format, extract
from moe.models import SourceFormat


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
