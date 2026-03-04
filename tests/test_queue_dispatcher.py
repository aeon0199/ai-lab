from __future__ import annotations

from ailab_domain.queueing import (
    ACTOR_PROCESS_RESEARCH_RUN,
    ACTOR_PROCESS_SINGLE_CYCLE,
    QUEUE_RESEARCH_RUNS,
)

from app.services.queue import DramatiqTaskDispatcher


class _FakeBroker:
    def __init__(self) -> None:
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)
        return message


def test_dramatiq_dispatcher_enqueues_research_run_message() -> None:
    broker = _FakeBroker()
    dispatcher = DramatiqTaskDispatcher(broker=broker)  # type: ignore[arg-type]

    message_id = dispatcher.enqueue_research_run("run-123")

    assert message_id
    assert len(broker.messages) == 1
    message = broker.messages[0]
    assert message.actor_name == ACTOR_PROCESS_RESEARCH_RUN
    assert message.queue_name == QUEUE_RESEARCH_RUNS
    assert message.args == ("run-123",)


def test_dramatiq_dispatcher_enqueues_single_cycle_message() -> None:
    broker = _FakeBroker()
    dispatcher = DramatiqTaskDispatcher(broker=broker)  # type: ignore[arg-type]

    message_id = dispatcher.enqueue_single_cycle("run-xyz")

    assert message_id
    assert len(broker.messages) == 1
    message = broker.messages[0]
    assert message.actor_name == ACTOR_PROCESS_SINGLE_CYCLE
    assert message.queue_name == QUEUE_RESEARCH_RUNS
    assert message.args == ("run-xyz",)
