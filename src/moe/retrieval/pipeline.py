"""Query-time orchestration: embed → route → hybrid search → rerank → (optional) synthesize.
This is the read path shared by the MCP server and the dashboard Playground."""

from __future__ import annotations

from moe.clients.bedrock import BedrockClient
from moe.clients.qdrant import QdrantKB
from moe.config import Settings
from moe.models import RetrievalResult
from moe.retrieval.rerank import rerank_and_build
from moe.retrieval.router import route
from moe.retrieval.search import search_experts
from moe.retrieval.synthesize import synthesize
from moe.store.db import Registry


def answer_question(
    question: str,
    *,
    settings: Settings,
    registry: Registry,
    kb: QdrantKB,
    bedrock: BedrockClient,
    top_k: int | None = None,
    experts: list[str] | None = None,
    synthesize_answer: bool = False,
) -> RetrievalResult:
    top_k = top_k or settings.top_k

    q_dense = bedrock.embed_one(question, input_type="search_query")
    q_sparse = kb.sparse_query(question)

    selected_names = route(q_dense, registry, settings, override=experts)
    experts_by_name = {e.name: e for e in registry.list_experts()}
    selected = [experts_by_name[n] for n in selected_names if n in experts_by_name]

    candidates = search_experts(kb, selected, q_dense, q_sparse, settings)
    passages = rerank_and_build(
        question, candidates, experts_by_name, kb, bedrock, settings, top_k
    )

    answer = synthesize(question, passages, bedrock) if synthesize_answer else None
    return RetrievalResult(
        question=question,
        experts_selected=selected_names,
        passages=passages,
        answer=answer,
    )
