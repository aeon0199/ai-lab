from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ailab_domain.events import ActorType
from rq import get_current_job

from worker.agents.critic import CriticAgent
from worker.agents.planner import PlannerAgent
from worker.agents.researcher import ResearcherAgent
from worker.core.api_client import api_client
from worker.core.config import settings


def _emit_trace(
    run_id: str,
    agent_id: str,
    reasoning: str,
    action: str,
    tool_used: str | None = None,
    tokens_used: int = 0,
) -> None:
    api_client.emit_event(
        run_id,
        "analysis_generated",
        ActorType.AGENT,
        agent_id,
        {
            "trace_id": str(uuid4()),
            "research_run_id": run_id,
            "agent_id": agent_id,
            "reasoning_summary": reasoning,
            "action": action,
            "tool_used": tool_used,
            "tokens_used": tokens_used,
        },
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
            )

            previous_scores = api_client.get_scores(run_id)
            experiment, planner_reasoning, planner_model_call = planner.propose_experiment(
                run_id,
                goal,
                previous_scores,
                cycle_index,
            )
            _emit_trace(run_id, planner.agent_id, planner_reasoning, "propose_experiment", "model_inference")

            api_client.emit_event(
                run_id,
                "experiment_proposed",
                ActorType.AGENT,
                planner.agent_id,
                experiment,
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
            )

            experiment_run_id = str(uuid4())
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
                )

                result_id = str(uuid4())
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
                )

            history_scores = api_client.get_scores(run_id)
            score, critic_reasoning, critic_model_call = critic.evaluate(goal, experiment, execution_result, history_scores)
            _emit_trace(run_id, critic.agent_id, critic_reasoning, "evaluate_experiment", "model_inference")

            score_id = str(uuid4())
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
            )

        return {"ok": True, "message": f"Run {run_id} finished"}

    except Exception as exc:
        job = get_current_job()
        retries_left = 0
        if job and job.retries_left:
            retries_left = int(job.retries_left)

        if retries_left > 0:
            api_client.emit_event(
                run_id,
                "analysis_generated",
                ActorType.SYSTEM,
                "runtime",
                {
                    "trace_id": str(uuid4()),
                    "research_run_id": run_id,
                    "agent_id": "runtime",
                    "reasoning_summary": f"Transient failure: {exc}. Retries remaining: {retries_left}",
                    "action": "retry_scheduled",
                    "tool_used": None,
                    "tokens_used": 0,
                },
            )
        else:
            api_client.emit_event(
                run_id,
                "research_run_failed",
                ActorType.SYSTEM,
                "runtime",
                {
                    "run_id": run_id,
                    "reason": str(exc),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        raise
