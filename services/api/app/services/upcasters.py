from __future__ import annotations

from typing import Any

from ailab_domain.events import EVENT_TYPES

LATEST_EVENT_SCHEMA_VERSION = 1


class UpcastError(Exception):
    pass


def upcast_event_payload(event_type: str, schema_version: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if event_type not in EVENT_TYPES:
        raise UpcastError(f"Unsupported event type for upcast: {event_type}")

    if schema_version > LATEST_EVENT_SCHEMA_VERSION:
        raise UpcastError(
            f"Incoming schema_version {schema_version} is newer than supported {LATEST_EVENT_SCHEMA_VERSION}"
        )

    # v1 is current in this release. Framework exists for future event migrations.
    if schema_version == LATEST_EVENT_SCHEMA_VERSION:
        return schema_version, payload

    # Placeholder for future explicit transformations.
    current_payload = payload
    current_version = schema_version
    while current_version < LATEST_EVENT_SCHEMA_VERSION:
        current_version += 1

    return current_version, current_payload
