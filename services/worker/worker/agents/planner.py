from __future__ import annotations

from typing import Any
from uuid import uuid4

from ailab_domain.models import ChatMessage, ModelRequest

from worker.models.router import ModelRouter


class PlannerAgent:
    agent_id = "planner-agent"
    role = "planner"
    capabilities = ["propose_experiment", "prioritize_direction"]
    tool_access = ["model_inference"]

    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()

    def propose_experiment(
        self,
        run_id: str,
        goal: dict[str, Any],
        previous_scores: list[dict[str, Any]],
        cycle_index: int,
    ) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
        score_hint = previous_scores[-1]["recommendation"] if previous_scores else "continue"
        prompt = (
            "You are a research planner. Return a short hypothesis and method. "
            f"Goal: {goal['title']} - {goal['description']}. "
            f"Previous recommendation: {score_hint}. Cycle: {cycle_index}."
        )

        model_req = ModelRequest(
            provider="local",
            model="llama3.1",
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.2,
            max_tokens=120,
        )
        model_res = self.router.generate_sync(model_req)
        plan_text = model_res.output.strip()

        hypothesis = f"Cycle {cycle_index}: targeted probe on '{goal['title']}'"
        method = "Use python_exec to run a focused deterministic probe and compare outcome metrics."
        if plan_text:
            method = f"{method} Planner note: {plan_text[:200]}"

        experiment = {
            "experiment_id": str(uuid4()),
            "research_run_id": run_id,
            "goal_id": goal["id"],
            "hypothesis": hypothesis,
            "method": method,
            "tools_required": ["python_exec", "model_inference"],
            "parameters": {"cycle": cycle_index, "seed": cycle_index},
            "evaluation_method": "rule_and_model_hybrid",
        }
        reasoning = f"Proposed experiment with score hint '{score_hint}' for cycle {cycle_index}."

        model_call = {
            "provider": model_req.provider,
            "model": model_req.model,
            "request_payload": model_req.model_dump(),
            "response_payload": model_res.model_dump(),
            "token_usage": model_res.token_usage,
            "latency_ms": model_res.latency_ms,
            "provider_request_id": model_res.provider_request_id,
            "success": True,
        }

        return experiment, reasoning, model_call
