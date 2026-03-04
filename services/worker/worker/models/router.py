from __future__ import annotations

import asyncio
import os
import time
from typing import Protocol

import requests
from ailab_domain.models import ModelRequest, ModelResponse


class ProviderAdapter(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class _FallbackAdapter:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def generate(self, request: ModelRequest) -> ModelResponse:
        start = time.perf_counter()
        combined = " ".join([m.content for m in request.messages])
        text = f"[{self.provider} fallback] {combined[:500]}"
        return ModelResponse(
            output=text,
            token_usage={"input_tokens": max(1, len(combined) // 4), "output_tokens": max(1, len(text) // 4)},
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_request_id=None,
            raw_metadata={"fallback": True},
        )


class OpenAIAdapter:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            return _FallbackAdapter("openai").generate(request)

        start = time.perf_counter()
        res = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": request.model,
                "messages": [m.model_dump() for m in request.messages],
                "temperature": request.temperature,
                "top_p": request.top_p,
                "max_tokens": request.max_tokens,
                **({"seed": request.seed} if request.seed is not None else {}),
            },
            timeout=request.timeout,
        )
        res.raise_for_status()
        data = res.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return ModelResponse(
            output=choice["message"]["content"],
            tool_calls=choice["message"].get("tool_calls", []),
            token_usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_request_id=data.get("id"),
            raw_metadata={"model": data.get("model")},
        )


class AnthropicAdapter:
    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            return _FallbackAdapter("anthropic").generate(request)

        start = time.perf_counter()
        prompt = "\n".join([f"{m.role}: {m.content}" for m in request.messages])
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": request.model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=request.timeout,
        )
        res.raise_for_status()
        data = res.json()
        output_text = " ".join([chunk.get("text", "") for chunk in data.get("content", [])])
        usage = data.get("usage", {})
        return ModelResponse(
            output=output_text,
            token_usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_request_id=data.get("id"),
            raw_metadata={"stop_reason": data.get("stop_reason")},
        )


class GeminiAdapter:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            return _FallbackAdapter("gemini").generate(request)

        start = time.perf_counter()
        prompt = "\n".join([f"{m.role}: {m.content}" for m in request.messages])
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent?key={self.api_key}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=request.timeout,
        )
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = " ".join([p.get("text", "") for p in parts])
        return ModelResponse(
            output=text,
            token_usage={},
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_request_id=None,
            raw_metadata={"candidate_count": len(candidates)},
        )


class OpenAICompatibleAdapter:
    def __init__(self) -> None:
        self.base_url = os.getenv("LOCAL_OPENAI_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("LOCAL_OPENAI_API_KEY", "ollama")

    def generate(self, request: ModelRequest) -> ModelResponse:
        start = time.perf_counter()
        try:
            res = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": request.model,
                    "messages": [m.model_dump() for m in request.messages],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
                timeout=request.timeout,
            )
        except requests.RequestException:
            return _FallbackAdapter("local").generate(request)
        if res.status_code >= 400:
            return _FallbackAdapter("local").generate(request)
        data = res.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return ModelResponse(
            output=choice["message"].get("content", ""),
            token_usage=usage,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_request_id=data.get("id"),
            raw_metadata={"model": data.get("model")},
        )


class ModelRouter:
    def __init__(self) -> None:
        self.adapters: dict[str, ProviderAdapter] = {
            "openai": OpenAIAdapter(),
            "anthropic": AnthropicAdapter(),
            "gemini": GeminiAdapter(),
            "local": OpenAICompatibleAdapter(),
            "ollama": OpenAICompatibleAdapter(),
        }

    async def generate(self, request: ModelRequest) -> ModelResponse:
        adapter = self.adapters.get(request.provider, _FallbackAdapter(request.provider))
        return await asyncio.to_thread(adapter.generate, request)

    def generate_sync(self, request: ModelRequest) -> ModelResponse:
        return asyncio.run(self.generate(request))
