from __future__ import annotations

from redis import Redis
from rq import Queue

from app.core.config import settings


_redis_conn = Redis.from_url(settings.redis_url)
run_queue = Queue("research_runs", connection=_redis_conn, default_timeout=900)


def enqueue_research_run(run_id: str) -> str:
    job = run_queue.enqueue("worker.jobs.process_research_run", run_id)
    return job.id


def enqueue_single_cycle(run_id: str) -> str:
    job = run_queue.enqueue("worker.jobs.process_single_cycle", run_id)
    return job.id
