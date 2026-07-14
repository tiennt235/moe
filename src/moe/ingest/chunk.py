"""Structure-aware, token-bounded chunking.

Chunks never cross a section (major heading) boundary, are packed toward a target token
count with overlap, and carry everything needed to cite them: heading path, page range,
char offsets, and a document-global chunk index."""

from __future__ import annotations

import re
from functools import lru_cache

from moe.config import Settings
from moe.models import Chunk, ChunkParams, Document, make_chunk_id

_SENT_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|\n+|$)", re.MULTILINE)


@lru_cache
def _encoder():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def _ntok(text: str) -> int:
    return len(_encoder().encode(text))


class _Effective:
    """Per-expert chunk params falling back to global settings."""

    def __init__(self, settings: Settings, params: ChunkParams):
        self.target = params.target_tokens or settings.chunk_target_tokens
        self.minimum = params.min_tokens or settings.chunk_min_tokens
        self.maximum = params.max_tokens or settings.chunk_max_tokens
        self.overlap = settings.chunk_overlap if params.overlap is None else params.overlap


def _sentences(text: str) -> list[tuple[str, int]]:
    """Return [(sentence, char_start)] preserving offsets within ``text``."""
    out = []
    for m in _SENT_RE.finditer(text):
        s = m.group(0)
        if s.strip():
            out.append((s, m.start()))
    return out or [(text, 0)]


def _chunk_section(text: str, cfg: _Effective) -> list[dict]:
    """Pack a single section's sentences into token-bounded, overlapping chunks. Never
    crosses into another section — that boundary is enforced by the caller."""
    sents = _sentences(text)
    raw: list[dict] = []
    i = 0
    while i < len(sents):
        cur: list[tuple[str, int]] = []
        tok = 0
        j = i
        while j < len(sents):
            stok = _ntok(sents[j][0])
            if cur and tok + stok > cfg.maximum:
                break
            cur.append(sents[j])
            tok += stok
            j += 1
            if tok >= cfg.target:
                break

        chunk_text = "".join(s for s, _ in cur).strip()
        if chunk_text:
            raw.append(
                {
                    "text": chunk_text,
                    "cs": cur[0][1],
                    "ce": cur[-1][1] + len(cur[-1][0]),
                    "tok": tok,
                }
            )
        if j >= len(sents):
            break
        # rewind for overlap so the next chunk repeats trailing sentences
        overlap_tokens = int(cfg.target * cfg.overlap)
        back, acc, k = 0, 0, j - 1
        while k > i and acc < overlap_tokens:
            acc += _ntok(sents[k][0])
            back += 1
            k -= 1
        i = max(i + 1, j - back)

    # merge a too-small trailing chunk into its predecessor — but only WITHIN this section
    if len(raw) >= 2 and raw[-1]["tok"] < cfg.minimum:
        last = raw.pop()
        raw[-1]["text"] = f"{raw[-1]['text']} {last['text']}".strip()
        raw[-1]["ce"] = last["ce"]
    return raw


def chunk_document(doc: Document, settings: Settings, params: ChunkParams) -> list[Chunk]:
    cfg = _Effective(settings, params)
    chunks: list[Chunk] = []
    idx = 0
    for section in doc.sections:
        for piece in _chunk_section(section.text, cfg):
            chunks.append(
                Chunk(
                    id=make_chunk_id(doc.source_id, idx),
                    source_id=doc.source_id,
                    chunk_index=idx,
                    text=piece["text"],
                    heading_path=section.heading_path,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    char_start=piece["cs"],
                    char_end=piece["ce"],
                )
            )
            idx += 1
    return chunks
