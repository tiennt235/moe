"""Qdrant Cloud wrapper: collection lifecycle, hybrid upsert (dense + BM25 sparse),
hybrid Query-API search with RRF fusion, neighbor lookup, and snapshot import/export.

Sparse (BM25) vectors are produced locally with FastEmbed — no model API call needed."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from moe.config import Settings, get_settings
from moe.models import Chunk

DENSE = "dense"
SPARSE = "sparse"


class QdrantKB:
    def __init__(self, settings: Settings):
        self.s = settings
        from qdrant_client import QdrantClient

        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            prefer_grpc=settings.qdrant_prefer_grpc,
        )
        self._bm25 = None  # lazy FastEmbed model

    # -- sparse embedding ------------------------------------------------------------
    def _bm25_model(self):
        if self._bm25 is None:
            from fastembed import SparseTextEmbedding

            self._bm25 = SparseTextEmbedding(model_name=self.s.bm25_model)
        return self._bm25

    def _to_sparse(self, sparse_emb) -> Any:
        from qdrant_client import models

        return models.SparseVector(
            indices=sparse_emb.indices.tolist(), values=sparse_emb.values.tolist()
        )

    def sparse_documents(self, texts: list[str]) -> list[Any]:
        return [self._to_sparse(e) for e in self._bm25_model().embed(texts)]

    def sparse_query(self, text: str) -> Any:
        return self._to_sparse(next(iter(self._bm25_model().query_embed(text))))

    # -- collection lifecycle --------------------------------------------------------
    def ensure_collection(self, name: str) -> None:
        from qdrant_client import models

        if self.client.collection_exists(name):
            return
        self.client.create_collection(
            collection_name=name,
            vectors_config={
                DENSE: models.VectorParams(
                    size=self.s.embed_dim, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        for field, schema in (
            ("source_id", models.PayloadSchemaType.KEYWORD),
            ("chunk_index", models.PayloadSchemaType.INTEGER),
        ):
            self.client.create_payload_index(name, field_name=field, field_schema=schema)

    def delete_collection(self, name: str) -> None:
        if self.client.collection_exists(name):
            self.client.delete_collection(name)

    def collection_exists(self, name: str) -> bool:
        return self.client.collection_exists(name)

    def list_expert_collections(self) -> list[str]:
        return [
            c.name
            for c in self.client.get_collections().collections
            if c.name.startswith("expert_")
        ]

    def count(self, name: str) -> int:
        return self.client.count(name, exact=True).count

    # -- upsert ----------------------------------------------------------------------
    def upsert_chunks(
        self, collection: str, expert: str, doc_meta: dict, chunks: list[Chunk],
        dense_vectors: list[list[float]],
    ) -> None:
        from qdrant_client import models

        sparse = self.sparse_documents([c.embed_text for c in chunks])
        points = []
        for chunk, dvec, svec in zip(chunks, dense_vectors, sparse, strict=True):
            points.append(
                models.PointStruct(
                    id=chunk.id,
                    vector={DENSE: dvec, SPARSE: svec},
                    payload={
                        "expert": expert,
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        "heading_path": chunk.heading_path,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "title": doc_meta.get("title"),
                        "author": doc_meta.get("author"),
                        "url": doc_meta.get("url"),
                    },
                )
            )
        # upsert in batches to stay within request-size limits
        for i in range(0, len(points), 128):
            self.client.upsert(collection, points=points[i : i + 128], wait=True)

    def delete_by_source(self, collection: str, source_id: str) -> None:
        from qdrant_client import models

        self.client.delete(
            collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_id", match=models.MatchValue(value=source_id)
                        )
                    ]
                )
            ),
            wait=True,
        )

    # -- search ----------------------------------------------------------------------
    def hybrid_search(
        self, collection: str, dense_vec: list[float], sparse_vec: Any, *, limit: int
    ) -> list[dict]:
        from qdrant_client import models

        result = self.client.query_points(
            collection_name=collection,
            prefetch=[
                models.Prefetch(
                    query=dense_vec, using=DENSE, limit=self.s.dense_candidates
                ),
                models.Prefetch(
                    query=sparse_vec, using=SPARSE, limit=self.s.sparse_candidates
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return [{"id": p.id, "score": p.score, "payload": p.payload} for p in result.points]

    def get_neighbors(
        self, collection: str, source_id: str, chunk_index: int, window: int
    ) -> list[dict]:
        from qdrant_client import models

        points, _ = self.client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_id", match=models.MatchValue(value=source_id)
                    ),
                    models.FieldCondition(
                        key="chunk_index",
                        range=models.Range(
                            gte=chunk_index - window, lte=chunk_index + window
                        ),
                    ),
                ]
            ),
            with_payload=True,
            limit=2 * window + 1,
        )
        return sorted(
            ({"id": p.id, "payload": p.payload} for p in points),
            key=lambda x: x["payload"]["chunk_index"],
        )

    def compute_centroid(self, collection: str, sample: int = 4096) -> list[float] | None:
        """Mean of dense vectors — the corpus half of the routing profile. Sampled for
        large collections; rebuildable at any time from Qdrant alone."""
        points, _ = self.client.scroll(
            collection_name=collection,
            with_vectors=[DENSE],
            with_payload=False,
            limit=sample,
        )
        vecs = [p.vector[DENSE] for p in points if p.vector and DENSE in p.vector]
        if not vecs:
            return None
        dim = len(vecs[0])
        acc = [0.0] * dim
        for v in vecs:
            for i, x in enumerate(v):
                acc[i] += x
        return [x / len(vecs) for x in acc]

    def source_index(self, collection: str) -> dict[str, dict]:
        """One scroll over the collection → {source_id: {title, author, url, fmt, count}}.
        Used by ``sync`` to rebuild the registry's source records from Qdrant alone."""
        index: dict[str, dict] = {}
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=collection,
                with_payload=["source_id", "title", "author", "url"],
                with_vectors=False,
                limit=256,
                offset=offset,
            )
            for p in points:
                pl = p.payload or {}
                sid = pl.get("source_id")
                if not sid:
                    continue
                rec = index.setdefault(
                    sid,
                    {"title": pl.get("title"), "author": pl.get("author"),
                     "url": pl.get("url"), "count": 0},
                )
                rec["count"] += 1
            if offset is None:
                break
        return index

    # -- snapshots (portability) -----------------------------------------------------
    def create_snapshot(self, collection: str) -> str:
        return self.client.create_snapshot(collection_name=collection).name

    def download_snapshot(self, collection: str, snapshot_name: str, dest_path: str) -> None:
        # qdrant-client has no download helper; stream it over the REST API instead.
        import httpx

        headers = {"api-key": self.s.qdrant_api_key} if self.s.qdrant_api_key else {}
        url = f"{self.s.qdrant_url.rstrip('/')}/collections/{collection}/snapshots/{snapshot_name}"
        with httpx.stream("GET", url, headers=headers, timeout=600) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as fh:
                for chunk in resp.iter_bytes():
                    fh.write(chunk)

    def check(self) -> str:
        try:
            self.client.get_collections()
            return "ok"
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"


@lru_cache
def get_kb() -> QdrantKB:
    return QdrantKB(get_settings())
