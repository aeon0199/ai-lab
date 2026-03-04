from __future__ import annotations

from dataclasses import dataclass

from ailab_domain.queueing import (
    ACTOR_PROCESS_RESEARCH_RUN,
    ACTOR_PROCESS_SINGLE_CYCLE,
    QUEUE_RESEARCH_RUNS,
)
from dramatiq import Message
from dramatiq.brokers.redis import RedisBroker

from app.core.config import settings


@dataclass
class DramatiqTaskDispatcher:
    broker: RedisBroker

    @classmethod
    def from_settings(cls) -> "DramatiqTaskDispatcher":
        broker = RedisBroker(url=settings.redis_url, namespace=settings.dramatiq_namespace)
        broker.declare_queue(QUEUE_RESEARCH_RUNS)
        return cls(broker=broker)

    def enqueue_research_run(self, run_id: str) -> str:
        message = Message(
            queue_name=QUEUE_RESEARCH_RUNS,
            actor_name=ACTOR_PROCESS_RESEARCH_RUN,
            args=(run_id,),
            kwargs={},
            options={
                "max_retries": settings.dramatiq_max_retries,
                "min_backoff": settings.dramatiq_min_backoff_ms,
                "max_backoff": settings.dramatiq_max_backoff_ms,
            },
        )
        enqueued = self.broker.enqueue(message)
        return enqueued.message_id

    def enqueue_single_cycle(self, run_id: str) -> str:
        message = Message(
            queue_name=QUEUE_RESEARCH_RUNS,
            actor_name=ACTOR_PROCESS_SINGLE_CYCLE,
            args=(run_id,),
            kwargs={},
            options={
                "max_retries": settings.dramatiq_max_retries,
                "min_backoff": settings.dramatiq_min_backoff_ms,
                "max_backoff": settings.dramatiq_max_backoff_ms,
            },
        )
        enqueued = self.broker.enqueue(message)
        return enqueued.message_id


def get_task_dispatcher() -> DramatiqTaskDispatcher:
    return DramatiqTaskDispatcher.from_settings()


_dispatcher = get_task_dispatcher()


def enqueue_research_run(run_id: str) -> str:
    return _dispatcher.enqueue_research_run(run_id)


def enqueue_single_cycle(run_id: str) -> str:
    return _dispatcher.enqueue_single_cycle(run_id)
