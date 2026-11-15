"""Tests for TASK-IG-STR-09 assistant_pack (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.assistant_pack import (DISCIPLINE_NOTES, DISCLAIMER,
                               REQUIRED_SECTIONS, render_trade_plan,
                               validate_plan_document)

ARGS = dict(symbol="BTCUSDT", timeframe="4h", context="range regime",
            setup="retest of range high", evidence="RD bar not yet run",
            invalidation="close below range mid", sizing="0.1% venue equity",
            review="after 20 forward trades")


def test_render_complete_plan_validates():
    doc = render_trade_plan(**ARGS)
    assert validate_plan_document(doc) is True
    for s in REQUIRED_SECTIONS:
        assert ("## " + s) in doc
    assert DISCLAIMER in doc
    assert "not a signal" in DISCLAIMER


def test_empty_section_refused():
    bad = dict(ARGS)
    bad["invalidation"] = "  "
    try:
        render_trade_plan(**bad)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty invalidation")


def test_discipline_notes_wellformed_and_clean():
    assert len(DISCIPLINE_NOTES) >= 5
    for note in DISCIPLINE_NOTES:
        assert note["title"] and note["text"]
        low = (note["title"] + note["text"]).lower()
        assert "guaranteed" not in low
        assert "get rich" not in low
    titles = [n["title"] for n in DISCIPLINE_NOTES]
    assert "No tips, no signals" in titles
    assert "Consistency over jackpots" in titles
