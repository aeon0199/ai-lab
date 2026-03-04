import os

from ailab_domain.queueing import QUEUE_RESEARCH_RUNS
from worker.core.config import settings


def main() -> None:
    _exec_dramatiq()


def _exec_dramatiq() -> None:
    cmd = [
        "dramatiq",
        "worker.dramatiq_app",
        "--processes",
        str(settings.dramatiq_processes),
        "--threads",
        str(settings.dramatiq_threads),
        "--queues",
        QUEUE_RESEARCH_RUNS,
    ]
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
