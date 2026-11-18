"""Universe intel feed entries and the broadcast publisher — TASK-INT-014.

Owner decision 2026-11-18: IntelX shares its data with Futuris, Stratex and
all agents. The shared channel is the one the code already has: Memora's
durable event feed. ``publish_research_notice`` posts a signed
``intelx.news`` envelope to Memora's ``/mesh/envelope``; a recipient of
``"all"`` is stored with ``target_agent=NULL``, which every agent's cursor
poll (``GET /v1/events/poll``) can see. So one broadcast publish reaches
all ten agents — no new channel, no per-agent fan-out, and the existing
Futuris consumer picks entries up unchanged.

An entry is a *verified finding*: something that already passed one of
IntelX's deterministic bars (a standing watch's tuned score threshold, or
a completed research run). The feed never carries raw, unscored items —
that is what keeps a broadcast channel from becoming a noise channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from intelx.integrations.memora_events import publish_research_notice

# A watch alert passed a tuned deterministic threshold plus structural
# dedupe before it may become an entry; that bar is what this confidence
# records. It is a band label, not a probability estimate.
WATCH_ALERT_FEED_CONFIDENCE = 0.8

Publisher = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class IntelFeedEntry:
    """One verified finding, addressed to the whole Universe."""

    entry_id: str  # stable; retries of the same finding dedupe downstream
    headline: str
    summary: str
    domain: str  # a TASK-INT-013 domain id — the subscription unit
    category: str = "research_finding"
    confidence: float = WATCH_ALERT_FEED_CONFIDENCE
    topics: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)

    def finding_text(self) -> str:
        """The single text the mesh publisher carries (headline+summary)."""
        if self.summary and self.summary != self.headline:
            return f"{self.headline}\n\n{self.summary}"
        return self.headline or self.summary


async def publish_feed_entry(
    entry: IntelFeedEntry,
    *,
    publisher: Publisher = publish_research_notice,
    client: Any = None,
) -> dict[str, Any]:
    """Publish ``entry`` ONCE to the Universe (recipient ``"all"``).

    The publisher is injectable so the watch engine and tests can observe
    or replace delivery without touching the network path. All of the
    publisher's own gates still apply (production/env enablement, mock
    mode, credential presence) — this wrapper adds no bypass.
    """
    return await publisher(
        target_agent="all",
        run_id=entry.entry_id,
        finding_summary=entry.finding_text(),
        category=entry.category,
        domain=entry.domain,
        confidence=entry.confidence,
        recommended_targets=list(entry.topics),
        sources=list(entry.sources),
        client=client,
    )
