from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import docker
import requests
from ailab_policy.registry import DEFAULT_TOOL_REGISTRY
from docker.errors import APIError, DockerException

from app.config import settings


class PolicyError(Exception):
    pass


class SandboxExecutionError(Exception):
    pass


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None


class SandboxExecutor:
    def __init__(self) -> None:
        self.client = docker.DockerClient(base_url=settings.docker_socket)

    def health(self) -> bool:
        try:
            self.client.ping()
            return True
        except DockerException:
            return False

    def execute(self, tool_name: str, params: dict[str, Any], workspace_root: str) -> ToolResult:
        policy = DEFAULT_TOOL_REGISTRY.get(tool_name)
        if not policy:
            raise PolicyError(f"Unknown tool: {tool_name}")
        self._validate_schema(tool_name, params)

        if tool_name == "python_exec":
            return self._run_python(params["code"], workspace_root)
        if tool_name == "shell_exec":
            return self._run_shell(params["command"], workspace_root)
        if tool_name == "web_fetch":
            return self._run_web_fetch(params["url"])
        if tool_name == "dataset_read":
            return self._run_dataset_read(params["path"], workspace_root)

        raise PolicyError(f"Unsupported tool in sandbox service: {tool_name}")

    def _validate_schema(self, tool_name: str, params: dict[str, Any]) -> None:
        schema = DEFAULT_TOOL_REGISTRY[tool_name].input_schema
        required = schema.get("required", [])
        for key in required:
            if key not in params:
                raise PolicyError(f"Missing required input '{key}' for {tool_name}")

    def _run_python(self, code: str, workspace_root: str) -> ToolResult:
        policy = DEFAULT_TOOL_REGISTRY["python_exec"]
        return self._run_container(
            command=["python", "-c", code],
            workspace_root=workspace_root,
            timeout=policy.limits.timeout_seconds,
            cpu_limit=policy.limits.cpu_limit,
            memory_limit=policy.limits.memory_limit,
            max_stdout_kb=policy.limits.max_stdout_kb,
            network_disabled=True,
        )

    def _run_shell(self, command: str, workspace_root: str) -> ToolResult:
        if len(command) > 2000:
            raise PolicyError("shell command too long")
        self._validate_shell_command(command)
        policy = DEFAULT_TOOL_REGISTRY["shell_exec"]
        return self._run_container(
            command=["sh", "-lc", command],
            workspace_root=workspace_root,
            timeout=policy.limits.timeout_seconds,
            cpu_limit=policy.limits.cpu_limit,
            memory_limit=policy.limits.memory_limit,
            max_stdout_kb=policy.limits.max_stdout_kb,
            network_disabled=True,
        )

    def _run_web_fetch(self, url: str) -> ToolResult:
        policy = DEFAULT_TOOL_REGISTRY["web_fetch"]
        host = (urlparse(url).hostname or "").lower()
        allowlist = [domain.lower() for domain in policy.network_allowlist]
        if allowlist and not any(host == domain or host.endswith(f".{domain}") for domain in allowlist):
            raise PolicyError(f"Domain not allowlisted: {host}")

        try:
            res = requests.get(url, timeout=policy.limits.timeout_seconds)
        except requests.RequestException as exc:
            return ToolResult(success=False, output="", error=f"web_fetch failed: {exc}")

        snippet = self._truncate_output(policy.limits.max_stdout_kb, res.text)
        if res.ok:
            return ToolResult(success=True, output=snippet)
        return ToolResult(success=False, output=snippet, error=f"HTTP {res.status_code}")

    def _run_dataset_read(self, relative_path: str, workspace_root: str) -> ToolResult:
        policy = DEFAULT_TOOL_REGISTRY["dataset_read"]
        root = self._resolve_workspace_root(workspace_root)
        candidate = (root / relative_path).resolve()
        if not str(candidate).startswith(str(root)):
            raise PolicyError(f"Dataset path escapes workspace: {relative_path}")

        allowed = False
        for allowed_path in policy.allowed_paths:
            resolved_allowed = Path(allowed_path).resolve()
            if str(candidate).startswith(str(resolved_allowed)):
                allowed = True
                break
        if not allowed:
            raise PolicyError(f"Path not allowed: {relative_path}")

        try:
            content = candidate.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, output="", error=f"dataset_read failed: {exc}")

        return ToolResult(success=True, output=self._truncate_output(policy.limits.max_stdout_kb, content))

    def _run_container(
        self,
        *,
        command: list[str],
        workspace_root: str,
        timeout: int,
        cpu_limit: str,
        memory_limit: str,
        max_stdout_kb: int,
        network_disabled: bool,
    ) -> ToolResult:
        workdir = self._container_workdir(workspace_root)
        self._ensure_workspace_dir(workdir)

        container = None
        try:
            container = self.client.containers.run(
                image=settings.sandbox_image,
                command=command,
                detach=True,
                remove=False,
                working_dir=workdir,
                user=settings.sandbox_user,
                network_disabled=network_disabled,
                mem_limit=memory_limit,
                nano_cpus=self._to_nano_cpus(cpu_limit),
                pids_limit=128,
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                read_only=False,
                environment={"PYTHONUNBUFFERED": "1"},
                volumes={settings.workspace_volume: {"bind": "/workspace", "mode": "rw"}},
            )
            wait_result = container.wait(timeout=timeout)
            logs = container.logs(stdout=True, stderr=True)
            output = self._truncate_output(max_stdout_kb, logs.decode("utf-8", errors="replace"))
            exit_code = int(wait_result.get("StatusCode", 1))
            if exit_code == 0:
                return ToolResult(success=True, output=output)
            return ToolResult(success=False, output=output, error=output or f"container exited {exit_code}")
        except requests.exceptions.ReadTimeout:
            if container is not None:
                try:
                    container.kill()
                except APIError:
                    pass
            return ToolResult(success=False, output="", error="sandbox timeout")
        except (DockerException, APIError) as exc:
            raise SandboxExecutionError(f"Sandbox execution failed: {exc}") from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError:
                    pass

    def _resolve_workspace_root(self, workspace_root: str) -> Path:
        rel = self._workspace_relative(workspace_root)
        root = (Path("/workspace") / rel).resolve()
        if not str(root).startswith(str(Path("/workspace").resolve())):
            raise PolicyError(f"Workspace root escapes allowed mount: {workspace_root}")
        return root

    def _container_workdir(self, workspace_root: str) -> str:
        rel = self._workspace_relative(workspace_root)
        clean = str(rel).strip("/")
        if not clean:
            return "/workspace"
        return f"/workspace/{clean}"

    def _workspace_relative(self, workspace_root: str) -> PurePosixPath:
        path = PurePosixPath(workspace_root)
        if not path.is_absolute():
            raise PolicyError(f"workspace_root must be absolute: {workspace_root}")
        if path == PurePosixPath("/"):
            raise PolicyError("workspace_root cannot be /")
        raw = str(path)
        if not raw.startswith("/workspace"):
            raise PolicyError(f"workspace_root must stay under /workspace: {workspace_root}")
        suffix = raw[len("/workspace") :]
        if suffix and not suffix.startswith("/"):
            raise PolicyError(f"workspace_root must stay under /workspace: {workspace_root}")
        rel = PurePosixPath(suffix.lstrip("/"))
        if ".." in rel.parts:
            raise PolicyError(f"workspace_root cannot traverse upward: {workspace_root}")
        return rel

    def _ensure_workspace_dir(self, workdir: str) -> None:
        host_path = Path(workdir)
        host_path.mkdir(parents=True, exist_ok=True)

    def _truncate_output(self, max_stdout_kb: int, output: str) -> str:
        max_chars = max_stdout_kb * 1024
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

    def _to_nano_cpus(self, cpu_limit: str) -> int:
        try:
            return max(100_000_000, int(float(cpu_limit) * 1_000_000_000))
        except ValueError:
            return 1_000_000_000
