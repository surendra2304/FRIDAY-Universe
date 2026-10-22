from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    max_retries: int = 2
    timeout_seconds: float = 90
    base_delay: float = 1.0


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    request_id: str | None = None


class ProviderProtocol(Protocol):
    async def generate(self, prompt: str, system_prompt: str | None = None) -> ProviderResponse: ...


class ReliableProvider:
    def __init__(self, provider: ProviderProtocol, config: ProviderConfig):
        self.provider = provider
        self.config = config

    async def generate(self, prompt: str, system_prompt: str | None = None) -> ProviderResponse:
        last: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self.provider.generate(prompt, system_prompt),
                    timeout=self.config.timeout_seconds,
                )
            except Exception as exc:
                last = exc
                if attempt == self.config.max_retries:
                    break
                await asyncio.sleep(self.config.base_delay * (2**attempt))
        raise ProviderError(str(last) if last else "provider failed")
