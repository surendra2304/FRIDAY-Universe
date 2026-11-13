"""
exchanges/exchange_implementations.py — Concrete Adapters for Binance, Bybit, OKX, and Coinbase.

Implements concrete subclasses of BaseExchange with full normalization of symbols, orders, positions, and fees.
Provides ccxt-based integration when available, with resilient native REST/mock fallbacks.
"""

import os
import time
from typing import Any

from exchanges.base_exchange import (
    BaseExchange,
    ExchangeCapabilities,
    UnifiedBalance,
    UnifiedOrderResult,
    UnifiedPosition,
    UnifiedTicker,
)
from logger import get_logger

logger = get_logger("exchange_adapters")


def _env_flag(name: str, default: str = "false") -> bool:
    """True when the env var holds a truthy value (1/true/yes/on, case-insensitive)."""
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _enforce_no_live_trading(venue: str) -> None:
    """Fail-closed order gate shared by every adapter in this module.

    Mirrors the permanent invariant enforced by stratex_ccxt_adapter/client.py:
    live trading is blocked by design, and PAPER/RESEARCH modes may not place
    real venue orders. Raises PermissionError when either rule is violated.
    """
    trading_mode = os.environ.get("TRADING_MODE", "TESTNET").upper()
    if trading_mode == "LIVE" or os.environ.get("LIVE_TRADING_ENABLED") == "1":
        raise PermissionError(
            f"SECURITY CRITICAL: LIVE trading is permanently blocked by design "
            f"(venue={venue}, TRADING_MODE={trading_mode})."
        )
    if trading_mode == "PAPER" or os.environ.get("RESEARCH_MODE") == "1":
        raise PermissionError(
            f"STRATEX_ORDER_BLOCKED: cannot place real venue orders in "
            f"{trading_mode} / research mode (venue={venue})."
        )


def _live_trading_authorized() -> bool:
    """True only when the owner explicitly sets ALLOW_LIVE_TRADING=true (TASK-STR-001).

    Default false: every adapter in this module refuses live-endpoint orders
    and live-endpoint client construction unless this explicit opt-in exists.
    """
    return _env_flag("ALLOW_LIVE_TRADING", "false")

# Import new adapters
try:
    from exchanges.oanda_adapter import OandaExchangeAdapter
except ImportError:
    OandaExchangeAdapter = None

try:
    from exchanges.binance_futures_adapter import BinanceFuturesAdapter
except ImportError:
    BinanceFuturesAdapter = None


