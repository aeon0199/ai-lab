import os

from ailab_domain.models import ChatMessage, ModelRequest
from worker.models.router import AnthropicAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_anthropic_adapter_preserves_messages_and_system(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "id": "msg_123",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 12, "output_tokens": 4},
                "stop_reason": "end_turn",
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    adapter = AnthropicAdapter()
    request = ModelRequest(
        provider="anthropic",
        model="claude-sonnet-4-5",
        system="be concise",
        messages=[
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Second question"),
        ],
        max_tokens=128,
        temperature=0.2,
    )

    response = adapter.generate(request)

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["json"]["system"] == "be concise"
    assert len(captured["json"]["messages"]) == 3
    assert captured["json"]["messages"][0]["role"] == "user"
    assert captured["json"]["messages"][1]["role"] == "assistant"
    assert response.output == "ok"
    assert response.token_usage["input_tokens"] == 12
