"""
autonomy/multi_venue_engine.py — Multi-Venue Trading Engine for Stratex.

Orchestrates trading across Binance Futures (Crypto) and OANDA (Forex/Indices/Commodities).
Unified risk management, balance tracking, and position management across venues.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from exchanges.base_exchange import (
    UnifiedBalance,
    UnifiedOrderResult,
    UnifiedPosition,
    UnifiedTicker,
)
from logger import get_logger

logger = get_logger("multi_venue_engine")


class MultiVenueEngine:
    """
    Multi-Venue Trading Engine.
    
    Manages trading across:
    - Binance Futures: Crypto perpetual futures (24/7)
    - OANDA: Forex, Indices, Commodities, Crypto CFDs (24/5)
    
    Features:
    - Unified balance tracking across venues
    - Cross-venue position limits
    - Venue-specific risk management
    - Unified candle data for signals
    """

    def __init__(
        self,
        binance_api_key: str = "",
        binance_secret: str = "",
        binance_testnet: bool = True,
        oanda_api_key: str = "",
        oanda_account_id: str = "",
        oanda_practice: bool = True,
        starting_balance: float = 1000.0,
        max_positions_per_venue: int = 9999,
        max_total_positions: int = 9999,
        risk_per_trade_pct: float = 0.02,
        max_daily_loss_pct: float = 1.0,
        telegram_bot: Optional[Any] = None,
    ):
        self.starting_balance = starting_balance
        # No position limits
        self.max_positions_per_venue = max_positions_per_venue
        self.max_total_positions = max_total_positions
        self.risk_per_trade_pct = risk_per_trade_pct
        # No daily loss limit
        self.max_daily_loss_pct = max_daily_loss_pct
        self.telegram_bot = telegram_bot

        # Initialize venues
        self.venues: Dict[str, Any] = {}
        
        # Binance Futures (Crypto)
        binance_key = binance_api_key or os.getenv("BINANCE_API_KEY", "")
        if binance_key:
            try:
                from exchanges.binance_futures_adapter import BinanceFuturesAdapter
                self.venues["binance_futures"] = BinanceFuturesAdapter(
                    api_key=binance_key,
                    secret_key=binance_secret or os.getenv("BINANCE_API_SECRET", ""),
                    testnet=binance_testnet,
                )
                logger.info("[MULTI_VENUE] Binance Futures adapter initialized")
            except Exception as e:
                logger.warning(f"[MULTI_VENUE] Binance Futures init failed: {e}")
        else:
            logger.info("[MULTI_VENUE] Binance Futures skipped (no API key)")

        # OANDA (Forex/Indices/Commodities)
        oanda_key = oanda_api_key or os.getenv("OANDA_API_KEY", "")
        oanda_acct = oanda_account_id or os.getenv("OANDA_ACCOUNT_ID", "")
        if oanda_key and oanda_acct:
            try:
                from exchanges.oanda_adapter import OandaExchangeAdapter
                self.venues["oanda"] = OandaExchangeAdapter(
                    api_key=oanda_key,
                    account_id=oanda_acct,
                    practice=oanda_practice,
                )
                logger.info("[MULTI_VENUE] OANDA adapter initialized")
            except Exception as e:
                logger.warning(f"[MULTI_VENUE] OANDA init failed: {e}")
        else:
            logger.info("[MULTI_VENUE] OANDA skipped (credentials not configured)")

        # Venue health (TASK-STR-PHASE2-001): venue name ->
        # {"ok": bool, "checked_at": epoch}. A venue whose account reads
        # come back empty (auth failure / unreachable) is excluded from
        # every total and flagged, never represented by a cached figure.
        self.venue_health: Dict[str, Dict[str, Any]] = {}

        # State tracking
        self.realized_pnl: float = 0.0
        self.daily_realized_pnl: float = 0.0
        self.daily_start_equity: float = 0.0
        self.daily_start_date: str = ""
        self.positions: Dict[str, UnifiedPosition] = {}  # venue:symbol -> position
        self.position_opened_at: Dict[str, int] = {}  # venue:symbol -> ms epoch
        # Attribution: strategy and timeframe that opened each position
        self.position_strategy: Dict[str, str] = {}
        self.position_timeframe: Dict[str, str] = {}
        self._candle_cache: Dict[str, tuple] = {}
        self.order_history: List[Dict] = []
        self.daily_loss_limit_hit: bool = False

        # Re-entry protection: a symbol that just exited is quarantined for a
        # while so a stale signal cannot immediately put the risk back on.
        self.symbol_cooldown_sec: int = int(os.getenv("STRATEX_SYMBOL_COOLDOWN_SEC", "900"))
        self.last_exit: Dict[str, float] = {}

        # Booked PnL survives restarts.
        self._load_state()

        logger.info(f"[MULTI_VENUE] Initialized with {len(self.venues)} venues: {list(self.venues.keys())}")

    def adopt_existing_positions(self) -> int:
        """Track positions that were already open when the process started.

        Without this a restart forgets open trades, so a later SL/TP fill would
        never be detected or reported.
        """
        adopted = 0
        now_ms = int(time.time() * 1000)
        for venue, adapter in self.venues.items():
            try:
                getter = getattr(adapter, "get_positions_or_none", None)
                positions = getter() if callable(getter) else adapter.get_positions()
                if not positions:
                    continue
                for pos in positions:
                    key = f"{venue}:{pos.symbol}"
                    if key in self.positions:
                        continue
                    self.positions[key] = pos
                    self.position_opened_at[key] = now_ms
                    adopted += 1
                    # Ownership tag (TASK-STR-PHASE2-001): adopted positions
                    # predate attribution, so they are tagged UNATTRIBUTED —
                    # visibly, not silently — for later reconciliation.
                    try:
                        from measurement import fill_ledger as _fl

                        _fl.append_position_tag({
                            "engine": "daemon",
                            "venue": venue,
                            "venue_env": getattr(adapter, "base_url", ""),
                            "symbol": pos.symbol,
                            "strategy": "UNATTRIBUTED",
                            "side": pos.side,
                            "qty": pos.quantity,
                            "entry_price": pos.entry_price,
                            "note": "adopted_at_startup",
                        })
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"[MULTI_VENUE] Adoption failed for {venue}: {e}")

        if adopted:
            logger.info(f"[MULTI_VENUE] Adopted {adopted} existing position(s) into tracking")
        return adopted

    # ------------------------------------------------------------------------
    # Balance & Equity
    # ------------------------------------------------------------------------
    def get_total_balance(self) -> Dict[str, UnifiedBalance]:
        """Get combined balance across all venues (last-known-unhealthy excluded)."""
        combined: Dict[str, UnifiedBalance] = {}
        for venue_name, venue in self.venues.items():
            if self.venue_health.get(venue_name, {}).get("ok") is False:
                continue
            try:
                balances = venue.get_balance()
                for currency, bal in balances.items():
                    if currency in combined:
                        combined[currency].free += bal.free
                        combined[currency].used += bal.used
                        combined[currency].total += bal.total
                    else:
                        combined[currency] = UnifiedBalance(
                            currency=currency,
                            free=bal.free,
                            used=bal.used,
                            total=bal.total,
                        )
            except Exception as e:
                logger.warning(f"[MULTI_VENUE] Balance fetch failed for {venue_name}: {e}")
        return combined

    def _venue_account(self, venue_name: str, venue) -> Tuple[Dict[str, Any], float, bool]:
        """Probe one venue: (account_summary, equity_usd, healthy).

        Healthy means the venue actually answered: a non-empty account
        summary or a non-zero wallet. A venue failing auth returns empty
        reads from its adapter (e.g. the OANDA adapter returns {} on a
        401); such a venue is UNHEALTHY — it contributes 0 to totals, is
        recorded in self.venue_health, and latches a measurement alert —
        instead of silently folding a stale/cached NAV into the totals
        (phase-1 finding: the daemon's OANDA venue 401'd while its NAV
        still appeared in headline equity).
        """
        summary: Dict[str, Any] = {}
        equity = 0.0
        healthy = False
        try:
            if hasattr(venue, "get_account_summary"):
                summary = venue.get_account_summary() or {}
                equity = float(summary.get("equity", 0) or 0)
                if equity <= 0:
                    equity = float(summary.get("balance", 0) or 0)
                healthy = equity > 0
            if not healthy:
                balances = venue.get_balance() or {}
                wallet = sum(
                    self._to_usd(venue, asset, bal.total)
                    for asset, bal in balances.items()
                )
                if wallet > 0:
                    equity = wallet
                    healthy = True
        except Exception as e:
            logger.debug(f"Venue account probe failed for {venue_name}: {e}")
            healthy = False
            equity = 0.0

        previous = self.venue_health.get(venue_name, {}).get("ok")
        self.venue_health[venue_name] = {"ok": healthy, "checked_at": time.time()}
        if previous is not None and previous != healthy:
            if healthy:
                logger.info(f"[MULTI_VENUE] Venue {venue_name} healthy again")
            else:
                logger.warning(
                    f"[MULTI_VENUE] Venue {venue_name} UNHEALTHY: account reads "
                    f"empty (auth/unreachable); excluded from totals"
                )
        if not healthy and previous is not False:
            try:
                from measurement import fill_ledger as _fl

                _fl.raise_alert(
                    "venue_unhealthy",
                    f"venue {venue_name} account reads empty (auth/unreachable); "
                    f"excluded from daemon totals",
                )
            except Exception:
                pass
        if healthy and previous is False:
            # Clear the shared alert only when every venue is healthy.
            if all(h.get("ok") for h in self.venue_health.values()):
                try:
                    from measurement import fill_ledger as _fl

                    _fl.clear_alert("venue_unhealthy")
                except Exception:
                    pass
        return summary, equity, healthy

    def get_total_equity(self) -> float:
        """Total equity across HEALTHY venues (balance + unrealized PnL), USD."""
        total = 0.0
        for venue_name, venue in self.venues.items():
            _summary, equity, healthy = self._venue_account(venue_name, venue)
            if healthy:
                total += equity
        return total

    def equity_snapshot(self, trigger: str = "manual") -> Dict[str, Any]:
        """Per-venue equity snapshot for the measurement store.

        Binance demo equity in the snapshot is the USDT margin figure
        only — the demo account runs multi-asset margin, so the venue's
        reported total values the faucet-granted BTC/USDC too; that
        reported total is kept separately in venues_reported and never
        used as the snapshot's trading equity (see
        measurement.fill_ledger FAUCET_EXCLUSION_RULE). Unhealthy venues
        appear as None and are listed in excluded_venues; they never
        contribute a cached figure.
        """
        venues: Dict[str, Optional[float]] = {}
        reported: Dict[str, Optional[float]] = {}
        excluded: List[str] = []
        total = 0.0
        for venue_name, venue in self.venues.items():
            summary, equity, healthy = self._venue_account(venue_name, venue)
            if not healthy:
                venues[venue_name] = None
                reported[venue_name] = None
                excluded.append(venue_name)
                continue
            reported[venue_name] = round(equity, 2)
            if venue_name == "binance_futures":
                # USDT-only trading equity: USDT wallet + unrealized PnL.
                try:
                    balances = venue.get_balance() or {}
                    usdt = balances.get("USDT")
                    if usdt is not None:
                        equity = float(usdt.total or 0.0) + float(
                            summary.get("unrealized_pnl", 0) or 0
                        )
                except Exception:
                    pass
            venues[venue_name] = round(equity, 2)
            total += equity
        return {
            "engine": "daemon",
            "trigger": trigger,
            "total_equity": round(total, 2),
            "venues": venues,
            "venues_reported": reported,
            "excluded_venues": excluded,
            "faucet_exclusion": (
                "binance demo/testnet equity = USDT futures margin balance only; "
                "non-USDT faucet assets (e.g. BTC/USDC grants) excluded"
                if any("binance" in v for v in self.venues)
                else ""
            ),
            "realized_pnl": self.realized_pnl,
            "daily_realized_pnl": self.daily_realized_pnl,
        }

    @staticmethod
    def _to_usd(venue, asset: str, qty: float) -> float:
        """Convert a balance to USD terms using the venue's own tickers."""
        if qty <= 0:
            return 0.0
        if asset.upper() in ("USD", "USDT", "USDC", "FDUSD", "BUSD", "USD1", "DAI"):
            return float(qty)
        try:
            ticker = venue.get_ticker(f"{asset.upper()}USDT")
            if ticker and getattr(ticker, "last", 0) > 0:
                return float(qty) * float(ticker.last)
        except Exception:
            pass
        return 0.0

    def get_daily_pnl(self) -> float:
        """Realized PnL today."""
        self._check_daily_reset()
        return self.daily_realized_pnl

    def _check_daily_reset(self) -> None:
        """Reset daily PnL tracking at midnight UTC."""
        today = time.strftime("%Y-%m-%d")
        if today != self.daily_start_date:
            self.daily_start_date = today
            self.daily_realized_pnl = 0.0
            self.daily_start_equity = self.get_total_equity()
            self.daily_loss_limit_hit = False
            self.save_state()
        elif self.daily_start_equity <= 0:
            # Same-day restart with a zero baseline: the persisted state
            # carried daily_start_equity=0.0 (a reset that ran while venue
            # reads were failing, or a state file from before the field
            # was restored on load). A zero baseline DISARMS the
            # daily-loss breaker, so seed it from live equity now; if
            # venues are unreadable this retries on the next call.
            equity = self.get_total_equity()
            if equity > 0:
                self.daily_start_equity = equity
                logger.warning(
                    f"[MULTI_VENUE] Seeded daily-loss breaker baseline from "
                    f"live equity: ${equity:,.2f} (persisted baseline was 0.0)"
                )
                self.save_state()

    # ------------------------------------------------------------------------
    # State Persistence
    # ------------------------------------------------------------------------
    def _state_path(self) -> Path:
        """Path of the realized PnL state file (Stratex/state/realized_pnl.json)."""
        override = os.getenv("STRATEX_STATE_DIR")
        base = Path(override) if override else Path(__file__).resolve().parent.parent / "state"
        return base / "realized_pnl.json"

    def _load_state(self) -> None:
        """Restore booked PnL so a restart does not forget realized losses."""
        try:
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                return
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
            self.realized_pnl = float(data.get("realized_pnl", 0.0) or 0.0)
            self.daily_realized_pnl = float(data.get("daily_realized_pnl", 0.0) or 0.0)
            self.daily_start_date = str(data.get("daily_start_date", "") or "")
            # TASK-STR-PHASE2-001: save_state() has always WRITTEN
            # daily_start_equity, but _load_state never read it back — so
            # every restart zeroed the daily-loss breaker's baseline and
            # _check_daily_loss_limit() silently never fired (it returns
            # early on a non-positive baseline). Restore it here; the
            # daily reset overwrites it when the date rolls over.
            self.daily_start_equity = float(data.get("daily_start_equity", 0.0) or 0.0)
            # Restore the breaker latch: a restart used to clear it, so a
            # limit-hit day resumed trading the moment the daemon recycled.
            if self.daily_start_date == time.strftime("%Y-%m-%d"):
                self.daily_loss_limit_hit = bool(data.get("daily_loss_limit_hit", False))
                if self.daily_loss_limit_hit:
                    logger.warning(
                        "[MULTI_VENUE] Restored DAILY LOSS LIMIT latch from state; "
                        "entries remain halted for today"
                    )
            logger.info(
                f"[MULTI_VENUE] Restored state: realized=${self.realized_pnl:+.2f} "
                f"daily=${self.daily_realized_pnl:+.2f} ({self.daily_start_date or 'n/a'})"
            )
        except Exception as e:
            logger.warning(f"[MULTI_VENUE] State load failed: {e}")

    def save_state(self) -> None:
        """Persist realized PnL. Never raises."""
        try:
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "realized_pnl": round(self.realized_pnl, 8),
                "daily_realized_pnl": round(self.daily_realized_pnl, 8),
                "daily_start_date": self.daily_start_date,
                "daily_loss_limit_hit": self.daily_loss_limit_hit,
                "daily_start_equity": round(self.daily_start_equity, 8),
                "updated_at": time.time(),
            }
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.warning(f"[MULTI_VENUE] State save failed: {e}")

    # ------------------------------------------------------------------------
    # Position Management
    # ------------------------------------------------------------------------
    def get_all_positions(self) -> List[UnifiedPosition]:
        """Get all open positions across venues."""
        all_positions = []
        for venue_name, venue in self.venues.items():
            try:
                positions = venue.get_positions()
                for pos in positions:
                    if venue_name not in str(pos.exchange).split(":"):
                        pos.exchange = f"{venue_name}:{pos.exchange}"
                    all_positions.append(pos)
            except Exception as e:
                logger.warning(f"[MULTI_VENUE] Position fetch failed for {venue_name}: {e}")
        return all_positions

    def get_positions_by_venue(self, venue: str) -> List[UnifiedPosition]:
        """Get positions for specific venue."""
        if venue not in self.venues:
            return []
        try:
            return self.venues[venue].get_positions()
        except Exception:
            return []

    def get_position_count(self, venue: Optional[str] = None) -> int:
        """Count open positions."""
        if venue:
            return len(self.get_positions_by_venue(venue))
        return len(self.get_all_positions())

    def mark_exit(self, venue: str, symbol: str) -> None:
        """Record an exit so the symbol is cooldown-gated against instant re-entry."""
        self.last_exit[f"{venue}:{symbol}"] = time.time()
        logger.info(
            f"[MULTI_VENUE] Exit recorded for {venue}:{symbol}; "
            f"re-entry blocked for {self.symbol_cooldown_sec}s"
        )

    def symbol_in_cooldown(self, venue: str, symbol: str) -> bool:
        """True while the symbol is quarantined after a recent exit.

        The 900s re-entry cooldown was previously write-only: mark_exit()
        recorded the timestamp but nothing ever read it, so the daemon
        re-entered the same symbol within seconds of being stopped out.
        """
        last = self.last_exit.get(f"{venue}:{symbol}")
        if last is None:
            return False
        if time.time() - last < self.symbol_cooldown_sec:
            return True
        # Expired: drop the entry so the dict does not grow forever.
        self.last_exit.pop(f"{venue}:{symbol}", None)
        return False

    def has_open_position(self, venue: str, symbol: str) -> bool:
        """True if the engine already tracks a position on this symbol.

        Anti-pyramiding gate: without it every 15s scan re-fired the same
        strategy signal and stacked a new entry on the existing position
        (live evidence: NEARUSDT, 991 fills in 2 days, position grew to
        128k units bought). One position per symbol, no averaging down.
        """
        return f"{venue}:{symbol}" in self.positions

    def get_free_margin(self, venue: str) -> float:
        """Free margin on a venue in USD terms.

        Used to stop the margin-exhaustion loop: when positions consumed
        100% of margin the daemon still attempted ~2,000 orders/day, each
        bouncing with -2019 'Margin is insufficient'.
        """
        v = self.venues.get(venue)
        if v is None:
            return 0.0
        try:
            free = 0.0
            balances = v.get_balance() or {}
            for asset, bal in balances.items():
                free += self._to_usd(v, asset, bal.free)
            return free
        except Exception as e:
            logger.debug(f"Free margin calc failed for {venue}: {e}")
            return 0.0

    def can_open_position(self, venue: str) -> Tuple[bool, str]:
        """Check if we can open a new position on this venue.

        The old body returned (True, "OK") unconditionally ("All limits
        removed for demo testing"). That is what allowed the account to
        run 100% margined with thousands of rejected orders per day.
        Limits restored: per-venue count, total count, and a free-margin
        floor so new entries stop before the exchange rejects them.
        """
        if venue not in self.venues:
            return False, f"Venue {venue} not available"

        by_venue = self.get_position_count(venue)
        if by_venue >= self.max_positions_per_venue:
            return False, f"venue position limit ({by_venue}/{self.max_positions_per_venue})"

        total = self.get_position_count(None)
        if total >= self.max_total_positions:
            return False, f"total position limit ({total}/{self.max_total_positions})"

        # Margin floor: refuse to attempt entries when almost no free margin
        # is left. Each rejected order costs an API call and log spam; worse,
        # a later success would put the account in liquidation range.
        free = self.get_free_margin(venue)
        if free <= 0:
            return False, "no free margin on venue"

        return True, "OK"

    # ------------------------------------------------------------------------
    # Market Data
    # ------------------------------------------------------------------------
    def get_ticker(self, venue: str, symbol: str) -> Optional[UnifiedTicker]:
        """Get ticker from specific venue."""
        if venue not in self.venues:
            return None
        try:
            return self.venues[venue].get_ticker(symbol)
        except Exception:
            return None

    def get_candles(self, venue: str, symbol: str, timeframe: str = "15m", limit: int = 100) -> List[Dict]:
        """Get candles from a venue, cached briefly so one scan cycle reuses them.

        A cycle asks for the same symbol/timeframe while running ~20 strategies;
        without this cache the venue is hit twice per pair (prefetch + scan).
        """
        if venue not in self.venues:
            return []
        key = f"{venue}:{symbol}:{timeframe}:{limit}"
        now = time.time()
        cached = self._candle_cache.get(key)
        if cached and (now - cached[0]) < 55:
            return cached[1]
        try:
            data = self.venues[venue].get_historical_data(symbol, timeframe, limit) or []
        except Exception as e:
            logger.warning(f"[MULTI_VENUE] Candle fetch failed for {venue}:{symbol}: {e}")
            return []
        if len(self._candle_cache) > 300:
            cutoff = now - 120
            self._candle_cache = {
                k: v for k, v in self._candle_cache.items() if v[0] >= cutoff
            }
        self._candle_cache[key] = (now, data)
        return data

    def get_candles_multi(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> Dict[str, List[Dict]]:
        """Get candles from all venues that support the symbol."""
        result = {}
        for venue_name, venue in self.venues.items():
            try:
                candles = venue.get_historical_data(symbol, timeframe, limit)
                if candles:
                    result[venue_name] = candles
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------------
    # Order Execution
    # ------------------------------------------------------------------------
    def place_order(
        self,
        venue: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy_name: str = "",
        timeframe: str = "",
    ) -> Optional[UnifiedOrderResult]:
        """Place order on specific venue with native SL/TP. NO RESTRICTIONS."""
        if venue not in self.venues:
            logger.error(f"[MULTI_VENUE] Venue {venue} not available")
            return None

        # All gates removed for demo testing - unlimited trading
        can_open, reason = self.can_open_position(venue)
        if not can_open:
            logger.warning(f"[MULTI_VENUE] Cannot open position on {venue}: {reason}")
            return None

        venue_obj = self.venues[venue]
        try:
            result = venue_obj.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            if result and result.status in ("FILLED", "PARTIALLY_FILLED", "PENDING"):
                entry_price = result.avg_price or price or 0.0
                self.order_history.append({
                    "timestamp": time.time(),
                    "venue": venue,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": entry_price,
                    "order_id": result.order_id,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                })
                logger.info(f"[MULTI_VENUE] Order placed: {venue} {symbol} {side} {quantity} @ {result.avg_price}")

                # Track the filled position so reconciliation can detect a
                # broker-side SL/TP exit and book its PnL. Keyed venue:symbol to
                # match the exit path and the reconciliation reader below.
                key = f"{venue}:{symbol}"
                if result.status in ("FILLED", "PARTIALLY_FILLED"):
                    filled_qty = result.executed_qty or quantity
                    # NOTE: UnifiedPosition has no strategy/timeframe fields —
                    # attribution lives in self.position_strategy /
                    # self.position_timeframe below. This call used to pass
                    # strategy=/timeframe= and raised TypeError AFTER the fill,
                    # leaving an untracked, unprotected position at the broker.
                    self.positions[key] = UnifiedPosition(
                        symbol=symbol,
                        side="LONG" if side in ("BUY", "LONG") else "SHORT",
                        quantity=filled_qty,
                        entry_price=entry_price,
                        mark_price=entry_price,
                        unrealized_pnl=0.0,
                        exchange=venue,
                        stop_loss=float(stop_loss or 0.0),
                        take_profit=float(take_profit or 0.0),
                    )
                    self.position_opened_at[key] = int(time.time() * 1000)
                    self.position_strategy[key] = strategy_name
                    self.position_timeframe[key] = timeframe
                    # Ownership tag (TASK-STR-PHASE2-001): every position
                    # opened from now on is attributable to engine+strategy.
                    try:
                        from measurement import fill_ledger as _fl

                        _fl.append_position_tag({
                            "engine": "daemon",
                            "venue": venue,
                            "venue_env": getattr(venue_obj, "base_url", ""),
                            "symbol": symbol,
                            "strategy": strategy_name or "UNATTRIBUTED",
                            "timeframe": timeframe,
                            "side": "LONG" if side in ("BUY", "LONG") else "SHORT",
                            "qty": filled_qty,
                            "entry_price": entry_price,
                            "order_id": result.order_id,
                        })
                    except Exception:
                        pass

                # Send Telegram notification
                if result.status == "FILLED" and self.telegram_bot and self.telegram_bot.is_configured:
                    try:
                        emoji = "🟢" if side in ("BUY", "LONG") else "🔴"
                        self.telegram_bot.send_message(
                            f"{emoji} <b>TRADE EXECUTED</b>\n\n"
                            f"• <b>Venue</b>: <code>{venue}</code>\n"
                            f"• <b>Symbol</b>: <code>{symbol}</code>\n"
                            f"• <b>Side</b>: <code>{side}</code>\n"
                            f"• <b>Qty</b>: <code>{quantity}</code>\n"
                            f"• <b>Entry</b>: <code>{entry_price:.5f}</code>\n"
                            f"• <b>SL</b>: <code>{(stop_loss or 0.0):.5f}</code>\n"
                            f"• <b>TP</b>: <code>{(take_profit or 0.0):.5f}</code>\n"
                            f"• <b>Ticket</b>: <code>{result.order_id}</code>\n"
                            f"• <b>Status</b>: <code>{result.status}</code>"
                        )
                    except Exception as e:
                        logger.debug(f"Telegram notification failed: {e}")

            return result
        except Exception as e:
            logger.error(f"[MULTI_VENUE] Order failed on {venue}: {e}")
            return None

    def close_position(self, venue: str, symbol: str) -> bool:
        """Close position on specific venue."""
        if venue not in self.venues:
            return False
        try:
            positions = self.venues[venue].get_positions()
            for pos in positions:
                if pos.symbol == symbol:
                    # Place opposite order to close
                    close_side = "SELL" if pos.side in ("LONG", "BUY") else "BUY"
                    result = self.venues[venue].place_order(
                        symbol=symbol,
                        side=close_side,
                        order_type="MARKET",
                        quantity=pos.quantity,
                    )
                    if result is None:
                        logger.warning(
                            f"[MULTI_VENUE] Close order failed for {venue}:{symbol}; "
                            f"protective orders left in place"
                        )
                        return False

                    # Cancel the SL/TP conditional orders only once the position
                    # is actually closed, so they can't fire against no position.
                    adapter = self.venues[venue]
                    if hasattr(adapter, "cancel_protective_orders"):
                        try:
                            cancelled = adapter.cancel_protective_orders(symbol)
                            if cancelled:
                                logger.info(
                                    f"[MULTI_VENUE] Cancelled {cancelled} protective order(s) on {symbol}"
                                )
                        except Exception as e:
                            logger.debug(
                                f"[MULTI_VENUE] Protective order cleanup failed on {symbol}: {e}"
                            )

                    # Stop tracking it and start the re-entry cooldown.
                    key = f"{venue}:{symbol}"
                    self.position_opened_at.pop(key, None)
                    self.positions.pop(key, None)
                    self.mark_exit(venue, symbol)

                    # TASK-STR-PHASE2-001: an engine-initiated close is a
                    # fill like any other — book it through the reconciler's
                    # path (breaker check included) and record it in the
                    # fill ledger, so it can never happen silently. Fees
                    # are unknown on this path: the row is labelled
                    # fees_source=estimate with fees=0 rather than
                    # inventing a broker figure.
                    try:
                        strat = self.position_strategy.pop(key, "UNATTRIBUTED")
                        self.position_timeframe.pop(key, None)
                        exit_price = float(getattr(result, "avg_price", 0.0) or 0.0) or float(pos.mark_price or 0.0)
                        qty = float(pos.quantity or 0.0)
                        gross = (exit_price - float(pos.entry_price or 0.0)) * qty
                        if str(pos.side).upper() in ("SHORT", "SELL"):
                            gross = -gross
                        self.book_reconciled_pnl(venue, symbol, gross)
                        from measurement import fill_ledger as _fl

                        _fl.append_fill({
                            "strategy": strat,
                            "engine": "daemon",
                            "venue": venue,
                            "symbol": symbol,
                            "side": pos.side,
                            "qty": qty,
                            "entry_price": float(pos.entry_price or 0.0),
                            "exit_price": exit_price,
                            "entry_time": 0.0,
                            "exit_time": time.time(),
                            "gross_pnl": gross,
                            "fees": 0.0,
                            "fees_source": "estimate",
                            "net_pnl": gross,
                            "exit_reason": "ENGINE_CLOSE",
                            "order_id": str(getattr(result, "order_id", "") or ""),
                        })
                    except Exception as e:
                        logger.warning(f"[MULTI_VENUE] Close booking failed for {venue}:{symbol}: {e}")

                    if self.telegram_bot and self.telegram_bot.is_configured:
                        try:
                            emoji = "💰" if pos.unrealized_pnl >= 0 else "🔻"
                            self.telegram_bot.send_message(
                                f"{emoji} <b>POSITION CLOSED</b>\n\n"
                                f"• <b>Venue</b>: <code>{venue}</code>\n"
                                f"• <b>Symbol</b>: <code>{symbol}</code>\n"
                                f"• <b>Side</b>: <code>{pos.side}</code>\n"
                                f"• <b>Qty</b>: <code>{pos.quantity}</code>\n"
                                f"• <b>Entry</b>: <code>{pos.entry_price:.5f}</code>\n"
                                f"• <b>Exit</b>: <code>{pos.mark_price:.5f}</code>\n"
                                f"• <b>Realized PnL</b>: {emoji} <code>${pos.unrealized_pnl:+.2f}</code>\n"
                                f"• <b>Ticket</b>: <code>{pos.position_id}</code>"
                            )
                        except Exception as e:
                            logger.debug(f"Telegram notification failed: {e}")
                    return result is not None
            return False
        except Exception as e:
            logger.error(f"[MULTI_VENUE] Close position failed: {e}")
            return False

    # ------------------------------------------------------------------------
    # Risk Management
    # ------------------------------------------------------------------------
    def update_realized_pnl(self, venue: str, symbol: str, realized_pnl: float) -> None:
        """Record realized PnL from closed position."""
        self.realized_pnl += realized_pnl
        self.daily_realized_pnl += realized_pnl
        self._check_daily_loss_limit()
        self.save_state()
        logger.info(f"[MULTI_VENUE] Realized PnL: {venue}:{symbol} = ${realized_pnl:+.2f} (Total: ${self.realized_pnl:+.2f})")

    def book_reconciled_pnl(self, venue: str, symbol: str, net: float) -> None:
        """Book broker-side realized PnL (reconciliation path).

        The daemon previously mutated realized_pnl / daily_realized_pnl
        directly, which bypassed the daily-loss check below.
        """
        self.realized_pnl += net
        self.daily_realized_pnl += net
        self._check_daily_loss_limit()
        self.save_state()

    def _check_daily_loss_limit(self) -> None:
        """Latch the daily-loss circuit breaker when realized losses breach the cap.

        The flag was read in five places but never set anywhere: on
        2026-11-11 the account lost 63% in one day and the daemon kept
        trading. Latched here on REALIZED day PnL only (unrealized swings
        would halt on noise); auto-clears at the UTC daily reset.
        """
        if self.daily_loss_limit_hit:
            return
        if self.daily_start_equity <= 0:
            return
        cap = self.max_daily_loss_pct * self.daily_start_equity
        if cap <= 0:
            return
        if self.daily_realized_pnl <= -cap:
            self.daily_loss_limit_hit = True
            logger.warning(
                f"[MULTI_VENUE] DAILY LOSS LIMIT HIT: realized "
                f"{self.daily_realized_pnl:+.2f} <= -{cap:.2f} "
                f"({self.max_daily_loss_pct*100:.1f}% of day-start equity "
                f"{self.daily_start_equity:.2f}). Entries halted until UTC midnight."
            )

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary."""
        self._check_daily_reset()
        
        total_equity = 0.0
        total_balance = 0.0
        unrealized = 0.0
        venue_alerts: List[str] = []
        for venue_name, venue in self.venues.items():
            try:
                summary, equity, healthy = self._venue_account(venue_name, venue)
                if not healthy:
                    # Unauthenticated/unreachable venue: contributes 0 and
                    # is flagged — never represented by a cached figure.
                    venue_alerts.append(venue_name)
                    continue
                balance = float(summary.get("balance", 0) or 0)
                if balance <= 0:
                    balance = equity

                total_equity += equity
                total_balance += balance if balance > 0 else equity
                if "unrealized_pnl" in summary:
                    unrealized += float(summary.get("unrealized_pnl", 0) or 0)
                else:
                    unrealized += equity - balance
            except Exception as e:
                logger.debug(f"Risk valuation failed for {venue_name}: {e}")

        return {
            "total_equity": total_equity,
            "total_balance": total_balance,
            "unrealized_pnl": unrealized,
            "realized_pnl": self.realized_pnl,
            "daily_realized_pnl": self.daily_realized_pnl,
            "daily_start_equity": self.daily_start_equity,
            "daily_loss_pct": (self.daily_start_equity - total_equity) / self.daily_start_equity if self.daily_start_equity > 0 else 0,
            "positions": self.get_position_count(),
            "max_positions": self.max_total_positions,
            "daily_loss_limit_hit": self.daily_loss_limit_hit,
            "venues": {v: self.get_position_count(v) for v in self.venues},
            "venue_health": {v: bool(h.get("ok")) for v, h in self.venue_health.items()},
            "venue_alerts": venue_alerts,
        }

    # ------------------------------------------------------------------------
    # Symbol Universe
    # ------------------------------------------------------------------------
    def get_tradeable_symbols(self) -> Dict[str, List[str]]:
        """Get tradeable symbols per venue."""
        # This would ideally fetch from exchange info
        # For now, return known symbols
        return {
            "binance_futures": [
                "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT", "DOTUSDT",
                "LTCUSDT", "LINKUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT",
            ],
            "oanda": [
                "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
                "EURGBP", "EURJPY", "EURAUD", "EURCAD", "EURCHF",
                "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF",
                "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY",
                "XAUUSD", "XAGUSD", "US30", "US500", "USTEC", "DE30", "UK100",
                "USOIL", "UKOIL", "BCOUSD", "NATGAS",
            ],
        }

    def get_symbol_venue(self, symbol: str) -> Optional[str]:
        """Determine which venue trades a symbol."""
        symbols = self.get_tradeable_symbols()
        for venue, syms in symbols.items():
            if symbol in syms:
                return venue
        return None


# Factory function
def create_multi_venue_engine(
    binance_api_key: str = "",
    binance_secret: str = "",
    binance_testnet: bool = True,
    oanda_api_key: str = "",
    oanda_account_id: str = "",
    oanda_practice: bool = True,
    **kwargs
) -> "MultiVenueEngine":
    """Create multi-venue engine from environment or parameters."""
    return MultiVenueEngine(
        binance_api_key=binance_api_key,
        binance_secret=binance_secret,
        binance_testnet=binance_testnet,
        oanda_api_key=oanda_api_key,
        oanda_account_id=oanda_account_id,
        oanda_practice=oanda_practice,
        **kwargs
    )