"""Background job runner. Ingestion is slow, so it never runs inline in a request — the
dashboard/API submits work here and streams progress from the ``jobs`` table (see the SSE
endpoint in :mod:`moe.api`). The CLI runs ingestion synchronously instead."""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from moe.models import Job, JobStatus
from moe.store.db import Registry, get_registry

# work_fn receives an update callback: update(stage: str, fraction: float)
Update = Callable[[str, float], None]
WorkFn = Callable[[Update], dict | None]


class JobRunner:
    def __init__(self, registry: Registry, max_workers: int = 2):
        self.registry = registry
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="moe-job")

    def submit(self, kind: str, expert: str | None, work: WorkFn) -> str:
        job_id = uuid.uuid4().hex[:12]
        self.registry.create_job(Job(id=job_id, kind=kind, expert=expert))
        self._pool.submit(self._run, job_id, work)
        return job_id

    def _run(self, job_id: str, work: WorkFn) -> None:
        reg = self.registry
        reg.update_job(job_id, status=JobStatus.running, stage="starting", progress=0.0)

        def update(stage: str, fraction: float) -> None:
            reg.update_job(job_id, stage=stage, progress=max(0.0, min(1.0, fraction)))

        try:
            meta = work(update) or {}
            reg.update_job(
                job_id, status=JobStatus.done, stage="done", progress=1.0, meta=meta
            )
        except Exception as e:  # noqa: BLE001
            reg.update_job(
                job_id,
                status=JobStatus.failed,
                error=f"{e}",
                meta={"traceback": traceback.format_exc()},
            )

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


@lru_cache
def get_runner() -> JobRunner:
    return JobRunner(get_registry())
