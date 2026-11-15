"""LLM chart-reading explainer — describes charts, never advises.

TASK-IG-STR-08 (IG corpus item Def5xMKtvmC — an ad for an AI that
"interprets charts for you"; implemented here under FRIDAY's rules).

Two layers:
  1. features() — deterministic extraction from OHLC candles: trend
     (EMA slope), momentum (RSI-14), volatility (ATR as % of price),
     distance to the nearest swing high/low.
  2. explain() — a plain-language rendering of exactly those features,
     plus PROMPT_TEMPLATE: the instructions an LLM layer must use if
     it narrates the features, which forbid recommendations outright.

HARD GUARDRAILS: the output schema has no advice, recommendation,
signal, or order fields — by construction, not by policy text — and
the test suite asserts the rendered text contains no recommendation
language. This module explains charts alongside the strategy engine;
it never tells anyone what to do with them.

Stdlib only, Python 3.10-compatible. Candles are dicts with
open/high/low/close, oldest first.
"""

PROMPT_TEMPLATE = """You are a chart describer for a trading research desk.
Describe ONLY what the features below show, in plain language, for the
symbol {symbol}. Refer to trend, momentum, volatility, and the nearest
levels. NEVER recommend buying, selling, holding, entering, exiting,
or sizing any position. NEVER predict future prices. If the features
are insufficient, say what is missing.

Features (JSON):
{features_json}
"""


def _ema(values, period):
    if not values:
        return None
    k = 2.0 / (period + 1)
    out = values[0]
    for v in values[1:]:
        out = v * k + out * (1 - k)
    return out


def _rsi(closes, period=14):
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        # no losses: 100 when there were gains; a perfectly flat
        # series has no momentum at all -> neutral 50, not 100
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _atr_pct(candles, period=14):
    if len(candles) <= period:
        return None
    trs = []
    for i in range(1, len(candles)):
        c, p = candles[i], candles[i - 1]
        trs.append(max(c["high"] - c["low"],
                       abs(c["high"] - p["close"]),
                       abs(c["low"] - p["close"])))
    atr = sum(trs[-period:]) / period
    last = candles[-1]["close"]
    return (atr / last * 100.0) if last else None


def _nearest_levels(candles, window=30):
    recent = candles[-window:]
    last = candles[-1]["close"]
    above = [c["high"] for c in recent if c["high"] > last]
    below = [c["low"] for c in recent if c["low"] < last]
    return (min(above) if above else None,
            max(below) if below else None)


def features(candles):
    """Deterministic chart features. Fields that cannot be computed
    from the data are None — described as missing, never invented."""
    closes = [c["close"] for c in candles]
    if len(closes) < 35:
        return {"sufficient": False, "candles": len(closes),
                "reason": "need >= 35 candles for trend/momentum features"}
    fast = _ema(closes[-35:], 10)
    slow = _ema(closes[-35:], 30)
    slope = (fast - slow) / slow if slow else 0.0
    trend = "up" if slope > 0.001 else "down" if slope < -0.001 else "flat"
    rsi = _rsi(closes)
    momentum = ("overbought" if rsi is not None and rsi >= 70 else
                "oversold" if rsi is not None and rsi <= 30 else "neutral")
    atr_pct = _atr_pct(candles)
    vol = ("high" if atr_pct is not None and atr_pct >= 3.0 else
           "low" if atr_pct is not None and atr_pct <= 0.5 else "moderate")
    res, sup = _nearest_levels(candles)
    last = closes[-1]
    return {
        "sufficient": True,
        "candles": len(closes),
        "last_close": last,
        "trend": trend,
        "ema_slope_pct": slope * 100.0,
        "rsi": rsi,
        "momentum": momentum,
        "atr_pct": atr_pct,
        "volatility": vol,
        "nearest_resistance": res,
        "resistance_distance_pct": ((res - last) / last * 100.0) if res else None,
        "nearest_support": sup,
        "support_distance_pct": ((last - sup) / last * 100.0) if sup else None,
    }


def explain(candles, symbol=""):
    """Plain-language description of the computed features. The text
    is assembled only from measured values — it describes, it does
    not recommend, and it does not predict."""
    f = features(candles)
    if not f["sufficient"]:
        return {"symbol": symbol, "features": f,
                "text": "Not enough data to describe this chart: %s."
                        % f["reason"]}
    lines = []
    lines.append(
        "Trend: price is trending %s over the window "
        "(fast/slow average slope %+.2f%%)."
        % (f["trend"], f["ema_slope_pct"]))
    lines.append(
        "Momentum: %s (RSI %.0f)." % (f["momentum"], f["rsi"]))
    lines.append(
        "Volatility: %s (average true range %.2f%% of price)."
        % (f["volatility"], f["atr_pct"]))
    if f["nearest_resistance"] is not None:
        lines.append(
            "Nearest overhead swing high in the window: %.4f "
            "(%.2f%% above the last close)."
            % (f["nearest_resistance"], f["resistance_distance_pct"]))
    if f["nearest_support"] is not None:
        lines.append(
            "Nearest swing low below in the window: %.4f "
            "(%.2f%% below the last close)."
            % (f["nearest_support"], f["support_distance_pct"]))
    lines.append("This is a description of past price action only.")
    return {"symbol": symbol, "features": f, "text": " ".join(lines)}
