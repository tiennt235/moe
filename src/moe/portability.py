"""Delivery & portability: export/import an expert team bundle, and rebuild the local
registry from Qdrant (the same-cluster fast path).

State model:
  * Qdrant Cloud  — the vectors (the real KB); shared when machines use the same cluster.
  * SQLite registry — rebuildable from Qdrant + experts.yaml.
  * materials/     — raw files; only needed to re-ingest.

A bundle is a gzip-compressed tar containing experts.yaml, registry.json, manifest.json,
and (optionally) materials/ and per-collection Qdrant snapshots."""

from __future__ import annotations

import json
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from moe import __version__
from moe.clients.qdrant import get_kb
from moe.config import get_settings
from moe.ingest.pipeline import refresh_routing_profile
from moe.models import ChunkParams, Expert, Source, SourceFormat, SourceStatus
from moe.store.db import get_registry


# --------------------------------------------------------------------------------------
# experts.yaml (declarative import/export)
# --------------------------------------------------------------------------------------
def dump_experts_yaml(experts: list[str] | None = None) -> str:
    reg = get_registry()
    out = {"experts": []}
    for e in reg.list_experts():
        if experts and e.name not in experts:
            continue
        out["experts"].append(
            {
                "name": e.name,
                "description": e.description,
                "chunk": e.chunk.model_dump(exclude_none=True),
                "sources": [
                    {"origin": s.origin, "title": s.title, "content_hash": s.content_hash}
                    for s in reg.list_sources(e.name)
                ],
            }
        )
    return yaml.safe_dump(out, sort_keys=False)


# --------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------
def export_team(
    out_path: str,
    *,
    experts: list[str] | None = None,
    with_materials: bool = False,
    with_snapshots: bool = False,
) -> str:
    s = get_settings()
    reg = get_registry()
    kb = get_kb()
    selected = [e for e in reg.list_experts() if not experts or e.name in experts]

    registry_blob = {
        "experts": [
            {
                "expert": e.model_dump(mode="json"),
                "profile": reg.get_routing_profiles().get(e.name, {}),
                "sources": [x.model_dump(mode="json") for x in reg.list_sources(e.name)],
            }
            for e in selected
        ]
    }
    manifest = {
        "moe_version": __version__,
        "embed_model": s.embed_model_id,
        "embed_dim": s.embed_dim,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experts": [e.name for e in selected],
        "with_materials": with_materials,
        "with_snapshots": with_snapshots,
    }

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "team"
        root.mkdir()
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (root / "registry.json").write_text(json.dumps(registry_blob, indent=2))
        (root / "experts.yaml").write_text(dump_experts_yaml([e.name for e in selected]))

        if with_materials:
            for e in selected:
                src_dir = s.materials_dir / e.name
                if src_dir.exists():
                    _copytree(src_dir, root / "materials" / e.name)

        if with_snapshots:
            snap_dir = root / "snapshots"
            snap_dir.mkdir()
            for e in selected:
                if not kb.collection_exists(e.collection):
                    continue
                name = kb.create_snapshot(e.collection)
                kb.download_snapshot(
                    e.collection, name, str(snap_dir / f"{e.collection}.snapshot")
                )

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out, "w:gz") as tar:
            tar.add(root, arcname="team")
    return str(out_path)


