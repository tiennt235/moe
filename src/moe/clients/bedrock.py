"""AWS Bedrock wrappers: Cohere Embed v4 (embeddings), Cohere Rerank 3.5 (reranking),
and Claude (contextual-retrieval context + optional answer synthesis).

Boto3 clients are created lazily and cached so importing this module never requires AWS
credentials (keeps ``moe-ingest doctor`` and unit tests cheap)."""

from __future__ import annotations

import json
from functools import lru_cache

from moe.config import Settings, get_settings


class BedrockError(RuntimeError):
    pass


class BedrockClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._runtime: dict[str, object] = {}  # region -> bedrock-runtime client
        self._agent: dict[str, object] = {}  # region -> bedrock-agent-runtime client

    # -- boto3 client cache ----------------------------------------------------------
    def _rt(self, region: str):
        if region not in self._runtime:
            import boto3

            self._runtime[region] = boto3.client("bedrock-runtime", region_name=region)
        return self._runtime[region]

    def _ar(self, region: str):
        if region not in self._agent:
            import boto3

            self._agent[region] = boto3.client(
                "bedrock-agent-runtime", region_name=region
            )
        return self._agent[region]

    # -- embeddings ------------------------------------------------------------------
    def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        """Embed texts with Cohere Embed v4.

        ``input_type`` is ``"search_document"`` at ingest and ``"search_query"`` at query
        time — Cohere uses it to asymmetrically optimize the two sides of retrieval.
        """
        if not texts:
            return []
        region = self.s.region_for("embed")
        body = {
            "texts": texts,
            "input_type": input_type,
            "output_dimension": self.s.embed_dim,
            "embedding_types": ["float"],
        }
        resp = self._rt(region).invoke_model(
            modelId=self.s.embed_model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
        payload = json.loads(resp["body"].read())
        embs = payload.get("embeddings")
        # Cohere returns either {"embeddings": {"float": [...]}} or {"embeddings": [...]}
        if isinstance(embs, dict):
            embs = embs.get("float", [])
        if not embs or len(embs) != len(texts):
            raise BedrockError(f"embed returned {len(embs or [])} vectors for {len(texts)} texts")
        return embs

    def embed_one(self, text: str, *, input_type: str) -> list[float]:
        return self.embed([text], input_type=input_type)[0]

    # -- rerank ----------------------------------------------------------------------
    def rerank(self, query: str, documents: list[str], *, top_n: int) -> list[tuple[int, float]]:
        """Return [(original_index, relevance_score)] sorted best-first via Cohere Rerank 3.5."""
        if not documents:
            return []
        region = self.s.region_for("rerank")
        model_arn = f"arn:aws:bedrock:{region}::foundation-model/{self.s.rerank_model_id}"
        resp = self._ar(region).rerank(
            queries=[{"type": "TEXT", "textQuery": {"text": query}}],
            sources=[
                {
                    "type": "INLINE",
                    "inlineDocumentSource": {
                        "type": "TEXT",
                        "textDocument": {"text": doc},
                    },
                }
                for doc in documents
            ],
            rerankingConfiguration={
                "type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {
                    "numberOfResults": min(top_n, len(documents)),
                    "modelConfiguration": {"modelArn": model_arn},
                },
            },
        )
        return [(r["index"], r["relevanceScore"]) for r in resp["results"]]

    # -- LLM (Claude via Converse) ---------------------------------------------------
    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 512) -> str:
        region = self.s.region_for("llm")
        kwargs: dict = {
            "modelId": self.s.llm_model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            # Note: newer Claude models (Sonnet 5+) reject `temperature` in Converse.
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if system:
            kwargs["system"] = [{"text": system}]
        resp = self._rt(region).converse(**kwargs)
        return resp["output"]["message"]["content"][0]["text"].strip()

    # -- diagnostics -----------------------------------------------------------------
    def check(self) -> dict[str, str]:
        """Preflight used by ``moe-ingest doctor``. Never raises — reports per-service."""
        out: dict[str, str] = {}
        try:
            self.embed_one("ping", input_type="search_query")
            out["embed"] = "ok"
        except Exception as e:  # noqa: BLE001
            out["embed"] = f"error: {e}"
        try:
            self.rerank("ping", ["pong"], top_n=1)
            out["rerank"] = "ok"
        except Exception as e:  # noqa: BLE001
            out["rerank"] = f"error: {e}"
        return out


@lru_cache
def get_bedrock() -> BedrockClient:
    return BedrockClient(get_settings())
