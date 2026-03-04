from app.services.upcasters import LATEST_EVENT_SCHEMA_VERSION, upcast_event_payload


def test_upcast_v1_passthrough():
    version, payload = upcast_event_payload("goal_created", 1, {"goal_id": "g1", "title": "t", "description": "d"})
    assert version == LATEST_EVENT_SCHEMA_VERSION
    assert payload["goal_id"] == "g1"
