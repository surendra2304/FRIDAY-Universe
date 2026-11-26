"""BSM-vs-market option mispricing scan — Stratex research utility.

TASK-STR-064. Research only: scans a list of option instruments and flags
those whose market price breaks from the Black-Scholes-Merton model price
computed by TASK-IG-STR-01 (``ig.options_pricing``). Emits a ranked
mispricing report. It places no orders, connects to no venue, and feeds no
production engine — Stratex trades no options today; the report is a
research memo, not a signal.

Method, per instrument:
  model price  = bs_price(S, K, T, r, sigma_ref, option_type, q)
  abs deviation = market_price - model_price
  rel deviation = abs deviation / model_price (inf when model is 0 and the
                  market price is positive — a worthless-by-model option
                  trading above zero)
  implied vol  = implied_vol(market_price, ...) — None when the market
                  price violates no-arbitrage bounds (no implied vol
                  exists); that row is INVALID_PRICE, the strongest break.
  status       = FLAGGED when |rel deviation| >= flag_threshold (default
                  5%), otherwise OK; INVALID_PRICE when no implied vol
                  exists; ERROR when the instrument record itself is
                  malformed (missing/negative inputs) — the scan records
                  the error and continues instead of dying on one bad row.

Ranking: by |rel deviation| descending (invalid-price rows carry inf, so
they rank first), ties by |abs deviation| descending.

Stdlib only, offline, deterministic. The market-price list is
caller-supplied: a live chain is fetched separately (checkpoint 2,
Deribit public API) and passed in as data, so this module stays testable
on fixtures with no network.
"""

import math

from ig.options_pricing import bs_price, implied_vol

DEFAULT_FLAG_THRESHOLD = 0.05

_REQUIRED = ("instrument", "option_type", "S", "K", "T", "market_price")


def _validate_instrument(inst):
    """Return an error string for a malformed instrument, else None."""
    if not isinstance(inst, dict):
        return "instrument is not a mapping"
    for key in _REQUIRED:
        if key not in inst:
            return "missing field %r" % (key,)
    if inst["option_type"] not in ("call", "put"):
        return "option_type must be 'call' or 'put'"
    for key in ("S", "K", "T", "market_price"):
        value = inst[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return "field %r is not a number" % (key,)
        if not math.isfinite(value):
            return "field %r is not finite" % (key,)
    if inst["S"] <= 0:
        return "spot S must be > 0"
    if inst["K"] <= 0:
        return "strike K must be > 0"
    if inst["T"] < 0:
        return "time to expiry T must be >= 0"
    if inst["market_price"] < 0:
        return "market_price must be >= 0"
    return None


def scan_mispricing(instruments, r, sigma_ref, flag_threshold=DEFAULT_FLAG_THRESHOLD,
                    q=0.0):
    """Scan instruments for BSM mispricing.

    instruments: iterable of dicts with keys instrument, option_type
        ('call'/'put'), S, K, T (years), market_price; optional q.
    r: risk-free rate (annual, continuous). sigma_ref: reference
        volatility the model price is computed at. q: default dividend
        yield applied when an instrument carries none.
    Returns a list of result dicts, one per instrument, in input order.
    """
    if sigma_ref is None or sigma_ref <= 0:
        raise ValueError("sigma_ref must be > 0")
    results = []
    for inst in instruments:
        error = _validate_instrument(inst)
        if error is not None:
            results.append({
                "instrument": inst.get("instrument") if isinstance(inst, dict) else None,
                "option_type": inst.get("option_type") if isinstance(inst, dict) else None,
                "S": None, "K": None, "T": None, "market_price": None,
                "model_price": None, "abs_dev": None, "rel_dev": None,
                "implied_vol": None, "iv_dev": None, "moneyness": None,
                "status": "ERROR", "error": error,
            })
            continue
        S, K, T = inst["S"], inst["K"], inst["T"]
        market = inst["market_price"]
        q_inst = inst.get("q", q)
        model = bs_price(S, K, T, r, sigma_ref, inst["option_type"], q_inst)
        abs_dev = market - model
        if model > 0:
            rel_dev = abs_dev / model
        else:
            rel_dev = math.inf if market > 0 else 0.0
        iv = None
        iv_dev = None
        status = "FLAGGED" if abs(rel_dev) >= flag_threshold else "OK"
        if T > 0:
            try:
                iv = implied_vol(market, S, K, T, r, inst["option_type"], q_inst)
                iv_dev = iv - sigma_ref
            except ValueError:
                status = "INVALID_PRICE"
        results.append({
            "instrument": inst["instrument"],
            "option_type": inst["option_type"],
            "S": S, "K": K, "T": T, "market_price": market,
            "model_price": model, "abs_dev": abs_dev, "rel_dev": rel_dev,
            "implied_vol": iv, "iv_dev": iv_dev,
            "moneyness": S / K,
            "status": status, "error": None,
        })
    return results


def ranked_report(results):
    """Results ranked by |rel deviation| desc, ties by |abs deviation| desc.

    INVALID_PRICE rows carry rel_dev inf, so they rank first. ERROR rows
    carry no deviation and rank last.
    """
    def key(row):
        rel = row["rel_dev"]
        rel_key = abs(rel) if rel is not None else -1.0
        dev = row["abs_dev"]
        dev_key = abs(dev) if dev is not None else -1.0
        return (-rel_key, -dev_key)
    return sorted(results, key=key)


def render_markdown(results, title="BSM mispricing scan"):
    """Render the ranked report as markdown (research memo)."""
    ranked = ranked_report(results)
    flagged = sum(1 for row in ranked if row["status"] == "FLAGGED")
    invalid = sum(1 for row in ranked if row["status"] == "INVALID_PRICE")
    errors = sum(1 for row in ranked if row["status"] == "ERROR")
    lines = ["# %s" % title, "",
             "Scanned %d instruments: %d OK, %d FLAGGED, %d INVALID_PRICE, "
             "%d ERROR." % (len(ranked), len(ranked) - flagged - invalid - errors,
                            flagged, invalid, errors),
             "",
             "| instrument | type | S | K | T | market | model | rel dev | IV | status |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for row in ranked:
        def fmt(value, spec="%.4f"):
            return "—" if value is None else spec % value
        rel = row["rel_dev"]
        if rel is None:
            rel_text = "—"
        elif rel == math.inf:
            rel_text = "inf"
        else:
            rel_text = fmt(rel * 100.0, "%+.2f") + "%"
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            row["instrument"], row["option_type"],
            fmt(row["S"], "%.2f"), fmt(row["K"], "%.2f"),
            fmt(row["T"], "%.4f"), fmt(row["market_price"], "%.2f"),
            fmt(row["model_price"], "%.2f"), rel_text,
            fmt(row["implied_vol"], "%.4f"), row["status"]))
    return "\n".join(lines) + "\n"
