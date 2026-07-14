"""Shared service layer — the operations the dashboard and CLI both perform, over one core.
Keeping them here guarantees the two surfaces stay behaviorally identical."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from moe.clients.bedrock import get_bedrock
from moe.clients.qdrant import get_kb
from moe.config import get_settings
from moe.ingest.pipeline import ingest_source
from moe.models import ChunkParams, Expert, RetrievalResult, Source, SourceFormat, slugify
from moe.retrieval import answer_question
from moe.store.db import get_registry
from moe.store.jobs import Update, get_runner


@dataclass
class Item:
    """One thing to ingest: its origin (path/url), raw bytes, and optional metadata."""

    origin: str
    data: bytes
    fmt: SourceFormat | None = None
    title: str | None = None
    author: str | None = None


# --------------------------------------------------------------------------------------
# Experts
# --------------------------------------------------------------------------------------
def ensure_expert(
    name: str, description: str, chunk: ChunkParams | None = None
) -> Expert:
    slug = slugify(name)
    if not slug:
        raise ValueError("expert name must contain alphanumeric characters")
    reg = get_registry()
    expert = Expert(name=slug, description=description, chunk=chunk or ChunkParams())
    reg.upsert_expert(expert)
    get_kb().ensure_collection(expert.collection)
    return reg.get_expert(slug)


def update_expert(
    name: str, description: str | None = None, chunk: ChunkParams | None = None
) -> Expert:
    reg = get_registry()
    expert = reg.get_expert(name)
    if not expert:
        raise KeyError(name)
    if description is not None:
        expert.description = description
    if chunk is not None:
        expert.chunk = chunk
    reg.upsert_expert(expert)
    return reg.get_expert(name)


def delete_expert(name: str) -> None:
    reg = get_registry()
    expert = reg.get_expert(name)
    if not expert:
        raise KeyError(name)
    get_kb().delete_collection(expert.collection)
    reg.delete_expert(name)


def list_experts() -> list[Expert]:
    return get_registry().list_experts()


def list_sources(name: str) -> list[Source]:
    return get_registry().list_sources(name)


def delete_source(expert: str, source_id: str) -> None:
    reg = get_registry()
    exp = reg.get_expert(expert)
    if not exp:
        raise KeyError(expert)
    get_kb().delete_by_source(exp.collection, source_id)
    reg.delete_source(source_id)


# --------------------------------------------------------------------------------------
# Loading material into Items
# --------------------------------------------------------------------------------------
def item_from_path(path: str | Path, title: str | None = None) -> Item:
    p = Path(path)
    return Item(origin=str(p), data=p.read_bytes(), title=title)


def item_from_url(url: str, title: str | None = None) -> Item:
    import httpx

    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    return Item(origin=url, data=resp.content, fmt=SourceFormat.html, title=title)


def items_from_dir(directory: str | Path) -> list[Item]:
    from moe.ingest.extract import _EXT_MAP

    d = Path(directory)
    items: list[Item] = []
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.suffix.lower() in _EXT_MAP:
            items.append(item_from_path(p))
    return items


def store_material(expert: str, filename: str, data: bytes) -> Path:
    """Persist an uploaded file under materials/<expert>/ so reindex works offline."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "upload"
    dest = get_settings().materials_dir / expert / safe
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


# --------------------------------------------------------------------------------------
# Ingestion (sync for CLI, job-wrapped for the dashboard)
# --------------------------------------------------------------------------------------
def ingest_items(
    expert_name: str, items: list[Item], *, force: bool = False, update: Update | None = None
) -> list[Source]:
    settings, reg, kb, bedrock = (
        get_settings(), get_registry(), get_kb(), get_bedrock()
    )
    expert = reg.get_expert(expert_name)
    if not expert:
        raise KeyError(expert_name)

    results: list[Source] = []
    n = len(items)
    for i, item in enumerate(items):
        def item_progress(stage: str, frac: float, i=i) -> None:
            if update:
                update(f"[{i + 1}/{n}] {Path(item.origin).name}: {stage}", (i + frac) / n)

        src = ingest_source(
            expert=expert,
            origin=item.origin,
            data=item.data,
            settings=settings,
            registry=reg,
            kb=kb,
            bedrock=bedrock,
            fmt=item.fmt,
            title=item.title,
            author=item.author,
            force=force,
            progress=item_progress,
        )
        results.append(src)
    return results


def submit_ingest(expert_name: str, items: list[Item], *, force: bool = False) -> str:
    """Non-blocking: run ingestion as a background job, return its id (dashboard path)."""

    def work(update: Update) -> dict:
        sources = ingest_items(expert_name, items, force=force, update=update)
        return {"sources": len(sources), "ids": [s.source_id for s in sources]}

    return get_runner().submit("ingest", expert_name, work)


def submit_reindex(expert_name: str) -> str:
    """Re-ingest every stored source of an expert from materials/ (force)."""
    reg = get_registry()
    sources = reg.list_sources(expert_name)
    items = [
        Item(origin=s.origin, data=Path(s.origin).read_bytes(), title=s.title, author=s.author)
        for s in sources
        if Path(s.origin).exists()
    ]

    def work(update: Update) -> dict:
        sources = ingest_items(expert_name, items, force=True, update=update)
        return {"reindexed": len(sources)}

    return get_runner().submit("reindex", expert_name, work)


# --------------------------------------------------------------------------------------
# Query
# --------------------------------------------------------------------------------------
def query(
    question: str,
    *,
    top_k: int | None = None,
    experts: list[str] | None = None,
    synthesize: bool = False,
) -> RetrievalResult:
    return answer_question(
        question,
        settings=get_settings(),
        registry=get_registry(),
        kb=get_kb(),
        bedrock=get_bedrock(),
        top_k=top_k,
        experts=experts,
        synthesize_answer=synthesize,
    )


def health() -> dict:
    s = get_settings()
    return {
        "qdrant": get_kb().check(),
        "region": s.aws_region,
        "rerank_region": s.region_for("rerank"),
        "embed_model": s.embed_model_id,
        "rerank_model": s.rerank_model_id,
        "experts": len(list_experts()),
    }
