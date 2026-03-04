from __future__ import annotations

from datetime import datetime, timezone

import dramatiq
from ailab_domain.events import ActorType
from ailab_domain.queueing import (
    ACTOR_PROCESS_RESEARCH_RUN,
    ACTOR_PROCESS_SINGLE_CYCLE,
    ACTOR_RUN_RETRY_EXHAUSTED,
    QUEUE_RESEARCH_RUNS,
)

from worker.core.api_client import api_client
from worker.core.config import settings
from worker.core.heartbeat import start_worker_heartbeat
from worker.jobs import process_research_run, process_single_cycle
from worker.queue.broker import get_broker


broker = get_broker()
broker.declare_queue(QUEUE_RESEARCH_RUNS)

# Every Dramatiq worker process imports this module, so each process emits heartbeat.
start_worker_heartbeat(
    redis_url=settings.redis_url,
    key=settings.worker_heartbeat_key,
    backend="dramatiq",
    ttl_seconds=settings.worker_heartbeat_ttl_seconds,
    interval_seconds=settings.worker_heartbeat_interval_seconds,
)


@dramatiq.actor(
    actor_name=ACTOR_PROCESS_RESEARCH_RUN,
    queue_name=QUEUE_RESEARCH_RUNS,
    max_retries=settings.dramatiq_max_retries,
    min_backoff=settings.dramatiq_min_backoff_ms,
    max_backoff=settings.dramatiq_max_backoff_ms,
    on_retry_exhausted=ACTOR_RUN_RETRY_EXHAUSTED,
)
def process_research_run_actor(run_id: str) -> dict:
    return process_research_run(run_id)


@dramatiq.actor(
    actor_name=ACTOR_PROCESS_SINGLE_CYCLE,
    queue_name=QUEUE_RESEARCH_RUNS,
    max_retries=settings.dramatiq_max_retries,
    min_backoff=settings.dramatiq_min_backoff_ms,
    max_backoff=settings.dramatiq_max_backoff_ms,
    on_retry_exhausted=ACTOR_RUN_RETRY_EXHAUSTED,
)
def process_single_cycle_actor(run_id: str) -> dict:
    return process_single_cycle(run_id)


@dramatiq.actor(
    actor_name=ACTOR_RUN_RETRY_EXHAUSTED,
    queue_name=QUEUE_RESEARCH_RUNS,
    max_retries=0,
)
def run_retry_exhausted_actor(message_data: dict, retry_data: dict) -> dict:
    args = message_data.get("args") or []
    run_id = args[0] if args else None
    if not run_id:
        return {"ok": False, "message": "missing run_id in exhausted callback"}

    retries = int(retry_data.get("retries", 0))
    max_retries = int(retry_data.get("max_retries", settings.dramatiq_max_retries))

    api_client.emit_event(
        run_id,
        "research_run_failed",
        ActorType.SYSTEM,
        "runtime",
        {
            "run_id": run_id,
            "reason": f"Retries exhausted in Dramatiq actor after {retries}/{max_retries} attempts",
            "ended_at": datetime.now(timezone.utc).isoformat(),
        },
        idempotency_key=f"run-retry-exhausted:{run_id}",
    )
    return {"ok": True, "run_id": run_id, "retries": retries}
