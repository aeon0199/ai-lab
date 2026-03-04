from worker.agents.planner import _extract_plan_json
from worker.agents.researcher import _extract_metrics_from_output


def test_extract_plan_json_from_fenced_block():
    text = """```json
{"hypothesis":"h","method":"m","python_code":"print(1)"}
```"""
    parsed = _extract_plan_json(text)
    assert parsed["hypothesis"] == "h"
    assert parsed["method"] == "m"


def test_extract_metrics_from_output_prefers_last_json_line():
    output = "some log\n{\"quality\":0.1}\n{\"quality\":0.8,\"goal_progress\":0.7,\"confidence\":0.6}\n"
    metrics = _extract_metrics_from_output(output)
    assert metrics["quality"] == 0.8
    assert metrics["goal_progress"] == 0.7
    assert metrics["confidence"] == 0.6
