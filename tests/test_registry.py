import tempfile
from datetime import datetime, timezone
from pathlib import Path

from moe.models import (
    Expert,
    Job,
    JobStatus,
    Source,
    SourceFormat,
    SourceStatus,
    content_hash,
    make_chunk_id,
    make_source_id,
    slugify,
)
from moe.store.db import Registry


def _reg():
    return Registry(Path(tempfile.mkdtemp()) / "moe.db")


def test_id_helpers():
    h = content_hash(b"hello")
    sid = make_source_id("a.pdf", h)
    assert make_source_id("a.pdf", h) == sid  # deterministic
    assert make_chunk_id(sid, 3) == make_chunk_id(sid, 3)
    assert make_chunk_id(sid, 3) != make_chunk_id(sid, 4)
    assert slugify("Roman History!") == "roman_history"


def test_expert_and_source_counts():
    reg = _reg()
    reg.upsert_expert(Expert(name="hist", description="history"))
    sid = make_source_id("g.pdf", content_hash(b"x"))
    reg.upsert_source(
        Source(
            source_id=sid, expert="hist", title="Gibbon", fmt=SourceFormat.pdf,
            origin="g.pdf", content_hash="x", n_chunks=42,
            status=SourceStatus.ready, added_at=datetime.now(timezone.utc),
        )
    )
    e = reg.get_expert("hist")
    assert e.n_sources == 1 and e.n_chunks == 42
    reg.delete_source(sid)
    assert reg.get_expert("hist").n_sources == 0


def test_job_lifecycle():
    reg = _reg()
    reg.create_job(Job(id="j1", kind="ingest", expert="hist"))
    reg.update_job("j1", status=JobStatus.running, stage="embedding", progress=0.5)
    j = reg.get_job("j1")
    assert j.status == JobStatus.running and j.progress == 0.5
    reg.update_job("j1", status=JobStatus.done, progress=1.0)
    assert reg.get_job("j1").status == JobStatus.done


def test_routing_profile_roundtrip():
    reg = _reg()
    reg.upsert_expert(Expert(name="x", description="d"))
    reg.set_routing_profile("x", [0.1, 0.2], [0.3, 0.4])
    prof = reg.get_routing_profiles()["x"]
    assert prof["centroid"] == [0.1, 0.2]
    assert prof["desc_embedding"] == [0.3, 0.4]
