from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    params: dict[str, Any]
    workspace_root: str


class ExecuteResponse(BaseModel):
    success: bool
    output: str
    error: str | None = None
    artifact: dict[str, Any] | None = None
    model_call: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    docker: str
