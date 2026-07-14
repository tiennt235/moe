"""Query router — the "mixture" in mixture-of-experts. Compares the query embedding to each
expert's routing profile (corpus centroid + description embedding) and selects the experts
to query. Multi-expert allowed; falls back to the top-N when nothing clears the threshold."""

from __future__ import annotations

import math

from moe.config import Settings
from moe.store.db import Registry


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def route(
    q_dense: list[float],
    registry: Registry,
    settings: Settings,
    override: list[str] | None = None,
) -> list[str]:
    experts = registry.list_experts()
    if not experts:
        return []
    if override:
        valid = {e.name for e in experts}
        picked = [name for name in override if name in valid]
        if picked:
            return picked
    if len(experts) == 1:
        return [experts[0].name]

    profiles = registry.get_routing_profiles()
    scored: list[tuple[str, float]] = []
    for e in experts:
        prof = profiles.get(e.name, {})
        sims = [
            cosine(q_dense, vec)
            for vec in (prof.get("centroid"), prof.get("desc_embedding"))
            if vec
        ]
        scored.append((e.name, max(sims) if sims else 0.0))

    scored.sort(key=lambda x: x[1], reverse=True)
    selected = [name for name, score in scored if score >= settings.route_threshold]
    if not selected:
        selected = [name for name, _ in scored[: settings.route_fallback_k]]
    return selected
