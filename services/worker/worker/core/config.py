import os


class WorkerSettings:
    api_base_url: str = os.getenv("AILAB_API_BASE_URL", "http://localhost:8000")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_cycles_default: int = int(os.getenv("MAX_CYCLES_DEFAULT", "10"))
    stop_confidence_threshold: float = float(os.getenv("STOP_CONFIDENCE_THRESHOLD", "0.9"))
    sandbox_api_url: str = os.getenv("SANDBOX_API_URL", "http://localhost:8010")
    sandbox_required: bool = os.getenv("SANDBOX_REQUIRED", "true").strip().lower() == "true"
    worker_heartbeat_key: str = os.getenv("WORKER_HEARTBEAT_KEY", "ailab:worker:heartbeat")
    worker_heartbeat_ttl_seconds: int = int(os.getenv("WORKER_HEARTBEAT_TTL_SECONDS", "90"))
    worker_heartbeat_interval_seconds: int = int(os.getenv("WORKER_HEARTBEAT_INTERVAL_SECONDS", "20"))
    run_lock_prefix: str = os.getenv("RUN_LOCK_PREFIX", "ailab:run-lock")
    run_lock_ttl_seconds: int = int(os.getenv("RUN_LOCK_TTL_SECONDS", "60"))
    run_lock_refresh_seconds: int = int(os.getenv("RUN_LOCK_REFRESH_SECONDS", "15"))

    dramatiq_namespace: str = os.getenv("DRAMATIQ_NAMESPACE", "ailab")
    dramatiq_processes: int = int(os.getenv("DRAMATIQ_PROCESSES", "2"))
    dramatiq_threads: int = int(os.getenv("DRAMATIQ_THREADS", "2"))
    dramatiq_worker_timeout_ms: int = int(os.getenv("DRAMATIQ_WORKER_TIMEOUT_MS", "1000"))
    dramatiq_max_retries: int = int(os.getenv("DRAMATIQ_MAX_RETRIES", "3"))
    dramatiq_min_backoff_ms: int = int(os.getenv("DRAMATIQ_MIN_BACKOFF_MS", "10000"))
    dramatiq_max_backoff_ms: int = int(os.getenv("DRAMATIQ_MAX_BACKOFF_MS", "60000"))

    planner_provider: str = os.getenv("PLANNER_PROVIDER", "local")
    planner_model: str = os.getenv("PLANNER_MODEL", "llama3.1")
    planner_temperature: float = float(os.getenv("PLANNER_TEMPERATURE", "0.2"))
    planner_max_tokens: int = int(os.getenv("PLANNER_MAX_TOKENS", "300"))

    researcher_provider: str = os.getenv("RESEARCHER_PROVIDER", "local")
    researcher_model: str = os.getenv("RESEARCHER_MODEL", "llama3.1")
    researcher_temperature: float = float(os.getenv("RESEARCHER_TEMPERATURE", "0.2"))
    researcher_max_tokens: int = int(os.getenv("RESEARCHER_MAX_TOKENS", "200"))

    critic_provider: str = os.getenv("CRITIC_PROVIDER", "local")
    critic_model: str = os.getenv("CRITIC_MODEL", "llama3.1")
    critic_temperature: float = float(os.getenv("CRITIC_TEMPERATURE", "0.2"))
    critic_max_tokens: int = int(os.getenv("CRITIC_MAX_TOKENS", "200"))


settings = WorkerSettings()
