from app.services.commands import ALLOWED_TRANSITIONS


def test_run_status_transition_table_is_guarded():
    assert "running" in ALLOWED_TRANSITIONS["queued"]
    assert "paused" in ALLOWED_TRANSITIONS["running"]
    assert not ALLOWED_TRANSITIONS["completed"]
    assert not ALLOWED_TRANSITIONS["failed"]
