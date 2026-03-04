from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActorType(str, Enum):
    SYSTEM = "system"
    AGENT = "agent"
    TOOL = "tool"
    USER = "user"


EVENT_TYPES = {
    "goal_created",
    "research_run_created",
    "research_run_started",
    "research_run_paused",
    "research_run_resumed",
    "research_run_completed",
    "research_run_failed",
    "agent_spawned",
    "agent_cycle_started",
    "agent_cycle_finished",
    "experiment_proposed",
    "experiment_approved_by_policy",
    "experiment_run_queued",
    "experiment_run_started",
    "tool_invocation_started",
    "tool_invocation_finished",
    "experiment_run_completed",
    "experiment_run_failed",
    "result_recorded",
    "analysis_generated",
    "experiment_evaluated",
    "goal_progress_updated",
    "direction_recommended",
    "world_state_snapshot_created",
}


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    stream_id: UUID
    event_type: str
    schema_version: int = 1
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_type: ActorType
    actor_id: str
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    idempotency_key: str
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_event_type(self) -> "EventEnvelope":
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {self.event_type}")
        return self
