"""Runtime configuration.

All settings come from environment variables (optionally via a local ``.env``). Nothing
here holds durable state — the SQLite registry (see :mod:`moe.store.db`) does that.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Bedrock regions that serve Cohere Rerank 3.5. The active AWS_REGION must be one of these
# (unless BEDROCK_RERANK_REGION overrides it) or reranking will fail at request time.
RERANK_REGIONS = frozenset({"us-west-2", "ca-central-1", "eu-central-1", "ap-northeast-1"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MOE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Qdrant Cloud ---------------------------------------------------------------
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_prefer_grpc: bool = False

    # --- AWS Bedrock ----------------------------------------------------------------
    aws_region: str = Field(default="us-west-2", alias="AWS_REGION")
    # Per-service region overrides (fall back to aws_region when unset).
    bedrock_embed_region: str | None = Field(default=None, alias="BEDROCK_EMBED_REGION")
    bedrock_rerank_region: str | None = Field(default=None, alias="BEDROCK_RERANK_REGION")
    bedrock_llm_region: str | None = Field(default=None, alias="BEDROCK_LLM_REGION")

    # Embed v4 requires a cross-region inference profile (bare model id has no on-demand
    # throughput). Rerank is called via the Rerank API with a bare model ARN, so it stays
    # unqualified.
    embed_model_id: str = "us.cohere.embed-v4:0"
    rerank_model_id: str = "cohere.rerank-v3-5:0"
    # Used for contextual-retrieval context generation + optional answer synthesis. Set
    # MOE_LLM_MODEL_ID to a Haiku profile to cut contextualization cost on large corpora.
    llm_model_id: str = "us.anthropic.claude-sonnet-5"

    embed_dim: int = 1536  # Cohere embed-v4 configurable output dimension

    # --- Local state ----------------------------------------------------------------
    db_path: Path = Field(default=Path("moe.db"), alias="MOE_DB_PATH")
    materials_dir: Path = Field(default=Path("materials"), alias="MATERIALS_DIR")

    # --- Dashboard ------------------------------------------------------------------
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8848

    # --- Chunking defaults (overridable per-expert) ---------------------------------
    chunk_target_tokens: int = 512
    chunk_min_tokens: int = 300
    chunk_max_tokens: int = 800
    chunk_overlap: float = 0.15
    contextual_retrieval: bool = True  # Anthropic contextual retrieval on by default

    # --- Retrieval tunables ---------------------------------------------------------
    top_k: int = 8
    dense_candidates: int = 60
    sparse_candidates: int = 60
    rerank_pool: int = 40
    route_threshold: float = 0.30  # min cosine to a routing profile to select an expert
    route_fallback_k: int = 2  # experts to query if none pass the threshold
    neighbor_window: int = 1  # adjacent chunks attached to each survivor

    def region_for(self, service: str) -> str:
        """Resolve the effective AWS region for a Bedrock service."""
        override = {
            "embed": self.bedrock_embed_region,
            "rerank": self.bedrock_rerank_region,
            "llm": self.bedrock_llm_region,
        }.get(service)
        return override or self.aws_region

    @property
    def bm25_model(self) -> str:
        return "Qdrant/bm25"


@lru_cache
def get_settings() -> Settings:
    return Settings()
