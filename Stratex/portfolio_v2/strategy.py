"""Stratex v2.1 - trend-pullback signal engine.

Rules (H1 candles, evaluated on CLOSED candles only, no lookahead):
  * Trend:   EMA50 vs EMA200, price on the trend side of EMA50,
             |EMA50 - EMA200| >= min_trend_sep_atr * ATR (regime filter).
  * Entry:   PULLBACK-RESUMPTION, not breakout chasing:
             - long:  candle dips to/below EMA(pullback_ema), then CLOSES back
                      above it with a bullish body, RSI(14) in the long band;
             - short: mirror.
  * Exit:    SL = sl_atr x ATR, TP = tp_atr x ATR (server-side, GTC).
  * Time:    session_utc hours only (default London open -> NY morning).
"""
from .indicators import atr, ema, rsi


def compute(candles, cfg):
    opens = [c["o"] for c in candles]
    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    return {
        "t": [c["t"] for c in candles],
        "open": opens,
        "close": closes,
        "high": highs,
        "low": lows,
        "ema9": ema(closes, cfg["ema_fast"]),
        "ema20": ema(closes, cfg["ema_mid"]),
        "ema50": ema(closes, cfg["ema_trend"]),
        "ema200": ema(closes, cfg["ema_macro"]),
        "rsi": rsi(closes, cfg["rsi_period"]),
        "atr": atr(highs, lows, closes, cfg["atr_period"]),
    }


def _ready(ind, i):
    for key in ("ema9", "ema20", "ema50", "ema200", "rsi", "atr"):
        if ind[key][i] is None or ind[key][i - 1] is None:
            return False
    return True


def signal_at(ind, i, cfg):
    """Return {'side','atr','strength'} when closed candle i triggers, else None.

    Modes:
      * meanrev       - RSI extreme against an EMA200 regime (Connors-style).
      * breakout      - Donchian channel break in the EMA200 trend direction.
      * trend-pullback- dip to EMA(pullback_ema) that closes back through it.
    """
    min_i = max(cfg["ema_macro"], cfg["ema_trend"]) + 2
    if i < min_i or not _ready(ind, i):
        return None
    hour = int((ind["t"][i] // 3600) % 24)
    h0, h1 = cfg["session_utc"]
    if not (h0 <= hour < h1):
        return None
    e50, e200 = ind["ema50"][i], ind["ema200"][i]
    o, c = ind["open"][i], ind["close"][i]
    hi, lo = ind["high"][i], ind["low"][i]
    atr_v, rsi_v = ind["atr"][i], ind["rsi"][i]
    if not atr_v or atr_v <= 0:
        return None
    mode = cfg.get("mode", "trend-pullback")

    if mode == "meanrev":
        if c > e200 and rsi_v <= cfg["rsi_buy_max"]:
            return {"side": "long", "atr": atr_v, "strength": round(rsi_v, 1)}
        if c < e200 and rsi_v >= cfg["rsi_sell_min"]:
            return {"side": "short", "atr": atr_v, "strength": round(rsi_v, 1)}
        return None

    if mode == "breakout":
        lookback = cfg.get("breakout_bars", 24)
        if i - lookback < 1:
            return None
        window_high = max(ind["high"][i - lookback:i])
        window_low = min(ind["low"][i - lookback:i])
        if c > e200 and c > window_high:
            return {"side": "long", "atr": atr_v, "strength": round((c - e200) / atr_v, 2)}
        if c < e200 and c < window_low:
            return {"side": "short", "atr": atr_v, "strength": round((e200 - c) / atr_v, 2)}
        return None

    # ---- trend-pullback (v2.1) ----
    strength = abs(e50 - e200) / atr_v
    if strength < cfg["min_trend_sep_atr"]:
        return None
    e20 = ind[f"ema{cfg['pullback_ema']}"][i]
    r_lo, r_hi = cfg["rsi_long"]
    s_lo, s_hi = cfg["rsi_short"]
    long_trend = e50 > e200 and c > e50
    short_trend = e50 < e200 and c < e50
    depth = cfg.get("dip_depth_atr", 0.0) * atr_v
    pull_long = lo <= e20 - depth and c > e20 and c > o
    pull_short = hi >= e20 + depth and c < e20 and c < o
    if long_trend and pull_long and r_lo <= rsi_v <= r_hi:
        return {"side": "long", "atr": atr_v, "strength": round(strength, 2)}
    if short_trend and pull_short and s_lo <= rsi_v <= s_hi:
        return {"side": "short", "atr": atr_v, "strength": round(strength, 2)}
    return None


def protective_levels(side, entry, atr_value, cfg):
    """(stop_loss, take_profit) around `entry` using ATR distances."""
    if side == "long":
        return entry - cfg["sl_atr"] * atr_value, entry + cfg["tp_atr"] * atr_value
    return entry + cfg["sl_atr"] * atr_value, entry - cfg["tp_atr"] * atr_value
