"""Order-book / depth-of-market features — Stratex research inputs.

TASK-IG-STR-02 (IG corpus item DXRVxfjDZmu).

Computes standard microstructure features from a single order-book
snapshot: top-of-book spread, mid, microprice, top-N bid/ask imbalance,
cumulative depth within a price band, and "wall" detection (single
levels whose size dwarfs the typical level on that side).

RESEARCH INPUTS ONLY. These features describe a snapshot; they are not
signals, they place no orders, and nothing in production consumes them.
A feature that cannot be computed from the snapshot (e.g. an empty
side) is reported as None — never interpolated or fabricated.

Input shape: bids and asks are sequences of (price, size) pairs, best
first (bids descending by price, asks ascending). Sizes are in base
units; prices in quote units. Stdlib only, Python 3.10-compatible.
"""

import statistics


def _check_side(levels, side):
    for price, size in levels:
        if price <= 0:
            raise ValueError("%s level price must be > 0" % side)
        if size < 0:
            raise ValueError("%s level size must be >= 0" % side)


def mid_price(bids, asks):
    if not bids or not asks:
        return None
    return 0.5 * (bids[0][0] + asks[0][0])


def spread_bps(bids, asks):
    mid = mid_price(bids, asks)
    if mid is None or mid == 0:
        return None
    return (asks[0][0] - bids[0][0]) / mid * 10000.0


def microprice(bids, asks):
    """Size-weighted top-of-book price (Stoikov)."""
    if not bids or not asks:
        return None
    bid_px, bid_sz = bids[0]
    ask_px, ask_sz = asks[0]
    total = bid_sz + ask_sz
    if total == 0:
        return mid_price(bids, asks)
    return (ask_px * bid_sz + bid_px * ask_sz) / total


def imbalance(bids, asks, levels=5):
    """Top-N volume imbalance in [-1, 1]: +1 = all bid depth."""
    if levels <= 0:
        raise ValueError("levels must be > 0")
    bid_vol = sum(sz for _, sz in bids[:levels])
    ask_vol = sum(sz for _, sz in asks[:levels])
    total = bid_vol + ask_vol
    if total == 0:
        return None
    return (bid_vol - ask_vol) / total


def depth_within_bps(levels_side, mid, band_bps, side):
    """Cumulative size within band_bps of mid on one side."""
    if mid is None:
        return None
    total = 0.0
    for price, size in levels_side:
        dist = abs(price - mid) / mid * 10000.0
        if dist <= band_bps:
            total += size
        elif side == "bid" and price < mid:
            break
        elif side == "ask" and price > mid:
            break
    return total


def detect_walls(levels_side, side, multiple=5.0, min_share=0.25):
    """Levels whose size is >= `multiple` x the side's median level
    size AND >= `min_share` of the side's visible depth."""
    if multiple <= 1:
        raise ValueError("multiple must be > 1")
    sizes = [sz for _, sz in levels_side if sz > 0]
    if len(sizes) < 3:
        return []
    med = statistics.median(sizes)
    total = sum(sizes)
    if med == 0 or total == 0:
        return []
    walls = []
    for price, size in levels_side:
        if size >= multiple * med and size >= min_share * total:
            walls.append({"side": side, "price": price, "size": size,
                          "median_multiple": size / med,
                          "depth_share": size / total})
    return walls


def snapshot_features(bids, asks, levels=5, band_bps=50.0,
                      wall_multiple=5.0):
    """All features for one snapshot, as a plain dict (None where a
    feature is not computable from the data given)."""
    bids = list(bids)
    asks = list(asks)
    _check_side(bids, "bid")
    _check_side(asks, "ask")
    mid = mid_price(bids, asks)
    return {
        "mid": mid,
        "spread_bps": spread_bps(bids, asks),
        "microprice": microprice(bids, asks),
        "imbalance_top": imbalance(bids, asks, levels),
        "bid_depth_band": depth_within_bps(bids, mid, band_bps, "bid"),
        "ask_depth_band": depth_within_bps(asks, mid, band_bps, "ask"),
        "walls": detect_walls(bids, "bid", wall_multiple)
                 + detect_walls(asks, "ask", wall_multiple),
        "bid_levels": len(bids),
        "ask_levels": len(asks),
    }
