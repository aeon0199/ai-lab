from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from typing import Any

from ailab_domain.models import WorldStateModel


WorldState = dict[str, Any]


def initial_world_state(stream_id: str) -> WorldState:
    return {
        "stream_id": stream_id,
        "goals": {},
        "agents": {},
        "experiments": {},
        "experiment_runs": {},
        "results": {},
        "scores": [],
        "recommendations": [],
        "resources": {},
        "last_updated": datetime.utcnow().isoformat(),
    }


def apply_event(state: WorldState, event_type: str, payload: dict[str, Any], occurred_at: str | None = None) -> WorldState:
    next_state = deepcopy(state)

    if event_type == "goal_created":
        next_state["goals"][payload["goal_id"]] = {
            "title": payload["title"],
            "description": payload["description"],
            "status": "active",
        }

    elif event_type == "agent_spawned":
        next_state["agents"][payload["agent_id"]] = {
            "role": payload.get("role", "unknown"),
            "capabilities": payload.get("capabilities", []),
            "tool_access": payload.get("tool_access", []),
        }

    elif event_type == "experiment_proposed":
        next_state["experiments"][payload["experiment_id"]] = {
            "hypothesis": payload["hypothesis"],
            "method": payload["method"],
            "parameters": payload.get("parameters", {}),
            "evaluation_method": payload.get("evaluation_method", ""),
            "status": "proposed",
        }

    elif event_type == "experiment_run_queued":
        next_state["experiment_runs"][payload["experiment_run_id"]] = {
            "experiment_id": payload["experiment_id"],
            "status": "queued",
            "parameters": payload.get("parameters", {}),
            "logs": {},
        }

    elif event_type == "experiment_run_started":
        run = next_state["experiment_runs"].setdefault(payload["experiment_run_id"], {})
        run["status"] = "running"

    elif event_type == "experiment_run_completed":
        run = next_state["experiment_runs"].setdefault(payload["experiment_run_id"], {})
        run["status"] = "completed"
        run["metrics"] = payload.get("metrics", {})
        run["result_summary"] = payload.get("result_summary")

    elif event_type == "experiment_run_failed":
        run = next_state["experiment_runs"].setdefault(payload["experiment_run_id"], {})
        run["status"] = "failed"
        run["error"] = payload.get("error", "unknown")

    elif event_type == "result_recorded":
        next_state["results"][payload["result_id"]] = {
            "experiment_run_id": payload["experiment_run_id"],
            "metrics": payload.get("metrics", {}),
            "artifacts": payload.get("artifacts", {}),
            "summary": payload.get("summary", ""),
        }

    elif event_type == "experiment_evaluated":
        next_state["scores"].append(payload)

    elif event_type == "direction_recommended":
        next_state["recommendations"].append(payload)

    next_state["last_updated"] = occurred_at or datetime.utcnow().isoformat()
    return next_state


def reduce_events(stream_id: str, events: Iterable[dict[str, Any]], seed_state: WorldState | None = None) -> WorldState:
    state = deepcopy(seed_state) if seed_state else initial_world_state(stream_id)
    for event in events:
        state = apply_event(
            state,
            event_type=event["event_type"],
            payload=event["payload"],
            occurred_at=event.get("occurred_at"),
        )
    # Validate final reduced shape to prevent silent schema drift.
    return WorldStateModel.model_validate(state).model_dump()