class BinanceExchangeAdapter(BaseExchange):
    """
    Binance Exchange Adapter supporting Spot and USD-M Futures.
    """

    def __init__(self, api_key: str = "", secret_key: str = ""):
        super().__init__(
            "binance",
            capabilities=ExchangeCapabilities(
                supports_futures=True,
                supports_shorting=True,
                supports_margin=True,
                supports_limit_orders=True,
                supports_stop_orders=True,
                supports_websocket=True,
                max_leverage=50.0
            )
        )
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.secret_key = secret_key or os.getenv("BINANCE_API_SECRET", "")
        self.is_connected = True
        self._client = None

    def _get_client(self):
        """Builds the python-binance client, fail-closed on live endpoints.

        BINANCE_TESTNET (default true) routes futures endpoints to the testnet.
        A live-endpoint client is only built when the owner has explicitly set
        ALLOW_LIVE_TRADING=true; otherwise this adapter returns None so read
        paths report empty data and order paths refuse to fabricate fills.
        """
        if self._client is None and self.api_key and self.secret_key:
            try:
                from binance.client import Client
                testnet = _env_flag("BINANCE_TESTNET", "true")
                if not testnet and not _live_trading_authorized():
                    logger.warning(
                        "[BINANCE_ADAPTER] BINANCE_TESTNET disabled without ALLOW_LIVE_TRADING=true; "
                        "refusing to build a live-endpoint client."
                    )
                    return None
                self._client = Client(self.api_key, self.secret_key, testnet=testnet)
            except Exception as e:
                logger.warning(f"[BINANCE_ADAPTER] python-binance client init skipped: {e}")
        return self._client

    def get_balance(self) -> dict[str, UnifiedBalance]:
        client = self._get_client()
        if client:
            try:
                acc = client.get_account()
                res = {}
                for b in acc.get("balances", []):
                    free_val = float(b.get("free", 0.0))
                    locked_val = float(b.get("locked", 0.0))
                    tot = free_val + locked_val
                    if tot > 0:
                        res[b["asset"]] = UnifiedBalance(b["asset"], free=free_val, used=locked_val, total=tot)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"[BINANCE_ADAPTER] get_balance API call failed: {e}")

        # No live API credentials or API failure: return empty rather than fabricating balances.
        if not (self.api_key and self.secret_key):
            logger.warning("[BINANCE_ADAPTER] No API credentials configured — returning empty balance set.")
        return {}

    def get_positions(self) -> list[UnifiedPosition]:
        client = self._get_client()
        if client:
            try:
                raw_positions = client.futures_account_positions()
                res: list[UnifiedPosition] = []
                for p in raw_positions:
                    amt = float(p.get("positionAmt", 0.0) or 0.0)
                    if amt == 0.0:
                        continue
                    entry = float(p.get("entryPrice", 0.0) or 0.0)
                    mark = float(p.get("markPrice", 0.0) or 0.0)
                    u_pnl = float(p.get("unRealizedProfit", 0.0) or 0.0)
                    lev = float(p.get("leverage", 1.0) or 1.0)
                    res.append(UnifiedPosition(
                        symbol=self.normalize_symbol(p.get("symbol", "")),
                        side="LONG" if amt > 0 else "SHORT",
                        quantity=abs(amt),
                        entry_price=entry,
                        mark_price=mark,
                        unrealized_pnl=u_pnl,
                        leverage=lev,
                        exchange="binance"
                    ))
                if res:
                    return res
            except Exception as e:
                logger.warning(f"[BINANCE_ADAPTER] get_positions API call failed: {e}")

        # No credentials or API failure: return empty rather than fabricating positions.
        logger.warning("[BINANCE_ADAPTER] Returning empty position set (no live client).")
        return []

    def get_ticker(self, symbol: str) -> UnifiedTicker:
        """Real ticker only (TASK-TRUST-001): raise instead of fabricating prices.

        The previous behaviour returned a hardcoded BTC ticker (~60,490) when
        no client was configured or the API failed — a strategy consuming that
        ticker could trade on invented prices. Read paths now fail exactly like
        order paths already do.
        """
        u_sym = self.normalize_symbol(symbol)
        client = self._get_client()
        if client is None:
            raise RuntimeError(
                f"[BINANCE_ADAPTER] No real ticker for {u_sym}: no exchange client configured "
                "(credentials missing, or live endpoints blocked by ALLOW_LIVE_TRADING=false). "
                "Refusing to fabricate prices."
            )
        try:
            raw_sym = self.denormalize_symbol(u_sym)
            t = client.get_ticker(symbol=raw_sym)
            bid = float(t.get("bidPrice") or 0.0)
            ask = float(t.get("askPrice") or 0.0)
            last = float(t.get("lastPrice") or 0.0)
            if bid <= 0 or ask <= 0 or last <= 0:
                raise RuntimeError(f"incomplete ticker payload for {u_sym}")
            return UnifiedTicker(
                symbol=u_sym, bid=bid, ask=ask, last=last,
                volume_24h=float(t.get("volume") or 0.0),
            )
        except Exception as e:
            logger.warning(f"[BINANCE_ADAPTER] get_ticker failed: {e}")
            raise RuntimeError(f"[BINANCE_ADAPTER] No real ticker for {u_sym}: {e}") from e

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict[str, list[list[float]]]:
        """Real order book only (TASK-TRUST-001): raise instead of returning a fake book."""
        u_sym = self.normalize_symbol(symbol)
        client = self._get_client()
        if client is None:
            raise RuntimeError(
                f"[BINANCE_ADAPTER] No real order book for {u_sym}: no exchange client configured. "
                "Refusing to fabricate liquidity."
            )
        try:
            raw_sym = self.denormalize_symbol(u_sym)
            ob = client.get_order_book(symbol=raw_sym, limit=limit)
            bids = [[float(p), float(q)] for p, q in ob.get("bids", [])]
            asks = [[float(p), float(q)] for p, q in ob.get("asks", [])]
            if not bids or not asks:
                raise RuntimeError(f"empty order book payload for {u_sym}")
            return {"bids": bids, "asks": asks}
        except Exception as e:
            logger.warning(f"[BINANCE_ADAPTER] get_orderbook failed: {e}")
            raise RuntimeError(f"[BINANCE_ADAPTER] No real order book for {u_sym}: {e}") from e

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None
    ) -> UnifiedOrderResult:
        """Places a real (testnet-routed) order via python-binance; never fabricates a fill.

        Fail-closed: live trading is permanently blocked, PAPER/RESEARCH modes
        cannot place real orders, and an unconfigured adapter raises instead of
        inventing a FILLED result (TASK-STR-001).
        """
        _enforce_no_live_trading("binance")
        u_sym = self.normalize_symbol(symbol)
        client = self._get_client()
        if client is None:
            raise RuntimeError(
                "[BINANCE_ADAPTER] Cannot place order: no exchange client configured "
                "(credentials missing, or live endpoints blocked by ALLOW_LIVE_TRADING=false). "
                "Refusing to fabricate a fill."
            )
        kwargs: dict[str, Any] = {
            "symbol": self.denormalize_symbol(u_sym),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if price is not None:
            kwargs["price"] = price
        if stop_price is not None:
            kwargs["stopPrice"] = stop_price
        raw = client.futures_create_order(**kwargs)
        executed_qty = float(raw.get("executedQty", 0.0) or 0.0)
        order_price = float(raw.get("price", 0.0) or 0.0)
        avg_price = float(raw.get("avgPrice", 0.0) or 0.0)
        return UnifiedOrderResult(
            order_id=str(raw.get("orderId", "")),
            symbol=u_sym,
            side=side.upper(),
            order_type=order_type.upper(),
            price=order_price or (price or 0.0),
            quantity=quantity,
            status=str(raw.get("status", "NEW")).upper(),
            executed_qty=executed_qty,
            avg_price=avg_price or order_price,
            fee_paid=0.0,  # Real venue fees arrive with later fill events; never invent them.
            exchange="binance",
        )

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancels a real order via python-binance; never fabricates success."""
        _enforce_no_live_trading("binance")
        client = self._get_client()
        if client is None:
            raise RuntimeError(
                "[BINANCE_ADAPTER] Cannot cancel order: no exchange client configured. "
                "Refusing to fabricate success."
            )
        try:
            client.futures_cancel_order(
                symbol=self.denormalize_symbol(self.normalize_symbol(symbol)), orderId=order_id
            )
            return True
        except Exception as e:
            logger.warning(f"[BINANCE_ADAPTER] cancel_order failed: {e}")
            return False

    def get_historical_data(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> list[dict[str, Any]]:
        """Real klines only (TASK-TRUST-001): raise instead of returning synthetic candles.

        The previous behaviour never contacted the venue at all — it returned a
        deterministic ascending 60,000+i*10 series presented as market history.
        """
        u_sym = self.normalize_symbol(symbol)
        client = self._get_client()
        if client is None:
            raise RuntimeError(
                f"[BINANCE_ADAPTER] No real candles for {u_sym}: no exchange client configured. "
                "Refusing to fabricate historical data."
            )
        try:
            raw = client.futures_klines(
                symbol=self.denormalize_symbol(u_sym), interval=timeframe, limit=min(limit, 1000)
            )
            candles = [
                {
                    "timestamp": int(k[0] / 1000),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                for k in (raw or [])
            ]
            if not candles:
                raise RuntimeError(f"empty klines payload for {u_sym}")
            return candles
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"[BINANCE_ADAPTER] get_historical_data failed: {e}")
            raise RuntimeError(f"[BINANCE_ADAPTER] No real candles for {u_sym}: {e}") from e

    def get_fees(self, symbol: str) -> tuple[float, float]:
        return 0.0002, 0.0004


# Aliases
BinanceExchange = BinanceExchangeAdapter


class BybitExchangeAdapter(BaseExchange):
    """
    Bybit Exchange Adapter (ccxt-compatible with resilient fallback).
    """

    def __init__(self, api_key: str = "", secret_key: str = ""):
        super().__init__(
            "bybit",
            capabilities=ExchangeCapabilities(
                supports_futures=True,
                supports_shorting=True,
                supports_margin=True,
                supports_limit_orders=True,
                supports_stop_orders=True,
                supports_websocket=True,
                max_leverage=100.0
            )
        )
        self.api_key = api_key or os.getenv("BYBIT_API_KEY", "")
        self.secret_key = secret_key or os.getenv("BYBIT_API_SECRET", "")
        self.is_connected = True
        self._ccxt_client = None
        self._init_ccxt()

    def _init_ccxt(self):
        try:
            import ccxt
            self._ccxt_client = ccxt.bybit({
                "apiKey": self.api_key,
                "secret": self.secret_key,
                "enableRateLimit": True
            })
        except Exception:
            self._ccxt_client = None

    def get_balance(self) -> dict[str, UnifiedBalance]:
        """Real balances only (TASK-TRUST-001): honest empty dict when unavailable.

        The previous behaviour fabricated a USDT 2,700 balance for the unified
        portfolio endpoint when no client was configured.
        """
        if self._ccxt_client and self.api_key:
            try:
                b = self._ccxt_client.fetch_balance()
                res = {}
                for cur, data in b.items():
                    if isinstance(data, dict) and data.get("total", 0) > 0:
                        res[cur] = UnifiedBalance(cur, free=data.get("free", 0.0), used=data.get("used", 0.0), total=data.get("total", 0.0))
                if res:
                    return res
            except Exception as e:
                logger.warning(f"[BYBIT_ADAPTER] get_balance failed: {e}")
        return {}

    def get_positions(self) -> list[UnifiedPosition]:
        """Real positions only (TASK-TRUST-001): honest empty list when unavailable.

        The previous behaviour returned a fabricated ETH/USDT LONG position
        that appeared in cross-exchange portfolio aggregations.
        """
        if self._ccxt_client and self.api_key:
            try:
                raw = self._ccxt_client.fetch_positions() or []
                res: list[UnifiedPosition] = []
                for p in raw:
                    amt = float(p.get("contracts") or 0.0) * (1 if p.get("side") == "long" else -1)
                    if amt == 0:
                        continue
                    res.append(UnifiedPosition(
                        symbol=self.normalize_symbol(p.get("symbol", "")),
                        side="LONG" if amt > 0 else "SHORT",
                        quantity=abs(amt),
                        entry_price=float(p.get("entryPrice") or 0.0),
                        mark_price=float(p.get("markPrice") or 0.0),
                        unrealized_pnl=float(p.get("unrealizedPnl") or 0.0),
                        leverage=float(p.get("leverage") or 1.0),
                        exchange="bybit",
                    ))
                if res:
                    return res
            except Exception as e:
                logger.warning(f"[BYBIT_ADAPTER] get_positions failed: {e}")
        return []

    def get_ticker(self, symbol: str) -> UnifiedTicker:
        """Real ticker only (TASK-TRUST-001): raise instead of fabricating prices."""
        u_sym = self.normalize_symbol(symbol)
        if self._ccxt_client is None:
            raise RuntimeError(
                f"[BYBIT_ADAPTER] No real ticker for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate prices."
            )
        try:
            t = self._ccxt_client.fetch_ticker(u_sym)
            bid = float(t.get("bid") or 0.0)
            ask = float(t.get("ask") or 0.0)
            last = float(t.get("last") or 0.0)
            if bid <= 0 or ask <= 0 or last <= 0:
                raise RuntimeError(f"incomplete ticker payload for {u_sym}")
            return UnifiedTicker(symbol=u_sym, bid=bid, ask=ask, last=last, volume_24h=float(t.get("baseVolume") or 0.0))
        except Exception as e:
            logger.warning(f"[BYBIT_ADAPTER] get_ticker failed: {e}")
            raise RuntimeError(f"[BYBIT_ADAPTER] No real ticker for {u_sym}: {e}") from e

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict[str, list[list[float]]]:
        """Real order book only (TASK-TRUST-001): raise instead of returning a fake book."""
        u_sym = self.normalize_symbol(symbol)
        if self._ccxt_client is None:
            raise RuntimeError(
                f"[BYBIT_ADAPTER] No real order book for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate liquidity."
            )
        try:
            ob = self._ccxt_client.fetch_order_book(u_sym, limit=limit)
            bids = [[float(p), float(q)] for p, q in ob.get("bids", [])]
            asks = [[float(p), float(q)] for p, q in ob.get("asks", [])]
            if not bids or not asks:
                raise RuntimeError(f"empty order book payload for {u_sym}")
            return {"bids": bids, "asks": asks}
        except Exception as e:
            logger.warning(f"[BYBIT_ADAPTER] get_orderbook failed: {e}")
            raise RuntimeError(f"[BYBIT_ADAPTER] No real order book for {u_sym}: {e}") from e

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None
    ) -> UnifiedOrderResult:
        """Refuses the order: real execution is not implemented for Bybit.

        The previous behaviour returned a fabricated FILLED result without
        contacting any venue. The fail-closed guard plus this honest refusal
        replace that fabricated success (TASK-STR-001).
        """
        _enforce_no_live_trading("bybit")
        raise RuntimeError(
            "[BYBIT_ADAPTER] Real order execution is not implemented for this venue; "
            "refusing to fabricate a fill."
        )

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Refuses to fabricate a cancellation for a venue without order execution."""
        _enforce_no_live_trading("bybit")
        raise RuntimeError(
            "[BYBIT_ADAPTER] Real order execution is not implemented for this venue; "
            "refusing to fabricate a cancellation."
        )

    def get_historical_data(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> list[dict[str, Any]]:
        """Real OHLCV only (TASK-TRUST-001): raise instead of returning synthetic candles."""
        u_sym = self.normalize_symbol(symbol)
        if self._ccxt_client is None:
            raise RuntimeError(
                f"[BYBIT_ADAPTER] No real candles for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate historical data."
            )
        try:
            ohlcv = self._ccxt_client.fetch_ohlcv(u_sym, timeframe=timeframe, limit=min(limit, 1000))
            candles = [
                {"timestamp": int(c[0] / 1000), "open": float(c[1]), "high": float(c[2]),
                 "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])}
                for c in (ohlcv or [])
            ]
            if not candles:
                raise RuntimeError(f"empty OHLCV payload for {u_sym}")
            return candles
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"[BYBIT_ADAPTER] get_historical_data failed: {e}")
            raise RuntimeError(f"[BYBIT_ADAPTER] No real candles for {u_sym}: {e}") from e

    def get_fees(self, symbol: str) -> tuple[float, float]:
        return 0.0002, 0.00055


# Aliases
BybitExchange = BybitExchangeAdapter


class OKXExchangeAdapter(BaseExchange):
    """
    OKX Exchange Adapter (ccxt-compatible with hyphenated pair normalization).
    """

    def __init__(self, api_key: str = "", secret_key: str = "", passphrase: str = ""):
        super().__init__(
            "okx",
            capabilities=ExchangeCapabilities(
                supports_futures=True,
                supports_shorting=True,
                supports_margin=True,
                supports_limit_orders=True,
                supports_stop_orders=True,
                supports_websocket=True,
                max_leverage=100.0
            )
        )
        self.api_key = api_key or os.getenv("OKX_API_KEY", "")
        self.secret_key = secret_key or os.getenv("OKX_API_SECRET", "")
        self.passphrase = passphrase or os.getenv("OKX_PASSPHRASE", "")
        self.is_connected = True
        self._ccxt_client = None
        self._init_ccxt()

    def _init_ccxt(self):
        try:
            import ccxt
            self._ccxt_client = ccxt.okx({
                "apiKey": self.api_key,
                "secret": self.secret_key,
                "password": self.passphrase,
                "enableRateLimit": True
            })
        except Exception:
            self._ccxt_client = None

    def denormalize_symbol(self, unified_symbol: str) -> str:
        # OKX uses hyphen: BTC-USDT
        return unified_symbol.replace("/", "-")

    def get_balance(self) -> dict[str, UnifiedBalance]:
        """Real balances only (TASK-TRUST-001): honest empty dict when unavailable."""
        if self._ccxt_client and self.api_key:
            try:
                b = self._ccxt_client.fetch_balance()
                res = {}
                for cur, data in b.items():
                    if isinstance(data, dict) and data.get("total", 0) > 0:
                        res[cur] = UnifiedBalance(cur, free=data.get("free", 0.0), used=data.get("used", 0.0), total=data.get("total", 0.0))
                if res:
                    return res
            except Exception as e:
                logger.warning(f"[OKX_ADAPTER] get_balance failed: {e}")
        return {}

    def get_positions(self) -> list[UnifiedPosition]:
        """Real positions only (TASK-TRUST-001): honest empty list when unavailable."""
        if self._ccxt_client and self.api_key:
            try:
                raw = self._ccxt_client.fetch_positions() or []
                res: list[UnifiedPosition] = []
                for p in raw:
                    amt = float(p.get("contracts") or 0.0) * (1 if p.get("side") == "long" else -1)
                    if amt == 0:
                        continue
                    res.append(UnifiedPosition(
                        symbol=self.normalize_symbol(p.get("symbol", "")),
                        side="LONG" if amt > 0 else "SHORT",
                        quantity=abs(amt),
                        entry_price=float(p.get("entryPrice") or 0.0),
                        mark_price=float(p.get("markPrice") or 0.0),
                        unrealized_pnl=float(p.get("unrealizedPnl") or 0.0),
                        leverage=float(p.get("leverage") or 1.0),
                        exchange="okx",
                    ))
                if res:
                    return res
            except Exception as e:
                logger.warning(f"[OKX_ADAPTER] get_positions failed: {e}")
        return []

    def get_ticker(self, symbol: str) -> UnifiedTicker:
        """Real ticker only (TASK-TRUST-001): raise instead of fabricating prices."""
        u_sym = self.normalize_symbol(symbol)
        if self._ccxt_client is None:
            raise RuntimeError(
                f"[OKX_ADAPTER] No real ticker for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate prices."
            )
        try:
            t = self._ccxt_client.fetch_ticker(u_sym)
            bid = float(t.get("bid") or 0.0)
            ask = float(t.get("ask") or 0.0)
            last = float(t.get("last") or 0.0)
            if bid <= 0 or ask <= 0 or last <= 0:
                raise RuntimeError(f"incomplete ticker payload for {u_sym}")
            return UnifiedTicker(symbol=u_sym, bid=bid, ask=ask, last=last, volume_24h=float(t.get("baseVolume") or 0.0))
        except Exception as e:
            logger.warning(f"[OKX_ADAPTER] get_ticker failed: {e}")
            raise RuntimeError(f"[OKX_ADAPTER] No real ticker for {u_sym}: {e}") from e

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict[str, list[list[float]]]:
        """Real order book only (TASK-TRUST-001): raise instead of returning a fake book."""
        u_sym = self.normalize_symbol(symbol)
        if self._ccxt_client is None:
            raise RuntimeError(
                f"[OKX_ADAPTER] No real order book for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate liquidity."
            )
        try:
            ob = self._ccxt_client.fetch_order_book(u_sym, limit=limit)
            bids = [[float(p), float(q)] for p, q in ob.get("bids", [])]
            asks = [[float(p), float(q)] for p, q in ob.get("asks", [])]
            if not bids or not asks:
                raise RuntimeError(f"empty order book payload for {u_sym}")
            return {"bids": bids, "asks": asks}
        except Exception as e:
            logger.warning(f"[OKX_ADAPTER] get_orderbook failed: {e}")
            raise RuntimeError(f"[OKX_ADAPTER] No real order book for {u_sym}: {e}") from e

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None
    ) -> UnifiedOrderResult:
        """Refuses the order: real execution is not implemented for OKX.

        The previous behaviour returned a fabricated FILLED result without
        contacting any venue. The fail-closed guard plus this honest refusal
        replace that fabricated success (TASK-STR-001).
        """
        _enforce_no_live_trading("okx")
        raise RuntimeError(
            "[OKX_ADAPTER] Real order execution is not implemented for this venue; "
            "refusing to fabricate a fill."
        )

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Refuses to fabricate a cancellation for a venue without order execution."""
        _enforce_no_live_trading("okx")
        raise RuntimeError(
            "[OKX_ADAPTER] Real order execution is not implemented for this venue; "
            "refusing to fabricate a cancellation."
        )

    def get_historical_data(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> list[dict[str, Any]]:
        """Real OHLCV only (TASK-TRUST-001): raise instead of returning synthetic candles."""
        u_sym = self.normalize_symbol(symbol)
        if self._ccxt_client is None:
            raise RuntimeError(
                f"[OKX_ADAPTER] No real candles for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate historical data."
            )
        try:
            ohlcv = self._ccxt_client.fetch_ohlcv(u_sym, timeframe=timeframe, limit=min(limit, 1000))
            candles = [
                {"timestamp": int(c[0] / 1000), "open": float(c[1]), "high": float(c[2]),
                 "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])}
                for c in (ohlcv or [])
            ]
            if not candles:
                raise RuntimeError(f"empty OHLCV payload for {u_sym}")
            return candles
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"[OKX_ADAPTER] get_historical_data failed: {e}")
            raise RuntimeError(f"[OKX_ADAPTER] No real candles for {u_sym}: {e}") from e

    def get_fees(self, symbol: str) -> tuple[float, float]:
        return 0.0002, 0.0005


# Aliases
OKXExchange = OKXExchangeAdapter


class CoinbaseExchangeAdapter(BaseExchange):
    """
    Coinbase Exchange Adapter (Spot only) — real ccxt-backed implementation.
    Falls back to empty results (never fabricated data) when credentials/client
    are unavailable.
    """

    def __init__(self, api_key: str = "", secret_key: str = ""):
        super().__init__(
            "coinbase",
            capabilities=ExchangeCapabilities(
                supports_futures=False,
                supports_shorting=False,
                supports_margin=False,
                supports_limit_orders=True,
                supports_stop_orders=False,
                supports_websocket=True,
                max_leverage=1.0
            )
        )
        self.api_key = api_key or os.getenv("COINBASE_API_KEY", "")
        self.secret_key = secret_key or os.getenv("COINBASE_API_SECRET", "")
        self.is_connected = False
        self._client = None

    def _get_client(self):
        if self._client is None and self.api_key and self.secret_key:
            try:
                import ccxt
                self._client = ccxt.coinbaseadvanced({
                    "apiKey": self.api_key,
                    "secret": self.secret_key,
                    "enableRateLimit": True,
                })
                self.is_connected = True
            except Exception as e:
                logger.warning(f"[COINBASE_ADAPTER] ccxt client init skipped: {e}")
        return self._client

    def get_balance(self) -> dict[str, UnifiedBalance]:
        """Real balances only (TASK-TRUST-001): honest empty dict when unavailable.

        The previous behaviour fabricated a USD 1,000 / BTC 0.01 balance when
        no client was configured — contradicting this adapter's own docstring.
        """
        client = self._get_client()
        if not client:
            return {}
        try:
            bal = client.fetch_balance()
            res: dict[str, UnifiedBalance] = {}
            for asset in (bal.get("total") or {}):
                total = float(bal.get("total", {}).get(asset, 0.0) or 0.0)
                free = float(bal.get("free", {}).get(asset, 0.0) or 0.0)
                used = float(bal.get("used", {}).get(asset, 0.0) or 0.0)
                if total > 0:
                    res[asset] = UnifiedBalance(asset, free=free, used=used, total=total)
            return res
        except Exception as e:
            logger.warning(f"[COINBASE_ADAPTER] get_balance failed: {e}")
            return {}

    def get_positions(self) -> list[UnifiedPosition]:
        # Spot-only venue: no derivatives positions by definition.
        return []

    def get_ticker(self, symbol: str) -> UnifiedTicker:
        """Real ticker only (TASK-TRUST-001): raise instead of fabricating prices."""
        u_sym = self.normalize_symbol(symbol)
        client = self._get_client()
        if not client:
            raise RuntimeError(
                f"[COINBASE_ADAPTER] No real ticker for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate prices."
            )
        try:
            t = client.fetch_ticker(self.denormalize_symbol(u_sym))
            bid = float(t.get("bid") or 0.0)
            ask = float(t.get("ask") or 0.0)
            last = float(t.get("last") or t.get("close") or 0.0)
            if bid <= 0 or ask <= 0 or last <= 0:
                raise RuntimeError(f"incomplete ticker payload for {u_sym}")
            return UnifiedTicker(symbol=u_sym, bid=bid, ask=ask, last=last, volume_24h=float(t.get("quoteVolume") or 0.0))
        except Exception as e:
            logger.warning(f"[COINBASE_ADAPTER] get_ticker failed: {e}")
            raise RuntimeError(f"[COINBASE_ADAPTER] No real ticker for {u_sym}: {e}") from e

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict[str, list[list[float]]]:
        """Real order book only (TASK-TRUST-001): raise instead of returning a fake book."""
        u_sym = self.normalize_symbol(symbol)
        client = self._get_client()
        if not client:
            raise RuntimeError(
                f"[COINBASE_ADAPTER] No real order book for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate liquidity."
            )
        try:
            ob = client.fetch_order_book(self.denormalize_symbol(u_sym), limit=limit)
            bids = [[float(p), float(q)] for p, q in ob.get("bids", [])]
            asks = [[float(p), float(q)] for p, q in ob.get("asks", [])]
            if not bids or not asks:
                raise RuntimeError(f"empty order book payload for {u_sym}")
            return {"bids": bids, "asks": asks}
        except Exception as e:
            logger.warning(f"[COINBASE_ADAPTER] get_orderbook failed: {e}")
            raise RuntimeError(f"[COINBASE_ADAPTER] No real order book for {u_sym}: {e}") from e

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None
    ) -> UnifiedOrderResult:
        """Places a real order through ccxt coinbase; gated fail-closed.

        Coinbase has no testnet venue, so any real order is a live order and
        requires the explicit owner opt-in ALLOW_LIVE_TRADING=true.
        """
        _enforce_no_live_trading("coinbase")
        if not _live_trading_authorized():
            raise PermissionError(
                "STRATEX_ORDER_BLOCKED: coinbase has no testnet venue; a real order requires "
                "explicit ALLOW_LIVE_TRADING=true (venue=coinbase)."
            )
        client = self._get_client()
        if not client:
            raise RuntimeError("[COINBASE_ADAPTER] Cannot place order without live credentials.")
        o = client.create_order(
            self.denormalize_symbol(self.normalize_symbol(symbol)),
            order_type.lower(), side.lower(), quantity, price, {}
        )
        fill_price = float(o.get("average") or o.get("price") or price or 0.0)
        return UnifiedOrderResult(
            order_id=str(o.get("id", "")),
            symbol=self.normalize_symbol(symbol),
            side=side.upper(),
            order_type=order_type.upper(),
            price=fill_price,
            quantity=float(o.get("filled") or quantity),
            status=str(o.get("status", "OPEN")).upper(),
            executed_qty=float(o.get("filled") or 0.0),
            avg_price=fill_price,
            fee_paid=float((o.get("fee") or {}).get("cost", 0.0) or 0.0),
            exchange="coinbase"
        )

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancels a real order; gated fail-closed (no testnet venue for coinbase)."""
        _enforce_no_live_trading("coinbase")
        if not _live_trading_authorized():
            raise PermissionError(
                "STRATEX_ORDER_BLOCKED: coinbase has no testnet venue; cancelling a real order "
                "requires explicit ALLOW_LIVE_TRADING=true (venue=coinbase)."
            )
        client = self._get_client()
        if not client:
            return False
        try:
            client.cancel_order(order_id, self.denormalize_symbol(self.normalize_symbol(symbol)))
            return True
        except Exception as e:
            logger.warning(f"[COINBASE_ADAPTER] cancel_order failed: {e}")
            return False

    def get_historical_data(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> list[dict[str, Any]]:
        """Real OHLCV only (TASK-TRUST-001): raise instead of returning synthetic candles."""
        u_sym = self.normalize_symbol(symbol)
        client = self._get_client()
        if not client:
            raise RuntimeError(
                f"[COINBASE_ADAPTER] No real candles for {u_sym}: no ccxt client configured. "
                "Refusing to fabricate historical data."
            )
        try:
            ohlcv = client.fetch_ohlcv(
                self.denormalize_symbol(u_sym),
                timeframe=timeframe, limit=min(limit, 300)
            )
            candles = [
                {"timestamp": int(c[0] / 1000), "open": float(c[1]), "high": float(c[2]),
                 "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])}
                for c in (ohlcv or [])
            ]
            if not candles:
                raise RuntimeError(f"empty OHLCV payload for {u_sym}")
            return candles
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"[COINBASE_ADAPTER] get_historical_data failed: {e}")
            raise RuntimeError(f"[COINBASE_ADAPTER] No real candles for {u_sym}: {e}") from e

    def get_fees(self, symbol: str) -> tuple[float, float]:
        client = self._get_client()
        if client:
            try:
                market = client.market(self.denormalize_symbol(self.normalize_symbol(symbol)))
                return float(market.get("maker", 0.004) or 0.004), float(market.get("taker", 0.006) or 0.006)
            except Exception:
                pass
        return 0.004, 0.006


CoinbaseExchange = CoinbaseExchangeAdapter


def get_exchange_adapter(exchange_id: str) -> BaseExchange:
    """Factory function to instantiate configured exchange adapter."""
    ex_map = {
        "binance": BinanceExchangeAdapter,
        "bybit": BybitExchangeAdapter,
        "okx": OKXExchangeAdapter,
        "coinbase": CoinbaseExchangeAdapter,
        "binance_futures": BinanceFuturesAdapter,
        "oanda": OandaExchangeAdapter,
    }
    adapter_cls = ex_map.get(exchange_id.lower())
    if not adapter_cls:
        raise ValueError(f"Unsupported exchange identifier: {exchange_id}")
    if adapter_cls is None:
        raise ValueError(f"Adapter {exchange_id} not available (import failed)")
    return adapter_cls()  # type: ignore[abstract]

