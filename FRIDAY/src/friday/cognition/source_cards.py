"""Source cards on answers (TASK-IG-FRD-006).

Pattern source: IG corpus item ``DfO5vLSjodF`` — answers that carry a
card for each web source behind their claims, so the owner can see (and
check) where an answer came from.

Cards are extracted from the turn's *actual* tool results — structured
source dicts, tool-result metadata, and bare URLs in result text. A
source is never invented to decorate an answer: if the turn produced no
sources, the response is returned untouched.

:meth:`attach_source_cards` is wired at the single response chokepoint
(``FridayAgent.process_message``) and is fail-open by design — the
caller wraps it so any extraction error leaves the response unchanged.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from typing import Any, List, Optional
from urllib.parse import urlparse

MAX_CARDS = 8
_URL_RE = re.compile(r"https?://[^\s<>\)\]\"']+")
_URL_KEYS = ("url", "link", "source_url", "href")
_TITLE_KEYS = ("title", "name", "headline")
_CLAIM_KEYS = ("claim", "snippet", "description", "summary")


@dataclass
class SourceCard:
    title: str
    url: str
    publisher: str
    claim: str = ""
    via: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _publisher(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except ValueError:
        return url


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:!?")


def _card_from_mapping(mapping: dict, via: str) -> Optional[SourceCard]:
    url = ""
    for key in _URL_KEYS:
        value = mapping.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            url = _clean_url(value)
            break
    if not url:
        return None
    title = ""
    for key in _TITLE_KEYS:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            title = value.strip()
            break
    claim = ""
    for key in _CLAIM_KEYS:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            claim = value.strip()[:200]
            break
    return SourceCard(
        title=title or _publisher(url),
        url=url,
        publisher=_publisher(url),
        claim=claim,
        via=via,
    )


def _walk(value: Any, via: str, out: List[SourceCard], depth: int = 0) -> None:
    if depth > 4 or len(out) >= MAX_CARDS * 3:
        return
    if isinstance(value, dict):
        card = _card_from_mapping(value, via)
        if card is not None:
            out.append(card)
        for item in value.values():
            _walk(item, via, out, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _walk(item, via, out, depth + 1)
    elif isinstance(value, str):
        for match in _URL_RE.findall(value):
            url = _clean_url(match)
            out.append(
                SourceCard(title=_publisher(url), url=url, publisher=_publisher(url), via=via)
            )


def extract_source_cards(tool_results: Any) -> List[SourceCard]:
    """Extract deduped source cards from a turn's tool results."""
    raw: List[SourceCard] = []
    if not tool_results:
        return []
    for result in tool_results:
        via = ""
        content: Any = result
        metadata: Any = None
        if not isinstance(result, (dict, list, str)):
            via = str(getattr(result, "name", "") or "")
            content = getattr(result, "content", None)
            metadata = getattr(result, "metadata", None)
        elif isinstance(result, dict):
            via = str(result.get("name", "") or "")
            content = result.get("content")
            metadata = result.get("metadata")
        if metadata:
            _walk(metadata, via, raw)
        if content is not None:
            _walk(content, via, raw)
    seen = set()
    cards: List[SourceCard] = []
    for card in raw:
        if card.url in seen:
            continue
        seen.add(card.url)
        cards.append(card)
        if len(cards) >= MAX_CARDS:
            break
    return cards


def render_sources_section(cards: List[SourceCard]) -> str:
    lines = ["Sources:"]
    for card in cards:
        lines.append(f"- {card.title} — {card.url}")
    return "\n".join(lines)


def attach_source_cards(response: Any) -> Any:
    """Attach source cards to an AgentResponse (metadata + text section).

    Returns the response unchanged when it carries no tool results or
    the turn produced no sources. Uses ``model_copy`` when available so
    the original response object is never mutated.
    """
    if response is None:
        return response
    tool_results = getattr(response, "tool_results", None)
    if not tool_results:
        return response
    cards = extract_source_cards(tool_results)
    if not cards:
        return response

    metadata = dict(getattr(response, "metadata", None) or {})
    metadata["source_cards"] = [c.to_dict() for c in cards]
    metadata["source_cards_at"] = time.time()

    content = getattr(response, "content", "") or ""
    if "Sources:" not in content[-2000:]:
        content = content.rstrip() + "\n\n" + render_sources_section(cards)

    if hasattr(response, "model_copy"):
        return response.model_copy(update={"content": content, "metadata": metadata})
    # Plain-object fallback (tests, lightweight stubs).
    response.content = content
    response.metadata = metadata
    return response


__all__ = [
    "MAX_CARDS",
    "SourceCard",
    "extract_source_cards",
    "render_sources_section",
    "attach_source_cards",
]
