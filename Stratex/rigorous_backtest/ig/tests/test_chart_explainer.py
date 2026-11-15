"""Tests for TASK-IG-STR-08 chart_explainer (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.chart_explainer import PROMPT_TEMPLATE, explain, features

FORBIDDEN = ["you should buy", "you should sell", "we recommend",
             "buy now", "sell now", "guaranteed", "will rise",
             "will fall", "strong buy", "strong sell", "entry point",
             "take profit", "stop loss"]


def _trend(n=60, step=0.5, start=100.0):
    return [{"open": start + i * step, "high": start + i * step + 1.0,
             "low": start + i * step - 1.0, "close": start + i * step + 0.4}
            for i in range(n)]


def test_uptrend_features():
    f = features(_trend())
    assert f["sufficient"] is True
    assert f["trend"] == "up"
    assert f["rsi"] is not None and f["rsi"] > 50
    assert f["nearest_resistance"] is not None
    assert f["nearest_support"] is not None


def test_explain_describes_without_advising():
    out = explain(_trend(), symbol="BTCUSDT")
    text = out["text"].lower()
    assert "trending up" in text
    assert "description of past price action only" in text
    for phrase in FORBIDDEN:
        assert phrase not in text, phrase
    # schema guardrail: no advice-shaped fields anywhere
    assert not ({"advice", "recommendation", "signal", "order"}
                & set(out.keys()))
    assert not ({"advice", "recommendation", "signal", "order"}
                & set(out["features"].keys()))


def test_insufficient_data_is_honest():
    out = explain(_trend(10), symbol="X")
    assert out["features"]["sufficient"] is False
    assert "not enough data" in out["text"].lower()


def test_prompt_template_forbids_advice():
    t = PROMPT_TEMPLATE.lower()
    assert "never recommend" in t
    assert "{symbol}" in PROMPT_TEMPLATE
    assert "{features_json}" in PROMPT_TEMPLATE


def test_flat_market_labels():
    flat = [{"open": 100.0, "high": 100.6, "low": 99.4, "close": 100.0}
            for _ in range(60)]
    f = features(flat)
    assert f["trend"] == "flat"
    assert f["momentum"] == "neutral"
    assert f["volatility"] in ("low", "moderate")
