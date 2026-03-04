from uuid import uuid4

import pytest

from ailab_domain.events import ActorType, EventEnvelope


def test_event_payload_validation_rejects_missing_fields() -> None:
    with pytest.raises(ValueError):
        EventEnvelope(
            stream_id=uuid4(),
            event_type="experiment_evaluated",
            actor_type=ActorType.AGENT,
            actor_id="critic-agent",
            idempotency_key="k1",
            payload={
                "score_id": str(uuid4()),
                "research_run_id": str(uuid4()),
                "experiment_run_id": str(uuid4()),
                "goal_progress": 0.5,
                "experiment_quality": 0.5,
                "novelty": 0.5,
                "confidence": 0.5,
                # recommendation is missing on purpose
            },
        )


def test_event_payload_validation_accepts_required_fields() -> None:
    evt = EventEnvelope(
        stream_id=uuid4(),
        event_type="goal_created",
        actor_type=ActorType.USER,
        actor_id="user",
        idempotency_key="k2",
        payload={"goal_id": str(uuid4()), "title": "A", "description": "B"},
    )
    assert evt.event_type == "goal_created"
