"""Telegram public-channel threat-intelligence monitor (TASK-IG-SEN-03).

Corpus source DV6UeTQkUH9: Telegram functions as a "mini dark web" —
leak announcements, stealer-log sales and breach chatter appear in
public channels long before they reach curated feeds. This adapter
watches configured PUBLIC channels for owner/fleet-relevant terms and
surfaces matches as threat-intel findings.

Design constraints (defensive, read-only, fail-closed):
* Public web preview only (https://t.me/s/<channel>) — no Telegram
  account, no API key, no bot, nothing is posted or joined.
* Watchlist, not firehose: a post is surfaced only if it matches a
  configured keyword. Everything else is ignored.
* IOCs are extracted with the existing threat_intel IOC extractor and
  are defanged before they are put into an alert.
* Any fetch/parse failure records ``last_error`` and yields zero new
  findings — the monitor never fabricates a post.
* Findings are emitted as BaselineDeltas into the shared operations
  AlertEngine (the SEN-006/SEN-008 dispatch channel); dedupe is by
  channel/message id (persisted) plus the engine's own fingerprinting.
"""

from __future__ import annotations

import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from pydantic import BaseModel, Field

from sentinel.core.models import ActionRequest, ActionResult, SeverityLevel
from sentinel.integrations.threat_feeds.adapters import ThreatFeedAdapter
from sentinel.modules.operations.baseline import BaselineDelta, ChangeType
from sentinel.modules.threat_intel.ioc_extractor import defang_ioc, extract_iocs

PREVIEW_URL = "https://t.me/s/{channel}"


class TelegramPost(BaseModel):
    channel: str
    message_id: int
    text: str

    @property
    def ref(self) -> str:
        return f"{self.channel}/{self.message_id}"

    @property
    def url(self) -> str:
        return f"https://t.me/{self.channel}/{self.message_id}"


class TelegramMatch(BaseModel):
    post: TelegramPost
    matched_terms: list[str]
    critical_term: bool = False
    iocs: list[str] = Field(default_factory=list)

    @property
    def severity(self) -> SeverityLevel:
        if self.critical_term:
            return SeverityLevel.HIGH
        if self.iocs:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW


