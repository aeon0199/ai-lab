from app.reducers.world_state import reduce_events


def test_reducer_replay_equivalence():
    stream_id = "run-1"
    events = [
        {
            "event_type": "goal_created",
            "payload": {"goal_id": "g1", "title": "Goal", "description": "Desc"},
            "occurred_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "event_type": "experiment_proposed",
            "payload": {
                "experiment_id": "e1",
                "hypothesis": "H",
                "method": "M",
                "parameters": {"x": 1},
                "evaluation_method": "rule",
            },
            "occurred_at": "2026-01-01T00:00:01+00:00",
        },
    ]

    state1 = reduce_events(stream_id, events)
    state2 = reduce_events(stream_id, events)
    assert state1 == state2
