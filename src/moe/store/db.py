"""SQLite registry — the local source of truth for experts, sources, jobs, and routing
profiles. Authoritative for a machine's operations but rebuildable from Qdrant +
``experts.yaml`` (see :mod:`moe.portability`)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from moe.config import get_settings
from moe.models import (
    ChunkParams,
    Expert,
    Job,
    JobStatus,
    Source,
    SourceFormat,
    SourceStatus,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experts (
    name           TEXT PRIMARY KEY,
    description    TEXT NOT NULL,
    chunk_json     TEXT NOT NULL DEFAULT '{}',
    n_sources      INTEGER NOT NULL DEFAULT 0,
    n_chunks       INTEGER NOT NULL DEFAULT 0,
    updated_at     TEXT,
    centroid_json  TEXT,           -- JSON list[float] or NULL
    desc_emb_json  TEXT            -- JSON list[float] or NULL
);
CREATE TABLE IF NOT EXISTS sources (
    source_id      TEXT PRIMARY KEY,
    expert         TEXT NOT NULL REFERENCES experts(name) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    author         TEXT,
    fmt            TEXT NOT NULL,
    origin         TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    n_chunks       INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'pending',
    error          TEXT,
    added_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_sources_expert ON sources(expert);
CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    expert         TEXT,
    status         TEXT NOT NULL DEFAULT 'queued',
    stage          TEXT NOT NULL DEFAULT '',
    progress       REAL NOT NULL DEFAULT 0,
    error          TEXT,
    created_at     TEXT,
    updated_at     TEXT,
    meta_json      TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Registry:
    """Thread-safe wrapper over a single SQLite connection.

    A process-wide lock serializes writes; SQLite is used in WAL mode so dashboard reads
    don't block behind ingest writes.
    """

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- experts ---------------------------------------------------------------------
    def upsert_expert(self, expert: Expert) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO experts (name, description, chunk_json, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     description=excluded.description,
                     chunk_json=excluded.chunk_json,
                     updated_at=excluded.updated_at""",
                (
                    expert.name,
                    expert.description,
                    expert.chunk.model_dump_json(exclude_none=True),
                    _now(),
                ),
            )
            self._conn.commit()

    def get_expert(self, name: str) -> Expert | None:
        row = self._conn.execute("SELECT * FROM experts WHERE name=?", (name,)).fetchone()
        return self._row_to_expert(row) if row else None

    def list_experts(self) -> list[Expert]:
        rows = self._conn.execute("SELECT * FROM experts ORDER BY name").fetchall()
        return [self._row_to_expert(r) for r in rows]

    def delete_expert(self, name: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM experts WHERE name=?", (name,))
            self._conn.commit()

    def set_routing_profile(
        self, name: str, centroid: list[float] | None, desc_embedding: list[float] | None
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE experts SET centroid_json=?, desc_emb_json=?, updated_at=? WHERE name=?",
                (
                    json.dumps(centroid) if centroid is not None else None,
                    json.dumps(desc_embedding) if desc_embedding is not None else None,
                    _now(),
                    name,
                ),
            )
            self._conn.commit()

    def get_routing_profiles(self) -> dict[str, dict[str, list[float] | None]]:
        rows = self._conn.execute(
            "SELECT name, centroid_json, desc_emb_json FROM experts"
        ).fetchall()
        out: dict[str, dict[str, list[float] | None]] = {}
        for r in rows:
            out[r["name"]] = {
                "centroid": json.loads(r["centroid_json"]) if r["centroid_json"] else None,
                "desc_embedding": json.loads(r["desc_emb_json"]) if r["desc_emb_json"] else None,
            }
        return out

    def refresh_counts(self, name: str) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS s, COALESCE(SUM(n_chunks),0) AS c "
                "FROM sources WHERE expert=?",
                (name,),
            ).fetchone()
            self._conn.execute(
                "UPDATE experts SET n_sources=?, n_chunks=?, updated_at=? WHERE name=?",
                (row["s"], row["c"], _now(), name),
            )
            self._conn.commit()

    # -- sources ---------------------------------------------------------------------
    def upsert_source(self, source: Source) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO sources
                     (source_id, expert, title, author, fmt, origin, content_hash,
                      n_chunks, status, error, added_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_id) DO UPDATE SET
                     title=excluded.title, author=excluded.author, fmt=excluded.fmt,
                     origin=excluded.origin, content_hash=excluded.content_hash,
                     n_chunks=excluded.n_chunks, status=excluded.status,
                     error=excluded.error""",
                (
                    source.source_id,
                    source.expert,
                    source.title,
                    source.author,
                    source.fmt.value,
                    source.origin,
                    source.content_hash,
                    source.n_chunks,
                    source.status.value,
                    source.error,
                    source.added_at.isoformat() if source.added_at else _now(),
                ),
            )
            self._conn.commit()
        self.refresh_counts(source.expert)

    def get_source(self, source_id: str) -> Source | None:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE source_id=?", (source_id,)
        ).fetchone()
        return self._row_to_source(row) if row else None

    def list_sources(self, expert: str) -> list[Source]:
        rows = self._conn.execute(
            "SELECT * FROM sources WHERE expert=? ORDER BY added_at", (expert,)
        ).fetchall()
        return [self._row_to_source(r) for r in rows]

    def set_source_status(
        self, source_id: str, status: SourceStatus, error: str | None = None,
        n_chunks: int | None = None,
    ) -> None:
        with self._lock:
            if n_chunks is None:
                self._conn.execute(
                    "UPDATE sources SET status=?, error=? WHERE source_id=?",
                    (status.value, error, source_id),
                )
            else:
                self._conn.execute(
                    "UPDATE sources SET status=?, error=?, n_chunks=? WHERE source_id=?",
                    (status.value, error, n_chunks, source_id),
                )
            self._conn.commit()

    def delete_source(self, source_id: str) -> None:
        src = self.get_source(source_id)
        with self._lock:
            self._conn.execute("DELETE FROM sources WHERE source_id=?", (source_id,))
            self._conn.commit()
        if src:
            self.refresh_counts(src.expert)

    # -- jobs ------------------------------------------------------------------------
    def create_job(self, job: Job) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO jobs
                     (id, kind, expert, status, stage, progress, error,
                      created_at, updated_at, meta_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    job.id,
                    job.kind,
                    job.expert,
                    job.status.value,
                    job.stage,
                    job.progress,
                    job.error,
                    _now(),
                    _now(),
                    json.dumps(job.meta),
                ),
            )
            self._conn.commit()

    def update_job(self, job_id: str, **fields) -> None:
        if not fields:
            return
        if "status" in fields and isinstance(fields["status"], JobStatus):
            fields["status"] = fields["status"].value
        if "meta" in fields:
            fields["meta_json"] = json.dumps(fields.pop("meta"))
        fields["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self._conn.execute(
                f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id)
            )
            self._conn.commit()

    def get_job(self, job_id: str) -> Job | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[Job]:
        rows = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    # -- row mappers -----------------------------------------------------------------
    @staticmethod
    def _row_to_expert(row: sqlite3.Row) -> Expert:
        return Expert(
            name=row["name"],
            description=row["description"],
            chunk=ChunkParams(**json.loads(row["chunk_json"] or "{}")),
            n_sources=row["n_sources"],
            n_chunks=row["n_chunks"],
            updated_at=_parse_dt(row["updated_at"]),
        )

    @staticmethod
    def _row_to_source(row: sqlite3.Row) -> Source:
        return Source(
            source_id=row["source_id"],
            expert=row["expert"],
            title=row["title"],
            author=row["author"],
            fmt=SourceFormat(row["fmt"]),
            origin=row["origin"],
            content_hash=row["content_hash"],
            n_chunks=row["n_chunks"],
            status=SourceStatus(row["status"]),
            error=row["error"],
            added_at=_parse_dt(row["added_at"]),
        )

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            kind=row["kind"],
            expert=row["expert"],
            status=JobStatus(row["status"]),
            stage=row["stage"],
            progress=row["progress"],
            error=row["error"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            meta=json.loads(row["meta_json"] or "{}"),
        )


@lru_cache
def get_registry() -> Registry:
    return Registry(get_settings().db_path)
