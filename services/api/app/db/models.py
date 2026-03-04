from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    stream_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    causation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("stream_id", "idempotency_key", name="uq_stream_idempotency"),
        Index("idx_events_stream", "stream_id"),
        Index("idx_events_type", "event_type"),
        Index("idx_events_occurred", "occurred_at"),
    )


class GoalModel(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ResearchRunModel(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    budget: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    workspace_root: Mapped[str] = mapped_column(String(400), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ExperimentModel(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    goal_reference: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    tools_required: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evaluation_method: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ExperimentRunModel(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    logs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ResultModel(Base):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    experiment_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    artifacts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AgentTraceModel(Base):
    __tablename__ = "agent_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    tool_used: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EvaluatorScoreModel(Base):
    __tablename__ = "evaluator_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    experiment_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    goal_progress: Mapped[float] = mapped_column(Float, nullable=False)
    experiment_quality: Mapped[float] = mapped_column(Float, nullable=False)
    novelty: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ArtifactIndexModel(Base):
    __tablename__ = "artifacts_index"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    experiment_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ModelCallModel(Base):
    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    experiment_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WorldStateSnapshotModel(Base):
    __tablename__ = "world_state_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    last_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
