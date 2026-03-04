from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

from ailab_domain.events import ActorType, EventEnvelope
from ailab_policy.registry import DEFAULT_TOOL_REGISTRY
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
import requests
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core.config import settings
from app.db import models
from app.db.session import get_db
from app.schemas.api import (
    AgentTraceView,
    CreateGoalRequest,
    CreateGoalResponse,
    CreateResearchRunRequest,
    CreateResearchRunResponse,
    EvaluatorScoreView,
    EventView,
    ExperimentRunView,
    ExperimentView,
    GoalView,
    HealthResponse,
    RebuildProjectionsResponse,
    ResearchRunView,
    RunCommandResponse,
    WorldStateResponse,
)
from app.services.commands import cancel_run, create_goal, create_research_run, pause_run, resume_run, start_run
from app.services.event_store import DuplicateEventError, append_event, rebuild_all_projections, rebuild_world_state
from app.services.queue import enqueue_research_run
from app.ws.manager import ws_manager


api_router = APIRouter()
request_counter = Counter("ailab_api_requests_total", "Total API requests", ["endpoint"])


def _to_goal_view(row: models.GoalModel) -> GoalView:
    return GoalView(
        id=UUID(row.id),
        title=row.title,
        description=row.description,
        status=row.status,
        created_at=row.created_at,
    )


def _to_run_view(row: models.ResearchRunModel) -> ResearchRunView:
    return ResearchRunView(
        id=UUID(row.id),
        goal_id=UUID(row.goal_id),
        status=row.status,
        config=row.config,
        budget=row.budget,
        workspace_root=row.workspace_root,
        started_at=row.started_at,
        ended_at=row.ended_at,
        failure_reason=row.failure_reason,
    )


@api_router.post("/goals", response_model=CreateGoalResponse)
def create_goal_route(payload: CreateGoalRequest, db: Session = Depends(get_db)) -> CreateGoalResponse:
    request_counter.labels(endpoint="create_goal").inc()
    goal_id = create_goal(db, payload.title, payload.description)
    return CreateGoalResponse(goal_id=goal_id)


@api_router.get("/goals", response_model=list[GoalView])
def list_goals(db: Session = Depends(get_db)) -> list[GoalView]:
    request_counter.labels(endpoint="list_goals").inc()
    rows = list(db.scalars(select(models.GoalModel).order_by(models.GoalModel.created_at.desc())))
    return [_to_goal_view(row) for row in rows]


@api_router.get("/goals/{goal_id}", response_model=GoalView)
def get_goal(goal_id: UUID, db: Session = Depends(get_db)) -> GoalView:
    request_counter.labels(endpoint="get_goal").inc()
    row = db.get(models.GoalModel, str(goal_id))
    if not row:
        raise HTTPException(status_code=404, detail="Goal not found")
    return _to_goal_view(row)


