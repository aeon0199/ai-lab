from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Lab API"
    database_url: str = "postgresql+psycopg://ailab:ailab@localhost:5432/ailab"
    redis_url: str = "redis://localhost:6379/0"
    snapshot_cadence: int = 500
    max_experiments_per_run: int = 100
    max_tool_runtime_seconds: int = 300


settings = Settings()
