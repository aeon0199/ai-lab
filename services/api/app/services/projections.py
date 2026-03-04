from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db import models


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def apply_projection_event(db: Session, event_type: str, payload: dict[str, Any]) -> None:
    if event_type == "goal_created":
        goal = models.GoalModel(
            id=payload["goal_id"],
            title=payload["title"],
            description=payload["description"],
            status="active",
        )
        db.merge(goal)

    elif event_type == "research_run_created":
        run = models.ResearchRunModel(
            id=payload["run_id"],
            goal_id=payload["goal_id"],
            status="queued",
            config=payload.get("config", {}),
            budget=payload.get("budget", {}),
            workspace_root=payload.get("workspace_root", "/workspace"),
        )
        db.merge(run)

    elif event_type == "research_run_started":
        run = db.get(models.ResearchRunModel, payload["run_id"])
        if run:
            run.status = "running"
            run.started_at = _iso_to_dt(payload.get("started_at")) or datetime.now(timezone.utc)

    elif event_type == "research_run_paused":
        run = db.get(models.ResearchRunModel, payload["run_id"])
        if run:
            run.status = "paused"

    elif event_type == "research_run_resumed":
        run = db.get(models.ResearchRunModel, payload["run_id"])
        if run:
            run.status = "running"

    elif event_type == "research_run_completed":
        run = db.get(models.ResearchRunModel, payload["run_id"])
        if run:
            run.status = "completed"
            run.ended_at = _iso_to_dt(payload.get("ended_at")) or datetime.now(timezone.utc)

    elif event_type == "research_run_failed":
        run = db.get(models.ResearchRunModel, payload["run_id"])
        if run:
            reason = payload.get("reason", "unknown")
            run.status = "cancelled" if "cancel" in reason.lower() else "failed"
            run.failure_reason = reason
            run.ended_at = _iso_to_dt(payload.get("ended_at")) or datetime.now(timezone.utc)

    elif event_type == "experiment_proposed":
        experiment = models.ExperimentModel(
            id=payload["experiment_id"],
            research_run_id=payload["research_run_id"],
            goal_reference=payload["goal_id"],
            hypothesis=payload["hypothesis"],
            method=payload["method"],
            tools_required=payload.get("tools_required", []),
            parameters=payload.get("parameters", {}),
            evaluation_method=payload.get("evaluation_method", "rule_and_model"),
        )
        db.merge(experiment)

    elif event_type == "experiment_run_queued":
        er = models.ExperimentRunModel(
            id=payload["experiment_run_id"],
            experiment_id=payload["experiment_id"],
            research_run_id=payload["research_run_id"],
            status="queued",
            parameters=payload.get("parameters", {}),
            logs={},
            metrics={},
        )
        db.merge(er)

    elif event_type == "experiment_run_started":
        er = db.get(models.ExperimentRunModel, payload["experiment_run_id"])
        if er:
            er.status = "running"
            er.started_at = _iso_to_dt(payload.get("started_at")) or datetime.now(timezone.utc)

    elif event_type == "experiment_run_completed":
        er = db.get(models.ExperimentRunModel, payload["experiment_run_id"])
        if er:
            er.status = "completed"
            er.result_summary = payload.get("result_summary", "")
            er.metrics = payload.get("metrics", {})
            er.logs = payload.get("logs", {})
            er.ended_at = _iso_to_dt(payload.get("ended_at")) or datetime.now(timezone.utc)

    elif event_type == "experiment_run_failed":
        er = db.get(models.ExperimentRunModel, payload["experiment_run_id"])
        if er:
            er.status = "failed"
            er.logs = {"error": payload.get("error", "unknown")}
            er.ended_at = _iso_to_dt(payload.get("ended_at")) or datetime.now(timezone.utc)

    elif event_type == "result_recorded":
        result = models.ResultModel(
            id=payload["result_id"],
            experiment_run_id=payload["experiment_run_id"],
            experiment_id=payload["experiment_id"],
            research_run_id=payload["research_run_id"],
            metrics=payload.get("metrics", {}),
            artifacts=payload.get("artifacts", {}),
            summary=payload.get("summary", ""),
        )
        db.merge(result)

    elif event_type == "analysis_generated":
        trace = models.AgentTraceModel(
            id=payload["trace_id"],
            research_run_id=payload["research_run_id"],
            agent_id=payload["agent_id"],
            reasoning_summary=payload.get("reasoning_summary", ""),
            action=payload.get("action", "analyze"),
            tool_used=payload.get("tool_used"),
            tokens_used=payload.get("tokens_used", 0),
        )
        db.merge(trace)

    elif event_type == "experiment_evaluated":
        score = models.EvaluatorScoreModel(
            id=payload["score_id"],
            research_run_id=payload["research_run_id"],
            experiment_run_id=payload["experiment_run_id"],
            goal_progress=payload["goal_progress"],
            experiment_quality=payload["experiment_quality"],
            novelty=payload["novelty"],
            confidence=payload["confidence"],
            recommendation=payload["recommendation"],
            rationale=payload.get("rationale", ""),
        )
        db.merge(score)

    elif event_type == "tool_invocation_finished":
        artifact = payload.get("artifact")
        if artifact:
            record = models.ArtifactIndexModel(
                id=artifact["id"],
                experiment_run_id=payload["experiment_run_id"],
                research_run_id=payload["research_run_id"],
                artifact_type=artifact["artifact_type"],
                path=artifact["path"],
                checksum=artifact.get("checksum", "na"),
                size_bytes=artifact.get("size_bytes", 0),
            )
            db.merge(record)

        model_call = payload.get("model_call")
        if model_call:
            call = models.ModelCallModel(
                id=str(uuid4()),
                research_run_id=payload["research_run_id"],
                experiment_run_id=payload.get("experiment_run_id"),
                provider=model_call.get("provider", "unknown"),
                model=model_call.get("model", "unknown"),
                request_payload=model_call.get("request_payload", {}),
                response_payload=model_call.get("response_payload", {}),
                token_usage=model_call.get("token_usage", {}),
                latency_ms=model_call.get("latency_ms", 0),
                provider_request_id=model_call.get("provider_request_id"),
                success=model_call.get("success", True),
                error=model_call.get("error"),
            )
            db.add(call)

        planner_model_call = payload.get("planner_model_call")
        if planner_model_call:
            call = models.ModelCallModel(
                id=str(uuid4()),
                research_run_id=payload["research_run_id"],
                experiment_run_id=payload.get("experiment_run_id"),
                provider=planner_model_call.get("provider", "unknown"),
                model=planner_model_call.get("model", "unknown"),
                request_payload=planner_model_call.get("request_payload", {}),
                response_payload=planner_model_call.get("response_payload", {}),
                token_usage=planner_model_call.get("token_usage", {}),
                latency_ms=planner_model_call.get("latency_ms", 0),
                provider_request_id=planner_model_call.get("provider_request_id"),
                success=planner_model_call.get("success", True),
                error=planner_model_call.get("error"),
            )
            db.add(call)

    elif event_type == "world_state_snapshot_created":
        snapshot = models.WorldStateSnapshotModel(
            stream_id=payload["stream_id"],
            last_event_id=payload["last_event_id"],
            snapshot_payload=payload["snapshot_payload"],
        )
        db.add(snapshot)

    db.flush()
