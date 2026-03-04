from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import (
    AgeLimit,
    Callbacks,
    CurrentMessage,
    Pipelines,
    Retries,
    ShutdownNotifications,
    TimeLimit,
)

from worker.core.config import settings

try:
    from dramatiq.middleware.prometheus import Prometheus
except Exception:  # pragma: no cover
    Prometheus = None  # type: ignore[assignment]


_broker: RedisBroker | None = None


def get_broker() -> RedisBroker:
    global _broker
    if _broker is not None:
        return _broker

    middleware = [
        AgeLimit(),
        TimeLimit(),
        ShutdownNotifications(),
        Callbacks(),
        Pipelines(),
        CurrentMessage(),
        Retries(
            max_retries=settings.dramatiq_max_retries,
            min_backoff=settings.dramatiq_min_backoff_ms,
            max_backoff=settings.dramatiq_max_backoff_ms,
        ),
    ]
    if Prometheus is not None:
        middleware.append(Prometheus())

    _broker = RedisBroker(
        url=settings.redis_url,
        namespace=settings.dramatiq_namespace,
        middleware=middleware,
    )
    dramatiq.set_broker(_broker)
    return _broker
