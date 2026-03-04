from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from worker.tools.sandbox import SandboxToolRunner, ToolResult, create_artifact
from worker.core.config import settings


class ResearcherAgent:
    agent_id = "researcher-agent"
    role = "researcher"
    capabilities = ["execute_experiment", "analyze_result"]
    tool_access = ["python_exec", "shell_exec", "web_fetch", "model_inference", "dataset_read"]

    def __init__(self, workspace_root: str) -> None:
        self.runner = SandboxToolRunner(
            workspace_root=workspace_root,
            sandbox_api_url=settings.sandbox_api_url,
            sandbox_required=settings.sandbox_required,
        )

    def execute_experiment(self, run_id: str, experiment_run_id: str, experiment: dict[str, Any]) -> dict[str, Any]:
        parameters = experiment.get("parameters", {})
        cycle = int(parameters.get("cycle", 1))
        python_code = parameters.get("python_code") or (
            "import json\n"
            f"cycle = {cycle}\n"
            "print(json.dumps({\"quality\": 0.5 + (cycle * 0.02), \"goal_progress\": 0.45 + (cycle * 0.03), \"confidence\": 0.6}))\n"
        )

        python_result = self.runner.run("python_exec", {"code": python_code})
        extracted_metrics = _extract_metrics_from_output(python_result.output)

        model_result: ToolResult = self.runner.run(
            "model_inference",
            {
                "request": {
                    "provider": settings.researcher_provider,
                    "model": settings.researcher_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Summarize the experiment outcome in one concise sentence. "
                                f"Hypothesis: {experiment['hypothesis']}. Output: {python_result.output[:1200]}"
                            ),
                        }
                    ],
                    "temperature": settings.researcher_temperature,
                    "max_tokens": settings.researcher_max_tokens,
                }
            },
        )

        quality = _clamp(float(extracted_metrics.get("quality", extracted_metrics.get("experiment_quality", 0.5))))
        goal_progress = _clamp(float(extracted_metrics.get("goal_progress", 0.5)))
        confidence = _clamp(float(extracted_metrics.get("confidence", extracted_metrics.get("confidence_signal", 0.6))))

        novelty = _estimate_novelty(experiment, python_result.output)
        goal_progress_delta = round(goal_progress - 0.5, 4)

        metrics = {
            "goal_progress_delta": goal_progress_delta,
            "goal_progress": round(goal_progress, 4),
            "experiment_quality": round(quality, 4),
            "novelty": round(novelty, 4),
            "confidence_signal": round(confidence, 4),
            "tool_success_rate": 1.0 if python_result.success and model_result.success else 0.5,
            "raw_metric_count": len(extracted_metrics),
        }
        for key, value in extracted_metrics.items():
            if key not in metrics and isinstance(value, (int, float)):
                metrics[key] = round(float(value), 6)

        summary = (
            f"Experiment finished at {datetime.now(timezone.utc).isoformat()}. "
            f"python_exec={'ok' if python_result.success else 'fail'}; "
            f"model_inference={'ok' if model_result.success else 'fail'}."
        )

        artifact = create_artifact(run_id, experiment_run_id, f"{python_result.output}\n\n{model_result.output}")

        return {
            "metrics": metrics,
            "summary": summary,
            "logs": {
                "python_exec": python_result.output,
                "model_inference": model_result.output,
            },
            "artifact": artifact,
            "model_call": model_result.model_call,
            "success": python_result.success and model_result.success,
            "error": python_result.error or model_result.error,
        }


def _extract_metrics_from_output(output: str) -> dict[str, float]:
    if not output:
        return {}

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    # Look for JSON metrics from the last valid JSON object line.
    for line in reversed(lines):
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        result: dict[str, float] = {}
        for key, value in payload.items():
            if isinstance(value, (int, float)):
                result[key] = float(value)
        if result:
            return result
    return {}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _estimate_novelty(experiment: dict[str, Any], python_output: str) -> float:
    basis = f"{experiment.get('hypothesis', '')}|{experiment.get('method', '')}|{python_output[:500]}"
    unique_chars = len(set(basis))
    scaled = unique_chars / 80.0
    return _clamp(scaled)
