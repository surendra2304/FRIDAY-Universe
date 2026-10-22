from __future__ import annotations

from dataclasses import dataclass

from ..provider import ProviderResponse


@dataclass(frozen=True)
class StaticProvider:
    text: str = "No model provider configured."

    async def generate(self, prompt: str, system_prompt: str | None = None) -> ProviderResponse:
        return ProviderResponse(content=self.text, model="static", request_id="static")
