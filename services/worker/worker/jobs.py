from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from ailab_domain.events import ActorType

try:
    from dramatiq.middleware import CurrentMessage
except Exception:  # pragma: no cover
    CurrentMessage = None  # type: ignore[assignment]

from worker.agents.critic import CriticAgent
from worker.agents.planner import PlannerAgent
from worker.agents.researcher import ResearcherAgent
from worker.core.api_client import api_client
from worker.core.config import settings
from worker.core.run_lock import acquire_run_lock


def _stable_uuid(*parts: object) -> str:
    seed = ":".join(str(part) for part in parts)
    return str(uuid5(NAMESPACE_URL, seed))


def _event_key(
    run_id: str,
    event_type: str,
    *,
    cycle_index: int | None = None,
    suffix: str | None = None,
) -> str:
    parts = ["run", run_id, event_type]
    if cycle_index is not None:
        parts.append(f"cycle-{cycle_index}")
    if suffix:
        parts.append(suffix)
    return ":".join(parts)


def _emit_trace(
    run_id: str,
    agent_id: str,
    reasoning: str,
    action: str,
    *,
    cycle_index: int | None = None,
    scope: str | None = None,
    tool_used: str | None = None,
    tokens_used: int = 0,
) -> None:
    trace_scope = scope or action
    api_client.emit_event(
        run_id,
        "analysis_generated",
        ActorType.AGENT,
        agent_id,
        {
            "trace_id": _stable_uuid(run_id, "trace", agent_id, trace_scope, cycle_index or "run"),
            "research_run_id": run_id,
            "agent_id": agent_id,
            "reasoning_summary": reasoning,
            "action": action,
            "tool_used": tool_used,
            "tokens_used": tokens_used,
        },
        idempotency_key=_event_key(
            run_id,
            "analysis_generated",
            cycle_index=cycle_index,
            suffix=f"{agent_id}:{trace_scope}",
        ),
    )


def _spawn_agents(run_id: str, planner: PlannerAgent, researcher: ResearcherAgent, critic: CriticAgent) -> None:
    for agent in [planner, researcher, critic]:
        api_client.emit_event(
            run_id,
            "agent_spawned",
            ActorType.SYSTEM,
            "runtime",
            {
                "agent_id": agent.agent_id,
                "role": agent.role,
                "capabilities": agent.capabilities,
                "tool_access": agent.tool_access,
            },
            idempotency_key=_event_key(run_id, "agent_spawned", suffix=agent.agent_id),
        )


def process_single_cycle(run_id: str) -> dict[str, Any]:
    return _process(run_id, max_cycles=1)


def process_research_run(run_id: str) -> dict[str, Any]:
    return _process(run_id, max_cycles=None)


