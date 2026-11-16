"""Selective CCXT adapter for venues Stratex does NOT cover natively
(TASK-IG2-STR-02; CCXT is MIT — unified-API shape adopted, library used as
the already-declared Stratex dependency ccxt>=4.5.6).

Native Stratex adapters already cover binance / bybit / okx / coinbase
(Stratex/exchanges/exchange_implementations.py), Binance Futures, OANDA
(FX — CCXT has no OANDA, and none is attempted here), cTrader and MT5.
This module is ONLY for the gap venues below, and it is DEMO/TESTNET ONLY:

* construction refuses sandbox=False — there is no live mode to enable;
* order placement is forwarded only to a sandbox/testnet endpoint and
  still requires the caller's explicit ``confirm_testnet=True``;
* read paths (markets / ticker / OHLCV / balance) are normalized to the
  same shapes as Stratex.stratex_ccxt_adapter.models.

Per the spec card, on builder-code venues CCXT routing can add ~1bp on top
of exchange fees; ``BUILDER_FEE_NOTE`` venues carry that warning in their
metadata so the measurement programme prices it in before any demo flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# venue -> has a CCXT sandbox/testnet mode we can pin to
EXTRA_VENUES: dict[str, dict[str, Any]] = {
    "kraken": {"testnet": True, "builder_fee_note": False},
    "kucoin": {"testnet": True, "builder_fee_note": False},
    "gateio": {"testnet": True, "builder_fee_note": False},
    "bitget": {"testnet": True, "builder_fee_note": True},
    "mexc": {"testnet": False, "builder_fee_note": False},
    "hyperliquid": {"testnet": True, "builder_fee_note": False},
}

NATIVE_COVERED = {"binance", "binanceusdm", "bybit", "okx", "coinbase",
                  "coinbaseexchange", "oanda"}


class LiveTradingRefused(PermissionError):
    """Raised on any attempt to use this adapter outside demo/testnet."""


class UnsupportedVenue(ValueError):
    """Raised for native-covered, OANDA, or unregistered venue ids."""


class _ExchangeLike(Protocol):
    def set_sandbox_mode(self, enabled: bool) -> Any: ...
    def fetch_ticker(self, symbol: str) -> dict: ...
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list: ...
    def fetch_balance(self) -> dict: ...
    def create_order(self, symbol: str, type: str, side: str,
                     amount: float, price: float | None) -> dict: ...


@dataclass(frozen=True)
class NormalizedTicker:
    venue: str
    symbol: str
    last: float | None
    bid: float | None
    ask: float | None
    timestamp: int | None


@dataclass(frozen=True)
class NormalizedCandle:
    venue: str
    symbol: str
    timeframe: str
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class ExtraVenueAdapter:
    """CCXT-backed adapter restricted to gap venues, testnet-pinned."""

    def __init__(self, venue: str, *, sandbox: bool = True,
                 exchange: _ExchangeLike | None = None,
                 api_key: str | None = None, secret: str | None = None):
        venue = (venue or "").lower()
        if venue in NATIVE_COVERED:
            raise UnsupportedVenue(
                f"{venue!r} is covered by a native Stratex adapter (or is "
                "OANDA, which CCXT does not support) — do not route it here")
        if venue not in EXTRA_VENUES:
            raise UnsupportedVenue(
                f"{venue!r} is not in the selective EXTRA_VENUES registry "
                f"{sorted(EXTRA_VENUES)}; add it deliberately, not by default")
        if sandbox is not True:
            raise LiveTradingRefused(
                "ExtraVenueAdapter is demo/testnet ONLY: sandbox must be True. "
                "Stratex live trading stays gated by the owner and is never "
                "enabled by research-layer code.")
        if not EXTRA_VENUES[venue]["testnet"]:
            raise LiveTradingRefused(
                f"{venue!r} has no CCXT testnet mode, so this demo-only "
                "adapter cannot pin it to a safe endpoint — refused")
        self.venue = venue
        self.meta = EXTRA_VENUES[venue]
        if exchange is not None:
            self.exchange = exchange
        else:
            try:
                import ccxt
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("ccxt not installed (declared in "
                                   "Stratex/requirements.txt)") from exc
            if venue not in getattr(ccxt, "exchanges", ()):
                raise UnsupportedVenue(f"installed ccxt has no {venue!r}")
            cfg: dict[str, Any] = {"enableRateLimit": True}
            if api_key is not None:
                cfg["apiKey"] = api_key
            if secret is not None:
                cfg["secret"] = secret
            self.exchange = getattr(ccxt, venue)(cfg)
        # Pin to testnet; a venue object that cannot be pinned is refused.
        setter = getattr(self.exchange, "set_sandbox_mode", None)
        if not callable(setter):
            raise LiveTradingRefused(
                f"{venue!r} exchange object exposes no set_sandbox_mode; "
                "cannot prove testnet pinning — refused")
        setter(True)
        self._sandbox_pinned = True

    # -- normalized reads -------------------------------------------------
    def fetch_ticker(self, symbol: str) -> NormalizedTicker:
        raw = self.exchange.fetch_ticker(symbol)
        return NormalizedTicker(self.venue, symbol, raw.get("last"),
                                raw.get("bid"), raw.get("ask"),
                                raw.get("timestamp"))

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h",
                    limit: int = 200) -> list[NormalizedCandle]:
        rows = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [NormalizedCandle(self.venue, symbol, timeframe, int(r[0]),
                                  float(r[1]), float(r[2]), float(r[3]),
                                  float(r[4]), float(r[5])) for r in rows]

    def fetch_balance(self) -> dict[str, float]:
        raw = self.exchange.fetch_balance()
        total = raw.get("total") or {}
        return {k: float(v) for k, v in total.items()
                if isinstance(v, (int, float))}

    # -- testnet-only order path -------------------------------------------
    def create_testnet_order(self, symbol: str, side: str, amount: float,
                             price: float | None = None, *,
                             confirm_testnet: bool = False) -> dict:
        """Forward an order ONLY to the pinned testnet endpoint.

        Demo-only double gate: the adapter is sandbox-pinned at construction
        and the caller must still pass confirm_testnet=True per order. Any
        other path to a venue order does not exist in this module.
        """
        if not self._sandbox_pinned:
            raise LiveTradingRefused("sandbox pin lost — refusing order")
        if not confirm_testnet:
            raise LiveTradingRefused(
                "pass confirm_testnet=True to acknowledge this order goes to "
                "the venue TESTNET only; there is no live path here")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if amount <= 0:
            raise ValueError("amount must be positive")
        otype = "limit" if price is not None else "market"
        raw = self.exchange.create_order(symbol, otype, side, amount, price)
        return {"venue": self.venue, "symbol": symbol, "side": side,
                "amount": amount, "price": price, "type": otype,
                "testnet": True, "raw_id": raw.get("id"),
                "builder_fee_note": bool(self.meta["builder_fee_note"])}
