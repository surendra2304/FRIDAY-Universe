"""
exchanges/pepperstone_ctrader_adapter.py — Pepperstone cTrader adapter
(Spotware Open API), TASK-STR-PEP-001.

Why this adapter exists
-----------------------
Pepperstone is Stratex's venue for the instruments neither Binance demo
nor the retired OANDA practice account could trade: the 23 venue-excluded
near-miss rows (20 comm7 futures-panel streams judged on GC/SI/CL/BZ/NG/
HG/PL and 4 idx-panel streams) plus the 11 forex rows whose
forward_venues still point at the removed OANDA runner. The demo account
of record is Pepperstone DEMO 5376835 (cTrader, USD, $10,000 virtual,
1:200). DEMO ONLY: this adapter hard-pins the demo Open API endpoint and
refuses live endpoints the same way the rest of the fleet does.

Transport choice
----------------
Primary (and only) order path: the Spotware Open API (protobuf over
TLS, demo.ctraderapi.com:5035), implemented in exchanges/ctrader_openapi.py.
The FIX API visible in cTrader's settings plays NO role in order flow:
cTrader FIX NewOrderSingle cannot carry SL/TP (the Open-API custom tags
are rejected for that message type — see ctrader_fix_adapter.py), and
the legacy FIX adapter's get_balance() reads a local ledger file rather
than the broker. Those are precisely the two failure modes the owner
hit with the earlier IC Markets attempt (protection not kept, balance
never reported). The FIX adapter is left untouched and unused by this
lane; it remains useful only as a read-only price/session reference.

THE FAIL-CLOSED STANDARD (owner's requirements; non-negotiable)
---------------------------------------------------------------
1. Every entry order carries its stop-loss AND take-profit attached at
   placement. The Open API rejects absolute SL/TP on MARKET orders
   (ProtoOANewOrderReq fields 11/12: "Not supported for the MARKET
   orders"), so market entries attach relativeStopLoss /
   relativeTakeProfit (fields 19/20, 1/100000 of price) computed from
   the caller's absolute levels against the live spot — the judged
   bracket DISTANCE is preserved exactly. LIMIT/STOP entries attach
   the absolute fields directly.
2. After placement the adapter READS BACK the position's SL/TP from
   the broker (ProtoOAReconcileReq) and verifies them against the
   levels implied by the fill. Missing/wrong -> ONE amend attempt
   (ProtoOAAmendPositionSLTPReq with absolute levels) -> re-read ->
   still wrong: the position is closed immediately and the venue
   HALTS (no further orders) with a loud error.
3. Balance/equity are pulled from the broker on every read (never
   cached, never read from a local file). reconcile_balance() compares
   a fresh broker balance against the caller's ledger figure; a
   mismatch beyond tolerance HALTS the venue. A failed balance read
   returns {} / raises — the balance is never silently stale.
4. A dropped connection makes position/balance state UNKNOWN
   (get_positions_or_none() -> None, get_balance() -> {}), never
   "flat" or "unchanged". On reconnect, every open position's
   protection is re-verified from the broker before any order path
   reopens: broker-side protection is assumed only after read-back
   proof.

Credentials come from the environment only (names below; no values in
code, tests, or this file). The ONLY activation piece missing by design
is the owner's Spotware Open API authorization (his cTrader ID sign-in
+ approve tap), which issues the client_id/client_secret/access_token
these env names carry, plus the demo shakedown
(Stratex/scripts/pepperstone_shakedown.py) passing end-to-end. No
strategy trades this venue before that gate.

Env names:
  PEPPERSTONE_CTRADER_CLIENT_ID        Open API application client id
  PEPPERSTONE_CTRADER_CLIENT_SECRET    Open API application client secret
  PEPPERSTONE_CTRADER_ACCESS_TOKEN     OAuth access token (trade scope)
  PEPPERSTONE_CTRADER_REFRESH_TOKEN    OAuth refresh token (optional)
  PEPPERSTONE_CTRADER_ACCOUNT_ID       ctidTraderAccountId (optional if
                                       resolvable from the token)
  PEPPERSTONE_CTRADER_ACCOUNT_NUMBER   trader login shown in cTrader
                                       (the demo account number); used
                                       to pick the account from the
                                       token's account list
  PEPPERSTONE_CTRADER_HOST / _PORT     endpoint override — allowlist-pinned
                                       to demo.ctraderapi.com:5035; any
                                       other value is refused at
                                       construction (TASK-STR-PEP-002)

UNVERIFIED-UNTIL-SHAKEDOWN: protocol field numbers/encodings are taken
from Spotware's published .proto files (verified 2026-11-19), but demo
server behaviour cannot be exercised until the owner's authorization
exists. The shakedown is the empirical gate for: moneyDigits scaling of
the $10,000 balance, EURUSD volume encoding (0.01 lot == 1000 units),
relative-SL/TP acceptance on market orders, the account's HEDGED vs
NETTED type, and Pepperstone's exact symbol names for the 11 required
instruments.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from exchanges import ctrader_openapi as oa
from exchanges.base_exchange import (
    BaseExchange,
    ExchangeCapabilities,
    UnifiedBalance,
    UnifiedOrderResult,
    UnifiedPosition,
    UnifiedTicker,
)
from logger import get_logger

logger = get_logger("pepperstone_ctrader_adapter")

VENUE = "pepperstone_ctrader"
DEMO_HOST = "demo.ctraderapi.com"
DEMO_PORT = 5035
LIVE_HOST = "live.ctraderapi.com"

# Strategy-side / research-side names -> cTrader symbol-name hints.
# Resolution is ALWAYS verified against the broker's own symbol list;
# these are lookup hints, never assumptions. Pepperstone's exact names
# are confirmed by the shakedown (UNVERIFIED-UNTIL-SHAKEDOWN).
SYMBOL_ALIASES: dict[str, str] = {
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "WTI": "XTIUSD",
    "CRUDE": "XTIUSD",
    "BRENT": "XBRUSD",
    "NATGAS": "XNGUSD",
    "NATURALGAS": "XNGUSD",
    "COPPER": "XCUUSD",
    "PLATINUM": "XPTUSD",
    "NAS100": "USTEC",
    "US100": "USTEC",
    "USTEC": "USTEC",
    "US500": "US500",
    "SPX500": "US500",
    "US30": "US30",
    "GER40": "DE40",
    "DAX": "DE40",
    "UK100": "UK100",
    "JPN225": "JP225",
    "NIKKEI": "JP225",
}


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _live_trading_authorized() -> bool:
    """Both live gates open (TASK-STR-SAFETY-001) — mirrors the fleet's
    helper: env opt-in AND the code-level config.py invariant. With the
    shipped invariant this is always False; a config import failure
    fails closed."""
    if not _env_flag("ALLOW_LIVE_TRADING", "false"):
        return False
    try:
        import config as _stratex_config

        return bool(getattr(_stratex_config, "LIVE_TRADING_ENABLED", False))
    except Exception:
        return False


def _enforce_no_live_trading() -> None:
    trading_mode = os.environ.get("TRADING_MODE", "TESTNET").upper()
    if trading_mode == "LIVE" or os.environ.get("LIVE_TRADING_ENABLED") == "1":
        raise PermissionError(
            "SECURITY CRITICAL: LIVE trading is permanently blocked by design "
            f"(venue={VENUE}, TRADING_MODE={trading_mode})."
        )


class VenueHaltedError(RuntimeError):
    """The venue halted itself fail-closed; no further orders until an
    operator investigates and calls clear_halt()."""


class ProtectionVerificationError(RuntimeError):
    """A position's broker-side SL/TP could not be verified after fill."""


