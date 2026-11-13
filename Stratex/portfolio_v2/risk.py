"""Position sizing: risk-based unit calculation + quote-currency conversion."""
from .oanda_client import OandaError

_RATE_CACHE = {}


def quote_to_usd_rate(client, account_id, quote_ccy):
    """USD value of one unit of `quote_ccy`, via live pricing (cached per process)."""
    if quote_ccy == "USD":
        return 1.0
    if quote_ccy in _RATE_CACHE:
        return _RATE_CACHE[quote_ccy]
    for instrument in (f"{quote_ccy}_USD", f"USD_{quote_ccy}"):
        try:
            prices = client.pricing(account_id, [instrument])["prices"]
            if not prices:
                continue
            bid = float(prices[0]["bids"][0]["price"])
            ask = float(prices[0]["asks"][0]["price"])
            mid = (bid + ask) / 2.0
            rate = mid if instrument.endswith("_USD") else 1.0 / mid
            _RATE_CACHE[quote_ccy] = rate
            return rate
        except (OandaError, KeyError, IndexError, ValueError):
            continue
    return 1.0  # conservative fallback; sizing stays risk-capped


def position_units(balance, risk_pct, entry, stop_loss, quote_usd_rate,
                   min_units=1, max_units=None):
    """Units such that hitting the stop loses exactly `risk_pct` of `balance`.

    value_at_risk_per_unit = |entry - stop| * quote_usd_rate
    """
    distance = abs(entry - stop_loss)
    if distance <= 0 or quote_usd_rate <= 0 or balance <= 0:
        return 0
    risk_amount = balance * risk_pct
    units = int(risk_amount / (distance * quote_usd_rate))
    if max_units is not None:
        units = min(units, int(max_units))
    return units if units >= min_units else 0
