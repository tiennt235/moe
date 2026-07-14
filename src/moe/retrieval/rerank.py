"""Cross-expert reranking (Cohere Rerank 3.5 on Bedrock) + neighbor expansion, producing
the final cited passages. Reranking is the precision stage; neighbor expansion restores
context the chunker split apart."""

from __future__ import annotations

from moe.clients.bedrock import BedrockClient
from moe.clients.qdrant import QdrantKB
from moe.config import Settings
from moe.models import Citation, Expert, Passage


def _format_location(payload: dict) -> str | None:
    ps, pe = payload.get("page_start"), payload.get("page_end")
    if ps and pe and ps != pe:
        return f"pp. {ps}–{pe}"
    if ps:
        return f"p. {ps}"
    heading = payload.get("heading_path") or []
    return " › ".join(heading) if heading else None


def _expand(kb: QdrantKB, collection: str, payload: dict, window: int) -> str:
    """Attach adjacent chunks (same source, neighboring index) around the survivor."""
    if window <= 0:
        return payload["text"]
    try:
        neighbors = kb.get_neighbors(
            collection, payload["source_id"], payload["chunk_index"], window
        )
    except Exception:  # noqa: BLE001
        return payload["text"]
    if not neighbors:
        return payload["text"]
    return "\n".join(n["payload"]["text"] for n in neighbors)


def rerank_and_build(
    question: str,
    candidates: list[dict],
    experts_by_name: dict[str, Expert],
    kb: QdrantKB,
    bedrock: BedrockClient,
    settings: Settings,
    top_k: int,
) -> list[Passage]:
    if not candidates:
        return []

    docs = [c["payload"]["text"] for c in candidates]
    try:
        ranking = bedrock.rerank(question, docs, top_n=top_k)
    except Exception:  # noqa: BLE001 — degrade to fused order if rerank is unavailable
        ranking = [(i, candidates[i]["score"]) for i in range(len(candidates))]
        ranking.sort(key=lambda x: x[1], reverse=True)
        ranking = ranking[:top_k]

    passages: list[Passage] = []
    for idx, rscore in ranking:
        cand = candidates[idx]
        payload = cand["payload"]
        expert = experts_by_name.get(cand["expert"])
        collection = expert.collection if expert else f"expert_{cand['expert']}"
        text = _expand(kb, collection, payload, settings.neighbor_window)
        passages.append(
            Passage(
                text=text,
                expert=cand["expert"],
                chunk_id=str(cand["id"]),
                heading_path=payload.get("heading_path") or [],
                score=cand.get("score", 0.0),
                rerank_score=rscore,
                citation=Citation(
                    title=payload.get("title") or "(untitled)",
                    author=payload.get("author"),
                    source_id=payload["source_id"],
                    url=payload.get("url"),
                    location=_format_location(payload),
                ),
            )
        )
    return passages
