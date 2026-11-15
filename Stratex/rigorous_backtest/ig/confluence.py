"""Fib/BOS confluence entry model — RD-programme candidate family.

TASK-IG-STR-06 (IG corpus item DYeU6nSBl9K).

Implements EXACTLY the rules frozen in declaration.json /
CONFLUENCE_DECLARATION.md in this directory. The declaration governs:
if this code and the declaration disagree, the declaration wins and
the code is wrong. No parameter here may be tuned after seeing
out-of-sample results — that is the programme's Anti-Overfit Law.

THE RULES (long side; short is the mirror):
  1. Leg: a swing low L (fractal window 2) followed by a swing high H
     with H > L. Leg range R = H - L.
  2. Retracement: after H, a candle whose low enters the Fib zone
     [H - 0.618R, H - 0.500R] without any candle closing below L
     (a close below L kills the leg).
  3. Confirmation (break of structure): after the zone touch, the
     first candle closing above H emits the signal at that close.
  4. Stop = L. Targets are leg extensions from L:
     T1 = L + 1.272R, T2 = L + 1.618R.
Each leg produces at most one signal. This module only GENERATES
signals with their declared stop/targets; exits, costs and scoring
belong to the RD harness when the declared run happens.

RESEARCH ONLY — demo-only universe, no production consumer.

Stdlib only, Python 3.10-compatible. Candles are dicts with
high/low/close, oldest first.
"""

FIB_ZONE = (0.500, 0.618)
EXTENSIONS = (1.272, 1.618)
SWING_WINDOW = 2


def _swings(candles, window=SWING_WINDOW):
    highs, lows = [], []
    n = len(candles)
    for i in range(window, n - window):
        h, l = candles[i]["high"], candles[i]["low"]
        if all(h > candles[j]["high"] for j in range(i - window, i + window + 1) if j != i):
            highs.append(i)
        if all(l < candles[j]["low"] for j in range(i - window, i + window + 1) if j != i):
            lows.append(i)
    return highs, lows


def _long_signals(candles):
    hi_idx, lo_idx = _swings(candles)
    signals = []
    used_legs = set()
    for li in lo_idx:
        L = candles[li]["low"]
        # next swing high after this low forms the leg
        leg_high = None
        for hi in hi_idx:
            if hi > li and candles[hi]["high"] > L:
                leg_high = hi
                break
        if leg_high is None or leg_high in used_legs:
            continue
        H = candles[leg_high]["high"]
        R = H - L
        if R <= 0:
            continue
        zone_top = H - FIB_ZONE[0] * R
        zone_bot = H - FIB_ZONE[1] * R
        touched = False
        for j in range(leg_high + 1, len(candles)):
            c = candles[j]
            if c["close"] < L:
                break  # leg invalidated
            if not touched:
                # zone touch = the candle's range intersects the zone
                if c["low"] <= zone_top and c["high"] >= zone_bot:
                    touched = True
                continue
            if c["close"] > H:
                signals.append({
                    "direction": "long",
                    "leg_low_index": li, "leg_high_index": leg_high,
                    "entry_index": j, "entry": c["close"],
                    "stop": L,
                    "target1": L + EXTENSIONS[0] * R,
                    "target2": L + EXTENSIONS[1] * R,
                    "leg_range": R,
                })
                used_legs.add(leg_high)
                break
    return signals


def _short_signals(candles):
    hi_idx, lo_idx = _swings(candles)
    signals = []
    used_legs = set()
    for hi in hi_idx:
        H = candles[hi]["high"]
        leg_low = None
        for li in lo_idx:
            if li > hi and candles[li]["low"] < H:
                leg_low = li
                break
        if leg_low is None or leg_low in used_legs:
            continue
        L = candles[leg_low]["low"]
        R = H - L
        if R <= 0:
            continue
        zone_bot = L + FIB_ZONE[0] * R
        zone_top = L + FIB_ZONE[1] * R
        touched = False
        for j in range(leg_low + 1, len(candles)):
            c = candles[j]
            if c["close"] > H:
                break  # leg invalidated
            if not touched:
                # zone touch = the candle's range intersects the zone
                if c["high"] >= zone_bot and c["low"] <= zone_top:
                    touched = True
                continue
            if c["close"] < L:
                signals.append({
                    "direction": "short",
                    "leg_low_index": leg_low, "leg_high_index": hi,
                    "entry_index": j, "entry": c["close"],
                    "stop": H,
                    "target1": H - EXTENSIONS[0] * R,
                    "target2": H - EXTENSIONS[1] * R,
                    "leg_range": R,
                })
                used_legs.add(leg_low)
                break
    return signals


def generate_signals(candles):
    """All confluence signals in the series, sorted by entry index."""
    out = _long_signals(candles) + _short_signals(candles)
    out.sort(key=lambda s: s["entry_index"])
    return out