class _MessageHTMLParser(HTMLParser):
    """Extracts (message_id, text) pairs from a t.me/s/ preview page.

    Message blocks carry ``data-post="<channel>/<id>"``; the text lives
    in the ``tgme_widget_message_text`` div. Only those two facts are
    relied on — everything else in the page is ignored.
    """

    def __init__(self, channel: str):
        super().__init__(convert_charrefs=True)
        self.channel = channel
        self.posts: list[TelegramPost] = []
        self._current_id: int | None = None
        self._in_text = False
        self._depth = 0
        self._chunks: list[str] = []

    _VOID = {"br", "img", "hr", "meta", "link", "input", "wbr"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = dict(attrs)
        if tag == "div" and attr.get("data-post"):
            m = re.match(rf"^{re.escape(self.channel)}/(\d+)$", attr["data-post"] or "")
            if m:
                self._current_id = int(m.group(1))
        if self._current_id is not None:
            if tag == "div" and "tgme_widget_message_text" in (
                attr.get("class") or ""
            ):
                self._in_text = True
                self._depth = 1
                self._chunks = []
            elif self._in_text:
                if tag == "br":
                    self._chunks.append("\n")
                if tag not in self._VOID:
                    self._depth += 1

    def handle_endtag(self, tag: str):
        if self._in_text:
            self._depth -= 1
            if self._depth == 0:
                self._in_text = False
                text = " ".join("".join(self._chunks).split())
                if self._current_id is not None and text:
                    self.posts.append(
                        TelegramPost(
                            channel=self.channel,
                            message_id=self._current_id,
                            text=text,
                        )
                    )
                self._current_id = None

    def handle_data(self, data: str):
        if self._in_text:
            self._chunks.append(data)


def parse_channel_html(html: str, channel: str) -> list[TelegramPost]:
    parser = _MessageHTMLParser(channel)
    parser.feed(html)
    return parser.posts


async def _default_fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(
            url, headers={"User-Agent": "FRIDAY-Sentinel-ThreatIntel/1.0"}
        )
        resp.raise_for_status()
        return resp.text


class TelegramChannelMonitorAdapter(ThreatFeedAdapter):
    """Watches configured public Telegram channels for watchlist terms."""

    def __init__(
        self,
        channels: list[str],
        keywords: list[str],
        critical_keywords: list[str] | None = None,
        state_path: str | Path | None = None,
        fetcher: Callable[[str], Awaitable[str]] | None = None,
    ):
        self.channels = [c.lstrip("@") for c in channels]
        self.keywords = [k.lower() for k in keywords]
        self.critical_keywords = [k.lower() for k in (critical_keywords or [])]
        self.state_path = Path(state_path) if state_path else None
        self._fetch = fetcher or _default_fetch
        self._seen: set[str] = self._load_seen()
        self._matches: list[TelegramMatch] = []
        self.last_error: str | None = None

    # -- ToolAdapter interface -------------------------------------------

    @property
    def name(self) -> str:
        return "telegram_channel_monitor_adapter"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> list[str]:
        return ["threat_intel.telegram_watch", "threat_intel.leak_chatter"]

    async def health_check(self) -> bool:
        return True

    def validate_params(self, action: ActionRequest) -> tuple[bool, str | None]:
        return True, None

    async def run(self, action: ActionRequest) -> tuple[ActionResult, bytes, str]:
        start = time.time()
        new_count = await self.sync_feed()
        data = {
            "channels": self.channels,
            "new_matches": new_count,
            "total_matches": len(self._matches),
            "last_error": self.last_error,
        }
        result = ActionResult(
            action_id=action.id,
            task_id=action.task_id,
            success=self.last_error is None,
            output_summary=(
                f"Telegram watch: {new_count} new match(es) across "
                f"{len(self.channels)} channel(s)."
            ),
            duration_seconds=round(time.time() - start, 3),
        )
        return result, json.dumps(data, indent=2).encode("utf-8"), "application/json"

    # -- feed sync ---------------------------------------------------------

    def _load_seen(self) -> set[str]:
        if self.state_path and self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                return set(data.get("seen", []))
            except (ValueError, OSError):
                return set()
        return set()

    def _save_seen(self) -> None:
        if self.state_path:
            try:
                self.state_path.parent.mkdir(parents=True, exist_ok=True)
                self.state_path.write_text(
                    json.dumps({"seen": sorted(self._seen)}), encoding="utf-8"
                )
            except OSError:
                pass  # state persistence must never crash the monitor

    def match_post(self, post: TelegramPost) -> TelegramMatch | None:
        text = post.text.lower()
        matched = [k for k in self.keywords if k in text]
        critical = [k for k in self.critical_keywords if k in text]
        if not matched and not critical:
            return None
        iocs = extract_iocs(post.text)
        return TelegramMatch(
            post=post,
            matched_terms=sorted(set(matched + critical)),
            critical_term=bool(critical),
            iocs=[defang_ioc(i.value) for i in iocs],
        )

    async def sync_feed(self) -> int:
        """Fetch every configured channel once; return the number of NEW
        watchlist matches. Fail-closed: on any error, record it and
        return what was gathered before the failure (never invented)."""
        self.last_error = None
        new_matches = 0
        for channel in self.channels:
            try:
                html = await self._fetch(PREVIEW_URL.format(channel=channel))
                posts = parse_channel_html(html, channel)
            except Exception as exc:  # network/HTTP/parse — fail closed
                self.last_error = f"{channel}: {type(exc).__name__}: {exc}"
                continue
            for post in posts:
                if post.ref in self._seen:
                    continue
                self._seen.add(post.ref)
                match = self.match_post(post)
                if match is not None:
                    self._matches.append(match)
                    new_matches += 1
        self._save_seen()
        return new_matches

    # -- reporting ---------------------------------------------------------

    def drain_matches(self) -> list[TelegramMatch]:
        matches, self._matches = self._matches, []
        return matches

    @staticmethod
    def emit_alerts(matches: list[TelegramMatch], engine: Any) -> list[Any]:
        """Feed matches into the shared operations AlertEngine."""
        alerts = []
        for match in matches:
            post = match.post
            ioc_note = (
                f" IOCs (defanged): {', '.join(match.iocs[:8])}."
                if match.iocs
                else ""
            )
            delta = BaselineDelta(
                delta_id=f"igsen03-{post.ref}",
                target_ref=f"telegram:{post.channel}",
                change_type=ChangeType.NEW_FINDING,
                severity=match.severity,
                description=(
                    f"[TG-WATCH] Public Telegram channel @{post.channel} "
                    f"post {post.message_id} matched watchlist terms "
                    f"{match.matched_terms}: {post.text[:300]}"
                    f"{ioc_note} Source: {post.url}"
                ),
                new_state={"post_url": post.url, "matched_terms": match.matched_terms},
            )
            alerts.append(engine.process_delta(delta))
        return alerts
