from __future__ import annotations

from datetime import datetime, timezone
from random import Random
from typing import Any

from worker.tools.sandbox import SandboxToolRunner, ToolResult, create_artifact


class ResearcherAgent:
    agent_id = "researcher-agent"
    role = "researcher"
    capabilities = ["execute_experiment", "analyze_result"]
    tool_access = ["python_exec", "shell_exec", "web_fetch", "model_inference", "dataset_read"]

    def __init__(self, workspace_root: str) -> None:
        self.runner = SandboxToolRunner(workspace_root=workspace_root)

    def execute_experiment(self, run_id: str, experiment_run_id: str, experiment: dict[str, Any]) -> dict[str, Any]:
        cycle = int(experiment.get("parameters", {}).get("cycle", 1))

        probe_code = (
            "import math\n"
            f"x = {cycle}\n"
            "score = 0.5 + (math.sin(x) + 1) / 4\n"
            "print(f'probe_score={score:.4f}')\n"
        )

        python_result = self.runner.run("python_exec", {"code": probe_code})

        model_result: ToolResult = self.runner.run(
            "model_inference",
            {
                "request": {
                    "provider": "local",
                    "model": "llama3.1",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Summarize this experiment hypothesis in one sentence: {experiment['hypothesis']}",
                        }
                    ],
                    "temperature": 0.2,
                    "max_tokens": 80,
                }
            },
        )

        rng = Random(cycle)
        novelty = min(1.0, 0.2 + rng.random() * 0.7)
        quality = 0.4 + rng.random() * 0.5
        progress = (novelty * 0.5) + (quality * 0.5)

        metrics = {
            "goal_progress_delta": round(progress - 0.5, 4),
            "experiment_quality": round(quality, 4),
            "novelty": round(novelty, 4),
            "confidence_signal": round(0.55 + rng.random() * 0.4, 4),
            "tool_success_rate": 1.0 if python_result.success and model_result.success else 0.5,
        }

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
