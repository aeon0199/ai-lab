from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import worker.jobs as jobs


@dataclass
class _FakeLock:
    released: bool = False

    def release(self) -> None:
        self.released = True


class _FakePlanner:
    agent_id = "planner-agent"
    role = "planner"
    capabilities = ["propose_experiment"]
    tool_access = ["model_inference"]

    def propose_experiment(
        self,
        run_id: str,
        goal: dict[str, Any],
        previous_scores: list[dict[str, Any]],
        cycle_index: int,
    ) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
        return (
            {
                "experiment_id": "placeholder",
                "research_run_id": run_id,
                "goal_id": goal["id"],
                "hypothesis": f"cycle-{cycle_index}-hypothesis",
                "method": "execute deterministic test code",
                "tools_required": ["python_exec"],
                "parameters": {"cycle": cycle_index, "python_code": "print('ok')"},
                "evaluation_method": "rule_and_model_hybrid",
            },
            "planner reasoning",
            None,
        )


class _FakeResearcher:
    agent_id = "researcher-agent"
    role = "researcher"
    capabilities = ["execute_experiment"]
    tool_access = ["python_exec"]

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root

    def execute_experiment(self, run_id: str, experiment_run_id: str, experiment: dict[str, Any]) -> dict[str, Any]:
        return {
            "metrics": {
                "goal_progress": 0.72,
                "experiment_quality": 0.74,
                "novelty": 0.66,
                "confidence_signal": 0.71,
            },
            "summary": "synthetic success",
            "logs": {"python_exec": "ok"},
            "artifact": {
                "id": "artifact-1",
                "artifact_type": "text",
                "path": "/workspace/runs/r1/artifact.txt",
                "checksum": "abc",
                "size_bytes": 5,
            },
            "model_call": None,
            "success": True,
            "error": None,
        }


class _FakeCritic:
    agent_id = "critic-agent"
    role = "critic"
    capabilities = ["evaluate_experiment"]
    tool_access = ["model_inference"]

    def __init__(self, recommendation: str = "continue", confidence: float = 0.71) -> None:
        self._recommendation = recommendation
        self._confidence = confidence

    def evaluate(
        self,
        goal: dict[str, Any],
        experiment: dict[str, Any],
        result: dict[str, Any],
        history_scores: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
        score = {
            "goal_progress": 0.72,
            "experiment_quality": 0.74,
            "novelty": 0.66,
            "confidence": self._confidence,
            "recommendation": self._recommendation,
            "rationale": "good enough",
        }
        return score, "critic reasoning", None


class _FakeAPIClient:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []

    def get_run(self, run_id: str) -> dict[str, Any]:
        return {
            "id": run_id,
            "goal_id": "goal-1",
            "status": "running",
            "workspace_root": "/workspace",
            "budget": {"max_experiments": 1},
            "config": {"max_experiments": 1},
        }

    def get_goal(self, goal_id: str) -> dict[str, Any]:
        return {"id": goal_id, "title": "Goal", "description": "Test goal"}

    def get_scores(self, run_id: str) -> list[dict[str, Any]]:
        return list(self.scores)

    def emit_event(
        self,
        run_id: str,
        event_type: str,
        actor_type: Any,
        actor_id: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self.events.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "actor_id": actor_id,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
        )
        if event_type == "experiment_evaluated":
            self.scores.append(
                {
                    "goal_progress": payload["goal_progress"],
                    "recommendation": payload["recommendation"],
                }
            )


def _setup_job_runtime(monkeypatch, *, recommendation: str = "continue", confidence: float = 0.71) -> _FakeAPIClient:
    fake_api = _FakeAPIClient()
    fake_lock = _FakeLock()
    monkeypatch.setattr(jobs, "api_client", fake_api)
    monkeypatch.setattr(jobs, "PlannerAgent", _FakePlanner)
    monkeypatch.setattr(jobs, "ResearcherAgent", _FakeResearcher)
    monkeypatch.setattr(jobs, "CriticAgent", lambda: _FakeCritic(recommendation, confidence))
    monkeypatch.setattr(jobs, "acquire_run_lock", lambda run_id: fake_lock)
    return fake_api


def test_single_cycle_emits_deterministic_idempotency_keys(monkeypatch) -> None:
    run_id = "00000000-0000-0000-0000-000000000111"

    fake_api_a = _setup_job_runtime(monkeypatch, recommendation="continue", confidence=0.71)
    result_a = jobs.process_single_cycle(run_id)
    keys_a = [event["idempotency_key"] for event in fake_api_a.events]

    fake_api_b = _setup_job_runtime(monkeypatch, recommendation="continue", confidence=0.71)
    result_b = jobs.process_single_cycle(run_id)
    keys_b = [event["idempotency_key"] for event in fake_api_b.events]

    assert result_a["ok"] is True
    assert result_b["ok"] is True
    assert keys_a == keys_b
    assert all(key for key in keys_a)
    assert any(key.endswith("experiment_proposed:cycle-1") for key in keys_a)
    assert any(key.endswith("experiment_evaluated:cycle-1") for key in keys_a)


def test_critic_stop_recommendation_completes_run(monkeypatch) -> None:
    run_id = "00000000-0000-0000-0000-000000000222"
    fake_api = _setup_job_runtime(monkeypatch, recommendation="stop", confidence=0.97)

    result = jobs.process_single_cycle(run_id)

    completion_events = [e for e in fake_api.events if e["event_type"] == "research_run_completed"]
    assert result["ok"] is True
    assert "critic recommendation" in result["message"]
    assert len(completion_events) == 1
    assert completion_events[0]["payload"]["reason"] == "critic_stop_recommendation"
