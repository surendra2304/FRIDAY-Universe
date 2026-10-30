"""Jarvis adaptation: deterministic providers and real price calculations."""
from __future__ import annotations

import pytest
from friday_core.real_hybrid_assistant import HybridAssistantEngine
from Stratex.real_market_momentum import MarketMomentumEngine


def test_local_first():
    engine = HybridAssistantEngine([], None, lambda q: q.upper())
    assert engine.respond("Jarvis, time").text == "TIME"


def test_model_failover_and_history():
    def provider(model, messages):
        if model == "bad":
            raise RuntimeError("offline")
        return messages[-1]["content"]
    engine = HybridAssistantEngine(["bad", "good"], provider, lambda q: None, history_turns=1)
    assert engine.respond("hello").model == "good"
    engine.respond("next")
    assert [m["content"] for m in engine.history] == ["next", "next"]


def test_cooldown_and_recovery():
    now = [100.0]
    calls = []
    def provider(model, messages):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("rate limit: try again in 1m 2.5s")
        return "recovered"
    engine = HybridAssistantEngine(["m"], provider, lambda q: None, lambda: now[0])
    assert engine.respond("hello").source == "fallback"
    assert engine.cooldown_until == 164.5
    engine.respond("waiting")
    assert len(calls) == 1
    now[0] = 165
    assert engine.respond("again").text == "recovered"


def test_retry_header():
    error = RuntimeError("429")
    error.headers = {"Retry-After": "4.5"}
    assert HybridAssistantEngine.retry_delay(error) == 4.5


def test_no_history_and_empty_query():
    engine = HybridAssistantEngine(["m"], lambda *args: "ok", lambda q: None, history_turns=0)
    engine.respond("test")
    assert engine.history == []
    with pytest.raises(ValueError):
        engine.respond("Jarvis,")


@pytest.mark.parametrize("prices,price,signal", [(list(range(100, 115)), 116, "STRONG BUY"),
    (list(range(115, 100, -1)), 99, "STRONG SELL / SHORT"), ([100] * 10, 100, "HOLD")])
def test_momentum(prices, price, signal):
    report = MarketMomentumEngine().analyze("TEST", price, 107, prices)
    assert report.signal == signal
    assert report.short_average == sum(prices[-5:]) / 5
    assert report.percent_change == pytest.approx((price - 107) / 107 * 100)


def test_sparse_quotes():
    report = MarketMomentumEngine().analyze("BTC-USD", 100, 100, [None, 99])
    assert report.signal == "HOLD"
    assert report.short_average is None


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_price(value):
    with pytest.raises(ValueError):
        MarketMomentumEngine().analyze("X", value, 100, [])
