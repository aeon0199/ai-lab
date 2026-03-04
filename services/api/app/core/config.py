from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Lab API"
    database_url: str = "postgresql+psycopg://ailab:ailab@localhost:5432/ailab"
    redis_url: str = "redis://localhost:6379/0"
    snapshot_cadence: int = 500
    max_experiments_per_run: int = 100
    max_tool_runtime_seconds: int = 300
    queue_backend: str = "dramatiq"
    dramatiq_namespace: str = "ailab"
    dramatiq_max_retries: int = 3
    dramatiq_min_backoff_ms: int = 10_000
    dramatiq_max_backoff_ms: int = 60_000
    worker_heartbeat_key: str = "ailab:worker:heartbeat"
    worker_heartbeat_ttl_seconds: int = 90
    sandbox_health_url: str | None = "http://sandbox:8010/health"


settings = Settings()
