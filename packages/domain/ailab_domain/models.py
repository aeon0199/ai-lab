from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Goal(BaseModel):
    id: UUID
    title: str
    description: str
    status: str = "active"
    created_at: datetime


class ResearchRun(BaseModel):
    id: UUID
    goal_id: UUID
    status: RunStatus
    config: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    workspace_root: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failure_reason: str | None = None


class Experiment(BaseModel):
    id: UUID
    research_run_id: UUID
    goal_reference: UUID
    hypothesis: str
    method: str
    tools_required: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    evaluation_method: str
    created_at: datetime


class ExperimentRun(BaseModel):
    id: UUID
    experiment_id: UUID
    research_run_id: UUID
    status: ExperimentRunStatus
    parameters: dict[str, Any] = Field(default_factory=dict)
    logs: dict[str, Any] = Field(default_factory=dict)
    result_summary: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    started_at: datetime | None = None
    ended_at: datetime | None = None


class AgentTrace(BaseModel):
    id: UUID
    research_run_id: UUID
    agent_id: str
    reasoning_summary: str
    action: str
    tool_used: str | None = None
    tokens_used: int = 0
    created_at: datetime


class EvaluationRecommendation(str, Enum):
    CONTINUE = "continue"
    PIVOT = "pivot"
    STOP = "stop"


class EvaluationScore(BaseModel):
    id: UUID
    research_run_id: UUID
    experiment_run_id: UUID
    goal_progress: float
    experiment_quality: float
    novelty: float
    confidence: float
    recommendation: EvaluationRecommendation
    rationale: str
    created_at: datetime


class ChatMessage(BaseModel):
    role: str
    content: str


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    messages: list[ChatMessage]
    system: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    temperature: float = 0.2
    top_p: float = 1.0
    max_tokens: int = 1024
    seed: int | None = None
    timeout: int = 60


class ModelResponse(BaseModel):
    output: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: int
    provider_request_id: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class GoalState(BaseModel):
    title: str
    description: str
    status: str = "active"


class AgentState(BaseModel):
    role: str = "unknown"
    capabilities: list[str] = Field(default_factory=list)
    tool_access: list[str] = Field(default_factory=list)


class ExperimentState(BaseModel):
    hypothesis: str
    method: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    evaluation_method: str = ""
    status: str = "proposed"


class ExperimentRunState(BaseModel):
    experiment_id: str | None = None
    status: str = "queued"
    parameters: dict[str, Any] = Field(default_factory=dict)
    logs: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    result_summary: str | None = None
    error: str | None = None


class ResultState(BaseModel):
    experiment_run_id: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class WorldStateModel(BaseModel):
    stream_id: str
    goals: dict[str, GoalState] = Field(default_factory=dict)
    agents: dict[str, AgentState] = Field(default_factory=dict)
    experiments: dict[str, ExperimentState] = Field(default_factory=dict)
    experiment_runs: dict[str, ExperimentRunState] = Field(default_factory=dict)
    results: dict[str, ResultState] = Field(default_factory=dict)
    scores: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    resources: dict[str, Any] = Field(default_factory=dict)
    last_updated: str
