"""Production wiring for the standing IG feeds (X-07 follow-through).

TASK-IG-INT-01 shipped ``HeadlineWatch`` and TASK-IG2-INT-05 shipped
``AiRadar`` as libraries: both were referenced by nothing outside their
own modules and tests, so in production nothing ever polled them and no
consumer could read them. This module is the shared service layer that
ends that:

  * process-wide singletons (``get_headline_watch`` / ``get_ai_radar``)
    so the lifespan scheduler hooks in ``intelx.app.lifespan`` and the
    API routes in ``intelx.api.v1.feeds`` drive and read the SAME
    instances;
  * the StrateX delivery subscriber: when the operator enables
    ``HEADLINE_STRATEX_DELIVERY``, every sweep's new headlines at or
    above ``HEADLINE_STRATEX_MIN_SCORE`` are forwarded through the
    existing ``StratexConnector.notify_stratex_trade_signal`` webhook
    path (the same delivery channel IntelX research already uses).
    Delivery is opt-in and score-floored because the connector also
    publishes a Memora research notice per signal — a headline wire
    must not spam the mesh by default.

The watch/radar themselves stay pure libraries; all production
composition lives here and in the lifespan hooks.
"""

from __future__ import annotations

import logging

from intelx.core.settings import get_settings
from intelx.ingestion.ai_radar import AiRadar
from intelx.ingestion.headline_watch import Headline, HeadlineWatch

logger = logging.getLogger("intelx.feed_service")

_headline_watch: HeadlineWatch | None = None
_ai_radar: AiRadar | None = None
_delivery_attached = False


def get_headline_watch() -> HeadlineWatch:
    """The process-wide HeadlineWatch (created on first use)."""
    global _headline_watch, _delivery_attached
    if _headline_watch is None:
        _headline_watch = HeadlineWatch()
        if get_settings().HEADLINE_STRATEX_DELIVERY and not _delivery_attached:
            _headline_watch.subscribe(deliver_headlines_to_stratex)
            _delivery_attached = True
            logger.info(
                "headline watch: StrateX delivery attached (min_score=%s)",
                get_settings().HEADLINE_STRATEX_MIN_SCORE,
            )
    return _headline_watch


def get_ai_radar() -> AiRadar:
    """The process-wide AiRadar (created on first use)."""
    global _ai_radar
    if _ai_radar is None:
        _ai_radar = AiRadar()
    return _ai_radar


async def deliver_headlines_to_stratex(headlines: list[Headline]) -> list[dict]:
    """Forward market-moving headlines to StrateX via the existing webhook.

    Only headlines at or above the configured impact floor are sent;
    each delivery is isolated — one failure never blocks the others and
    never propagates into the watch's poll loop (the watch already
    guards subscribers, this is belt-and-braces for direct callers).
    Returns one ``{fingerprint, status}`` dict per attempted delivery.
    """
    from intelx.integrations.stratex_context import StratexConnector

    floor = get_settings().HEADLINE_STRATEX_MIN_SCORE
    results: list[dict] = []
    for headline in headlines:
        if headline.impact.score < floor:
            continue
        try:
            response = await StratexConnector.notify_stratex_trade_signal(
                finding_text=f"[{headline.source_name}] {headline.title}",
                run_id=f"headline-{headline.fingerprint[:16]}",
                domain="market_headlines",
                confidence=max(0.0, min(1.0, headline.impact.score / 100.0)),
                extra_context={
                    "sources": [{"title": headline.source_name, "url": headline.url}],
                    "headline": headline.to_dict(),
                },
            )
            results.append(
                {"fingerprint": headline.fingerprint, "status": response.get("status", "unknown")}
            )
        except Exception:  # delivery must never break the watch
            logger.exception("headline->stratex delivery failed for %s", headline.fingerprint)
            results.append({"fingerprint": headline.fingerprint, "status": "error"})
    return results


__all__ = [
    "deliver_headlines_to_stratex",
    "get_ai_radar",
    "get_headline_watch",
]
