from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.executor import PolicyError, SandboxExecutionError, SandboxExecutor
from app.schemas import ExecuteRequest, ExecuteResponse, HealthResponse

app = FastAPI(title="AI Lab Sandbox", version="0.1.0")
executor = SandboxExecutor()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    docker_ok = executor.health()
    return HealthResponse(status="ok" if docker_ok else "degraded", docker="ok" if docker_ok else "unavailable")


@app.post("/execute", response_model=ExecuteResponse)
def execute(payload: ExecuteRequest) -> ExecuteResponse:
    try:
        result = executor.execute(payload.tool_name, payload.params, payload.workspace_root)
        return ExecuteResponse(success=result.success, output=result.output, error=result.error)
    except PolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SandboxExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
