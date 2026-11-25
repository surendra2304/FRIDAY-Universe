"""TASK-FRD-060 — Daily Signal Brief tests (hermetic, no network).

Covers outbox reading (window filter, dedupe, malformed lines, missing
files), the adopted render format, brief generation + save, and the
agent tool. Outbox files are fakes in a scratch dir; nothing touches
the real IntelX checkout.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.tools.builtin.signal_brief_tools import GenerateSignalBriefTool  # noqa: E402
from friday.workflows import signal_brief as sb  # noqa: E402

NOW = datetime(2026, 11, 25, 14, 0, tzinfo=timezone.utc)


def _envelope(*, watch="watch-ai", title="Signal title", score=80, hours_ago=2, alert_class="digest", dedupe="k1"):
    fired = NOW - timedelta(hours=hours_ago)
    return {
        "schema": "intelx.watch_alert/1",
        "envelope_id": f"env-{dedupe}",
        "dedupe_key": f"intelx.watch:{watch}:{dedupe}",
        "watch_id": watch,
        "domain": "ai",
        "alert_class": alert_class,
        "severity": "high" if alert_class == "instant" else "info",
        "quiet_hours_exempt": alert_class == "instant",
        "title": title,
        "summary": f"{title} in brief.",
        "url": "https://example.com/signal",
        "publisher": "Example News",
        "published_at": fired.isoformat(),
        "fired_at": fired.isoformat(),
        "score": score,
        "score_reasons": ["keyword match"],
    }


def _write_outbox(path: Path, envelopes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in envelopes) + "\n", encoding="utf-8")
    return path


def test_read_window_filters_old_envelopes(tmp_path):
    main = _write_outbox(
        tmp_path / "outbox.jsonl",
        [
            _envelope(title="Fresh signal", hours_ago=2, dedupe="fresh"),
            _envelope(title="Stale signal", hours_ago=30, dedupe="stale"),
            _envelope(title="Future signal", hours_ago=-1, dedupe="future"),
        ],
    )
    result = sb.read_recent_signals(main, tmp_path / "instant.jsonl", hours=24, now=NOW)
    assert result["ok"] is True
    assert [s["title"] for s in result["signals"]] == ["Fresh signal"]
    assert result["total_in_window"] == 1


def test_read_dedupes_and_sorts_by_score(tmp_path):
    main = _write_outbox(
        tmp_path / "outbox.jsonl",
        [
            _envelope(title="Low score", score=40, dedupe="a"),
            _envelope(title="High score", score=95, dedupe="b"),
            _envelope(title="High score dup", score=95, dedupe="b"),
        ],
    )
    result = sb.read_recent_signals(main, tmp_path / "instant.jsonl", hours=24, now=NOW)
    assert [s["title"] for s in result["signals"]] == ["High score", "Low score"]


def test_read_merges_instant_outbox(tmp_path):
    main = _write_outbox(tmp_path / "outbox.jsonl", [_envelope(title="Digest signal", dedupe="d1")])
    instant = _write_outbox(
        tmp_path / "instant.jsonl",
        [_envelope(title="Big break", alert_class="instant", score=99, dedupe="i1")],
    )
    result = sb.read_recent_signals(main, instant, hours=24, now=NOW)
    assert [s["title"] for s in result["signals"]] == ["Big break", "Digest signal"]


def test_read_skips_malformed_lines_and_wrong_schema(tmp_path):
    main = tmp_path / "outbox.jsonl"
    good = _envelope(title="Good signal", dedupe="g1")
    main.write_text(
        json.dumps(good) + "\n"
        "this is not json\n"
        + json.dumps({"schema": "something.else/1", "title": "Wrong schema"}) + "\n"
        + json.dumps(["not", "an", "object"]) + "\n",
        encoding="utf-8",
    )
    result = sb.read_recent_signals(main, tmp_path / "instant.jsonl", hours=24, now=NOW)
    assert [s["title"] for s in result["signals"]] == ["Good signal"]
    assert result["malformed"] == 3


def test_read_missing_outboxes_is_honest_empty(tmp_path):
    result = sb.read_recent_signals(tmp_path / "nope.jsonl", tmp_path / "nope2.jsonl", hours=24, now=NOW)
    assert result["ok"] is True
    assert result["signals"] == []
    assert result["outbox_missing"] is True
    assert result["instant_missing"] is True


def test_render_brief_uses_only_envelope_facts(tmp_path):
    signals = [
        _envelope(watch="watch-ai", title="AI breakthrough", score=92, dedupe="s1"),
        _envelope(watch="watch-markets", title="Market move", score=70, dedupe="s2"),
    ]
    rendered = sb.render_brief(signals, hours=24, generated_at=NOW.astimezone(sb.OWNER_TZ))
    md = rendered["markdown"]
    assert "# 📡 Daily Signal Brief — 2026-11-25 IST" in md
    assert "2 IntelX signals" in rendered["spoken_summary"]
    assert "AI breakthrough" in md and "Market move" in md
    assert "watch-ai" in md and "watch-markets" in md
    assert "92" in md and "70" in md
    assert "https://example.com/signal" in md
    assert "What this brief does not cover" in md
    assert "significance scores, not probabilities" in md
    assert "F-40's closing segment was never recovered" in md
    assert rendered["signal_count"] == 2
    assert rendered["watch_count"] == 2


def test_render_brief_empty_is_honest():
    rendered = sb.render_brief([], hours=24, generated_at=NOW.astimezone(sb.OWNER_TZ))
    assert rendered["signal_count"] == 0
    assert "no IntelX signals fired" in rendered["markdown"]
    assert "won't invent" in rendered["spoken_summary"]


def test_generate_brief_saves_markdown(tmp_path, monkeypatch):
    main = _write_outbox(tmp_path / "outbox.jsonl", [_envelope(title="Saved signal", dedupe="sv1")])
    instant = tmp_path / "instant.jsonl"
    instant.write_text("", encoding="utf-8")
    monkeypatch.setattr(sb, "BRIEF_DIR", tmp_path / "briefs")
    result = sb.generate_brief(hours=24, outbox_path=main, instant_path=instant, now=NOW)
    assert result["ok"] is True
    assert result["signal_count"] == 1
    assert result["saved_to"] is not None
    saved = Path(result["saved_to"])
    assert saved.exists()
    assert "Saved signal" in saved.read_text(encoding="utf-8")


def test_generate_brief_missing_outbox_is_honest_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "BRIEF_DIR", tmp_path / "briefs")
    result = sb.generate_brief(hours=24, outbox_path=tmp_path / "gone.jsonl", instant_path=tmp_path / "gone2.jsonl", now=NOW)
    assert result["ok"] is True
    assert result["signal_count"] == 0
    assert result["outbox_missing"] is True
    assert "no IntelX signals fired" in result["markdown"]


def test_tool_returns_brief_and_metadata(tmp_path, monkeypatch):
    main = _write_outbox(tmp_path / "outbox.jsonl", [_envelope(title="Tool signal", score=88, dedupe="t1")])
    instant = tmp_path / "instant.jsonl"
    instant.write_text("", encoding="utf-8")
    monkeypatch.setattr(sb, "resolve_outbox_path", lambda: main)
    monkeypatch.setattr(sb, "resolve_instant_outbox_path", lambda _main=None: instant)
    monkeypatch.setattr(sb, "BRIEF_DIR", tmp_path / "briefs")
    result = GenerateSignalBriefTool().execute()
    assert result.is_error is False
    assert "Tool signal" in result.content
    assert result.metadata["signal_count"] == 1
    assert result.metadata["watch_count"] == 1


def test_tool_empty_window_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "resolve_outbox_path", lambda: tmp_path / "gone.jsonl")
    monkeypatch.setattr(sb, "resolve_instant_outbox_path", lambda _main=None: tmp_path / "gone2.jsonl")
    monkeypatch.setattr(sb, "BRIEF_DIR", tmp_path / "briefs")
    result = GenerateSignalBriefTool().execute()
    assert result.is_error is False
    assert result.metadata["signal_count"] == 0
    assert "no IntelX signals fired" in result.content
