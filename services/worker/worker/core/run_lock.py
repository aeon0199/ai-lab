from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from uuid import uuid4

from redis import Redis

from worker.core.config import settings


_REFRESH_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], ARGV[2])
else
  return 0
end
"""

_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
else
  return 0
end
"""


@dataclass
class RunLock:
    key: str
    token: str
    redis: Redis
    ttl_seconds: int
    refresh_seconds: int
    _stop: threading.Event
    _thread: threading.Thread

    def release(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self.refresh_seconds + 1)
        try:
            self.redis.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
        except Exception:
            pass


def acquire_run_lock(run_id: str) -> RunLock | None:
    redis = Redis.from_url(settings.redis_url)
    key = f"{settings.run_lock_prefix}:{run_id}"
    token = str(uuid4())
    acquired = redis.set(key, token, ex=settings.run_lock_ttl_seconds, nx=True)
    if not acquired:
        return None

    stop = threading.Event()

    def _refresh_loop() -> None:
        while not stop.wait(settings.run_lock_refresh_seconds):
            try:
                redis.eval(_REFRESH_SCRIPT, 1, key, token, settings.run_lock_ttl_seconds)
            except Exception:
                # If refresh fails transiently, let loop retry; TTL still protects stale lock cleanup.
                pass

    thread = threading.Thread(target=_refresh_loop, daemon=True, name=f"run-lock-refresh:{run_id}")
    thread.start()
    return RunLock(
        key=key,
        token=token,
        redis=redis,
        ttl_seconds=settings.run_lock_ttl_seconds,
        refresh_seconds=settings.run_lock_refresh_seconds,
        _stop=stop,
        _thread=thread,
    )