@api_router.post("/research-runs", response_model=CreateResearchRunResponse)
def create_run(payload: CreateResearchRunRequest, db: Session = Depends(get_db)) -> CreateResearchRunResponse:
    request_counter.labels(endpoint="create_run").inc()
    try:
        run_id = create_research_run(
            db,
            goal_id=payload.goal_id,
            config=payload.config,
            budget=payload.budget,
            workspace_root=payload.workspace_root,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CreateResearchRunResponse(run_id=run_id)


@api_router.post("/research-runs/{run_id}/start", response_model=RunCommandResponse)
def start_run_route(run_id: UUID, db: Session = Depends(get_db)) -> RunCommandResponse:
    request_counter.labels(endpoint="start_run").inc()
    try:
        status = start_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enqueue_research_run(str(run_id))
    return RunCommandResponse(run_id=run_id, status=status)


@api_router.post("/research-runs/{run_id}/pause", response_model=RunCommandResponse)
def pause_run_route(run_id: UUID, db: Session = Depends(get_db)) -> RunCommandResponse:
    request_counter.labels(endpoint="pause_run").inc()
    try:
        status = pause_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunCommandResponse(run_id=run_id, status=status)


@api_router.post("/research-runs/{run_id}/resume", response_model=RunCommandResponse)
def resume_run_route(run_id: UUID, db: Session = Depends(get_db)) -> RunCommandResponse:
    request_counter.labels(endpoint="resume_run").inc()
    try:
        status = resume_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enqueue_research_run(str(run_id))
    return RunCommandResponse(run_id=run_id, status=status)


@api_router.post("/research-runs/{run_id}/cancel", response_model=RunCommandResponse)
def cancel_run_route(run_id: UUID, db: Session = Depends(get_db)) -> RunCommandResponse:
    request_counter.labels(endpoint="cancel_run").inc()
    try:
        status = cancel_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunCommandResponse(run_id=run_id, status=status)


@api_router.get("/research-runs", response_model=list[ResearchRunView])
def list_runs(db: Session = Depends(get_db)) -> list[ResearchRunView]:
    request_counter.labels(endpoint="list_runs").inc()
    rows = list(db.scalars(select(models.ResearchRunModel).order_by(models.ResearchRunModel.created_at.desc())))
    return [_to_run_view(row) for row in rows]


@api_router.get("/research-runs/{run_id}", response_model=ResearchRunView)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> ResearchRunView:
    request_counter.labels(endpoint="get_run").inc()
    run = db.get(models.ResearchRunModel, str(run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _to_run_view(run)


@api_router.get("/research-runs/{run_id}/timeline", response_model=list[EventView])
def get_timeline(run_id: UUID, db: Session = Depends(get_db)) -> list[EventView]:
    request_counter.labels(endpoint="timeline").inc()
    rows = list(
        db.scalars(
            select(models.EventModel)
            .where(models.EventModel.stream_id == str(run_id))
            .order_by(models.EventModel.id.asc())
        )
    )
    return [
        EventView(
            event_id=UUID(row.event_id),
            stream_id=UUID(row.stream_id),
            event_type=row.event_type,
            schema_version=row.schema_version,
            occurred_at=row.occurred_at,
            actor_type=row.actor_type,
            actor_id=row.actor_id,
            correlation_id=UUID(row.correlation_id) if row.correlation_id else None,
            causation_id=UUID(row.causation_id) if row.causation_id else None,
            idempotency_key=row.idempotency_key,
            payload=row.payload,
        )
        for row in rows
    ]


@api_router.get("/research-runs/{run_id}/world-state", response_model=WorldStateResponse)
def get_world_state(run_id: UUID, db: Session = Depends(get_db)) -> WorldStateResponse:
    request_counter.labels(endpoint="world_state").inc()
    state = rebuild_world_state(db, str(run_id))
    return WorldStateResponse(stream_id=run_id, state=state)


@api_router.get("/experiments/{experiment_id}", response_model=ExperimentView)
def get_experiment(experiment_id: UUID, db: Session = Depends(get_db)) -> ExperimentView:
    request_counter.labels(endpoint="experiment").inc()
    row = db.get(models.ExperimentModel, str(experiment_id))
    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentView(
        id=UUID(row.id),
        research_run_id=UUID(row.research_run_id),
        goal_reference=UUID(row.goal_reference),
        hypothesis=row.hypothesis,
        method=row.method,
        tools_required=row.tools_required,
        parameters=row.parameters,
        evaluation_method=row.evaluation_method,
        created_at=row.created_at,
    )


@api_router.get("/experiment-runs/{run_id}", response_model=ExperimentRunView)
def get_experiment_run(run_id: UUID, db: Session = Depends(get_db)) -> ExperimentRunView:
    request_counter.labels(endpoint="experiment_run").inc()
    row = db.get(models.ExperimentRunModel, str(run_id))
    if not row:
        raise HTTPException(status_code=404, detail="Experiment run not found")
    return ExperimentRunView(
        id=UUID(row.id),
        experiment_id=UUID(row.experiment_id),
        research_run_id=UUID(row.research_run_id),
        status=row.status,
        parameters=row.parameters,
        logs=row.logs,
        result_summary=row.result_summary,
        metrics=row.metrics,
        started_at=row.started_at,
        ended_at=row.ended_at,
    )


@api_router.get("/experiment-runs/{run_id}/artifacts")
def get_artifacts(run_id: UUID, db: Session = Depends(get_db)) -> list[dict]:
    request_counter.labels(endpoint="artifacts").inc()
    rows = list(
        db.scalars(
            select(models.ArtifactIndexModel)
            .where(models.ArtifactIndexModel.experiment_run_id == str(run_id))
            .order_by(models.ArtifactIndexModel.created_at.asc())
        )
    )
    return [
        {
            "id": item.id,
            "artifact_type": item.artifact_type,
            "path": item.path,
            "checksum": item.checksum,
            "size_bytes": item.size_bytes,
            "created_at": item.created_at,
        }
        for item in rows
    ]


@api_router.get("/agent-traces/{run_id}", response_model=list[AgentTraceView])
def get_agent_traces(run_id: UUID, db: Session = Depends(get_db)) -> list[AgentTraceView]:
    request_counter.labels(endpoint="agent_traces").inc()
    rows = list(
        db.scalars(
            select(models.AgentTraceModel)
            .where(models.AgentTraceModel.research_run_id == str(run_id))
            .order_by(models.AgentTraceModel.created_at.asc())
        )
    )
    return [
        AgentTraceView(
            id=UUID(row.id),
            research_run_id=UUID(row.research_run_id),
            agent_id=row.agent_id,
            reasoning_summary=row.reasoning_summary,
            action=row.action,
            tool_used=row.tool_used,
            tokens_used=row.tokens_used,
            created_at=row.created_at,
        )
        for row in rows
    ]


@api_router.get("/evaluator-scores/{run_id}", response_model=list[EvaluatorScoreView])
def get_scores(run_id: UUID, db: Session = Depends(get_db)) -> list[EvaluatorScoreView]:
    request_counter.labels(endpoint="scores").inc()
    rows = list(
        db.scalars(
            select(models.EvaluatorScoreModel)
            .where(models.EvaluatorScoreModel.research_run_id == str(run_id))
            .order_by(models.EvaluatorScoreModel.created_at.asc())
        )
    )
    return [
        EvaluatorScoreView(
            id=UUID(row.id),
            research_run_id=UUID(row.research_run_id),
            experiment_run_id=UUID(row.experiment_run_id),
            goal_progress=row.goal_progress,
            experiment_quality=row.experiment_quality,
            novelty=row.novelty,
            confidence=row.confidence,
            recommendation=row.recommendation,
            rationale=row.rationale,
            created_at=row.created_at,
        )
        for row in rows
    ]


@api_router.get("/tools/registry")
def get_tool_registry() -> dict:
    request_counter.labels(endpoint="tool_registry").inc()
    return {name: policy.model_dump() for name, policy in DEFAULT_TOOL_REGISTRY.items()}


@api_router.post("/admin/rebuild-projections", response_model=RebuildProjectionsResponse)
def rebuild_route(db: Session = Depends(get_db)) -> RebuildProjectionsResponse:
    request_counter.labels(endpoint="rebuild").inc()
    rebuilt, streams = rebuild_all_projections(db)
    return RebuildProjectionsResponse(rebuilt_events=rebuilt, streams=streams)


@api_router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    request_counter.labels(endpoint="health").inc()
    db_state = "ok"
    redis_state = "ok"
    worker_state = "unknown"
    heartbeat_age: float | None = None
    sandbox_state = "unknown"
    try:
        db.execute(select(1))
    except Exception:
        db_state = "down"

    try:
        redis_conn = Redis.from_url(settings.redis_url)
        redis_conn.ping()
    except Exception:
        redis_state = "down"
        redis_conn = None

    if redis_conn is not None:
        try:
            raw = redis_conn.get(settings.worker_heartbeat_key)
            if raw is not None:
                payload = json.loads(raw.decode("utf-8"))
                heartbeat_ts = datetime.fromisoformat(payload["timestamp"])
                now = datetime.now(timezone.utc)
                heartbeat_age = max(0.0, (now - heartbeat_ts).total_seconds())
                worker_state = "ok" if heartbeat_age <= settings.worker_heartbeat_ttl_seconds else "down"
            else:
                worker_state = "down"
        except Exception:
            worker_state = "down"
            heartbeat_age = None
    else:
        worker_state = "down"

    if settings.sandbox_health_url:
        try:
            sandbox_res = requests.get(settings.sandbox_health_url, timeout=2)
            if sandbox_res.status_code == 200:
                payload = sandbox_res.json()
                sandbox_state = payload.get("docker", "ok")
            else:
                sandbox_state = "down"
        except Exception:
            sandbox_state = "down"
    else:
        sandbox_state = "disabled"

    overall = "ok" if all(v == "ok" for v in [db_state, redis_state, worker_state, sandbox_state]) else "degraded"
    return HealthResponse(
        status=overall,
        db=db_state,
        redis=redis_state,
        worker=worker_state,
        queue_backend=settings.queue_backend,
        worker_heartbeat_age_seconds=heartbeat_age,
        sandbox=sandbox_state,
    )


@api_router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@api_router.websocket("/research-runs/{run_id}/events")
async def run_events_ws(run_id: UUID, ws: WebSocket) -> None:
    stream = str(run_id)
    await ws_manager.connect_events(stream, ws)
    try:
        while True:
            await ws.receive_text()
    except Exception:
        await ws_manager.disconnect(stream, ws)


@api_router.websocket("/research-runs/{run_id}/status")
async def run_status_ws(run_id: UUID, ws: WebSocket) -> None:
    stream = str(run_id)
    await ws_manager.connect_status(stream, ws)
    try:
        while True:
            await ws.receive_text()
    except Exception:
        await ws_manager.disconnect(stream, ws)


@api_router.post("/internal/events")
async def internal_append_event(event: dict, db: Session = Depends(get_db)) -> dict:
    # Internal endpoint used by workers for event emission.
    request_counter.labels(endpoint="internal_event").inc()
    try:
        envelope = EventEnvelope(**event)
        row = append_event(db, envelope)
    except DuplicateEventError:
        return {"ok": True, "duplicate": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    event_data = {
        "event_id": row.event_id,
        "stream_id": row.stream_id,
        "event_type": row.event_type,
        "occurred_at": row.occurred_at.isoformat(),
        "payload": row.payload,
    }
    await ws_manager.broadcast_event(row.stream_id, event_data)

    if row.event_type in {
        "research_run_started",
        "research_run_paused",
        "research_run_resumed",
        "research_run_completed",
        "research_run_failed",
        "goal_progress_updated",
        "direction_recommended",
    }:
        await ws_manager.broadcast_status(
            row.stream_id,
            {
                "run_id": row.stream_id,
                "event_type": row.event_type,
                "payload": row.payload,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {"ok": True, "event_id": row.event_id}
