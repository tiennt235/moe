"""FastAPI dashboard backend (``moe-dashboard``).

Exposes the service layer as a JSON API + SSE job stream, and serves the built React SPA
as static files from the same process. Ingestion always runs as a background job."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from moe import service
from moe.config import get_settings
from moe.models import ChunkParams, JobStatus
from moe.store.db import get_registry

app = FastAPI(title="moe-dashboard", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev; SPA is same-origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------------------
# Request bodies
# --------------------------------------------------------------------------------------
class CreateExpert(BaseModel):
    name: str
    description: str
    chunk: ChunkParams | None = None


class UpdateExpert(BaseModel):
    description: str | None = None
    chunk: ChunkParams | None = None


class AddUrls(BaseModel):
    urls: list[str]


class QueryBody(BaseModel):
    question: str
    top_k: int | None = None
    experts: list[str] | None = None
    synthesize: bool = False


# --------------------------------------------------------------------------------------
# Health & experts
# --------------------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return service.health()


@app.get("/api/experts")
def list_experts() -> list[dict]:
    return [e.model_dump(mode="json") for e in service.list_experts()]


@app.post("/api/experts")
def create_expert(body: CreateExpert) -> dict:
    try:
        expert = service.ensure_expert(body.name, body.description, body.chunk)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return expert.model_dump(mode="json")


@app.get("/api/experts/{name}")
def get_expert(name: str) -> dict:
    expert = get_registry().get_expert(name)
    if not expert:
        raise HTTPException(404, "no such expert")
    return {
        "expert": expert.model_dump(mode="json"),
        "sources": [s.model_dump(mode="json") for s in service.list_sources(name)],
    }


@app.patch("/api/experts/{name}")
def patch_expert(name: str, body: UpdateExpert) -> dict:
    try:
        expert = service.update_expert(name, body.description, body.chunk)
    except KeyError as e:
        raise HTTPException(404, "no such expert") from e
    return expert.model_dump(mode="json")


@app.delete("/api/experts/{name}")
def remove_expert(name: str) -> dict:
    try:
        service.delete_expert(name)
    except KeyError as e:
        raise HTTPException(404, "no such expert") from e
    return {"deleted": name}


@app.post("/api/experts/{name}/reindex")
def reindex(name: str) -> dict:
    if not get_registry().get_expert(name):
        raise HTTPException(404, "no such expert")
    return {"job_id": service.submit_reindex(name)}


# --------------------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------------------
@app.post("/api/experts/{name}/sources")
async def add_sources(
    name: str,
    files: list[UploadFile] | None = None,
    urls: str | None = Form(default=None),
) -> dict:
    if not get_registry().get_expert(name):
        raise HTTPException(404, "no such expert")
    items: list[service.Item] = []
    for up in files or []:
        data = await up.read()
        path = service.store_material(name, up.filename or "upload", data)
        items.append(service.Item(origin=str(path), data=data, title=Path(path).stem))
    for url in (u.strip() for u in (urls or "").splitlines() if u.strip()):
        items.append(service.item_from_url(url))
    if not items:
        raise HTTPException(400, "no files or urls provided")
    return {"job_id": service.submit_ingest(name, items)}


@app.delete("/api/experts/{name}/sources/{source_id}")
def delete_source(name: str, source_id: str) -> dict:
    try:
        service.delete_source(name, source_id)
    except KeyError as e:
        raise HTTPException(404, "no such expert") from e
    return {"deleted": source_id}


# --------------------------------------------------------------------------------------
# Jobs (+ SSE)
# --------------------------------------------------------------------------------------
@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [j.model_dump(mode="json") for j in get_registry().list_jobs()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = get_registry().get_job(job_id)
    if not job:
        raise HTTPException(404, "no such job")
    return job.model_dump(mode="json")


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> EventSourceResponse:
    reg = get_registry()

    async def gen():
        terminal = {JobStatus.done, JobStatus.failed}
        while True:
            job = reg.get_job(job_id)
            if not job:
                yield {"event": "error", "data": "no such job"}
                return
            yield {"event": "progress", "data": job.model_dump_json()}
            if job.status in terminal:
                return
            await asyncio.sleep(0.5)

    return EventSourceResponse(gen())


# --------------------------------------------------------------------------------------
# Query (playground)
# --------------------------------------------------------------------------------------
@app.post("/api/query")
def query(body: QueryBody) -> dict:
    result = service.query(
        body.question,
        top_k=body.top_k,
        experts=body.experts,
        synthesize=body.synthesize,
    )
    return result.model_dump(mode="json")


# --------------------------------------------------------------------------------------
# Team export / import (portability — wired in moe.portability)
# --------------------------------------------------------------------------------------
@app.post("/api/team/export")
def team_export() -> dict:
    from moe import portability

    out = get_settings().materials_dir.parent / "team.tar.zst"
    portability.export_team(str(out))
    return {"path": str(out)}


# --------------------------------------------------------------------------------------
# Static SPA (built by Vite into src/moe/web_dist)
# --------------------------------------------------------------------------------------
def _mount_spa() -> None:
    dist = Path(__file__).parent / "web_dist"
    if dist.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")


_mount_spa()


def main() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run(app, host=s.dashboard_host, port=s.dashboard_port)


if __name__ == "__main__":
    main()
