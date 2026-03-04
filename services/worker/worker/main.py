from redis import Redis
from rq import Queue, Worker

from worker.core.config import settings


def main() -> None:
    redis = Redis.from_url(settings.redis_url)
    queue = Queue("research_runs", connection=redis)
    worker = Worker([queue], connection=redis)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
