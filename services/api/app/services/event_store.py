from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ailab_domain.events import EVENT_TYPES, ActorType, EventEnvelope
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.reducers.world_state import reduce_events
from app.services.projections import apply_projection_event


class DuplicateEventError(Exception):
    pass


class InvalidEventTypeError(Exception):
    pass


def _event_to_dict(row: models.EventModel) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "stream_id": row.stream_id,
        "event_type": row.event_type,
        "schema_version": row.schema_version,
        "occurred_at": row.occurred_at.isoformat(),
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "correlation_id": row.correlation_id,
        "causation_id": row.causation_id,
        "idempotency_key": row.idempotency_key,
        "payload": row.payload,
    }


def append_event(
    db: Session,
    envelope: EventEnvelope,
    *,
    allow_snapshot: bool = True,
) -> models.EventModel:
    if envelope.event_type not in EVENT_TYPES:
        raise InvalidEventTypeError(envelope.event_type)

    row = models.EventModel(
        event_id=str(envelope.event_id),
        stream_id=str(envelope.stream_id),
        event_type=envelope.event_type,
        schema_version=envelope.schema_version,
        occurred_at=envelope.occurred_at,
        actor_type=envelope.actor_type.value,
        actor_id=envelope.actor_id,
        correlation_id=str(envelope.correlation_id) if envelope.correlation_id else None,
        causation_id=str(envelope.causation_id) if envelope.causation_id else None,
        idempotency_key=envelope.idempotency_key,
        payload=envelope.payload,
    )

    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateEventError("duplicate event or idempotency key") from exc

    apply_projection_event(db, row.event_type, row.payload)
    db.commit()
    db.refresh(row)

    if allow_snapshot:
        _maybe_snapshot_stream(db, row.stream_id)

    return row


def get_stream_events(db: Session, stream_id: str) -> list[models.EventModel]:
    stmt: Select[tuple[models.EventModel]] = (
        select(models.EventModel)
        .where(models.EventModel.stream_id == stream_id)
        .order_by(models.EventModel.id.asc())
    )
    return list(db.scalars(stmt))


def get_events_after_id(db: Session, stream_id: str, after_id: int) -> list[models.EventModel]:
    stmt = (
        select(models.EventModel)
        .where(models.EventModel.stream_id == stream_id)
        .where(models.EventModel.id > after_id)
        .order_by(models.EventModel.id.asc())
    )
    return list(db.scalars(stmt))


def rebuild_world_state(db: Session, stream_id: str) -> dict[str, Any]:
    snapshot = db.scalars(
        select(models.WorldStateSnapshotModel)
        .where(models.WorldStateSnapshotModel.stream_id == stream_id)
        .order_by(models.WorldStateSnapshotModel.id.desc())
        .limit(1)
    ).first()

    seed = None
    events: list[models.EventModel]
    if snapshot:
        seed = snapshot.snapshot_payload
        anchor = db.scalars(select(models.EventModel).where(models.EventModel.event_id == snapshot.last_event_id)).first()
        anchor_id = anchor.id if anchor else 0
        events = get_events_after_id(db, stream_id, anchor_id)
    else:
        events = get_stream_events(db, stream_id)

    return reduce_events(stream_id, [_event_to_dict(e) for e in events], seed_state=seed)


def rebuild_all_projections(db: Session) -> tuple[int, int]:
    # Reset projection tables only; events table remains immutable source of truth.
    for table in [
        models.GoalModel,
        models.ResearchRunModel,
        models.ExperimentModel,
        models.ExperimentRunModel,
        models.ResultModel,
        models.AgentTraceModel,
        models.EvaluatorScoreModel,
        models.ArtifactIndexModel,
        models.ModelCallModel,
        models.WorldStateSnapshotModel,
    ]:
        db.query(table).delete()

    events = list(db.scalars(select(models.EventModel).order_by(models.EventModel.id.asc())))
    for event in events:
        apply_projection_event(db, event.event_type, event.payload)

    db.commit()
    stream_count = db.scalar(select(func.count(func.distinct(models.EventModel.stream_id)))) or 0
    return len(events), int(stream_count)


def _maybe_snapshot_stream(db: Session, stream_id: str) -> None:
    total = db.scalar(
        select(func.count(models.EventModel.id)).where(models.EventModel.stream_id == stream_id)
    ) or 0

    if total % settings.snapshot_cadence != 0:
        return

    state = rebuild_world_state(db, stream_id)
    last_event = db.scalars(
        select(models.EventModel)
        .where(models.EventModel.stream_id == stream_id)
        .order_by(models.EventModel.id.desc())
        .limit(1)
    ).first()

    if not last_event:
        return

    snapshot_event = EventEnvelope(
        stream_id=last_event.stream_id,
        event_type="world_state_snapshot_created",
        schema_version=1,
        occurred_at=datetime.now(timezone.utc),
        actor_type=ActorType.SYSTEM,
        actor_id="snapshotter",
        idempotency_key=f"snapshot-{stream_id}-{total}",
        payload={
            "stream_id": stream_id,
            "last_event_id": last_event.event_id,
            "snapshot_payload": state,
        },
    )
    append_event(db, snapshot_event, allow_snapshot=False)
