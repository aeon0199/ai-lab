from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import requests
from ailab_domain.models import ChatMessage, ModelRequest
from ailab_policy.registry import DEFAULT_TOOL_REGISTRY

from worker.models.router import ModelRouter


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    artifact: dict[str, Any] | None = None
    model_call: dict[str, Any] | None = None


class PolicyError(Exception):
    pass


class SandboxToolRunner:
    def __init__(self, workspace_root: str, model_router: ModelRouter | None = None) -> None:
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.router = model_router or ModelRouter()

    def run(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        policy = DEFAULT_TOOL_REGISTRY.get(tool_name)
        if not policy:
            raise PolicyError(f"Unknown tool: {tool_name}")

        self._validate_schema(tool_name, params)

        if tool_name == "python_exec":
            return self._run_python(params["code"], policy.limits.timeout_seconds)
        if tool_name == "shell_exec":
            return self._run_shell(params["command"], policy.limits.timeout_seconds)
        if tool_name == "web_fetch":
            return self._run_web_fetch(params["url"], policy.network_allowlist, policy.limits.timeout_seconds)
        if tool_name == "dataset_read":
            return self._run_dataset_read(params["path"], policy.allowed_paths)
        if tool_name == "model_inference":
            return self._run_model_inference(params["request"])

        raise PolicyError(f"Unhandled tool: {tool_name}")

    def _validate_schema(self, tool_name: str, params: dict[str, Any]) -> None:
        schema = DEFAULT_TOOL_REGISTRY[tool_name].input_schema
        required = schema.get("required", [])
        for key in required:
            if key not in params:
                raise PolicyError(f"Missing required input '{key}' for {tool_name}")

    def _run_python(self, code: str, timeout: int) -> ToolResult:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PYTHONUNBUFFERED": "1"},
            )
            output = (proc.stdout + "\n" + proc.stderr).strip()
            return ToolResult(success=proc.returncode == 0, output=output, error=None if proc.returncode == 0 else output)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="python_exec timeout")

    def _run_shell(self, command: str, timeout: int) -> ToolResult:
        if len(command) > 2000:
            raise PolicyError("shell command too long")
        try:
            proc = subprocess.run(
                ["sh", "-lc", command],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PATH": os.getenv("PATH", "/usr/bin:/bin")},
            )
            output = (proc.stdout + "\n" + proc.stderr).strip()
            return ToolResult(success=proc.returncode == 0, output=output, error=None if proc.returncode == 0 else output)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="shell_exec timeout")

    def _run_web_fetch(self, url: str, allowlist: list[str], timeout: int) -> ToolResult:
        host = urlparse(url).hostname or ""
        if allowlist and host not in allowlist:
            raise PolicyError(f"Domain not allowlisted: {host}")
        res = requests.get(url, timeout=timeout)
        snippet = res.text[:2000]
        return ToolResult(success=res.ok, output=snippet, error=None if res.ok else f"HTTP {res.status_code}")

    def _run_dataset_read(self, path: str, allowed_paths: list[str]) -> ToolResult:
        full = (self.workspace_root / path).resolve()
        for allowed in allowed_paths:
            allowed_full = Path(allowed)
            if str(full).startswith(str(allowed_full)):
                data = full.read_text(encoding="utf-8")
                return ToolResult(success=True, output=data[:4000])

        raise PolicyError(f"Path not allowed: {path}")

    def _run_model_inference(self, request: dict[str, Any]) -> ToolResult:
        model_request = ModelRequest(
            provider=request.get("provider", "local"),
            model=request.get("model", "llama3.1"),
            messages=[ChatMessage(**m) for m in request.get("messages", [])],
            system=request.get("system"),
            tools=request.get("tools", []),
            temperature=request.get("temperature", 0.2),
            top_p=request.get("top_p", 1.0),
            max_tokens=request.get("max_tokens", 512),
            seed=request.get("seed"),
            timeout=request.get("timeout", 60),
        )
        response = self.router.generate_sync(model_request)
        payload = response.model_dump()
        return ToolResult(
            success=True,
            output=response.output,
            model_call={
                "provider": model_request.provider,
                "model": model_request.model,
                "request_payload": model_request.model_dump(),
                "response_payload": payload,
                "token_usage": response.token_usage,
                "latency_ms": response.latency_ms,
                "provider_request_id": response.provider_request_id,
                "success": True,
            },
        )


def create_artifact(research_run_id: str, experiment_run_id: str, content: str, suffix: str = "txt") -> dict[str, Any]:
    base = Path("/workspace/artifacts") / research_run_id
    base.mkdir(parents=True, exist_ok=True)
    artifact_path = base / f"{experiment_run_id}.{suffix}"
    artifact_path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    return {
        "id": str(uuid4()),
        "artifact_type": "text",
        "path": str(artifact_path),
        "checksum": digest,
        "size_bytes": artifact_path.stat().st_size,
    }
