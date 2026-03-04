from pathlib import Path

import pytest
import requests

from worker.tools.sandbox import PolicyError, SandboxToolRunner


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


def test_sandbox_runner_uses_remote_execute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    def fake_post(url: str, json: dict, timeout: int):
        called["url"] = url
        called["json"] = json
        called["timeout"] = timeout
        return _FakeResponse(200, {"success": True, "output": "ok", "error": None})

    monkeypatch.setattr("worker.tools.sandbox.requests.post", fake_post)

    runner = SandboxToolRunner(
        workspace_root=str(tmp_path),
        sandbox_api_url="http://sandbox:8010",
        sandbox_required=True,
    )
    result = runner.run("python_exec", {"code": "print('hello')"})

    assert result.success is True
    assert result.output == "ok"
    assert called["url"] == "http://sandbox:8010/execute"
    assert called["json"] == {
        "tool_name": "python_exec",
        "params": {"code": "print('hello')"},
        "workspace_root": str(tmp_path),
    }


def test_sandbox_runner_surfaces_policy_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_post(url: str, json: dict, timeout: int):
        return _FakeResponse(400, {"detail": "Blocked shell pattern: rm -rf /"})

    monkeypatch.setattr("worker.tools.sandbox.requests.post", fake_post)

    runner = SandboxToolRunner(
        workspace_root=str(tmp_path),
        sandbox_api_url="http://sandbox:8010",
        sandbox_required=True,
    )

    with pytest.raises(PolicyError):
        runner.run("shell_exec", {"command": "rm -rf /"})


def test_sandbox_required_raises_when_unreachable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_post(url: str, json: dict, timeout: int):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr("worker.tools.sandbox.requests.post", fake_post)

    runner = SandboxToolRunner(
        workspace_root=str(tmp_path),
        sandbox_api_url="http://sandbox:8010",
        sandbox_required=True,
    )

    with pytest.raises(PolicyError):
        runner.run("python_exec", {"code": "print('x')"})
