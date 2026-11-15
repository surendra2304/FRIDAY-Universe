"""Black-Scholes options pricing + greeks — Stratex research utility.

TASK-IG-STR-01 (IG corpus item DXqzqc0Dh6K).

A pricing/research utility only: it prices European options under the
Black-Scholes model and solves for implied volatility. It places no
orders, connects to no venue, and feeds no production engine — Stratex
trades no options today; this exists so research can value and compare
option structures honestly instead of hand-waving.

Model assumptions (stated, not hidden): European exercise, constant
risk-free rate and volatility, lognormal underlying, optional constant
continuous dividend yield q (default 0). Prices outside these
assumptions (American exercise, vol smiles) are out of scope by design.

Stdlib only (math.erf), Python 3.10-compatible.
"""

import math

_SQRT2 = math.sqrt(2.0)


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _validate(S, K, T, sigma):
    if S <= 0:
        raise ValueError("spot S must be > 0")
    if K <= 0:
        raise ValueError("strike K must be > 0")
    if T < 0:
        raise ValueError("time to expiry T must be >= 0")
    if sigma is not None and sigma <= 0:
        raise ValueError("volatility sigma must be > 0")


def _d1_d2(S, K, T, r, sigma, q):
    vol_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def bs_price(S, K, T, r, sigma, option_type="call", q=0.0):
    """Black-Scholes price of a European option.

    S spot, K strike, T years to expiry, r risk-free rate (annual,
    continuous), sigma annualised volatility, q continuous dividend
    yield. At T == 0 returns intrinsic value.
    """
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")
    _validate(S, K, T, sigma)
    if T == 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_r = math.exp(-r * T)
    disc_q = math.exp(-q * T)
    if option_type == "call":
        return S * disc_q * _norm_cdf(d1) - K * disc_r * _norm_cdf(d2)
    return K * disc_r * _norm_cdf(-d2) - S * disc_q * _norm_cdf(-d1)


def greeks(S, K, T, r, sigma, option_type="call", q=0.0):
    """Black-Scholes greeks as a dict.

    delta/gamma are unitless / per-unit-spot; vega is per 1.00 (100 vol
    points) change in sigma; theta is per year; rho is per 1.00 change
    in r. Requires T > 0 (greeks are degenerate at expiry).
    """
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")
    _validate(S, K, T, sigma)
    if T == 0:
        raise ValueError("greeks are undefined at expiry (T == 0)")
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_r = math.exp(-r * T)
    disc_q = math.exp(-q * T)
    pdf = _norm_pdf(d1)
    sqrt_t = math.sqrt(T)
    gamma = disc_q * pdf / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf * sqrt_t
    if option_type == "call":
        delta = disc_q * _norm_cdf(d1)
        theta = (-(S * disc_q * pdf * sigma) / (2.0 * sqrt_t)
                 + q * S * disc_q * _norm_cdf(d1)
                 - r * K * disc_r * _norm_cdf(d2))
        rho = K * T * disc_r * _norm_cdf(d2)
    else:
        delta = -disc_q * _norm_cdf(-d1)
        theta = (-(S * disc_q * pdf * sigma) / (2.0 * sqrt_t)
                 - q * S * disc_q * _norm_cdf(-d1)
                 + r * K * disc_r * _norm_cdf(-d2))
        rho = -K * T * disc_r * _norm_cdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega,
            "theta": theta, "rho": rho}


def put_call_parity_residual(S, K, T, r, sigma, q=0.0):
    """C - P - (S*e^{-qT} - K*e^{-rT}); zero (to float error) if the
    pricer is internally consistent."""
    c = bs_price(S, K, T, r, sigma, "call", q)
    p = bs_price(S, K, T, r, sigma, "put", q)
    return c - p - (S * math.exp(-q * T) - K * math.exp(-r * T))


def implied_vol(price, S, K, T, r, option_type="call", q=0.0,
                tol=1e-10, max_iter=200):
    """Solve Black-Scholes implied volatility by bisection.

    Raises ValueError when the target price violates no-arbitrage
    bounds for the given inputs (no implied vol exists), or when the
    solver fails to converge.
    """
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")
    _validate(S, K, T, None)
    if T == 0:
        raise ValueError("implied vol is undefined at expiry (T == 0)")
    disc_r = math.exp(-r * T)
    disc_q = math.exp(-q * T)
    if option_type == "call":
        lo_bound = max(S * disc_q - K * disc_r, 0.0)
        hi_bound = S * disc_q
    else:
        lo_bound = max(K * disc_r - S * disc_q, 0.0)
        hi_bound = K * disc_r
    if price < lo_bound - 1e-12 or price > hi_bound + 1e-12:
        raise ValueError(
            "price %r outside no-arbitrage bounds [%r, %r]; "
            "no implied volatility exists" % (price, lo_bound, hi_bound))
    lo, hi = 1e-6, 5.0
    f_lo = bs_price(S, K, T, r, lo, option_type, q) - price
    f_hi = bs_price(S, K, T, r, hi, option_type, q) - price
    if f_lo > 0 or f_hi < 0:
        raise ValueError("could not bracket implied volatility")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = bs_price(S, K, T, r, mid, option_type, q) - price
        if abs(f_mid) < tol:
            return mid
        if f_mid > 0:
            hi = mid
        else:
            lo = mid
    raise ValueError("implied volatility solver did not converge")
