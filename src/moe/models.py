"""Canonical data models shared across ingestion, retrieval, storage, and the surfaces."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------------------
# Ingestion-side models
# --------------------------------------------------------------------------------------
class SourceFormat(str, Enum):
    pdf = "pdf"
    epub = "epub"
    mobi = "mobi"
    html = "html"
    markdown = "markdown"
    text = "text"


class Section(BaseModel):
    """A structural unit of a document (chapter / heading region)."""

    heading_path: list[str] = Field(default_factory=list)  # e.g. ["Ch. 3", "3.2 Valves"]
    text: str
    page_start: int | None = None
    page_end: int | None = None


class Document(BaseModel):
    """A parsed, normalized source before chunking. Carries the citation backbone."""

    source_id: str
    title: str | None = None
    author: str | None = None
    url: str | None = None
    fmt: SourceFormat
    sections: list[Section] = Field(default_factory=list)


class Chunk(BaseModel):
    """An embeddable unit with everything needed to cite it precisely."""

    id: str  # deterministic: hash(source_id + chunk_index)
    source_id: str
    chunk_index: int
    text: str  # raw chunk text (what is returned to the reader)
    context: str | None = None  # contextual-retrieval prefix (embedded, not shown)
    heading_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None

    @property
    def embed_text(self) -> str:
        """Text actually sent to the embedder: context prepended when present."""
        return f"{self.context}\n\n{self.text}" if self.context else self.text


# --------------------------------------------------------------------------------------
# Retrieval-side models
# --------------------------------------------------------------------------------------
class Citation(BaseModel):
    title: str
    author: str | None = None
    source_id: str
    url: str | None = None
    location: str | None = None  # human-readable: "p. 42" or "Ch. 3 › 3.2 Valves"


class Passage(BaseModel):
    """A retrieved, reranked chunk returned to the caller — always cited."""

    text: str
    expert: str
    citation: Citation
    score: float = 0.0  # fused retrieval score
    rerank_score: float | None = None
    chunk_id: str
    heading_path: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    question: str
    experts_selected: list[str]
    passages: list[Passage]
    answer: str | None = None  # populated only when synthesize=True


# --------------------------------------------------------------------------------------
# Registry records
# --------------------------------------------------------------------------------------
class ChunkParams(BaseModel):
    target_tokens: int | None = None
    min_tokens: int | None = None
    max_tokens: int | None = None
    overlap: float | None = None
    contextual: bool | None = None


class Expert(BaseModel):
    name: str  # slug; collection is expert_<name>
    description: str
    chunk: ChunkParams = Field(default_factory=ChunkParams)
    n_sources: int = 0
    n_chunks: int = 0
    updated_at: datetime | None = None

    @property
    def collection(self) -> str:
        return f"expert_{self.name}"


class SourceStatus(str, Enum):
    pending = "pending"
    ingesting = "ingesting"
    ready = "ready"
    error = "error"


class Source(BaseModel):
    source_id: str
    expert: str
    title: str
    author: str | None = None
    fmt: SourceFormat
    origin: str  # local path or URL
    content_hash: str
    n_chunks: int = 0
    status: SourceStatus = SourceStatus.pending
    error: str | None = None
    added_at: datetime | None = None


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Job(BaseModel):
    id: str
    kind: str  # "ingest" | "reindex" | "import" ...
    expert: str | None = None
    status: JobStatus = JobStatus.queued
    stage: str = ""  # e.g. "embedding 320/1024 chunks"
    progress: float = 0.0  # 0..1
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def make_source_id(origin: str, content_hash_hex: str) -> str:
    return hashlib.sha256(f"{origin}\x00{content_hash_hex}".encode()).hexdigest()[:16]


def make_chunk_id(source_id: str, chunk_index: int) -> str:
    """Deterministic point ID so re-ingesting an unchanged source is idempotent.

    Qdrant point IDs must be an unsigned int or a UUID string; we use a UUID derived
    from the source_id + index so the same chunk always lands on the same point.
    """
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{chunk_index}"))


def slugify(name: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in name.strip().lower())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")