class PepperstoneCTraderAdapter(BaseExchange):
    """Pepperstone cTrader (Spotware Open API) adapter — demo only.

    Quantities on the order path are in LOTS (1.0 = one standard lot of
    the symbol, per the broker's own lotSize). Positions report quantity
    in broker UNITS (e.g. 1000.0 for 0.01 lot EURUSD), matching the
    convention of the legacy FIX adapter.
    """

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        access_token: str = "",
        refresh_token: str = "",
        account_id: int | None = None,
        account_number: str = "",
        transport: Any = None,
        request_timeout: float = 15.0,
    ):
        super().__init__(
            VENUE,
            capabilities=ExchangeCapabilities(
                supports_futures=True,  # CFD margin trading, futures-like
                supports_shorting=True,
                supports_margin=True,
                supports_limit_orders=True,
                supports_stop_orders=True,
                supports_websocket=False,
                max_leverage=200.0,
            ),
        )
        _enforce_no_live_trading()

        self.client_id = client_id or os.getenv("PEPPERSTONE_CTRADER_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv(
            "PEPPERSTONE_CTRADER_CLIENT_SECRET", ""
        )
        self.access_token = access_token or os.getenv(
            "PEPPERSTONE_CTRADER_ACCESS_TOKEN", ""
        )
        self.refresh_token = refresh_token or os.getenv(
            "PEPPERSTONE_CTRADER_REFRESH_TOKEN", ""
        )
        env_account = os.getenv("PEPPERSTONE_CTRADER_ACCOUNT_ID", "").strip()
        self.account_id: int | None = account_id or (
            int(env_account) if env_account else None
        )
        self.account_number = account_number or os.getenv(
            "PEPPERSTONE_CTRADER_ACCOUNT_NUMBER", ""
        )

        # DEMO endpoint only, pinned by strict allowlist (TASK-STR-PEP-002,
        # supervisor condition on PR #1097): the sole accepted endpoint is
        # demo.ctraderapi.com:5035. ANY other host or port — the live host
        # included — raises at construction; there is no authorization
        # escape hatch on the endpoint itself. (TRADING_MODE=LIVE is
        # refused above by _enforce_no_live_trading(), and a resolved LIVE
        # account is refused at account resolution.)
        self.host = os.getenv("PEPPERSTONE_CTRADER_HOST", DEMO_HOST).strip() or DEMO_HOST
        self.port = int(os.getenv("PEPPERSTONE_CTRADER_PORT", str(DEMO_PORT)))
        if self.host != DEMO_HOST or self.port != DEMO_PORT:
            raise PermissionError(
                "SECURITY CRITICAL: refusing cTrader Open API endpoint "
                f"{self.host}:{self.port}; this adapter is demo-only and "
                f"the sole allowlisted endpoint is {DEMO_HOST}:{DEMO_PORT} "
                f"(venue={VENUE})."
            )

        self.request_timeout = request_timeout
        self.base_url = f"openapi://{self.host}:{self.port}"  # venue_env tag parity

        self._transport = transport  # injectable for tests
        self._account_authorized = False
        self._trader: dict = {}
        self._deposit_currency = ""
        self._symbols_by_name: dict[str, dict] = {}
        self._symbols_by_id: dict[int, dict] = {}
        self._symbol_details_cache: dict[int, dict] = {}
        self._spot_cache: dict[int, tuple[float, float, float]] = {}
        self._subscribed_spots: set[int] = set()
        # Positions THIS adapter opened: position_id -> intended levels.
        self._intended_protection: dict[int, dict] = {}
        self.halted = False
        self.halt_reason = ""
        self._ever_connected = False

    # ------------------------------------------------------------------
    # Halt machinery (fail-closed standard)
    # ------------------------------------------------------------------
    def _halt(self, reason: str) -> None:
        if not self.halted:
            logger.error(f"[{VENUE.upper()}] VENUE HALTED: {reason}")
        self.halted = True
        self.halt_reason = reason

    def clear_halt(self) -> None:
        """Operator-only reset after investigation. Never called by any
        automated path in this adapter."""
        if self.halted:
            logger.warning(
                f"[{VENUE.upper()}] Halt cleared by operator (was: {self.halt_reason})"
            )
        self.halted = False
        self.halt_reason = ""

    def _raise_if_halted(self) -> None:
        if self.halted:
            raise VenueHaltedError(
                f"[{VENUE.upper()}] Venue is HALTED: {self.halt_reason}"
            )

    def is_healthy(self) -> bool:
        return bool(self._account_authorized and self._transport is not None
                    and self._transport.is_connected and not self.halted)

    # ------------------------------------------------------------------
    # Connection / authorization
    # ------------------------------------------------------------------
    def _has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret and self.access_token)

    def _get_transport(self) -> Any:
        if self._transport is None:
            self._transport = oa.OpenApiTransport(
                self.host,
                self.port,
                on_event=self._on_event,
                on_disconnect=self._on_disconnect,
            )
        return self._transport

    def _on_disconnect(self, reason: str) -> None:
        logger.error(
            f"[{VENUE.upper()}] Connection lost ({reason}); account state is "
            "UNKNOWN until a reconnect re-verifies every position's protection."
        )
        self._account_authorized = False
        self.is_connected = False

    def _on_event(self, payload_type: int, payload: bytes) -> None:
        if payload_type == oa.PT_SPOT_EVENT:
            try:
                event = oa.decode_message(oa.SCHEMAS[oa.PT_SPOT_EVENT], payload)
            except Exception:
                return
            symbol_id = event.get("symbol_id")
            bid = event.get("bid")
            ask = event.get("ask")
            if symbol_id is not None and (bid or ask):
                bid_f = float(bid) / oa.PRICE_SCALE if bid else 0.0
                ask_f = float(ask) / oa.PRICE_SCALE if ask else 0.0
                self._spot_cache[int(symbol_id)] = (
                    bid_f, ask_f, time.time(),
                )

    def _request(self, payload_type: int, fields: dict, *, timeout: float | None = None) -> dict:
        transport = self._get_transport()
        return transport.request(
            payload_type, fields, timeout=timeout or self.request_timeout
        )

    def _ensure_connected(self) -> None:
        """Connect + authorize + load reference data, or raise.

        On a REconnect (the session dropped earlier), every open
        position's broker-side protection is re-verified before this
        returns — an unverified position is never silently trusted.
        """
        transport = self._get_transport()
        if self._account_authorized and transport.is_connected:
            return
        if not self._has_credentials():
            raise RuntimeError(
                f"[{VENUE.upper()}] Open API credentials not configured "
                "(PEPPERSTONE_CTRADER_CLIENT_ID / _CLIENT_SECRET / "
                "_ACCESS_TOKEN). These arrive with the owner's Spotware "
                "Open API authorization; refusing to fabricate a session."
            )
        reconnecting = self._ever_connected
        transport.connect()
        try:
            self._request(oa.PT_APPLICATION_AUTH_REQ, {
                "client_id": self.client_id, "client_secret": self.client_secret,
            })
            self._resolve_account_id()
            self._authorize_account()
        except oa.OpenApiErrorRes as e:
            if e.error_code in ("OA_AUTH_TOKEN_EXPIRED", "CH_ACCESS_TOKEN_INVALID") \
                    and self.refresh_token:
                self._refresh_access_token()
                self._resolve_account_id()
                self._authorize_account()
            else:
                raise
        self._account_authorized = True
        self.is_connected = True
        self._ever_connected = True
        self._load_reference_data()
        if reconnecting:
            self.verify_all_protection()
        logger.info(
            f"[{VENUE.upper()}] Authorized on DEMO account "
            f"ctid={self.account_id} login={self._trader.get('trader_login')}"
        )

    def _refresh_access_token(self) -> None:
        res = self._request(oa.PT_REFRESH_TOKEN_REQ, {
            "refresh_token": self.refresh_token,
        })
        if res.get("access_token"):
            self.access_token = str(res["access_token"])
        if res.get("refresh_token"):
            # The rotated refresh token lives only in memory; persisting
            # it is part of the deploy step (env wiring), flagged here so
            # it is never silently lost track of.
            self.refresh_token = str(res["refresh_token"])
            logger.warning(
                f"[{VENUE.upper()}] Access token refreshed; the rotated "
                "refresh token must be persisted by the deploy step."
            )

    def _resolve_account_id(self) -> None:
        if self.account_id:
            return
        res = self._request(oa.PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, {
            "access_token": self.access_token,
        })
        accounts = res.get("ctid_trader_account", [])
        if not accounts:
            raise RuntimeError(
                f"[{VENUE.upper()}] Access token grants no trading accounts."
            )
        chosen = None
        if self.account_number:
            for acc in accounts:
                if str(acc.get("trader_login", "")) == str(self.account_number):
                    chosen = acc
                    break
            if chosen is None:
                raise RuntimeError(
                    f"[{VENUE.upper()}] Account number {self.account_number} "
                    "is not among the accounts this token grants."
                )
        else:
            demo = [a for a in accounts if not a.get("is_live")]
            if len(demo) == 1:
                chosen = demo[0]
            elif len(accounts) == 1:
                chosen = accounts[0]
            else:
                raise RuntimeError(
                    f"[{VENUE.upper()}] Token grants {len(accounts)} accounts; "
                    "set PEPPERSTONE_CTRADER_ACCOUNT_ID or "
                    "PEPPERSTONE_CTRADER_ACCOUNT_NUMBER to choose."
                )
        if chosen.get("is_live"):
            raise PermissionError(
                f"[{VENUE.upper()}] Resolved account is a LIVE account; this "
                "adapter is demo-only (TASK-STR-PEP-001)."
            )
        self.account_id = int(chosen["ctid_trader_account_id"])

    def _authorize_account(self) -> None:
        self._request(oa.PT_ACCOUNT_AUTH_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "access_token": self.access_token,
        })

    def _load_reference_data(self) -> None:
        trader_res = self._request(oa.PT_TRADER_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
        })
        self._trader = trader_res.get("trader", {}) or {}
        symbols_res = self._request(oa.PT_SYMBOLS_LIST_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "include_archived_symbols": False,
        })
        self._symbols_by_name = {}
        self._symbols_by_id = {}
        for sym in symbols_res.get("symbol", []):
            name = str(sym.get("symbol_name", ""))
            if not name:
                continue
            self._symbols_by_name[self._name_key(name)] = sym
            self._symbols_by_id[int(sym["symbol_id"])] = sym
        # Deposit currency name from the asset list (never assumed).
        self._deposit_currency = ""
        try:
            assets_res = self._request(oa.PT_ASSET_LIST_REQ, {
                "ctid_trader_account_id": int(self.account_id or 0),
            })
            deposit_id = self._trader.get("deposit_asset_id")
            for asset in assets_res.get("asset", []):
                if asset.get("asset_id") == deposit_id:
                    self._deposit_currency = str(asset.get("name", ""))
                    break
        except Exception as e:
            logger.warning(f"[{VENUE.upper()}] Asset list read failed: {e}")

    # ------------------------------------------------------------------
    # Money / symbol helpers
    # ------------------------------------------------------------------
    def _money_digits(self) -> int:
        digits = self._trader.get("money_digits")
        return int(digits) if digits is not None else 2

    def _money(self, raw: Any, digits: int | None = None) -> float:
        if raw is None:
            return 0.0
        d = self._money_digits() if digits is None else int(digits)
        return float(raw) / (10 ** d)

    @staticmethod
    def _name_key(name: str) -> str:
        return "".join(ch for ch in str(name).upper() if ch.isalnum())

    def normalize_symbol(self, symbol: str) -> str:
        """Unified symbol = the cTrader symbol name (e.g. XAUUSD)."""
        key = self._name_key(symbol)
        alias = SYMBOL_ALIASES.get(key)
        return alias or key

    def denormalize_symbol(self, unified_symbol: str) -> str:
        return self.normalize_symbol(unified_symbol)

    def _resolve_symbol(self, symbol: str) -> dict:
        """Broker light-symbol record for a strategy-side name."""
        self._ensure_connected()
        key = self._name_key(self.normalize_symbol(symbol))
        record = self._symbols_by_name.get(key)
        if record is None:
            # One refresh in case the cache predates a symbol change.
            self._load_reference_data()
            record = self._symbols_by_name.get(key)
        if record is None:
            raise RuntimeError(
                f"[{VENUE.upper()}] Symbol '{symbol}' not offered by the "
                "broker on this account (checked the broker's own symbol list)."
            )
        return record

    def _symbol_details(self, symbol_id: int) -> dict:
        if symbol_id in self._symbol_details_cache:
            return self._symbol_details_cache[symbol_id]
        res = self._request(oa.PT_SYMBOL_BY_ID_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "symbol_id": [symbol_id],
        })
        for sym in res.get("symbol", []):
            self._symbol_details_cache[int(sym["symbol_id"])] = sym
        if symbol_id not in self._symbol_details_cache:
            raise RuntimeError(
                f"[{VENUE.upper()}] No symbol details for id {symbol_id}."
            )
        return self._symbol_details_cache[symbol_id]

    def _lots_to_volume_cents(self, symbol_id: int, lots: float) -> int:
        details = self._symbol_details(symbol_id)
        lot_size = int(details.get("lot_size") or 0)
        if lot_size <= 0:
            raise RuntimeError(
                f"[{VENUE.upper()}] Symbol {symbol_id} reports no lotSize; "
                "refusing to guess a volume."
            )
        volume = int(round(float(lots) * lot_size))
        min_v = int(details.get("min_volume") or 0)
        max_v = int(details.get("max_volume") or 0)
        step = int(details.get("step_volume") or 0)
        if min_v and volume < min_v:
            raise ValueError(
                f"[{VENUE.upper()}] Volume {volume} cents is below the broker "
                f"minimum {min_v} for symbol {symbol_id}; refusing to upsize "
                "the order silently."
            )
        if max_v and volume > max_v:
            raise ValueError(
                f"[{VENUE.upper()}] Volume {volume} cents exceeds the broker "
                f"maximum {max_v} for symbol {symbol_id}."
            )
        if step:
            volume = (volume // step) * step
            if min_v and volume < min_v:
                raise ValueError(
                    f"[{VENUE.upper()}] Volume snaps below the broker minimum "
                    f"after step rounding for symbol {symbol_id}."
                )
        return volume

    # ------------------------------------------------------------------
    # Account reads (always fresh from the broker; never cached values)
    # ------------------------------------------------------------------
    def _fetch_trader(self) -> dict:
        self._ensure_connected()
        res = self._request(oa.PT_TRADER_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
        })
        trader = res.get("trader") or {}
        if not trader:
            raise RuntimeError(f"[{VENUE.upper()}] Empty trader record from broker.")
        self._trader = trader
        return trader

    def _fetch_positions_raw(self) -> list[dict]:
        self._ensure_connected()
        res = self._request(oa.PT_RECONCILE_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "return_protection_orders": False,
        })
        return list(res.get("position", []) or [])

    def _fetch_position_pnl(self) -> dict[int, float]:
        res = self._request(oa.PT_GET_POSITION_UNREALIZED_PNL_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
        })
        digits = res.get("money_digits")
        out: dict[int, float] = {}
        for row in res.get("position_unrealized_pnl", []) or []:
            out[int(row["position_id"])] = self._money(
                row.get("net_unrealized_pnl"), digits
            )
        return out

    def _used_margin_total(self, raw_positions: list[dict]) -> float:
        total = 0.0
        for pos in raw_positions:
            digits = pos.get("money_digits")
            total += self._money(pos.get("used_margin"), digits)
        return total

    def get_balance(self) -> Dict[str, UnifiedBalance]:
        """Fresh broker balance. {} when the read fails — the engine
        treats an empty read as an unhealthy venue, never as $0."""
        try:
            trader = self._fetch_trader()
            raw_positions = self._fetch_positions_raw()
            pnl = self._fetch_position_pnl()
            balance = self._money(trader.get("balance"))
            net_pnl = sum(pnl.values())
            used = self._used_margin_total(raw_positions)
            currency = self._deposit_currency or "USD"
            return {
                currency: UnifiedBalance(
                    currency=currency,
                    free=max(balance + net_pnl - used, 0.0),
                    used=used,
                    total=balance,
                )
            }
        except Exception as e:
            logger.warning(f"[{VENUE.upper()}] get_balance failed: {e}")
            return {}

    def get_account_summary(self) -> Dict[str, Any]:
        """Account equity from the broker's own records (engine contract)."""
        try:
            trader = self._fetch_trader()
            raw_positions = self._fetch_positions_raw()
            pnl = self._fetch_position_pnl()
            balance = self._money(trader.get("balance"))
            net_pnl = sum(pnl.values())
            used = self._used_margin_total(raw_positions)
            return {
                "balance": balance,
                "equity": balance + net_pnl,
                "available": max(balance + net_pnl - used, 0.0),
                "unrealized_pnl": net_pnl,
                "can_trade": bool(self.is_healthy()),
                "currency": self._deposit_currency or "USD",
            }
        except Exception as e:
            logger.warning(f"[{VENUE.upper()}] get_account_summary failed: {e}")
            return {}

    def reconcile_balance(self, expected_balance: float, tolerance: float = 0.50) -> dict:
        """Fail-closed standard #3: fresh broker balance vs the caller's
        ledger figure. A mismatch beyond tolerance HALTS the venue."""
        trader = self._fetch_trader()
        broker_balance = self._money(trader.get("balance"))
        diff = broker_balance - float(expected_balance)
        result = {
            "broker_balance": broker_balance,
            "expected_balance": float(expected_balance),
            "diff": diff,
            "tolerance": float(tolerance),
            "ok": abs(diff) <= float(tolerance),
            "balance_version": trader.get("balance_version"),
        }
        if not result["ok"]:
            self._halt(
                f"balance reconciliation mismatch: broker={broker_balance:.2f} "
                f"ledger={float(expected_balance):.2f} diff={diff:+.2f} "
                f"tolerance={float(tolerance):.2f}"
            )
            result["halted"] = True
        return result

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------
    def _to_unified_position(self, raw: dict, pnl_by_id: dict[int, float]) -> UnifiedPosition:
        trade = raw.get("trade_data", {}) or {}
        symbol_id = int(trade.get("symbol_id", 0))
        light = self._symbols_by_id.get(symbol_id, {})
        name = str(light.get("symbol_name", f"ID_{symbol_id}"))
        side = "LONG" if int(trade.get("trade_side", 1)) == oa.SIDE_BUY else "SHORT"
        leverage = 1.0
        lev_cents = self._trader.get("leverage_in_cents")
        if lev_cents:
            leverage = float(lev_cents) / 100.0
        return UnifiedPosition(
            symbol=self.normalize_symbol(name),
            side=side,
            quantity=float(trade.get("volume", 0)) / 100.0,  # cents -> units
            entry_price=float(raw.get("price", 0.0) or 0.0),
            mark_price=float(raw.get("price", 0.0) or 0.0),
            unrealized_pnl=float(pnl_by_id.get(int(raw["position_id"]), 0.0)),
            leverage=leverage,
            exchange=VENUE,
            position_id=str(raw["position_id"]),
            stop_loss=float(raw.get("stop_loss") or 0.0),
            take_profit=float(raw.get("take_profit") or 0.0),
        )

    def get_positions_or_none(self) -> Optional[List[UnifiedPosition]]:
        """Positions, or None when the state is UNKNOWN (read failed /
        disconnected). An empty list means the broker says flat."""
        try:
            raw_positions = self._fetch_positions_raw()
            pnl = self._fetch_position_pnl()
            return [self._to_unified_position(p, pnl) for p in raw_positions]
        except Exception as e:
            logger.warning(
                f"[{VENUE.upper()}] Position read failed; state UNKNOWN: {e}"
            )
            return None

    def get_positions(self) -> List[UnifiedPosition]:
        positions = self.get_positions_or_none()
        return positions if positions is not None else []

    # ------------------------------------------------------------------
    # Protection verification (fail-closed standard #1/#2/#4)
    # ------------------------------------------------------------------
    @staticmethod
    def _protection_tolerance(digits: int) -> float:
        return 3.0 * (10 ** (-int(digits)))

    def _protection_ok(self, raw: dict, intended_sl: float, intended_tp: float,
                       digits: int) -> bool:
        tol = self._protection_tolerance(digits)
        sl = raw.get("stop_loss")
        tp = raw.get("take_profit")
        if intended_sl and (sl is None or abs(float(sl) - intended_sl) > tol):
            return False
        if intended_tp and (tp is None or abs(float(tp) - intended_tp) > tol):
            return False
        return True

    def _read_back_position(self, position_id: int) -> Optional[dict]:
        for raw in self._fetch_positions_raw():
            if int(raw.get("position_id", -1)) == int(position_id):
                return raw
        return None

    def _close_position_raw(self, position_id: int, volume_cents: int) -> dict:
        """Close via ProtoOAClosePositionReq; returns the fill event.
        Internal: bypasses the halt gate (closing is the safe action)."""
        transport = self._get_transport()
        msg_id, stream = transport.open_stream(oa.PT_CLOSE_POSITION_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "position_id": int(position_id),
            "volume": int(volume_cents),
        })
        try:
            deadline = time.time() + max(self.request_timeout, 20.0)
            while time.time() < deadline:
                _pt, event = transport.next_in_stream(
                    stream, timeout=max(deadline - time.time(), 0.1)
                )
                etype = int(event.get("execution_type", 0))
                if event.get("error_code"):
                    raise RuntimeError(
                        f"[{VENUE.upper()}] Close rejected: {event['error_code']}"
                    )
                if etype in (oa.EXEC_ORDER_FILLED, oa.EXEC_ORDER_PARTIAL_FILL):
                    return event
                if etype == oa.EXEC_ORDER_REJECTED:
                    raise RuntimeError(
                        f"[{VENUE.upper()}] Close order rejected by broker."
                    )
            raise RuntimeError(f"[{VENUE.upper()}] Close timed out.")
        finally:
            transport.close_stream(msg_id)

    def _ensure_protection(self, position_id: int, intended: dict) -> dict:
        """Read back SL/TP; amend once; close + halt if still unverified.

        Returns the verified raw position record on success.
        """
        symbol_id = int(intended["symbol_id"])
        digits = int(self._symbol_details(symbol_id).get("digits", 5))
        intended_sl = float(intended["stop_loss"])
        intended_tp = float(intended["take_profit"])

        raw = self._read_back_position(position_id)
        if raw is not None and self._protection_ok(raw, intended_sl, intended_tp, digits):
            return raw

        # One amend attempt with the absolute levels.
        logger.warning(
            f"[{VENUE.upper()}] Position {position_id} read-back protection "
            f"missing/wrong (sl={None if raw is None else raw.get('stop_loss')}, "
            f"tp={None if raw is None else raw.get('take_profit')}); amending once."
        )
        try:
            self._request(oa.PT_AMEND_POSITION_SLTP_REQ, {
                "ctid_trader_account_id": int(self.account_id or 0),
                "position_id": int(position_id),
                "stop_loss": intended_sl,
                "take_profit": intended_tp,
            })
        except Exception as e:
            logger.error(f"[{VENUE.upper()}] SL/TP amend failed: {e}")
        raw = self._read_back_position(position_id)
        if raw is not None and self._protection_ok(raw, intended_sl, intended_tp, digits):
            return raw

        # Fail closed: close the position and halt the venue.
        volume = 0
        if raw is not None:
            volume = int((raw.get("trade_data", {}) or {}).get("volume", 0))
        reason = (
            f"position {position_id} protection unverifiable after fill + amend "
            f"(intended sl={intended_sl}, tp={intended_tp}); position closed, "
            "venue halted"
        )
        try:
            if volume > 0:
                self._close_position_raw(position_id, volume)
        except Exception as e:
            reason += f"; EMERGENCY CLOSE ALSO FAILED: {e}"
        self._halt(reason)
        raise ProtectionVerificationError(f"[{VENUE.upper()}] {reason}")

    def verify_all_protection(self) -> dict:
        """Re-verify every open position's broker-side protection.

        Runs on reconnect (fail-closed standard #4) and from the
        shakedown. Positions this adapter opened are checked against
        their intended levels (amend-or-close+halt on failure, via
        _ensure_protection). Foreign/adopted positions must at least
        CARRY protection; an unprotected foreign position halts the
        venue loudly but is NOT auto-closed (it may be the owner's own
        manual trade — closing it is not this adapter's call).
        """
        raw_positions = self._fetch_positions_raw()
        checked = 0
        for raw in raw_positions:
            position_id = int(raw["position_id"])
            intended = self._intended_protection.get(position_id)
            if intended is not None:
                self._ensure_protection(position_id, intended)
            else:
                if not raw.get("stop_loss") or not raw.get("take_profit"):
                    self._halt(
                        f"adopted/foreign position {position_id} carries no "
                        "broker-side SL/TP; venue halted for investigation "
                        "(position NOT auto-closed)"
                    )
                    raise ProtectionVerificationError(
                        f"[{VENUE.upper()}] Unprotected foreign position "
                        f"{position_id}; venue halted."
                    )
            checked += 1
        return {"checked": checked, "halted": self.halted}

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------
    def _spot(self, symbol_id: int, wait_s: float = 3.0) -> tuple[float, float]:
        cached = self._spot_cache.get(symbol_id)
        if cached and (time.time() - cached[2]) < 30.0 and cached[0] > 0 and cached[1] > 0:
            return cached[0], cached[1]
        if symbol_id not in self._subscribed_spots:
            self._request(oa.PT_SUBSCRIBE_SPOTS_REQ, {
                "ctid_trader_account_id": int(self.account_id or 0),
                "symbol_id": [symbol_id],
                "subscribe_to_spot_timestamp": True,
            })
            self._subscribed_spots.add(symbol_id)
        deadline = time.time() + wait_s
        while time.time() < deadline:
            cached = self._spot_cache.get(symbol_id)
            if cached and cached[0] > 0 and cached[1] > 0:
                return cached[0], cached[1]
            time.sleep(0.05)
        raise RuntimeError(
            f"[{VENUE.upper()}] No spot price for symbol {symbol_id} within "
            f"{wait_s:.0f}s; refusing to fabricate a price."
        )

    def get_ticker(self, symbol: str) -> UnifiedTicker:
        record = self._resolve_symbol(symbol)
        symbol_id = int(record["symbol_id"])
        bid, ask = self._spot(symbol_id)
        return UnifiedTicker(
            symbol=self.normalize_symbol(symbol),
            bid=bid, ask=ask, last=(bid + ask) / 2.0, volume_24h=0.0,
        )

    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict[str, List[List[float]]]:
        # Depth-of-market subscription is out of scope for this lane; the
        # engine does not trade on book depth. Honest empty book (the
        # Binance futures adapter does the same when depth is absent).
        return {"bids": [], "asks": []}

    def get_historical_data(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> List[Dict[str, Any]]:
        period = oa.TRENDBAR_PERIODS.get(timeframe)
        if period is None:
            raise ValueError(
                f"[{VENUE.upper()}] Timeframe '{timeframe}' is not offered by "
                f"the Open API (available: {sorted(oa.TRENDBAR_PERIODS)})."
            )
        record = self._resolve_symbol(symbol)
        symbol_id = int(record["symbol_id"])
        period_seconds = {
            1: 60, 2: 120, 3: 180, 4: 240, 5: 300, 6: 600, 7: 900, 8: 1800,
            9: 3600, 10: 14400, 11: 43200, 12: 86400, 13: 604800, 14: 2592000,
        }[period]
        to_ms = int(time.time() * 1000)
        from_ms = to_ms - int(period_seconds * 1000 * (int(limit) + 2))
        res = self._request(oa.PT_GET_TRENDBARS_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "from_timestamp": from_ms,
            "to_timestamp": to_ms,
            "period": period,
            "symbol_id": symbol_id,
            "count": int(limit),
        })
        candles = []
        for bar in res.get("trendbar", []) or []:
            low = float(bar.get("low", 0)) / oa.PRICE_SCALE
            candles.append({
                "timestamp": int(bar.get("utc_timestamp_in_minutes", 0)) * 60,
                "open": low + float(bar.get("delta_open", 0)) / oa.PRICE_SCALE,
                "high": low + float(bar.get("delta_high", 0)) / oa.PRICE_SCALE,
                "low": low,
                "close": low + float(bar.get("delta_close", 0)) / oa.PRICE_SCALE,
                "volume": float(bar.get("volume", 0)),
            })
        candles.sort(key=lambda c: c["timestamp"])
        return candles[-int(limit):]

    def get_fees(self, symbol: str) -> tuple[float, float]:
        # cTrader charges a per-lot commission (EURUSD on this account:
        # 3.00 USD per lot per side, seen in cTrader), not a fraction of
        # notional — a fractional figure would be invented. Real fees are
        # reported per deal and summed by get_realized_pnl().
        return (0.0, 0.0)

    def get_realized_pnl(self, symbol: str, since_ms: Optional[int] = None) -> Dict[str, Any]:
        """Realized PnL from the broker's own closing deals."""
        zeros: Dict[str, Any] = {
            "gross": 0.0, "fees": 0.0, "net": 0.0, "trades": 0,
            "last_price": 0.0, "last_time": 0,
        }
        try:
            record = self._resolve_symbol(symbol)
            symbol_id = int(record["symbol_id"])
            to_ms = int(time.time() * 1000)
            from_ms = int(since_ms) if since_ms else to_ms - 30 * 86400 * 1000
            res = self._request(oa.PT_DEAL_LIST_REQ, {
                "ctid_trader_account_id": int(self.account_id or 0),
                "from_timestamp": from_ms,
                "to_timestamp": to_ms,
                "max_rows": 1000,
            })
            gross = 0.0
            fees = 0.0
            trades = 0
            last_price = 0.0
            last_time = 0
            for deal in res.get("deal", []) or []:
                detail = deal.get("close_position_detail")
                if not detail or int(deal.get("symbol_id", -1)) != symbol_id:
                    continue
                digits = detail.get("money_digits", deal.get("money_digits"))
                gross += self._money(detail.get("gross_profit"), digits) \
                    + self._money(detail.get("swap"), digits)
                fees += abs(self._money(detail.get("commission"), digits)) \
                    + abs(self._money(detail.get("pnl_conversion_fee"), digits))
                trades += 1
                ts = int(deal.get("execution_timestamp", 0) or 0)
                if ts >= last_time:
                    last_time = ts
                    last_price = float(deal.get("execution_price", 0.0) or 0.0)
            return {
                "gross": gross, "fees": fees, "net": gross - fees,
                "trades": trades, "last_price": last_price, "last_time": last_time,
            }
        except Exception as e:
            logger.warning(f"[{VENUE.upper()}] get_realized_pnl failed: {e}")
            return dict(zeros, error=str(e))

    # ------------------------------------------------------------------
    # Order placement (fail-closed standard #1 + #2)
    # ------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> UnifiedOrderResult:
        _enforce_no_live_trading()
        self._raise_if_halted()
        self._ensure_connected()

        norm_side = str(side).upper()
        if norm_side in ("BUY", "LONG"):
            trade_side = oa.SIDE_BUY
        elif norm_side in ("SELL", "SHORT"):
            trade_side = oa.SIDE_SELL
        else:
            raise ValueError(f"Invalid side: {side}")
        otype = str(order_type).upper()
        if otype == "MARKET":
            oa_type = oa.OT_MARKET
        elif otype == "LIMIT":
            oa_type = oa.OT_LIMIT
        elif otype == "STOP":
            oa_type = oa.OT_STOP
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        record = self._resolve_symbol(symbol)
        symbol_id = int(record["symbol_id"])
        details = self._symbol_details(symbol_id)
        digits = int(details.get("digits", 5))
        volume_cents = self._lots_to_volume_cents(symbol_id, float(quantity))

        # Engine close path: an opposite-side MARKET order with no SL/TP
        # and no explicit position reference means "close what is open"
        # (the engine's close_position works this way on the one-way
        # Binance book). Route it to ProtoOAClosePositionReq so a HEDGED
        # account never ends up long AND short the same symbol.
        if oa_type == oa.OT_MARKET and not stop_loss and not take_profit:
            closed = self._close_via_market(symbol_id, trade_side, volume_cents)
            if closed is not None:
                return closed
            raise RuntimeError(
                f"[{VENUE.upper()}] Refusing unprotected entry on {symbol}: "
                "every entry order must carry stop_loss and take_profit "
                "(fail-closed standard #1)."
            )
        if not stop_loss or not take_profit:
            raise RuntimeError(
                f"[{VENUE.upper()}] Refusing entry on {symbol}: both stop_loss "
                "and take_profit are required on every entry order "
                "(fail-closed standard #1)."
            )

        fields: Dict[str, Any] = {
            "ctid_trader_account_id": int(self.account_id or 0),
            "symbol_id": symbol_id,
            "order_type": oa_type,
            "trade_side": trade_side,
            "volume": volume_cents,
            "label": "stratex",
            "client_order_id": f"STX{uuid.uuid4().hex[:20]}",
        }
        intended_sl = float(stop_loss)
        intended_tp = float(take_profit)
        if oa_type == oa.OT_MARKET:
            # Absolute SL/TP is rejected for MARKET orders; attach the
            # judged DISTANCE as relative SL/TP against the live spot.
            bid, ask = self._spot(symbol_id)
            ref = ask if trade_side == oa.SIDE_BUY else bid
            sl_distance = abs(ref - intended_sl)
            tp_distance = abs(intended_tp - ref)
            if sl_distance <= 0 or tp_distance <= 0:
                raise ValueError(
                    f"[{VENUE.upper()}] SL/TP are on the wrong side of the "
                    f"market for {symbol} (ref={ref}, sl={intended_sl}, tp={intended_tp})."
                )
            fields["relative_stop_loss"] = int(round(sl_distance * oa.PRICE_SCALE))
            fields["relative_take_profit"] = int(round(tp_distance * oa.PRICE_SCALE))
        else:
            if otype == "LIMIT":
                if price is None:
                    raise ValueError("LIMIT order requires a price")
                fields["limit_price"] = float(price)
            else:
                trigger = stop_price if stop_price is not None else price
                if trigger is None:
                    raise ValueError("STOP order requires a stop price")
                fields["stop_price"] = float(trigger)
            fields["stop_loss"] = intended_sl
            fields["take_profit"] = intended_tp

        event = self._send_order(fields)
        order = event.get("order", {}) or {}
        position = event.get("position", {}) or {}
        deal = event.get("deal", {}) or {}
        status = "PENDING"
        executed_lots = 0.0
        fill_price = 0.0
        position_id: Optional[int] = None

        if int(event.get("execution_type", 0)) in (
            oa.EXEC_ORDER_FILLED, oa.EXEC_ORDER_PARTIAL_FILL,
        ):
            status = "FILLED" if int(event["execution_type"]) == oa.EXEC_ORDER_FILLED \
                else "PARTIALLY_FILLED"
            position_id = int(position.get("position_id") or order.get("position_id") or 0) or None
            fill_price = float(deal.get("execution_price") or position.get("price") or 0.0)
            filled_cents = int(deal.get("filled_volume") or order.get("executed_volume") or 0)
            lot_size = int(details.get("lot_size") or 0)
            executed_lots = (filled_cents / lot_size) if lot_size else float(quantity)
            if position_id is None:
                raise RuntimeError(
                    f"[{VENUE.upper()}] Fill event carried no position id; "
                    "cannot verify protection — treating as unverified."
                )
            # The levels the broker should now hold: for MARKET orders
            # the server derives them from the fill and the relative
            # distances we sent; for LIMIT/STOP they are the absolutes.
            if oa_type == oa.OT_MARKET:
                if trade_side == oa.SIDE_BUY:
                    verify_sl = fill_price - fields["relative_stop_loss"] / oa.PRICE_SCALE
                    verify_tp = fill_price + fields["relative_take_profit"] / oa.PRICE_SCALE
                else:
                    verify_sl = fill_price + fields["relative_stop_loss"] / oa.PRICE_SCALE
                    verify_tp = fill_price - fields["relative_take_profit"] / oa.PRICE_SCALE
            else:
                verify_sl, verify_tp = intended_sl, intended_tp
            intended = {
                "symbol_id": symbol_id,
                "stop_loss": verify_sl,
                "take_profit": verify_tp,
            }
            self._intended_protection[int(position_id)] = intended
            self._ensure_protection(int(position_id), intended)
        elif oa_type in (oa.OT_LIMIT, oa.OT_STOP):
            # Pending: verify the protection riding on the ORDER itself.
            order_id = int(order.get("order_id", 0))
            self._verify_pending_order(order_id, intended_sl, intended_tp, digits)
            status = "PENDING"

        fee = abs(self._money(deal.get("commission"), deal.get("money_digits")))
        return UnifiedOrderResult(
            order_id=str(order.get("order_id", "")),
            symbol=self.normalize_symbol(symbol),
            side=norm_side,
            order_type=otype,
            price=fill_price or float(price or 0.0),
            quantity=float(quantity),
            status=status,
            executed_qty=executed_lots,
            avg_price=fill_price,
            fee_paid=fee,
            exchange=VENUE,
        )

    def _send_order(self, fields: dict) -> dict:
        """Send ProtoOANewOrderReq and collect its execution events."""
        transport = self._get_transport()
        msg_id, stream = transport.open_stream(oa.PT_NEW_ORDER_REQ, fields)
        try:
            deadline = time.time() + max(self.request_timeout, 20.0)
            last_event: Optional[dict] = None
            while time.time() < deadline:
                try:
                    payload_type, event = transport.next_in_stream(
                        stream, timeout=max(deadline - time.time(), 0.1)
                    )
                except (TimeoutError, oa.TransportTimeout):
                    # The stream went quiet. If a non-terminal event was
                    # already seen, the tail below decides (fail closed);
                    # with no event at all this is the plain no-response
                    # timeout, also decided below.
                    break
                if payload_type == oa.PT_ORDER_ERROR_EVENT:
                    raise RuntimeError(
                        f"[{VENUE.upper()}] Order error: "
                        f"{event.get('error_code')}: {event.get('description', '')}"
                    )
                if payload_type != oa.PT_EXECUTION_EVENT:
                    continue
                last_event = event
                if event.get("error_code"):
                    raise RuntimeError(
                        f"[{VENUE.upper()}] Order rejected: {event['error_code']}"
                    )
                etype = int(event.get("execution_type", 0))
                if etype in (oa.EXEC_ORDER_FILLED, oa.EXEC_ORDER_PARTIAL_FILL,
                             oa.EXEC_ORDER_REJECTED, oa.EXEC_ORDER_EXPIRED,
                             oa.EXEC_ORDER_CANCELLED):
                    return event
                if etype == oa.EXEC_ORDER_ACCEPTED and int(
                    (event.get("order", {}) or {}).get("order_type", 1)
                ) != oa.OT_MARKET:
                    return event  # pending LIMIT/STOP accepted
            if last_event is not None:
                # Only non-terminal events arrived (e.g. a MARKET order
                # stuck at ACCEPTED until the deadline): the broker may
                # be holding an order/position whose protection was
                # never verified. Fail closed (TASK-STR-PEP-002,
                # supervisor condition on PR #1097): halt the venue and
                # raise instead of returning the event, which made
                # place_order report an unverified PENDING.
                reason = (
                    "order outcome UNCONFIRMED: no terminal execution "
                    "event before the deadline (last execution_type="
                    f"{last_event.get('execution_type')}); the order may "
                    "be open at the broker with unverified protection"
                )
                self._halt(reason)
                raise RuntimeError(f"[{VENUE.upper()}] {reason}; venue halted.")
            raise RuntimeError(f"[{VENUE.upper()}] Order timed out with no execution event.")
        finally:
            transport.close_stream(msg_id)

    def _verify_pending_order(self, order_id: int, intended_sl: float,
                              intended_tp: float, digits: int) -> None:
        """A pending LIMIT/STOP order must carry its SL/TP on the order
        record itself; read back via reconcile and check."""
        res = self._request(oa.PT_RECONCILE_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "return_protection_orders": False,
        })
        for order in res.get("order", []) or []:
            if int(order.get("order_id", -1)) == int(order_id):
                tol = self._protection_tolerance(digits)
                sl = order.get("stop_loss")
                tp = order.get("take_profit")
                if (sl is not None and abs(float(sl) - intended_sl) <= tol) and \
                        (tp is not None and abs(float(tp) - intended_tp) <= tol):
                    return
                break
        # Missing/wrong: cancel the unprotected pending order and halt.
        try:
            self.cancel_order("", str(order_id))
        except Exception:
            pass
        reason = (
            f"pending order {order_id} read-back protection missing/wrong; "
            "order cancelled, venue halted"
        )
        self._halt(reason)
        raise ProtectionVerificationError(f"[{VENUE.upper()}] {reason}")

    def _close_via_market(self, symbol_id: int, trade_side: int,
                          volume_cents: int) -> Optional[UnifiedOrderResult]:
        """Close open position(s) on a symbol opposite to trade_side.

        Returns None when nothing is open on the opposite side (the
        caller then treats the order as an entry and refuses it for
        missing SL/TP)."""
        raw_positions = self._fetch_positions_raw()
        targets = []
        for raw in raw_positions:
            trade = raw.get("trade_data", {}) or {}
            if int(trade.get("symbol_id", -1)) != symbol_id:
                continue
            pos_side = int(trade.get("trade_side", 0))
            if pos_side != trade_side:  # opposite side open -> closable
                targets.append(raw)
        if not targets:
            return None
        remaining = int(volume_cents)
        last_event: Optional[dict] = None
        closed_cents = 0
        for raw in targets:
            if remaining <= 0:
                break
            position_id = int(raw["position_id"])
            pos_volume = int((raw.get("trade_data", {}) or {}).get("volume", 0))
            close_volume = min(pos_volume, remaining)
            last_event = self._close_position_raw(position_id, close_volume)
            closed_cents += close_volume
            remaining -= close_volume
            if close_volume >= pos_volume:
                self._intended_protection.pop(position_id, None)
        deal = (last_event or {}).get("deal", {}) or {}
        light = self._symbols_by_id.get(symbol_id, {})
        details = self._symbol_details(symbol_id)
        lot_size = int(details.get("lot_size") or 0)
        return UnifiedOrderResult(
            order_id=str((last_event or {}).get("order", {}).get("order_id", "")),
            symbol=self.normalize_symbol(str(light.get("symbol_name", ""))),
            side="BUY" if trade_side == oa.SIDE_BUY else "SELL",
            order_type="MARKET",
            price=float(deal.get("execution_price") or 0.0),
            quantity=(closed_cents / lot_size) if lot_size else 0.0,
            status="FILLED",
            executed_qty=(closed_cents / lot_size) if lot_size else 0.0,
            avg_price=float(deal.get("execution_price") or 0.0),
            fee_paid=abs(self._money(deal.get("commission"), deal.get("money_digits"))),
            exchange=VENUE,
        )

    def close_position_by_id(self, position_id: int, volume_cents: int | None = None) -> dict:
        """Explicit close of one position (shakedown + future wiring)."""
        self._raise_if_halted()
        self._ensure_connected()
        if volume_cents is None:
            raw = self._read_back_position(position_id)
            if raw is None:
                raise RuntimeError(
                    f"[{VENUE.upper()}] Position {position_id} not found."
                )
            volume_cents = int((raw.get("trade_data", {}) or {}).get("volume", 0))
        event = self._close_position_raw(int(position_id), int(volume_cents))
        self._intended_protection.pop(int(position_id), None)
        return event

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        _enforce_no_live_trading()
        self._ensure_connected()
        transport = self._get_transport()
        msg_id, stream = transport.open_stream(oa.PT_CANCEL_ORDER_REQ, {
            "ctid_trader_account_id": int(self.account_id or 0),
            "order_id": int(order_id),
        })
        try:
            deadline = time.time() + self.request_timeout
            while time.time() < deadline:
                payload_type, event = transport.next_in_stream(
                    stream, timeout=max(deadline - time.time(), 0.1)
                )
                if payload_type == oa.PT_ORDER_ERROR_EVENT:
                    return False
                if payload_type == oa.PT_EXECUTION_EVENT:
                    if event.get("error_code"):
                        return False
                    if int(event.get("execution_type", 0)) == oa.EXEC_ORDER_CANCELLED:
                        return True
            return False
        except Exception as e:
            logger.warning(f"[{VENUE.upper()}] cancel_order failed: {e}")
            return False
        finally:
            transport.close_stream(msg_id)

    def cancel_protective_orders(self, symbol: str) -> int:
        """SL/TP are attributes of the position on cTrader, not separate
        orders: when the position closes they cease to exist. There is
        nothing to cancel (contrast the Binance algo-order model)."""
        return 0


# Alias, following the fleet's adapter naming pattern.
PepperstoneCTraderExchange = PepperstoneCTraderAdapter
