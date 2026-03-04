from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import requests
from ailab_domain.events import ActorType, EventEnvelope

from worker.core.config import settings


class APIClient:
    def __init__(self) -> None:
        self.base = settings.api_base_url.rstrip("/")
        self.session = requests.Session()

    def get_run(self, run_id: str) -> dict[str, Any]:
        res = self.session.get(f"{self.base}/research-runs/{run_id}", timeout=30)
        res.raise_for_status()
        return res.json()

    def get_goal(self, goal_id: str) -> dict[str, Any]:
        res = self.session.get(f"{self.base}/goals/{goal_id}", timeout=30)
        res.raise_for_status()
        return res.json()

    def get_scores(self, run_id: str) -> list[dict[str, Any]]:
        res = self.session.get(f"{self.base}/evaluator-scores/{run_id}", timeout=30)
        res.raise_for_status()
        return res.json()

    def emit_event(
        self,
        run_id: str,
        event_type: str,
        actor_type: ActorType,
        actor_id: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        env = EventEnvelope(
            stream_id=run_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            causation_id=causation_id,
            idempotency_key=idempotency_key or f"{event_type}-{actor_id}-{uuid4()}",
            payload=payload,
        )

        res = self.session.post(
            f"{self.base}/internal/events",
            json=env.model_dump(mode="json"),
            timeout=30,
        )
        res.raise_for_status()
        return res.json()


api_client = APIClient()
