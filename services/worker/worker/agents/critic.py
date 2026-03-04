from __future__ import annotations

from typing import Any

from ailab_domain.models import ChatMessage, ModelRequest

from worker.models.router import ModelRouter


class CriticAgent:
    agent_id = "critic-agent"
    role = "critic"
    capabilities = ["evaluate_experiment", "recommend_direction"]
    tool_access = ["model_inference"]

    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()

    def evaluate(
        self,
        goal: dict[str, Any],
        experiment: dict[str, Any],
        result: dict[str, Any],
        history_scores: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
        metrics = result["metrics"]
        goal_progress = max(0.0, min(1.0, 0.5 + metrics.get("goal_progress_delta", 0.0)))
        quality = max(0.0, min(1.0, metrics.get("experiment_quality", 0.0)))
        novelty = max(0.0, min(1.0, metrics.get("novelty", 0.0)))

        if history_scores:
            previous = history_scores[-1]["goal_progress"]
            if abs(previous - goal_progress) < 0.01:
                novelty = max(0.0, novelty - 0.2)

        confidence = max(0.0, min(1.0, metrics.get("confidence_signal", 0.6)))
        recommendation = "continue"
        if quality < 0.45 or novelty < 0.2:
            recommendation = "pivot"
        if confidence > 0.92 and goal_progress > 0.78:
            recommendation = "stop"

        prompt = (
            "You are a research critic. Give one concise rationale sentence. "
            f"Goal: {goal['title']}. Hypothesis: {experiment['hypothesis']}. "
            f"Metrics: {metrics}. Recommendation: {recommendation}."
        )
        req = ModelRequest(
            provider="local",
            model="llama3.1",
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.2,
            max_tokens=80,
        )
        res = self.router.generate_sync(req)
        rationale = res.output[:240] if res.output else "Rule-based critic recommendation"

        score = {
            "goal_progress": round(goal_progress, 4),
            "experiment_quality": round(quality, 4),
            "novelty": round(novelty, 4),
            "confidence": round(confidence, 4),
            "recommendation": recommendation,
            "rationale": rationale,
        }
        reasoning = f"Critic set recommendation={recommendation} with confidence={confidence:.2f}."

        model_call = {
            "provider": req.provider,
            "model": req.model,
            "request_payload": req.model_dump(),
            "response_payload": res.model_dump(),
            "token_usage": res.token_usage,
            "latency_ms": res.latency_ms,
            "provider_request_id": res.provider_request_id,
            "success": True,
        }

        return score, reasoning, model_call
