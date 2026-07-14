"""``moe-mcp`` — the read-only MCP server.

Exposes the expert team to MCP clients (Claude Code / Desktop). A single ``ask_experts``
tool auto-routes, retrieves, reranks, and returns cited passages; the tool contract
requires the caller to cite the returned sources."""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from moe import service

mcp = FastMCP("moe")


@mcp.tool()
def ask_experts(
    question: str,
    top_k: int = 8,
    experts: list[str] | None = None,
    synthesize: bool = False,
) -> dict:
    """Ask the mixture of domain experts a question.

    The server routes the question to the most relevant expert knowledge base(s), runs
    hybrid retrieval + reranking, and returns the best-supported passages. EACH passage
    includes a citation (title, author, location). You MUST cite these sources in your
    answer using their bracket numbers, and answer only from them.

    Args:
        question: The natural-language question.
        top_k: Max passages to return (default 8).
        experts: Optional list of expert names to force; omit to auto-route.
        synthesize: If true, the server also returns a grounded, cited answer string.
    """
    result = service.query(
        question, top_k=top_k, experts=experts, synthesize=synthesize
    )
    return {
        "question": result.question,
        "experts_selected": result.experts_selected,
        "answer": result.answer,
        "passages": [
            {
                "n": i + 1,
                "text": p.text,
                "expert": p.expert,
                "title": p.citation.title,
                "author": p.citation.author,
                "location": p.citation.location,
                "url": p.citation.url,
                "source_id": p.citation.source_id,
                "rerank_score": p.rerank_score,
            }
            for i, p in enumerate(result.passages)
        ],
    }


@mcp.tool()
def list_experts() -> list[dict]:
    """List the available domain experts and how much each one knows."""
    return [
        {
            "name": e.name,
            "description": e.description,
            "n_sources": e.n_sources,
            "n_chunks": e.n_chunks,
        }
        for e in service.list_experts()
    ]


@mcp.tool()
def get_source(source_id: str) -> dict:
    """Fetch metadata about a cited source (to expand or verify a citation)."""
    from moe.store.db import get_registry

    src = get_registry().get_source(source_id)
    if not src:
        return {"error": "no such source"}
    return {
        "source_id": src.source_id,
        "expert": src.expert,
        "title": src.title,
        "author": src.author,
        "format": src.fmt.value,
        "origin": src.origin,
        "n_chunks": src.n_chunks,
        "status": src.status.value,
    }


@mcp.resource("moe://experts")
def experts_resource() -> str:
    """Browsable list of experts."""
    lines = [f"- {e.name}: {e.description} ({e.n_chunks} chunks)" for e in service.list_experts()]
    return "\n".join(lines) or "(no experts yet)"


def main() -> None:
    parser = argparse.ArgumentParser(description="moe MCP server")
    parser.add_argument(
        "--http", action="store_true", help="serve over streamable-HTTP instead of stdio"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8849)
    args = parser.parse_args()

    if args.http:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()  # stdio (default for local MCP clients)


if __name__ == "__main__":
    main()
