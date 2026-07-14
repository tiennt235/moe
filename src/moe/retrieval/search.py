"""Per-expert hybrid retrieval (dense + BM25 sparse, RRF-fused via Qdrant's Query API)."""

from __future__ import annotations

from typing import Any

from moe.clients.qdrant import QdrantKB
from moe.config import Settings
from moe.models import Expert


def search_experts(
    kb: QdrantKB,
    experts: list[Expert],
    q_dense: list[float],
    q_sparse: Any,
    settings: Settings,
) -> list[dict]:
    """Return a merged candidate pool across the selected experts, each candidate tagged
    with its expert. Missing/empty collections are skipped."""
    pool: list[dict] = []
    for expert in experts:
        if not kb.collection_exists(expert.collection):
            continue
        hits = kb.hybrid_search(
            expert.collection, q_dense, q_sparse, limit=settings.rerank_pool
        )
        for h in hits:
            h["expert"] = expert.name
            pool.append(h)
    return pool
