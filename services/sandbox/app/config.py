from __future__ import annotations

import os


class SandboxSettings:
    docker_socket: str = os.getenv("SANDBOX_DOCKER_SOCKET", "unix://var/run/docker.sock")
    sandbox_image: str = os.getenv("SANDBOX_IMAGE", "python:3.12-slim")
    sandbox_user: str = os.getenv("SANDBOX_USER", "65534:65534")
    workspace_volume: str = os.getenv("SANDBOX_WORKSPACE_VOLUME", "ai_lab_workspace_data")
    default_timeout: int = int(os.getenv("SANDBOX_DEFAULT_TIMEOUT", "300"))


settings = SandboxSettings()
