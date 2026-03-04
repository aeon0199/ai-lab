from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from ailab_domain.events import ActorType, EventEnvelope
from sqlalchemy.orm import Session

from app.db import models
from app.services.event_store import append_event


ALLOWED_TRANSITIONS = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"paused", "completed", "failed", "cancelled"},
    "paused": {"running", "cancelled", "failed"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def create_goal(db: Session, title: str, description: str, actor_id: str = "user") -> UUID:
    goal_id = uuid4()
    event = EventEnvelope(
        stream_id=goal_id,
        event_type="goal_created",
        actor_type=ActorType.USER,
        actor_id=actor_id,
        idempotency_key=f"goal-create-{goal_id}",
        payload={
            "goal_id": str(goal_id),
            "title": title,
            "description": description,
        },
    )
    append_event(db, event)
    return goal_id


def create_research_run(
    db: Session,
    goal_id: UUID,
    config: dict,
    budget: dict,
    workspace_root: str,
    actor_id: str = "user",
) -> UUID:
    goal = db.get(models.GoalModel, str(goal_id))
    if not goal:
        raise ValueError("Goal does not exist")

    run_id = uuid4()
    event = EventEnvelope(
        stream_id=run_id,
        event_type="research_run_created",
        actor_type=ActorType.USER,
        actor_id=actor_id,
        idempotency_key=f"run-create-{run_id}",
        payload={
            "run_id": str(run_id),
            "goal_id": str(goal_id),
            "config": config,
            "budget": budget,
            "workspace_root": workspace_root,
        },
    )
    append_event(db, event)
    return run_id


def _transition_run(db: Session, run_id: UUID, target: str, actor_id: str = "user") -> str:
    run = db.get(models.ResearchRunModel, str(run_id))
    if not run:
        raise ValueError("Research run does not exist")

    current = run.status
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition {current} -> {target}")

    mapping = {
        "running": "research_run_started" if current == "queued" else "research_run_resumed",
        "paused": "research_run_paused",
        "completed": "research_run_completed",
        "failed": "research_run_failed",
        "cancelled": "research_run_failed",
    }

    payload = {"run_id": str(run_id)}
    now = datetime.now(timezone.utc).isoformat()
    if target == "running" and current == "queued":
        payload["started_at"] = now
    if target in {"completed", "failed", "cancelled"}:
        payload["ended_at"] = now
        if target == "failed":
            payload["reason"] = "run marked failed"
        if target == "cancelled":
            payload["reason"] = "run cancelled"

    event = EventEnvelope(
        stream_id=run_id,
        event_type=mapping[target],
        actor_type=ActorType.USER,
        actor_id=actor_id,
        idempotency_key=f"run-transition-{run_id}-{target}-{now}",
        payload=payload,
    )
    append_event(db, event)
    return target


def start_run(db: Session, run_id: UUID, actor_id: str = "user") -> str:
    return _transition_run(db, run_id, "running", actor_id)


def pause_run(db: Session, run_id: UUID, actor_id: str = "user") -> str:
    return _transition_run(db, run_id, "paused", actor_id)


def resume_run(db: Session, run_id: UUID, actor_id: str = "user") -> str:
    return _transition_run(db, run_id, "running", actor_id)


def cancel_run(db: Session, run_id: UUID, actor_id: str = "user") -> str:
    return _transition_run(db, run_id, "cancelled", actor_id)
