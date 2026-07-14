"""Optional server-side answer synthesis. Composes a grounded answer from the retrieved
passages with inline ``[n]`` citation markers mapped to the passage list. Default behavior
is to return passages and let the calling LLM answer; this is opt-in via ``synthesize=True``."""

from __future__ import annotations

from moe.clients.bedrock import BedrockClient
from moe.models import Passage

_SYSTEM = (
    "You answer strictly from the provided sources. Cite every claim with inline [n] markers "
    "that refer to the numbered sources. If the sources do not contain the answer, say so. "
    "Do not use outside knowledge."
)


def synthesize(question: str, passages: list[Passage], bedrock: BedrockClient) -> str:
    if not passages:
        return "No relevant sources were found to answer this question."
    blocks = []
    for i, p in enumerate(passages, 1):
        loc = f" — {p.citation.location}" if p.citation.location else ""
        blocks.append(f"[{i}] {p.citation.title}{loc}\n{p.text}")
    sources = "\n\n".join(blocks)
    prompt = (
        f"Question: {question}\n\n"
        f"Sources:\n{sources}\n\n"
        "Answer the question using only these sources, with inline [n] citations."
    )
    return bedrock.complete(prompt, system=_SYSTEM, max_tokens=1024)
