from moe.config import get_settings
from moe.ingest.chunk import chunk_document
from moe.ingest.extract import detect_format, extract
from moe.models import ChunkParams, content_hash, make_source_id

MD = b"""# Primer
Intro paragraph about the subject and its scope for readers.

## Chapter 1
The heart is a muscular organ. It pumps blood through the body.
It has four chambers. The atria receive blood. The ventricles pump it out.

### 1.1 Valves
The heart has four valves. The mitral valve sits on the left side.
The aortic valve controls flow into the aorta. Stenosis narrows it.

## Chapter 2
An arrhythmia is an irregular heartbeat. Atrial fibrillation is common.
"""


def _doc():
    origin = "primer.md"
    sid = make_source_id(origin, content_hash(MD))
    return extract(MD, origin, detect_format(origin), sid)


def test_sections_carry_heading_path():
    doc = _doc()
    headings = [s.heading_path for s in doc.sections]
    assert ["Primer", "Chapter 1", "1.1 Valves"] in headings


def test_chunks_do_not_cross_sections():
    doc = _doc()
    params = ChunkParams(target_tokens=40, min_tokens=8, max_tokens=60, overlap=0.2)
    chunks = chunk_document(doc, get_settings(), params)
    assert chunks
    # every chunk's heading_path must equal one of the document's section headings
    section_headings = {tuple(s.heading_path) for s in doc.sections}
    for c in chunks:
        assert tuple(c.heading_path) in section_headings


def test_chunk_ids_deterministic():
    doc = _doc()
    p = ChunkParams(target_tokens=40, min_tokens=8, max_tokens=60, overlap=0.2)
    a = chunk_document(doc, get_settings(), p)
    b = chunk_document(doc, get_settings(), p)
    assert [c.id for c in a] == [c.id for c in b]


def test_small_sections_do_not_merge_across_boundaries():
    # Regression: with a large min_tokens, small sections must NOT collapse into one chunk
    # spanning multiple headings. Each non-empty section yields at least one chunk.
    doc = _doc()
    params = ChunkParams(target_tokens=512, min_tokens=300, max_tokens=800, overlap=0.15)
    chunks = chunk_document(doc, get_settings(), params)
    headings = {tuple(c.heading_path) for c in chunks}
    assert ("Primer", "Chapter 1", "1.1 Valves") in headings
    assert ("Primer", "Chapter 2") in headings
    # no chunk mixes content from two different sections
    section_headings = {tuple(s.heading_path) for s in doc.sections}
    for c in chunks:
        assert tuple(c.heading_path) in section_headings


def test_embed_text_prepends_context():
    doc = _doc()
    chunks = chunk_document(doc, get_settings(), ChunkParams(target_tokens=40))
    chunks[0].context = "This chunk is from the primer intro."
    assert chunks[0].embed_text.startswith("This chunk is from the primer intro.")
    assert chunks[0].text in chunks[0].embed_text
