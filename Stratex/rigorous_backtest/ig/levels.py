"""Support/resistance level detection + chart annotation records.

TASK-IG-STR-03 (IG corpus item DWqHA4ghG56).

Finds swing highs/lows in an OHLC series, clusters nearby swings into
support/resistance levels, scores each level by how often price tested
it, and emits the levels as JSON-serialisable annotation records the
owner (or a chart UI) can draw directly.

`annotate_levels` (TASK-STR-066) extends the base S/R records with the
previous-day open/close (PDO/PDC) reference levels and with S/R levels
recomputed from the current day's 5-minute candles, so one annotation
output carries all three level families side by side.

ANNOTATION AID ONLY — a level is a place price reacted before, drawn
for the owner's own review. This module emits no signals, no entries,
no orders, and nothing in production consumes it.

Input: candles are dicts with at least "high", "low", "close" keys,
oldest first. Stdlib only, Python 3.10-compatible.
"""


def swing_points(candles, window=2):
    """Indices of swing highs and lows.

    Index i is a swing high when its high is strictly greater than the
    highs of the `window` candles on each side (ties do not count —
    a flat top is not a swing). Returns (high_indices, low_indices).
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    n = len(candles)
    highs, lows = [], []
    for i in range(window, n - window):
        h = candles[i]["high"]
        l = candles[i]["low"]
        if all(h > candles[j]["high"] for j in range(i - window, i + window + 1) if j != i):
            highs.append(i)
        if all(l < candles[j]["low"] for j in range(i - window, i + window + 1) if j != i):
            lows.append(i)
    return highs, lows


def _cluster(points, tol_frac):
    """Cluster (index, price) points whose prices sit within tol_frac
    (relative) of the running cluster mean. Returns clusters sorted by
    price, each {price (mean), touches, indices}."""
    clusters = []
    for idx, price in sorted(points, key=lambda p: p[1]):
        placed = False
        for c in clusters:
            if abs(price - c["price"]) <= tol_frac * c["price"]:
                c["indices"].append(idx)
                c["touches"] += 1
                c["price"] = (c["price"] * (c["touches"] - 1) + price) / c["touches"]
                placed = True
                break
        if not placed:
            clusters.append({"price": price, "touches": 1, "indices": [idx]})
    return clusters


def find_levels(candles, window=2, tol_frac=0.005, min_touches=1):
    """Detect S/R levels and classify them against the last close.

    Returns annotation records sorted by price:
    {kind: "support"|"resistance", price, touches, first_index,
     last_index, strength} where strength = touches normalised so the
    most-tested level scores 1.0. Levels exactly at the last close are
    labelled by their origin (swing high -> resistance, swing low ->
    support) and flagged "at_price": True.
    """
    if tol_frac <= 0:
        raise ValueError("tol_frac must be > 0")
    if len(candles) < 2 * window + 1:
        return []
    hi_idx, lo_idx = swing_points(candles, window)
    last_close = candles[-1]["close"]
    records = []
    for origin, idxs in (("resistance", hi_idx), ("support", lo_idx)):
        pts = [(i, candles[i]["high" if origin == "resistance" else "low"])
               for i in idxs]
        for c in _cluster(pts, tol_frac):
            if c["touches"] < min_touches:
                continue
            kind = origin
            at_price = abs(c["price"] - last_close) <= tol_frac * last_close
            if not at_price:
                kind = "resistance" if c["price"] > last_close else "support"
            records.append({
                "kind": kind,
                "origin": origin,
                "price": round(c["price"], 10),
                "touches": c["touches"],
                "first_index": min(c["indices"]),
                "last_index": max(c["indices"]),
                "at_price": at_price,
            })
    if records:
        top = max(r["touches"] for r in records)
        for r in records:
            r["strength"] = r["touches"] / top
    records.sort(key=lambda r: r["price"])
    return records


def _prev_day_records(prev_day, last_close, tol_frac):
    """PDO/PDC annotation records from the previous day's candle.

    prev_day is a dict with at least "open" and "close" keys. Each
    record is a single-touch reference level: kind "pdo" /
    "pdc", origin "prev_day", first/last index None (the level comes
    from one daily candle, not from a swing in the base series).
    """
    if not isinstance(prev_day, dict) or "open" not in prev_day \
            or "close" not in prev_day:
        raise ValueError('prev_day must be a dict with "open" and "close"')
    records = []
    for kind, price in (("pdo", prev_day["open"]),
                        ("pdc", prev_day["close"])):
        records.append({
            "kind": kind,
            "origin": "prev_day",
            "price": round(price, 10),
            "touches": 1,
            "first_index": None,
            "last_index": None,
            "at_price": abs(price - last_close) <= tol_frac * last_close,
        })
    return records


def annotate_levels(candles, prev_day=None, today_5m=None,
                    window=2, tol_frac=0.005, min_touches=1):
    """Full annotation output: base S/R levels plus PDO/PDC and
    current-day 5-minute levels (TASK-STR-066).

    - Base records come from find_levels() on `candles` (unchanged).
    - `prev_day` (optional dict with "open"/"close") adds one PDO and
      one PDC record, each a single-touch reference level.
    - `today_5m` (optional list of the current day's 5-minute candles)
      adds S/R levels recomputed from that series; those records carry
      "timeframe": "5m" and indices relative to the 5-minute series.
    - With neither extra input the output is identical to find_levels().
      Strength is normalised across the combined set so the most-tested
      level scores 1.0; records are sorted by price.
    """
    if tol_frac <= 0:
        raise ValueError("tol_frac must be > 0")
    if len(candles) < 2 * window + 1:
        return []
    records = find_levels(candles, window=window, tol_frac=tol_frac,
                          min_touches=min_touches)
    last_close = candles[-1]["close"]
    if prev_day is not None:
        records.extend(_prev_day_records(prev_day, last_close, tol_frac))
    if today_5m is not None:
        for r in find_levels(today_5m, window=window, tol_frac=tol_frac,
                             min_touches=min_touches):
            r["timeframe"] = "5m"
            records.append(r)
    if records:
        top = max(r["touches"] for r in records)
        for r in records:
            r["strength"] = r["touches"] / top
    records.sort(key=lambda r: r["price"])
    return records
