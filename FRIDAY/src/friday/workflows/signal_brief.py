"""TASK-FRD-060 — Daily Signal Brief (on-demand, from live IntelX data).

Adopts the recovered "Daily Slack Signal Brief" template (friday package
F-40, item DfHw7hsIfvd, PARTIAL — its closing segment was never recovered)
as FRIDAY's on-demand brief, generated from IntelX standing-watch digest
data. See docs/collaboration/TASK-FRD-060-BUILD-VERIFY.md for the
section-by-section comparison against FRIDAY's current brief formats.

Data source: IntelX's watch outbox (``data/watches/outbox.jsonl`` under
the IntelX checkout, ``INTELX_WATCH_OUTBOX_PATH`` override) plus its
instant sibling — the exact contract ``friday.proactive.intelx_watch``
drains (schema ``intelx.watch_alert/1``). Envelopes carry ``fired_at``,
``score``, ``watch_id``, ``title``, ``summary``, ``publisher`` and ``url``.

Constraint: template + on-demand generation ONLY. No new routine cron —
the owner removed routine briefings on 2026-11-23; the brief is produced
when asked, via the tool or the API route. This module never sends
anything and never enables any watch: it only reads the outbox files.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from friday.core.owner_time import OWNER_TZ, now_owner_tz
from friday.proactive.intelx_watch import (
    ENVELOPE_SCHEMA,
    resolve_instant_outbox_path,
    resolve_outbox_path,
)

#: Default coverage window for one brief.
DEFAULT_WINDOW_HOURS = 24

#: Where generated briefs are saved for re-reading.
BRIEF_DIR = Path(__file__).resolve().parents[3] / ".data" / "signal_briefs"

#: Cap so one brief never grows without bound.
MAX_SIGNALS = 30


def _parse_fired_at(value: Any) -> datetime | None:
    """Parse an envelope's ``fired_at`` ISO timestamp (None if unusable)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def read_recent_signals(
    outbox_path: Path | str | None = None,
    instant_path: Path | str | None = None,
    *,
    hours: int = DEFAULT_WINDOW_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read IntelX watch envelopes fired inside the window.

    Returns ``{"ok": True, "signals": [...], "malformed": n,
    "outbox_missing": bool, "instant_missing": bool}``. Signals are
    envelopes sorted by score descending, deduplicated by ``dedupe_key``
    (first occurrence wins). A missing outbox is a normal state — the
    result is an honest empty list, not an error. Malformed lines are
    skipped and counted, never fatal.
    """
    moment = now or datetime.now(timezone.utc)
    window_start = moment - timedelta(hours=max(hours, 1))
    main = Path(outbox_path) if outbox_path is not None else resolve_outbox_path()
    instant = (
        Path(instant_path)
        if instant_path is not None
        else resolve_instant_outbox_path(main)
    )

    signals: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    malformed = 0
    missing = {"outbox_missing": False, "instant_missing": False}

    for path, flag in ((main, "outbox_missing"), (instant, "instant_missing")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except FileNotFoundError:
            missing[flag] = True
            continue
        except OSError:
            missing[flag] = True
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(envelope, dict):
                malformed += 1
                continue
            if envelope.get("schema") != ENVELOPE_SCHEMA:
                malformed += 1
                continue
            fired_at = _parse_fired_at(envelope.get("fired_at"))
            if fired_at is None or fired_at < window_start or fired_at > moment:
                continue
            key = str(envelope.get("dedupe_key") or envelope.get("envelope_id") or "")
            if key:
                if key in seen_keys:
                    continue
                seen_keys.add(key)
            signals.append(envelope)

    signals.sort(key=lambda e: e.get("score") if isinstance(e.get("score"), (int, float)) else 0, reverse=True)
    return {
        "ok": True,
        "signals": signals[:MAX_SIGNALS],
        "malformed": malformed,
        "total_in_window": len(signals),
        **missing,
    }


def _score_of(envelope: dict[str, Any]) -> str:
    score = envelope.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        return f"{score:g}"
    return "—"


def render_brief(
    signals: list[dict[str, Any]],
    *,
    hours: int = DEFAULT_WINDOW_HOURS,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Render the adopted Daily Signal Brief format from live envelopes.

    Every figure comes from the envelopes; nothing is invented. An empty
    signal list renders an honest empty brief, not a fabricated one.
    """
    moment = generated_at or now_owner_tz()
    date_str = moment.strftime("%Y-%m-%d")
    watches: dict[str, int] = {}
    for envelope in signals:
        watch = str(envelope.get("watch_id") or "unknown watch")
        watches[watch] = watches.get(watch, 0) + 1

    if signals:
        top = signals[0]
        top_title = str(top.get("title") or "(untitled signal)")
        top_watch = str(top.get("watch_id") or "unknown watch")
        spoken = (
            f"Daily Signal Brief for {date_str}: {len(signals)} IntelX signal"
            f"{'s' if len(signals) != 1 else ''} in the last {hours} hours "
            f"across {len(watches)} watch{'es' if len(watches) != 1 else ''}. "
            f"Top signal, from {top_watch}: {top_title}."
        )
    else:
        spoken = (
            f"Daily Signal Brief for {date_str}: no IntelX signals fired in "
            f"the last {hours} hours. Nothing to report — and I won't invent any."
        )

    lines = [
        f"# 📡 Daily Signal Brief — {date_str} IST",
        "",
        f"> Coverage: IntelX standing watches, last {hours} hours. "
        "Generated on demand — there is no routine schedule for this brief.",
        "",
        "## Bottom line",
        spoken,
        "",
        "## Top signals",
    ]
    if signals:
        lines.append("| # | Signal | Watch | Score | Source |")
        lines.append("| ---: | :--- | :--- | :---: | :--- |")
        for i, envelope in enumerate(signals, 1):
            title = str(envelope.get("title") or "(untitled signal)").replace("|", "/")
            watch = str(envelope.get("watch_id") or "unknown watch")
            publisher = str(envelope.get("publisher") or "").strip()
            url = str(envelope.get("url") or "").strip()
            source = f"{publisher} — {url}" if publisher and url else (url or publisher or "—")
            lines.append(f"| {i} | {title} | {watch} | {_score_of(envelope)} | {source} |")
        lines.extend(["", "### Signal details"])
        for i, envelope in enumerate(signals, 1):
            title = str(envelope.get("title") or "(untitled signal)")
            summary = str(envelope.get("summary") or "").strip()
            if summary:
                lines.append(f"{i}. **{title}** — {summary}")
            else:
                lines.append(f"{i}. **{title}**")
    else:
        lines.append("No IntelX signals fired in this window. That is the real answer — no highlights were fabricated.")
    lines.extend([
        "",
        "## Watch coverage",
    ])
    if watches:
        for watch, count in sorted(watches.items(), key=lambda kv: -kv[1]):
            lines.append(f"- **{watch}**: {count} signal{'s' if count != 1 else ''}")
        lines.append(
            "Watches that did not fire leave no trace in the outbox, so a quiet "
            "watch is not listed here — silence is not evidence it was checked."
        )
    else:
        lines.append("No watch fired in this window.")
    lines.extend([
        "",
        "## What this brief does not cover",
        "- Only IntelX standing-watch envelopes in the window. No Futuris forecasts, no research queries, no fleet ops.",
        "- Scores are IntelX significance scores, not probabilities — a high score means IntelX found the item significant, not that an outcome is likely.",
        "- F-40's closing segment was never recovered; this brief closes with the sources and generation footer below instead of the template's lost closing.",
        "",
        "## Sources",
    ])
    if signals:
        seen_urls: set[str] = set()
        for envelope in signals:
            url = str(envelope.get("url") or "").strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                title = str(envelope.get("title") or "Source")[:160]
                lines.append(f"- {title}: {url}")
    else:
        lines.append("No sources — no signals in this window.")
    lines.extend([
        "",
        f"_Generated on demand at {moment.strftime('%H:%M')} IST from IntelX watch outbox data. "
        "On-demand only: no routine cron produces this brief._",
    ])
    return {
        "markdown": "\n".join(lines),
        "spoken_summary": spoken,
        "signal_count": len(signals),
        "watch_count": len(watches),
        "date": date_str,
    }


