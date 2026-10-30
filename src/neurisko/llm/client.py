"""LLM clients: a real OpenAI-compatible client, a replay client and a fake for tests."""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

Message = dict[str, str]


class LLMError(Exception):
    """The endpoint failed (connection, timeout, HTTP error, empty reply)."""


@dataclass(slots=True)
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0


class LLMClient(Protocol):
    model: str

    def complete(self, messages: list[Message]) -> LLMResponse: ...


class OpenAICompatClient:
    """Any OpenAI-compatible chat endpoint (Ollama, OpenAI, Bedrock gateways, ...), JSON mode."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout_s: float = 120,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> None:
        import openai

        self._openai = openai
        self._client = openai.OpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout_s, max_retries=0
        )
        self.model = model
        self.temperature = temperature
        self.seed = seed

    def complete(self, messages: list[Message]) -> LLMResponse:
        t = time.perf_counter()
        try:
            r = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=self.temperature,
                seed=self.seed,
            )
        except self._openai.OpenAIError as err:
            raise LLMError(f"{type(err).__name__}: {err}") from None
        text = (r.choices[0].message.content or "") if r.choices else ""
        if not text.strip():
            raise LLMError("empty response")
        usage = r.usage
        return LLMResponse(
            text=text,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_s=time.perf_counter() - t,
        )


@dataclass
class FakeClient:
    """Returns scripted replies in order; an Exception item is raised as LLMError."""

    replies: list[str | Exception]
    model: str = "fake"
    calls: list[list[Message]] = field(default_factory=list)

    def complete(self, messages: list[Message]) -> LLMResponse:
        self.calls.append(messages)
        if not self.replies:
            raise LLMError("fake client has no replies left")
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise LLMError(str(item))
        return LLMResponse(text=item, prompt_tokens=100, completion_tokens=50, latency_s=0.0)


class ReplayClient:
    """Replays the LLM calls and errors recorded in a run's events, in order."""

    def __init__(self, events: Iterable[dict], model: str = "replay") -> None:
        self.model = model
        self._items = [e for e in events if e["type"] in ("llm_call", "llm_error")]

    def complete(self, messages: list[Message]) -> LLMResponse:
        if not self._items:
            raise LLMError("replay: no recorded LLM responses left")
        e = self._items.pop(0)
        if e["type"] == "llm_error":
            raise LLMError(e["error"])
        return LLMResponse(
            text=e["response"],
            prompt_tokens=e.get("prompt_tokens", 0),
            completion_tokens=e.get("completion_tokens", 0),
            latency_s=0.0,
        )
