import os


class WorkerSettings:
    api_base_url: str = os.getenv("AILAB_API_BASE_URL", "http://localhost:8000")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_cycles_default: int = int(os.getenv("MAX_CYCLES_DEFAULT", "10"))
    stop_confidence_threshold: float = float(os.getenv("STOP_CONFIDENCE_THRESHOLD", "0.9"))
    sandbox_api_url: str = os.getenv("SANDBOX_API_URL", "http://localhost:8010")
    sandbox_required: bool = os.getenv("SANDBOX_REQUIRED", "true").strip().lower() == "true"

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
