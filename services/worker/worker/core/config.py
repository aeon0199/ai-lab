import os


class WorkerSettings:
    api_base_url: str = os.getenv("AILAB_API_BASE_URL", "http://localhost:8000")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_cycles_default: int = int(os.getenv("MAX_CYCLES_DEFAULT", "10"))
    stop_confidence_threshold: float = float(os.getenv("STOP_CONFIDENCE_THRESHOLD", "0.9"))


settings = WorkerSettings()
