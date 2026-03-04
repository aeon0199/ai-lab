from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self._event_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._status_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect_events(self, stream_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._event_clients[stream_id].add(ws)

    async def connect_status(self, stream_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._status_clients[stream_id].add(ws)

    async def disconnect(self, stream_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._event_clients[stream_id].discard(ws)
            self._status_clients[stream_id].discard(ws)

    async def broadcast_event(self, stream_id: str, message: dict[str, Any]) -> None:
        await self._broadcast(self._event_clients[stream_id], message)

    async def broadcast_status(self, stream_id: str, message: dict[str, Any]) -> None:
        await self._broadcast(self._status_clients[stream_id], message)

    async def _broadcast(self, clients: set[WebSocket], payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)
        for ws in stale:
            clients.discard(ws)


ws_manager = WSManager()
