from __future__ import annotations

from redis import Redis
from rq import Queue, Retry

from app.core.config import settings


_redis_conn = Redis.from_url(settings.redis_url)
run_queue = Queue("research_runs", connection=_redis_conn, default_timeout=900)


def enqueue_research_run(run_id: str) -> str:
    job = run_queue.enqueue(
        "worker.jobs.process_research_run",
        run_id,
        retry=Retry(max=settings.worker_retry_max, interval=_retry_intervals()),
        job_timeout=1800,
        failure_ttl=86400,
    )
    return job.id


def enqueue_single_cycle(run_id: str) -> str:
    job = run_queue.enqueue(
        "worker.jobs.process_single_cycle",
        run_id,
        retry=Retry(max=settings.worker_retry_max, interval=_retry_intervals()),
        job_timeout=900,
        failure_ttl=86400,
    )
    return job.id


def _retry_intervals() -> list[int]:
    values = []
    for part in settings.worker_retry_intervals.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values or [10, 30, 60]
