"""Prediction-market research lane (Polymarket-style) — READ-ONLY.

TASK-IG-STR-11 (IG corpus item DWBGc0dEZXj).

Registers prediction-market event contracts as a Stratex RESEARCH
lane: normalise public market data (Polymarket Gamma API shape),
expose implied probabilities, and snapshot them for study. The lane
is bound by the SAME evidence bar as every other Stratex lane: any
strategy derived from these markets must pass the RD programme bar
(expectancy/PF/folds/2x costs/Bonferroni/holdout) and the Phase-3
forward protocol before trading, and then only on demo venues —
prediction markets themselves are real-money venues and this module
will never touch them: no wallet, no keys, no orders, no POSTs.

The collector takes an injectable fetcher (url -> parsed JSON) so it
is fully testable offline; production use would pass a plain HTTPS
GET against the public, keyless Gamma API.

Stdlib only, Python 3.10-compatible.
"""

import json

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"


def _as_list(value):
    """Gamma returns outcomes/prices as JSON strings OR lists."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except ValueError:
            return []
    return []


def parse_market(raw):
    """Normalise one Gamma-shaped market dict. Returns None when the
    record lacks the fields a research snapshot needs (id, question,
    at least one priced outcome) — malformed records are skipped and
    counted by the caller, never repaired into existence."""
    if not isinstance(raw, dict):
        return None
    outcomes = _as_list(raw.get("outcomes"))
    prices = _as_list(raw.get("outcomePrices"))
    if raw.get("id") is None or not raw.get("question") or not outcomes:
        return None
    if len(prices) != len(outcomes):
        return None
    try:
        priced = [{"name": str(name), "price": float(px)}
                  for name, px in zip(outcomes, prices)]
    except (TypeError, ValueError):
        return None
    return {
        "id": str(raw["id"]),
        "question": raw["question"],
        "outcomes": priced,
        "volume": float(raw.get("volume") or 0.0),
        "liquidity": float(raw.get("liquidity") or 0.0),
        "end_date": raw.get("endDate"),
        "active": bool(raw.get("active")),
        "closed": bool(raw.get("closed")),
    }


def implied_probabilities(market):
    """Outcome name -> implied probability (the market price). For a
    binary market these sum to ~1.0 (the residual is the spread /
    overround — reported, not hidden)."""
    return {o["name"]: o["price"] for o in market["outcomes"]}


class PredictionLaneCollector:
    """Collects normalised market snapshots via an injected fetcher."""

    def __init__(self, fetcher, base_url=GAMMA_MARKETS_URL):
        self._fetcher = fetcher
        self._base_url = base_url

    def fetch_markets(self, limit=100, active_only=True):
        """Returns (markets, skipped_count)."""
        url = "%s?limit=%d" % (self._base_url, limit)
        if active_only:
            url += "&active=true&closed=false"
        raw_list = self._fetcher(url)
        if not isinstance(raw_list, list):
            raise ValueError("fetcher returned a non-list payload")
        markets, skipped = [], 0
        for raw in raw_list:
            m = parse_market(raw)
            if m is None:
                skipped += 1
            else:
                markets.append(m)
        return markets, skipped


LANE_REGISTRATION = {
    "lane": "prediction_markets",
    "status": "research_only",
    "evidence_bar": ("RD programme bar (expectancy_net > 0, PF >= 1.2, "
                     ">= 200 OOS trades, >= 4/5 positive folds, 2x costs, "
                     "Bonferroni, holdout) then Phase-3 forward protocol"),
    "trading": "none — real-money venue; no wallet, keys, or orders",
    "data": "Polymarket Gamma public API (keyless, read-only)",
}