def generate_brief(
    *,
    hours: int = DEFAULT_WINDOW_HOURS,
    outbox_path: Path | str | None = None,
    instant_path: Path | str | None = None,
    now: datetime | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Generate one Daily Signal Brief on demand from live IntelX data.

    Returns ``{"ok": True, "markdown": ..., "spoken_summary": ...,
    "signal_count": n, "watch_count": n, "saved_to": path | None, ...}``.
    ``ok`` is False only when the read itself fails unexpectedly; an
    empty window is an honest empty brief with ``ok`` True.
    """
    moment = now or datetime.now(timezone.utc)
    try:
        read = read_recent_signals(
            outbox_path, instant_path, hours=hours, now=moment
        )
    except Exception as exc:  # never raise into the caller
        return {
            "ok": False,
            "error": f"Could not read IntelX watch data: {type(exc).__name__}: {exc}",
            "signal_count": 0,
        }
    rendered = render_brief(
        read["signals"],
        hours=hours,
        generated_at=moment.astimezone(OWNER_TZ),
    )
    saved_to: str | None = None
    if save:
        try:
            BRIEF_DIR.mkdir(parents=True, exist_ok=True)
            path = BRIEF_DIR / f"{rendered['date']}.md"
            path.write_text(rendered["markdown"] + "\n", encoding="utf-8")
            saved_to = str(path)
        except OSError as exc:
            # A failed save must not hide a good brief.
            rendered["save_error"] = f"Brief generated but could not be saved: {exc}"
    return {
        "ok": True,
        "markdown": rendered["markdown"],
        "spoken_summary": rendered["spoken_summary"],
        "signal_count": rendered["signal_count"],
        "watch_count": rendered["watch_count"],
        "date": rendered["date"],
        "window_hours": hours,
        "malformed_lines": read["malformed"],
        "total_in_window": read["total_in_window"],
        "outbox_missing": read["outbox_missing"],
        "instant_missing": read["instant_missing"],
        "saved_to": saved_to,
        **({"save_error": rendered["save_error"]} if "save_error" in rendered else {}),
    }


__all__ = [
    "DEFAULT_WINDOW_HOURS",
    "BRIEF_DIR",
    "MAX_SIGNALS",
    "read_recent_signals",
    "render_brief",
    "generate_brief",
]
