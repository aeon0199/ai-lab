from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateGoalRequest(BaseModel):
    title: str
    description: str


class CreateGoalResponse(BaseModel):
    goal_id: UUID


class CreateResearchRunRequest(BaseModel):
    goal_id: UUID
    config: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    workspace_root: str = "/workspace"


class CreateResearchRunResponse(BaseModel):
    run_id: UUID


class RunCommandResponse(BaseModel):
    run_id: UUID
    status: str


class GoalView(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    created_at: datetime


class ResearchRunView(BaseModel):
    id: UUID
    goal_id: UUID
    status: str
    config: dict[str, Any]
    budget: dict[str, Any]
    workspace_root: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failure_reason: str | None = None


class EventView(BaseModel):
    event_id: UUID
    stream_id: UUID
    event_type: str
    schema_version: int
    occurred_at: datetime
    actor_type: str
    actor_id: str
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    idempotency_key: str
    payload: dict[str, Any]


class WorldStateResponse(BaseModel):
    stream_id: UUID
    state: dict[str, Any]


class RebuildProjectionsResponse(BaseModel):
    rebuilt_events: int
    streams: int


class ExperimentView(BaseModel):
    id: UUID
    research_run_id: UUID
    goal_reference: UUID
    hypothesis: str
    method: str
    tools_required: list[str]
    parameters: dict[str, Any]
    evaluation_method: str
    created_at: datetime


class ExperimentRunView(BaseModel):
    id: UUID
    experiment_id: UUID
    research_run_id: UUID
    status: str
    parameters: dict[str, Any]
    logs: dict[str, Any]
    result_summary: str | None = None
    metrics: dict[str, Any]
    started_at: datetime | None = None
    ended_at: datetime | None = None


class AgentTraceView(BaseModel):
    id: UUID
    research_run_id: UUID
    agent_id: str
    reasoning_summary: str
    action: str
    tool_used: str | None = None
    tokens_used: int
    created_at: datetime


class EvaluatorScoreView(BaseModel):
    id: UUID
    research_run_id: UUID
    experiment_run_id: UUID
    goal_progress: float
    experiment_quality: float
    novelty: float
    confidence: float
    recommendation: str
    rationale: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