# --------------------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------------------
def import_team(
    bundle_path: str,
    *,
    restore_snapshots: bool = False,
    reingest: bool = False,
    experts: list[str] | None = None,
) -> list[str]:
    s = get_settings()
    reg = get_registry()
    kb = get_kb()

    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(bundle_path, "r:*") as tar:
            tar.extractall(td)  # noqa: S202 — trusted, operator-provided bundle
        root = Path(td) / "team"
        manifest = json.loads((root / "manifest.json").read_text())
        registry_blob = json.loads((root / "registry.json").read_text())

        if restore_snapshots and manifest.get("embed_dim") != s.embed_dim:
            raise ValueError(
                f"snapshot embed_dim {manifest.get('embed_dim')} != local {s.embed_dim}; "
                "use --reingest instead"
            )

        imported: list[str] = []
        for entry in registry_blob["experts"]:
            edata = entry["expert"]
            if experts and edata["name"] not in experts:
                continue
            expert = Expert(
                name=edata["name"],
                description=edata["description"],
                chunk=ChunkParams(**(edata.get("chunk") or {})),
            )
            reg.upsert_expert(expert)
            kb.ensure_collection(expert.collection)

            # restore source records
            for sd in entry["sources"]:
                reg.upsert_source(
                    Source(
                        source_id=sd["source_id"],
                        expert=expert.name,
                        title=sd.get("title"),
                        author=sd.get("author"),
                        fmt=SourceFormat(sd["fmt"]),
                        origin=sd["origin"],
                        content_hash=sd["content_hash"],
                        n_chunks=sd.get("n_chunks", 0),
                        status=SourceStatus.ready,
                    )
                )

            if restore_snapshots:
                snap = root / "snapshots" / f"{expert.collection}.snapshot"
                if snap.exists():
                    _upload_snapshot(expert.collection, snap)
            elif reingest:
                _reingest_from_materials(root, expert)

            # profile: restore from bundle, or recompute if we restored/re-ingested vectors
            prof = entry.get("profile") or {}
            reg.set_routing_profile(
                expert.name, prof.get("centroid"), prof.get("desc_embedding")
            )
            imported.append(expert.name)

    return imported


def _reingest_from_materials(root: Path, expert: Expert) -> None:
    from moe.clients.bedrock import get_bedrock
    from moe.service import Item, ingest_items, store_material

    mdir = root / "materials" / expert.name
    if not mdir.exists():
        return
    items: list[Item] = []
    for f in sorted(mdir.rglob("*")):
        if f.is_file():
            data = f.read_bytes()
            dest = store_material(expert.name, f.name, data)  # copy into local materials/
            items.append(Item(origin=str(dest), data=data, title=f.stem))
    if items:
        _ = get_bedrock()  # ensure creds available; ingest_items uses it
        ingest_items(expert.name, items, force=True)


def _upload_snapshot(collection: str, snapshot: Path) -> None:
    """Upload a local snapshot file to the (possibly remote/cloud) Qdrant and recover into
    ``collection``. Works for Qdrant Cloud, unlike a server-local file path."""
    import httpx

    s = get_settings()
    headers = {"api-key": s.qdrant_api_key} if s.qdrant_api_key else {}
    url = f"{s.qdrant_url.rstrip('/')}/collections/{collection}/snapshots/upload?priority=snapshot"
    with snapshot.open("rb") as fh:
        resp = httpx.post(
            url, headers=headers, files={"snapshot": (snapshot.name, fh)}, timeout=600
        )
    resp.raise_for_status()


# --------------------------------------------------------------------------------------
# Sync from Qdrant (same-cluster fast path)
# --------------------------------------------------------------------------------------
def sync_from_qdrant() -> int:
    """Rebuild the local registry purely from the cloud collections (+ experts.yaml for
    descriptions/chunk params when present). Zero re-embedding."""
    s = get_settings()
    reg = get_registry()
    kb = get_kb()
    from moe.clients.bedrock import get_bedrock

    yaml_meta = _load_experts_yaml_meta()

    synced = 0
    for collection in kb.list_expert_collections():
        name = collection[len("expert_") :]
        meta = yaml_meta.get(name, {})
        expert = reg.get_expert(name) or Expert(
            name=name,
            description=meta.get("description", ""),
            chunk=ChunkParams(**(meta.get("chunk") or {})),
        )
        reg.upsert_expert(expert)

        for sid, info in kb.source_index(collection).items():
            reg.upsert_source(
                Source(
                    source_id=sid,
                    expert=name,
                    title=info.get("title"),
                    author=info.get("author"),
                    fmt=SourceFormat.text,  # unknown post-hoc; metadata only
                    origin=info.get("url") or sid,
                    content_hash=sid,
                    n_chunks=info.get("count", 0),
                    status=SourceStatus.ready,
                )
            )
        refresh_routing_profile(reg.get_expert(name), s, reg, kb, get_bedrock())
        synced += 1
    return synced


def _load_experts_yaml_meta(path: str = "experts.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    return {e["name"]: e for e in data.get("experts", [])}


def _copytree(src: Path, dst: Path) -> None:
    import shutil

    shutil.copytree(src, dst, dirs_exist_ok=True)
