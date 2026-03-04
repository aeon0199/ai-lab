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

REQUIRED_PAYLOAD_FIELDS: dict[str, set[str]] = {
    "goal_created": {"goal_id", "title", "description"},
    "research_run_created": {"run_id", "goal_id"},
    "research_run_started": {"run_id"},
    "research_run_paused": {"run_id"},
    "research_run_resumed": {"run_id"},
    "research_run_completed": {"run_id"},
    "research_run_failed": {"run_id"},
    "agent_spawned": {"agent_id"},
    "agent_cycle_started": {"run_id", "cycle_index"},
    "agent_cycle_finished": {"run_id", "cycle_index"},
    "experiment_proposed": {"experiment_id", "research_run_id", "goal_id", "hypothesis", "method"},
    "experiment_approved_by_policy": {"experiment_id", "research_run_id", "approved"},
    "experiment_run_queued": {"experiment_run_id", "experiment_id", "research_run_id"},
    "experiment_run_started": {"experiment_run_id"},
    "tool_invocation_started": {"research_run_id", "experiment_run_id"},
    "tool_invocation_finished": {"research_run_id", "experiment_run_id", "success"},
    "experiment_run_completed": {"experiment_run_id"},
    "experiment_run_failed": {"experiment_run_id"},
    "result_recorded": {"result_id", "research_run_id", "experiment_id", "experiment_run_id"},
    "analysis_generated": {"trace_id", "research_run_id", "agent_id", "reasoning_summary", "action"},
    "experiment_evaluated": {
        "score_id",
        "research_run_id",
        "experiment_run_id",
        "goal_progress",
        "experiment_quality",
        "novelty",
        "confidence",
        "recommendation",
    },
    "goal_progress_updated": {"research_run_id", "goal_id", "goal_progress", "confidence"},
    "direction_recommended": {"research_run_id", "recommendation", "rationale"},
    "world_state_snapshot_created": {"stream_id", "last_event_id", "snapshot_payload"},
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
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")
        required = REQUIRED_PAYLOAD_FIELDS.get(self.event_type, set())
        missing = sorted(field for field in required if field not in self.payload)
        if missing:
            raise ValueError(f"Missing required payload fields for {self.event_type}: {', '.join(missing)}")
        return self
