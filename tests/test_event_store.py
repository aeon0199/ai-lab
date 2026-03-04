from datetime import datetime, timezone
from uuid import uuid4

from ailab_domain.events import ActorType, EventEnvelope
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.event_store import DuplicateEventError, append_event, rebuild_world_state


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_append_event_and_rebuild_world_state():
    db = _session()
    stream = uuid4()

    event = EventEnvelope(
        stream_id=stream,
        event_type="goal_created",
        actor_type=ActorType.USER,
        actor_id="tester",
        occurred_at=datetime.now(timezone.utc),
        idempotency_key="goal-1",
        payload={"goal_id": str(stream), "title": "T", "description": "D"},
    )
    append_event(db, event)

    state = rebuild_world_state(db, str(stream))
    assert str(stream) in state["goals"]
    assert state["goals"][str(stream)]["title"] == "T"


def test_idempotency_duplicate_rejected():
    db = _session()
    stream = uuid4()

    payload = {"goal_id": str(stream), "title": "T", "description": "D"}
    event1 = EventEnvelope(
        stream_id=stream,
        event_type="goal_created",
        actor_type=ActorType.USER,
        actor_id="tester",
        idempotency_key="same-key",
        payload=payload,
    )
    append_event(db, event1)

    event2 = EventEnvelope(
        stream_id=stream,
        event_type="goal_created",
        actor_type=ActorType.USER,
        actor_id="tester",
        idempotency_key="same-key",
        payload=payload,
    )

    try:
        append_event(db, event2)
        assert False, "Expected DuplicateEventError"
    except DuplicateEventError:
        assert True
