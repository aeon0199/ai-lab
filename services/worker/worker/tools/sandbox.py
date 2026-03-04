from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import resource
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
    def __init__(
        self,
        workspace_root: str,
        model_router: ModelRouter | None = None,
        sandbox_api_url: str | None = None,
        sandbox_required: bool = True,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.router = model_router or ModelRouter()
        self.sandbox_api_url = (sandbox_api_url or os.getenv("SANDBOX_API_URL", "http://localhost:8010")).rstrip("/")
        self.sandbox_required = sandbox_required

    def run(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        policy = DEFAULT_TOOL_REGISTRY.get(tool_name)
        if not policy:
            raise PolicyError(f"Unknown tool: {tool_name}")

        self._validate_schema(tool_name, params)

        if tool_name == "model_inference":
            return self._run_model_inference(params["request"])

        remote = self._run_remote(tool_name, params, timeout=policy.limits.timeout_seconds)
        if remote is not None:
            return remote

        if self.sandbox_required:
            raise PolicyError("Sandbox unavailable and SANDBOX_REQUIRED=true")

        if tool_name == "python_exec":
            return self._run_python_local(params["code"], policy.limits.timeout_seconds)
        if tool_name == "shell_exec":
            return self._run_shell_local(params["command"], policy.limits.timeout_seconds)
        if tool_name == "web_fetch":
            return self._run_web_fetch_local(params["url"], policy.network_allowlist, policy.limits.timeout_seconds)
        if tool_name == "dataset_read":
            return self._run_dataset_read_local(params["path"], policy.allowed_paths)

        raise PolicyError(f"Unhandled tool: {tool_name}")

    def _run_remote(self, tool_name: str, params: dict[str, Any], timeout: int) -> ToolResult | None:
        if not self.sandbox_api_url:
            return None

        try:
            res = requests.post(
                f"{self.sandbox_api_url}/execute",
                json={
                    "tool_name": tool_name,
                    "params": params,
                    "workspace_root": str(self.workspace_root),
                },
                timeout=timeout + 10,
            )
        except requests.RequestException:
            return None

        if res.status_code >= 400:
            detail: str
            try:
                detail = res.json().get("detail", res.text)
            except ValueError:
                detail = res.text
            raise PolicyError(f"Sandbox rejected {tool_name}: {detail}")

        payload = res.json()
        return ToolResult(
            success=bool(payload.get("success", False)),
            output=str(payload.get("output", "")),
            error=payload.get("error"),
            artifact=payload.get("artifact"),
            model_call=payload.get("model_call"),
        )

    def _validate_schema(self, tool_name: str, params: dict[str, Any]) -> None:
        schema = DEFAULT_TOOL_REGISTRY[tool_name].input_schema
        required = schema.get("required", [])
        for key in required:
            if key not in params:
                raise PolicyError(f"Missing required input '{key}' for {tool_name}")

    # Legacy local fallback paths (used only when SANDBOX_REQUIRED=false).
    def _run_python_local(self, code: str, timeout: int) -> ToolResult:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PYTHONUNBUFFERED": "1"},
                preexec_fn=lambda: self._set_rlimits(
                    cpu_seconds=timeout,
                    memory_limit=DEFAULT_TOOL_REGISTRY["python_exec"].limits.memory_limit,
                ),
            )
            output = self._truncate_output("python_exec", (proc.stdout + "\n" + proc.stderr).strip())
            return ToolResult(success=proc.returncode == 0, output=output, error=None if proc.returncode == 0 else output)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="python_exec timeout")

    def _run_shell_local(self, command: str, timeout: int) -> ToolResult:
        if len(command) > 2000:
            raise PolicyError("shell command too long")
        self._validate_shell_command(command)
        try:
            proc = subprocess.run(
                ["sh", "-lc", command],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PATH": os.getenv("PATH", "/usr/bin:/bin")},
                preexec_fn=lambda: self._set_rlimits(
                    cpu_seconds=timeout,
                    memory_limit=DEFAULT_TOOL_REGISTRY["shell_exec"].limits.memory_limit,
                ),
            )
            output = self._truncate_output("shell_exec", (proc.stdout + "\n" + proc.stderr).strip())
            return ToolResult(success=proc.returncode == 0, output=output, error=None if proc.returncode == 0 else output)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="shell_exec timeout")

    def _run_web_fetch_local(self, url: str, allowlist: list[str], timeout: int) -> ToolResult:
        host = (urlparse(url).hostname or "").lower()
        allowlist = [domain.lower() for domain in allowlist]
        if allowlist and not any(host == domain or host.endswith(f".{domain}") for domain in allowlist):
            raise PolicyError(f"Domain not allowlisted: {host}")
        res = requests.get(url, timeout=timeout)
        snippet = self._truncate_output("web_fetch", res.text)
        return ToolResult(success=res.ok, output=snippet, error=None if res.ok else f"HTTP {res.status_code}")

    def _run_dataset_read_local(self, path: str, allowed_paths: list[str]) -> ToolResult:
        full = (self.workspace_root / path).resolve()
        if not str(full).startswith(str(self.workspace_root.resolve())):
            raise PolicyError(f"Dataset path escapes workspace: {path}")

        for allowed in allowed_paths:
            allowed_full = Path(allowed).resolve()
            if str(full).startswith(str(allowed_full)):
                data = full.read_text(encoding="utf-8")
                return ToolResult(success=True, output=self._truncate_output("dataset_read", data))

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

    def _truncate_output(self, tool_name: str, output: str) -> str:
        policy = DEFAULT_TOOL_REGISTRY[tool_name]
        max_chars = policy.limits.max_stdout_kb * 1024
        if len(output) <= max_chars:
            return output
        return output[:max_chars] + "\n[truncated]"

    def _validate_shell_command(self, command: str) -> None:
        normalized = command.lower()
        blocked_patterns = [
            "rm -rf /",
            "shutdown",
            "reboot",
            "mkfs",
            ":(){:|:&};:",
            "dd if=",
            "chmod 777 /",
        ]
        for pattern in blocked_patterns:
            if pattern in normalized:
                raise PolicyError(f"Blocked shell pattern: {pattern}")

    def _set_rlimits(self, cpu_seconds: int, memory_limit: str) -> None:
        mem_bytes = self._parse_memory_limit(memory_limit)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (5 * 1024 * 1024, 5 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))

    def _parse_memory_limit(self, value: str) -> int:
        raw = value.strip().lower()
        multipliers = {"k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}
        if raw[-1:] in multipliers:
            return int(float(raw[:-1]) * multipliers[raw[-1]])
        return int(raw)


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
