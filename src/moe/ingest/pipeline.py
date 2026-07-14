"""The ingestion pipeline: extract → chunk → contextualize → embed → upsert, plus the
routing-profile refresh. Shared by the dashboard, the CLI, and portability import."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from moe.clients.bedrock import BedrockClient
from moe.clients.qdrant import QdrantKB
from moe.config import Settings
from moe.ingest.chunk import chunk_document
from moe.ingest.contextual import contextualize_chunks
from moe.ingest.extract import detect_format, extract
from moe.models import (
    Expert,
    Source,
    SourceFormat,
    SourceStatus,
    content_hash,
    make_source_id,
)
from moe.store.db import Registry

# Progress callback: (stage description, fraction 0..1)
Progress = Callable[[str, float], None]

_EMBED_BATCH = 96


def _noop(stage: str, frac: float) -> None:  # pragma: no cover
    pass


def ingest_source(
    *,
    expert: Expert,
    origin: str,
    data: bytes,
    settings: Settings,
    registry: Registry,
    kb: QdrantKB,
    bedrock: BedrockClient,
    fmt: SourceFormat | None = None,
    title: str | None = None,
    author: str | None = None,
    force: bool = False,
    progress: Progress | None = None,
) -> Source:
    progress = progress or _noop
    fmt = detect_format(origin, fmt)
    chash = content_hash(data)
    source_id = make_source_id(origin, chash)

    existing = registry.get_source(source_id)
    if existing and existing.content_hash == chash and existing.status == SourceStatus.ready \
            and not force:
        progress("unchanged — skipped", 1.0)
        return existing

    src = Source(
        source_id=source_id,
        expert=expert.name,
        title=title or "",
        author=author,
        fmt=fmt,
        origin=origin,
        content_hash=chash,
        status=SourceStatus.ingesting,
        added_at=datetime.now(timezone.utc),
    )
    registry.upsert_source(src)

    try:
        progress("extracting", 0.05)
        doc = extract(data, origin, fmt, source_id, title=title, author=author)
        src.title = doc.title
        src.author = doc.author or author

        progress("chunking", 0.15)
        chunks = chunk_document(doc, settings, expert.chunk)
        if not chunks:
            raise ValueError("no extractable text")

        contextual = (
            expert.chunk.contextual
            if expert.chunk.contextual is not None
            else settings.contextual_retrieval
        )
        if contextual:
            contextualize_chunks(
                doc, chunks, bedrock, enabled=True,
                progress=lambda n, t: progress(f"contextualizing {n}/{t}", 0.15 + 0.35 * n / t),
            )

        progress("embedding", 0.55)
        dense: list[list[float]] = []
        texts = [c.embed_text for c in chunks]
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i : i + _EMBED_BATCH]
            dense.extend(bedrock.embed(batch, input_type="search_document"))
            progress(
                f"embedding {min(i + _EMBED_BATCH, len(texts))}/{len(texts)}",
                0.55 + 0.30 * min(i + _EMBED_BATCH, len(texts)) / len(texts),
            )

        progress("upserting", 0.90)
        kb.ensure_collection(expert.collection)
        kb.delete_by_source(expert.collection, source_id)  # replace on re-ingest
        kb.upsert_chunks(
            expert.collection,
            expert.name,
            {"title": doc.title, "author": src.author, "url": doc.url},
            chunks,
            dense,
        )

        src.n_chunks = len(chunks)
        src.status = SourceStatus.ready
        registry.upsert_source(src)

        progress("updating routing profile", 0.97)
        refresh_routing_profile(expert, settings, registry, kb, bedrock)
        progress("done", 1.0)
        return src
    except Exception as e:  # noqa: BLE001
        registry.set_source_status(source_id, SourceStatus.error, error=str(e))
        raise


def refresh_routing_profile(
    expert: Expert,
    settings: Settings,
    registry: Registry,
    kb: QdrantKB,
    bedrock: BedrockClient,
) -> None:
    """Recompute the corpus centroid (from Qdrant) + description embedding. Both live in
    document-space so the query (search_query) → profile comparison is asymmetric-correct."""
    centroid = None
    if kb.collection_exists(expert.collection):
        centroid = kb.compute_centroid(expert.collection)
    desc_emb = None
    if expert.description.strip():
        try:
            desc_emb = bedrock.embed_one(expert.description, input_type="search_document")
        except Exception:  # noqa: BLE001
            desc_emb = None
    registry.set_routing_profile(expert.name, centroid, desc_emb)
