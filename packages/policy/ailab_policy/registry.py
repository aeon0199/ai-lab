from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceLimits(BaseModel):
    timeout_seconds: int = 300
    cpu_limit: str = "1"
    memory_limit: str = "512m"
    max_stdout_kb: int = 256
    retries: int = 1


class ToolPolicy(BaseModel):
    name: str
    description: str
    input_schema: dict
    allowed_paths: list[str] = Field(default_factory=list)
    network_allowlist: list[str] = Field(default_factory=list)
    limits: ResourceLimits = Field(default_factory=ResourceLimits)


DEFAULT_TOOL_REGISTRY: dict[str, ToolPolicy] = {
    "python_exec": ToolPolicy(
        name="python_exec",
        description="Run Python code in an isolated workspace sandbox",
        input_schema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    ),
    "shell_exec": ToolPolicy(
        name="shell_exec",
        description="Run shell command in an isolated workspace sandbox",
        input_schema={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    ),
    "web_fetch": ToolPolicy(
        name="web_fetch",
        description="Fetch content from approved domains",
        input_schema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
        network_allowlist=["api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com"],
    ),
    "model_inference": ToolPolicy(
        name="model_inference",
        description="Call model router for LLM inference",
        input_schema={"type": "object", "properties": {"request": {"type": "object"}}, "required": ["request"]},
    ),
    "dataset_read": ToolPolicy(
        name="dataset_read",
        description="Read dataset files from read-only mounts",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        allowed_paths=["/workspace/data"],
    ),
}