def _process(run_id: str, max_cycles: int | None = None) -> dict[str, Any]:
    planner = PlannerAgent()
    critic = CriticAgent()

    run = api_client.get_run(run_id)
    if run["status"] not in {"running"}:
        return {"ok": True, "message": f"Run in status '{run['status']}', skipping"}

    goal = api_client.get_goal(run["goal_id"])
    researcher = ResearcherAgent(workspace_root=run.get("workspace_root") or "/workspace")

    _spawn_agents(run_id, planner, researcher, critic)

    budget_max = int(run.get("budget", {}).get("max_experiments", settings.max_cycles_default))
    config_max = int(run.get("config", {}).get("max_experiments", settings.max_cycles_default))
    default_max = min(budget_max, config_max)
    final_max = min(default_max, max_cycles) if max_cycles else default_max

    run_lock = acquire_run_lock(run_id)
    if run_lock is None:
        api_client.emit_event(
            run_id,
            "analysis_generated",
            ActorType.SYSTEM,
            "runtime",
            {
                "trace_id": _stable_uuid(run_id, "trace", "runtime", "run_lock_contention"),
                "research_run_id": run_id,
                "agent_id": "runtime",
                "reasoning_summary": "Skipped processing because another worker holds the run lock.",
                "action": "run_lock_contention",
                "tool_used": None,
                "tokens_used": 0,
            },
            idempotency_key=_event_key(run_id, "analysis_generated", suffix="runtime:run_lock_contention"),
        )
        return {"ok": True, "message": f"Run {run_id} is currently locked by another worker"}

    try:
        for cycle_index in range(1, final_max + 1):
            fresh_run = api_client.get_run(run_id)
            if fresh_run["status"] != "running":
                return {"ok": True, "message": f"Run stopped with status {fresh_run['status']}"}

            api_client.emit_event(
                run_id,
                "agent_cycle_started",
                ActorType.SYSTEM,
                "runtime",
                {
                    "run_id": run_id,
                    "cycle_index": cycle_index,
                    "agents": [planner.agent_id, researcher.agent_id, critic.agent_id],
                },
                idempotency_key=_event_key(run_id, "agent_cycle_started", cycle_index=cycle_index),
            )

            previous_scores = api_client.get_scores(run_id)
            experiment, planner_reasoning, planner_model_call = planner.propose_experiment(
                run_id,
                goal,
                previous_scores,
                cycle_index,
            )
            experiment["experiment_id"] = _stable_uuid(run_id, "experiment", cycle_index)
            _emit_trace(
                run_id,
                planner.agent_id,
                planner_reasoning,
                "propose_experiment",
                cycle_index=cycle_index,
                tool_used="model_inference",
            )

            api_client.emit_event(
                run_id,
                "experiment_proposed",
                ActorType.AGENT,
                planner.agent_id,
                experiment,
                idempotency_key=_event_key(run_id, "experiment_proposed", cycle_index=cycle_index),
            )

            api_client.emit_event(
                run_id,
                "experiment_approved_by_policy",
                ActorType.SYSTEM,
                "policy-engine",
                {
                    "experiment_id": experiment["experiment_id"],
                    "research_run_id": run_id,
                    "approved": True,
                    "reason": "all required tools in registry with policy constraints",
                },
                idempotency_key=_event_key(run_id, "experiment_approved_by_policy", cycle_index=cycle_index),
            )

            experiment_run_id = _stable_uuid(run_id, "experiment_run", cycle_index)
            api_client.emit_event(
                run_id,
                "experiment_run_queued",
                ActorType.SYSTEM,
                "runtime",
                {
                    "experiment_run_id": experiment_run_id,
                    "experiment_id": experiment["experiment_id"],
                    "research_run_id": run_id,
                    "parameters": experiment.get("parameters", {}),
                },
                idempotency_key=_event_key(run_id, "experiment_run_queued", cycle_index=cycle_index),
            )

            api_client.emit_event(
                run_id,
                "experiment_run_started",
                ActorType.SYSTEM,
                "runtime",
                {
                    "experiment_run_id": experiment_run_id,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                },
                idempotency_key=_event_key(run_id, "experiment_run_started", cycle_index=cycle_index),
            )

            api_client.emit_event(
                run_id,
                "tool_invocation_started",
                ActorType.TOOL,
                "tool-runner",
                {
                    "research_run_id": run_id,
                    "experiment_run_id": experiment_run_id,
                    "tools": experiment.get("tools_required", []),
                },
                idempotency_key=_event_key(run_id, "tool_invocation_started", cycle_index=cycle_index),
            )

            execution_result = researcher.execute_experiment(run_id, experiment_run_id, experiment)

            tool_payload: dict[str, Any] = {
                "research_run_id": run_id,
                "experiment_run_id": experiment_run_id,
                "success": execution_result["success"],
                "output_summary": execution_result["summary"],
                "artifact": execution_result.get("artifact"),
            }
            if execution_result.get("model_call"):
                tool_payload["model_call"] = execution_result["model_call"]
            if planner_model_call:
                tool_payload["planner_model_call"] = planner_model_call

            api_client.emit_event(
                run_id,
                "tool_invocation_finished",
                ActorType.TOOL,
                "tool-runner",
                tool_payload,
                idempotency_key=_event_key(run_id, "tool_invocation_finished", cycle_index=cycle_index),
            )

            if execution_result["success"]:
                api_client.emit_event(
                    run_id,
                    "experiment_run_completed",
                    ActorType.SYSTEM,
                    "runtime",
                    {
                        "experiment_run_id": experiment_run_id,
                        "metrics": execution_result["metrics"],
                        "result_summary": execution_result["summary"],
                        "logs": execution_result["logs"],
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                    },
                    idempotency_key=_event_key(run_id, "experiment_run_completed", cycle_index=cycle_index),
                )

                result_id = _stable_uuid(run_id, "result", cycle_index)
                api_client.emit_event(
                    run_id,
                    "result_recorded",
                    ActorType.AGENT,
                    researcher.agent_id,
                    {
                        "result_id": result_id,
                        "research_run_id": run_id,
                        "experiment_id": experiment["experiment_id"],
                        "experiment_run_id": experiment_run_id,
                        "metrics": execution_result["metrics"],
                        "artifacts": {"primary": execution_result["artifact"]},
                        "summary": execution_result["summary"],
                    },
                    idempotency_key=_event_key(run_id, "result_recorded", cycle_index=cycle_index),
                )
            else:
                api_client.emit_event(
                    run_id,
                    "experiment_run_failed",
                    ActorType.SYSTEM,
                    "runtime",
                    {
                        "experiment_run_id": experiment_run_id,
                        "error": execution_result.get("error", "unknown execution failure"),
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                    },
                    idempotency_key=_event_key(run_id, "experiment_run_failed", cycle_index=cycle_index),
                )

            history_scores = api_client.get_scores(run_id)
            score, critic_reasoning, critic_model_call = critic.evaluate(goal, experiment, execution_result, history_scores)
            _emit_trace(
                run_id,
                critic.agent_id,
                critic_reasoning,
                "evaluate_experiment",
                cycle_index=cycle_index,
                tool_used="model_inference",
            )

            score_id = _stable_uuid(run_id, "score", cycle_index)
            api_client.emit_event(
                run_id,
                "experiment_evaluated",
                ActorType.AGENT,
                critic.agent_id,
                {
                    "score_id": score_id,
                    "research_run_id": run_id,
                    "experiment_run_id": experiment_run_id,
                    **score,
                },
                idempotency_key=_event_key(run_id, "experiment_evaluated", cycle_index=cycle_index),
            )

            api_client.emit_event(
                run_id,
                "goal_progress_updated",
                ActorType.AGENT,
                critic.agent_id,
                {
                    "research_run_id": run_id,
                    "goal_id": goal["id"],
                    "goal_progress": score["goal_progress"],
                    "confidence": score["confidence"],
                },
                idempotency_key=_event_key(run_id, "goal_progress_updated", cycle_index=cycle_index),
            )

            recommendation_payload = {
                "research_run_id": run_id,
                "recommendation": score["recommendation"],
                "rationale": score["rationale"],
            }
            if critic_model_call:
                recommendation_payload["model_call"] = critic_model_call

            api_client.emit_event(
                run_id,
                "direction_recommended",
                ActorType.AGENT,
                critic.agent_id,
                recommendation_payload,
                idempotency_key=_event_key(run_id, "direction_recommended", cycle_index=cycle_index),
            )

            api_client.emit_event(
                run_id,
                "agent_cycle_finished",
                ActorType.SYSTEM,
                "runtime",
                {
                    "run_id": run_id,
                    "cycle_index": cycle_index,
                    "recommendation": score["recommendation"],
                    "goal_progress": score["goal_progress"],
                },
                idempotency_key=_event_key(run_id, "agent_cycle_finished", cycle_index=cycle_index),
            )

            if score["recommendation"] == "stop" and score["confidence"] >= settings.stop_confidence_threshold:
                api_client.emit_event(
                    run_id,
                    "research_run_completed",
                    ActorType.SYSTEM,
                    "runtime",
                    {
                        "run_id": run_id,
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                        "reason": "critic_stop_recommendation",
                    },
                    idempotency_key=_event_key(run_id, "research_run_completed", suffix="terminal"),
                )
                return {"ok": True, "message": f"Run {run_id} completed via critic recommendation"}

        final_run = api_client.get_run(run_id)
        if final_run["status"] == "running":
            api_client.emit_event(
                run_id,
                "research_run_completed",
                ActorType.SYSTEM,
                "runtime",
                {
                    "run_id": run_id,
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "max_cycles_reached",
                },
                idempotency_key=_event_key(run_id, "research_run_completed", suffix="terminal"),
            )

        return {"ok": True, "message": f"Run {run_id} finished"}

    except Exception as exc:
        retries = 0
        max_retries = settings.dramatiq_max_retries
        if CurrentMessage is not None:
            msg = CurrentMessage.get_current_message()
            if msg is not None:
                retries = int(msg.options.get("retries", 0))
                max_retries = int(msg.options.get("max_retries", settings.dramatiq_max_retries))
        attempts_used = retries + 1
        retries_left = max(0, max_retries - attempts_used)
        api_client.emit_event(
            run_id,
            "analysis_generated",
            ActorType.SYSTEM,
            "runtime",
            {
                "trace_id": _stable_uuid(run_id, "trace", "runtime", "dramatiq_retry", attempts_used),
                "research_run_id": run_id,
                "agent_id": "runtime",
                "reasoning_summary": (
                    f"Transient failure under Dramatiq: {exc}. "
                    f"Attempts used: {attempts_used}/{max_retries}"
                ),
                "action": "retry_scheduled" if retries_left > 0 else "retry_exhausted_pending_callback",
                "tool_used": None,
                "tokens_used": 0,
            },
            idempotency_key=_event_key(
                run_id,
                "analysis_generated",
                suffix=f"runtime:dramatiq_retry:{attempts_used}",
            ),
        )
        raise
    finally:
        run_lock.release()
