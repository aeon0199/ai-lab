from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone

from redis import Redis


def start_worker_heartbeat(
    *,
    redis_url: str,
    key: str,
    backend: str,
    ttl_seconds: int,
    interval_seconds: int,
) -> threading.Thread:
    redis = Redis.from_url(redis_url)

    def _beat() -> None:
        while True:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
                "backend": backend,
            }
            try:
                redis.set(key, json.dumps(payload), ex=ttl_seconds)
            except Exception:
                # Heartbeat failure should not crash workers.
                pass
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_beat, daemon=True, name="worker-heartbeat")
    thread.start()
    return thread
