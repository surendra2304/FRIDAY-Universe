"""
TASK-STR-PEP-001 — Pepperstone cTrader adapter contract tests.

Covers the fail-closed standard with a mocked broker transport:
  * SL/TP attached at placement (relative on MARKET, absolute on LIMIT)
    and verified by read-back;
  * read-back missing -> one amend -> re-read OK;
  * read-back missing + amend does not stick -> immediate close + HALT;
  * balance reconciliation mismatch -> HALT; failed reads never fabricate;
  * disconnect mid-position -> state UNKNOWN; on reconnect, protection is
    assumed broker-side only after read-back proof;
  * demo-only guards (live host / TRADING_MODE=LIVE refused);
  * wire codec field numbers pinned against Spotware's published protos.

Run: pytest Stratex/tests/test_pep001_pepperstone_ctrader_adapter.py
"""
import os
import queue
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from exchanges import ctrader_openapi as oa  # noqa: E402
from exchanges.pepperstone_ctrader_adapter import (  # noqa: E402
    PepperstoneCTraderAdapter,
    ProtectionVerificationError,
    VenueHaltedError,
)

ACCOUNT_CTID = 777001
ACCOUNT_LOGIN = 5376835
EURUSD_ID = 1
EURUSD_BID = 1.08000
EURUSD_ASK = 1.08020


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "TRADING_MODE", "LIVE_TRADING_ENABLED", "ALLOW_LIVE_TRADING",
        "PEPPERSTONE_CTRADER_HOST", "PEPPERSTONE_CTRADER_PORT",
        "PEPPERSTONE_CTRADER_CLIENT_ID", "PEPPERSTONE_CTRADER_CLIENT_SECRET",
        "PEPPERSTONE_CTRADER_ACCESS_TOKEN", "PEPPERSTONE_CTRADER_REFRESH_TOKEN",
        "PEPPERSTONE_CTRADER_ACCOUNT_ID", "PEPPERSTONE_CTRADER_ACCOUNT_NUMBER",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


# ----------------------------------------------------------------------
# Fake broker transport (dict-level, same interface as OpenApiTransport)
# ----------------------------------------------------------------------
class FakeTransport:
    """Scripted in-memory cTrader server.

    sltp_mode:
      attach    — fills carry SL/TP derived from the relative distances
      amendable — fills carry NO SL/TP, but AmendPositionSLTP sticks
      broken    — fills carry NO SL/TP and AmendPositionSLTP never sticks
    """

    def __init__(self, sltp_mode="attach"):
        self.sltp_mode = sltp_mode
        self.connected = False
        self.refuse_connect = False
        self.fail_trader = False
        self.drop_order_sltp = False
        self.on_event = None
        self.on_disconnect = None
        self.requests = []          # (payload_type, fields)
        self.streams_opened = []    # (payload_type, fields)
        self.positions = {}         # position_id -> raw position dict
        self.orders = {}            # order_id -> raw order dict
        self.closed_positions = []  # position_ids closed via ClosePosition
        self.balance_raw = 1_000_000
        self.money_digits = 2
        self.pnl_rows = []
        self.deals = []
        self._next_position_id = 5001
        self._next_order_id = 9001
        self._next_deal_id = 7001
        self._msg_seq = 0

    # -- connection -----------------------------------------------------
    def connect(self):
        if self.refuse_connect:
            raise ConnectionError("connection refused (fake)")
        self.connected = True

    def close(self):
        self.connected = False

    @property
    def is_connected(self):
        return self.connected

    def disconnect(self):
        self.connected = False
        if self.on_disconnect:
            self.on_disconnect("simulated drop")

    # -- request/response ------------------------------------------------
    def request(self, payload_type, fields, timeout=15.0):
        if not self.connected:
            raise ConnectionError("not connected (fake)")
        self.requests.append((payload_type, dict(fields)))
        handler = {
            oa.PT_APPLICATION_AUTH_REQ: lambda f: {},
            oa.PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ: self._accounts,
            oa.PT_ACCOUNT_AUTH_REQ: lambda f: {},
            oa.PT_REFRESH_TOKEN_REQ: lambda f: {
                "access_token": "tok2", "refresh_token": "ref2",
                "expires_in": 3600, "token_type": "bearer",
            },
            oa.PT_TRADER_REQ: self._trader,
            oa.PT_ASSET_LIST_REQ: lambda f: {
                "asset": [{"asset_id": 1, "name": "USD", "display_name": "USD"}]
            },
            oa.PT_SYMBOLS_LIST_REQ: lambda f: {"symbol": [
                {"symbol_id": EURUSD_ID, "symbol_name": "EURUSD", "enabled": True},
                {"symbol_id": 2, "symbol_name": "XAUUSD", "enabled": True},
            ]},
            oa.PT_SYMBOL_BY_ID_REQ: self._symbol_by_id,
            oa.PT_RECONCILE_REQ: lambda f: {
                "ctid_trader_account_id": ACCOUNT_CTID,
                "position": list(self.positions.values()),
                "order": list(self.orders.values()),
            },
            oa.PT_GET_POSITION_UNREALIZED_PNL_REQ: lambda f: {
                "position_unrealized_pnl": list(self.pnl_rows),
                "money_digits": self.money_digits,
            },
            oa.PT_AMEND_POSITION_SLTP_REQ: self._amend,
            oa.PT_SUBSCRIBE_SPOTS_REQ: self._subscribe_spots,
            oa.PT_GET_TRENDBARS_REQ: self._trendbars,
            oa.PT_DEAL_LIST_REQ: lambda f: {"deal": list(self.deals)},
        }.get(payload_type)
        if handler is None:
            raise AssertionError(f"unexpected request payload type {payload_type}")
        return handler(fields)

    def _accounts(self, fields):
        return {
            "ctid_trader_account": [{
                "ctid_trader_account_id": ACCOUNT_CTID,
                "is_live": False,
                "trader_login": ACCOUNT_LOGIN,
            }],
            "permission_scope": 1,
        }

    def _trader(self, fields):
        if self.fail_trader:
            raise TimeoutError("trader read timed out (fake)")
        return {"trader": {
            "ctid_trader_account_id": ACCOUNT_CTID,
            "balance": self.balance_raw,
            "balance_version": 3,
            "deposit_asset_id": 1,
            "leverage_in_cents": 20000,
            "trader_login": ACCOUNT_LOGIN,
            "money_digits": self.money_digits,
            "broker_name": "Pepperstone",
        }}

    def _symbol_by_id(self, fields):
        details = {
            EURUSD_ID: {
                "symbol_id": EURUSD_ID, "digits": 5, "pip_position": 4,
                "lot_size": 10_000_000, "min_volume": 1000,
                "max_volume": 500_000_000, "step_volume": 1000,
            },
            2: {
                "symbol_id": 2, "digits": 2, "pip_position": 0,
                "lot_size": 10_000, "min_volume": 100,
                "max_volume": 500_000, "step_volume": 100,
            },
        }
        return {"symbol": [details[i] for i in fields.get("symbol_id", [])
                           if i in details]}

    def _amend(self, fields):
        if self.sltp_mode in ("attach", "amendable"):
            pos = self.positions.get(int(fields["position_id"]))
            if pos is not None:
                if fields.get("stop_loss") is not None:
                    pos["stop_loss"] = fields["stop_loss"]
                if fields.get("take_profit") is not None:
                    pos["take_profit"] = fields["take_profit"]
        return {}

    def _subscribe_spots(self, fields):
        spots = {EURUSD_ID: (108000, 108020), 2: (265000, 265030)}
        for symbol_id in fields.get("symbol_id", []):
            bid, ask = spots.get(symbol_id, (0, 0))
            payload = oa.encode_message(oa.SCHEMAS[oa.PT_SPOT_EVENT], {
                "ctid_trader_account_id": ACCOUNT_CTID,
                "symbol_id": symbol_id, "bid": bid, "ask": ask,
                "timestamp": 1_700_000_000_000,
            })
            if self.on_event:
                self.on_event(oa.PT_SPOT_EVENT, payload)
        return {}

    def _trendbars(self, fields):
        return {
            "period": fields.get("period"),
            "symbol_id": fields.get("symbol_id"),
            "trendbar": [{
                "volume": 100, "low": 108000, "delta_open": 10,
                "delta_close": 50, "delta_high": 80,
                "utc_timestamp_in_minutes": 29_500_000,
            }],
        }

    # -- streaming (order lifecycle) --------------------------------------
    def open_stream(self, payload_type, fields):
        if not self.connected:
            raise ConnectionError("not connected (fake)")
        self.streams_opened.append((payload_type, dict(fields)))
        self._msg_seq += 1
        msg_id = f"fake-{self._msg_seq}"
        q: queue.Queue = queue.Queue()
        if payload_type == oa.PT_NEW_ORDER_REQ:
            for event in self._new_order_events(fields):
                q.put(event)
        elif payload_type == oa.PT_CLOSE_POSITION_REQ:
            q.put(self._close_event(fields))
        elif payload_type == oa.PT_CANCEL_ORDER_REQ:
            self.orders.pop(int(fields["order_id"]), None)
            q.put((oa.PT_EXECUTION_EVENT, {"execution_type": oa.EXEC_ORDER_CANCELLED}))
        else:
            raise AssertionError(f"unexpected stream payload type {payload_type}")
        return msg_id, q

    def next_in_stream(self, stream, timeout=15.0):
        try:
            return stream.get(timeout=max(timeout, 0.05))
        except queue.Empty:
            raise TimeoutError("stream timed out (fake)")

    def close_stream(self, client_msg_id):
        pass

    def _new_order_events(self, fields):
        order_id = self._next_order_id
        self._next_order_id += 1
        symbol_id = int(fields["symbol_id"])
        side = int(fields["trade_side"])
        volume = int(fields["volume"])
        ref = EURUSD_ASK if side == oa.SIDE_BUY else EURUSD_BID
        if int(fields["order_type"]) == oa.OT_MARKET:
            position_id = self._next_position_id
            self._next_position_id += 1
            position = {
                "position_id": position_id,
                "trade_data": {
                    "symbol_id": symbol_id, "volume": volume,
                    "trade_side": side, "open_timestamp": 1_700_000_000_000,
                },
                "position_status": 1,
                "price": ref,
            }
            if self.sltp_mode == "attach":
                rel_sl = int(fields.get("relative_stop_loss") or 0)
                rel_tp = int(fields.get("relative_take_profit") or 0)
                if side == oa.SIDE_BUY:
                    position["stop_loss"] = ref - rel_sl / oa.PRICE_SCALE
                    position["take_profit"] = ref + rel_tp / oa.PRICE_SCALE
                else:
                    position["stop_loss"] = ref + rel_sl / oa.PRICE_SCALE
                    position["take_profit"] = ref - rel_tp / oa.PRICE_SCALE
            self.positions[position_id] = position
            deal_id = self._next_deal_id
            self._next_deal_id += 1
            event = (oa.PT_EXECUTION_EVENT, {
                "execution_type": oa.EXEC_ORDER_FILLED,
                "position": dict(position),
                "order": {
                    "order_id": order_id, "order_type": oa.OT_MARKET,
                    "order_status": 2, "executed_volume": volume,
                    "position_id": position_id,
                },
                "deal": {
                    "deal_id": deal_id, "order_id": order_id,
                    "position_id": position_id, "volume": volume,
                    "filled_volume": volume, "symbol_id": symbol_id,
                    "execution_price": ref, "trade_side": side,
                    "deal_status": 2, "commission": -300,
                    "money_digits": self.money_digits,
                },
            })
            return [event]
        # LIMIT / STOP: pending order carrying absolute SL/TP (or not).
        order = {
            "order_id": order_id,
            "trade_data": {
                "symbol_id": symbol_id, "volume": volume, "trade_side": side,
            },
            "order_type": int(fields["order_type"]),
            "order_status": 1,
            "limit_price": fields.get("limit_price"),
            "stop_price": fields.get("stop_price"),
        }
        if not self.drop_order_sltp:
            order["stop_loss"] = fields.get("stop_loss")
            order["take_profit"] = fields.get("take_profit")
        self.orders[order_id] = order
        return [(oa.PT_EXECUTION_EVENT, {
            "execution_type": oa.EXEC_ORDER_ACCEPTED,
            "order": dict(order),
        })]

    def _close_event(self, fields):
        position_id = int(fields["position_id"])
        volume = int(fields["volume"])
        pos = self.positions.get(position_id)
        if pos is not None:
            remaining = int(pos["trade_data"]["volume"]) - volume
            if remaining <= 0:
                del self.positions[position_id]
                self.closed_positions.append(position_id)
            else:
                pos["trade_data"]["volume"] = remaining
        deal_id = self._next_deal_id
        self._next_deal_id += 1
        return (oa.PT_EXECUTION_EVENT, {
            "execution_type": oa.EXEC_ORDER_FILLED,
            "order": {"order_id": self._next_order_id, "order_type": oa.OT_MARKET},
            "deal": {
                "deal_id": deal_id, "position_id": position_id,
                "filled_volume": volume, "execution_price": EURUSD_BID,
                "commission": -300, "money_digits": self.money_digits,
            },
        })


def make_adapter(sltp_mode="attach", **overrides):
    fake = FakeTransport(sltp_mode=sltp_mode)
    kwargs = dict(
        client_id="cid", client_secret="secret", access_token="tok",
        account_number=str(ACCOUNT_LOGIN), transport=fake,
    )
    kwargs.update(overrides)
    adapter = PepperstoneCTraderAdapter(**kwargs)
    fake.on_event = adapter._on_event
    fake.on_disconnect = adapter._on_disconnect
    return adapter, fake


def sent_requests(fake, payload_type):
    return [f for pt, f in fake.requests if pt == payload_type]


def sent_streams(fake, payload_type):
    return [f for pt, f in fake.streams_opened if pt == payload_type]


# ----------------------------------------------------------------------
# Wire codec: field numbers pinned to Spotware's published protos
# ----------------------------------------------------------------------
def test_codec_envelope_and_new_order_field_numbers():
    payload = oa.encode_message(oa.SCHEMAS[oa.PT_NEW_ORDER_REQ], {
        "ctid_trader_account_id": ACCOUNT_CTID,
        "symbol_id": EURUSD_ID,
        "order_type": oa.OT_MARKET,
        "trade_side": oa.SIDE_BUY,
        "volume": 100_000,
        "relative_stop_loss": 500,
        "relative_take_profit": 1000,
    })
    frame = oa.encode_message(oa.ENVELOPE_SCHEMA, {
        "payload_type": oa.PT_NEW_ORDER_REQ, "payload": payload,
        "client_msg_id": "msg-1",
    })
    envelope = oa.decode_message(oa.ENVELOPE_SCHEMA, frame)
    payload_type = envelope["payload_type"]
    body = envelope["payload"]
    msg_id = envelope["client_msg_id"]
    assert payload_type == oa.PT_NEW_ORDER_REQ
    assert msg_id == "msg-1"
    # Probe decode: values must land on fields 19/20 (relative SL/TP),
    # NOT on 11/12 (absolute) — this pins the proto field numbers.
    probe = oa.decode_message(
        {"rel_sl": (19, "int64"), "rel_tp": (20, "int64"),
         "abs_sl": (11, "double"), "abs_tp": (12, "double")}, body)
    assert probe["rel_sl"] == 500
    assert probe["rel_tp"] == 1000
    assert "abs_sl" not in probe and "abs_tp" not in probe
    decoded = oa.decode_message(oa.SCHEMAS[oa.PT_NEW_ORDER_REQ], body)
    assert decoded["volume"] == 100_000
    assert decoded["symbol_id"] == EURUSD_ID


def test_codec_reconcile_roundtrip_with_nested_position():
    payload = oa.encode_message(oa.SCHEMAS[oa.PT_RECONCILE_RES], {
        "ctid_trader_account_id": ACCOUNT_CTID,
        "position": [{
            "position_id": 42,
            "trade_data": {"symbol_id": EURUSD_ID, "volume": 100_000,
                           "trade_side": oa.SIDE_BUY},
            "position_status": 1,
            "price": EURUSD_ASK,
            "stop_loss": 1.07520,
            "take_profit": 1.09020,
        }],
    })
    decoded = oa.decode_message(oa.SCHEMAS[oa.PT_RECONCILE_RES], payload)
    pos = decoded["position"][0]
    assert pos["position_id"] == 42
    assert pos["stop_loss"] == pytest.approx(1.07520)
    assert pos["take_profit"] == pytest.approx(1.09020)
    assert pos["trade_data"]["volume"] == 100_000


# ----------------------------------------------------------------------
# Auth flow
# ----------------------------------------------------------------------
def test_auth_flow_order_and_account_resolution():
    adapter, fake = make_adapter()
    summary = adapter.get_account_summary()
    assert summary["balance"] == pytest.approx(10_000.00)
    assert adapter.account_id == ACCOUNT_CTID
    first_three = [pt for pt, _ in fake.requests[:3]]
    assert first_three == [
        oa.PT_APPLICATION_AUTH_REQ,
        oa.PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
        oa.PT_ACCOUNT_AUTH_REQ,
    ]


def test_money_digits_scaling_is_self_describing():
    adapter, fake = make_adapter()
    assert adapter.get_account_summary()["balance"] == pytest.approx(10_000.00)
    # Same balance reported with moneyDigits=3 must read identically.
    adapter2, fake2 = make_adapter()
    fake2.money_digits = 3
    fake2.balance_raw = 10_000_000
    assert adapter2.get_account_summary()["balance"] == pytest.approx(10_000.00)


# ----------------------------------------------------------------------
# Fail-closed #1/#2: SL/TP attach + read-back verification
# ----------------------------------------------------------------------
def test_market_order_relative_sltp_and_readback_success():
    adapter, fake = make_adapter()
    result = adapter.place_order(
        "EURUSD", "BUY", "MARKET", 0.01,
        stop_loss=1.07520, take_profit=1.09020,
    )
    assert result.status == "FILLED"
    assert result.executed_qty == pytest.approx(0.01)
    assert adapter.halted is False
    order_fields = sent_streams(fake, oa.PT_NEW_ORDER_REQ)[0]
    # MARKET orders: judged distances ride as relative SL/TP (fields
    # 19/20); absolute fields stay empty (the API rejects them here).
    assert order_fields["relative_stop_loss"] == 500     # 0.00500 x 1e5
    assert order_fields["relative_take_profit"] == 1000  # 0.01000 x 1e5
    assert order_fields.get("stop_loss") is None
    assert order_fields.get("take_profit") is None
    # 0.01 lot of EURUSD (lotSize 10,000,000 cents) == 100,000 cents.
    assert order_fields["volume"] == 100_000
    # Read-back happened (reconcile) and the position carries protection.
    assert sent_requests(fake, oa.PT_RECONCILE_REQ)
    pos = next(iter(fake.positions.values()))
    assert pos["stop_loss"] == pytest.approx(1.07520)
    assert pos["take_profit"] == pytest.approx(1.09020)


def test_readback_missing_then_amend_recovers():
    adapter, fake = make_adapter(sltp_mode="amendable")
    result = adapter.place_order(
        "EURUSD", "BUY", "MARKET", 0.01,
        stop_loss=1.07520, take_profit=1.09020,
    )
    assert result.status == "FILLED"
    assert adapter.halted is False
    amends = sent_requests(fake, oa.PT_AMEND_POSITION_SLTP_REQ)
    assert len(amends) == 1
    assert amends[0]["stop_loss"] == pytest.approx(1.07520)
    assert amends[0]["take_profit"] == pytest.approx(1.09020)
    assert fake.closed_positions == []


def test_readback_missing_and_amend_fails_closes_and_halts():
    adapter, fake = make_adapter(sltp_mode="broken")
    with pytest.raises(ProtectionVerificationError):
        adapter.place_order(
            "EURUSD", "BUY", "MARKET", 0.01,
            stop_loss=1.07520, take_profit=1.09020,
        )
    # The unprotected position was closed immediately...
    assert len(fake.closed_positions) == 1
    assert fake.positions == {}
    # ...and the venue HALTED: further orders raise without any traffic.
    assert adapter.halted is True
    traffic_before = len(fake.requests) + len(fake.streams_opened)
    with pytest.raises(VenueHaltedError):
        adapter.place_order(
            "EURUSD", "BUY", "MARKET", 0.01,
            stop_loss=1.07520, take_profit=1.09020,
        )
    assert len(fake.requests) + len(fake.streams_opened) == traffic_before


def test_limit_order_absolute_sltp_verified_on_order():
    adapter, fake = make_adapter()
    result = adapter.place_order(
        "EURUSD", "SELL", "LIMIT", 0.01, price=1.09000,
        stop_loss=1.09500, take_profit=1.08000,
    )
    assert result.status == "PENDING"
    assert adapter.halted is False
    fields = sent_streams(fake, oa.PT_NEW_ORDER_REQ)[0]
    assert fields["stop_loss"] == pytest.approx(1.09500)
    assert fields["take_profit"] == pytest.approx(1.08000)
    assert fields.get("relative_stop_loss") is None
    assert fields.get("relative_take_profit") is None


def test_limit_order_protection_dropped_cancels_and_halts():
    adapter, fake = make_adapter()
    fake.drop_order_sltp = True
    with pytest.raises(ProtectionVerificationError):
        adapter.place_order(
            "EURUSD", "SELL", "LIMIT", 0.01, price=1.09000,
            stop_loss=1.09500, take_profit=1.08000,
        )
    assert fake.orders == {}  # the unprotected pending order was cancelled
    assert adapter.halted is True


def test_entry_without_sltp_is_refused_before_any_order():
    adapter, fake = make_adapter()
    with pytest.raises(RuntimeError):
        adapter.place_order("EURUSD", "BUY", "MARKET", 0.01)
    assert sent_streams(fake, oa.PT_NEW_ORDER_REQ) == []


def test_opposite_market_order_closes_open_position():
    adapter, fake = make_adapter()
    adapter.place_order("EURUSD", "BUY", "MARKET", 0.01,
                        stop_loss=1.07520, take_profit=1.09020)
    assert len(fake.positions) == 1
    result = adapter.place_order("EURUSD", "SELL", "MARKET", 0.01)
    assert result.status == "FILLED"
    assert fake.positions == {}


def test_volume_below_broker_minimum_raises():
    adapter, fake = make_adapter()
    with pytest.raises(ValueError):
        adapter.place_order("EURUSD", "BUY", "MARKET", 0.00005,
                            stop_loss=1.07520, take_profit=1.09020)
    assert sent_streams(fake, oa.PT_NEW_ORDER_REQ) == []


# ----------------------------------------------------------------------
# Fail-closed #3: balance reconciliation
# ----------------------------------------------------------------------
def test_balance_reconciliation_match_and_mismatch():
    adapter, fake = make_adapter()
    ok = adapter.reconcile_balance(10_000.00)
    assert ok["ok"] is True
    assert adapter.halted is False
    bad = adapter.reconcile_balance(9_000.00)
    assert bad["ok"] is False
    assert bad["broker_balance"] == pytest.approx(10_000.00)
    assert adapter.halted is True


def test_failed_balance_read_never_fabricates():
    adapter, fake = make_adapter()
    adapter.get_account_summary()  # connect once
    fake.fail_trader = True
    assert adapter.get_balance() == {}
    assert adapter.get_account_summary() == {}


# ----------------------------------------------------------------------
# Fail-closed #4: disconnect handling
# ----------------------------------------------------------------------
def test_disconnect_mid_position_reverified_on_reconnect():
    adapter, fake = make_adapter()
    adapter.place_order("EURUSD", "BUY", "MARKET", 0.01,
                        stop_loss=1.07520, take_profit=1.09020)
    fake.disconnect()
    # State is UNKNOWN while down; the next read reconnects and the
    # position's protection is re-proven from the broker before use.
    positions = adapter.get_positions_or_none()
    assert positions is not None and len(positions) == 1
    assert positions[0].stop_loss == pytest.approx(1.07520)
    assert adapter.halted is False


def test_disconnect_with_unprotected_foreign_position_halts():
    adapter, fake = make_adapter()
    adapter.place_order("EURUSD", "BUY", "MARKET", 0.01,
                        stop_loss=1.07520, take_profit=1.09020)
    # A foreign position with NO broker-side protection appears.
    fake.positions[9999] = {
        "position_id": 9999,
        "trade_data": {"symbol_id": EURUSD_ID, "volume": 100_000,
                       "trade_side": oa.SIDE_BUY},
        "position_status": 1, "price": EURUSD_ASK,
    }
    fake.disconnect()
    assert adapter.get_positions_or_none() is None  # unknown, not trusted
    assert adapter.halted is True
    # The foreign position was NOT auto-closed by the adapter.
    assert 9999 in fake.positions


def test_orders_raise_while_connection_refused():
    adapter, fake = make_adapter()
    adapter.get_account_summary()
    fake.disconnect()
    fake.refuse_connect = True
    with pytest.raises(ConnectionError):
        adapter.place_order("EURUSD", "BUY", "MARKET", 0.01,
                            stop_loss=1.07520, take_profit=1.09020)


# ----------------------------------------------------------------------
# Demo-only guards
# ----------------------------------------------------------------------
def test_live_host_is_refused(monkeypatch):
    monkeypatch.setenv("PEPPERSTONE_CTRADER_HOST", "live.ctraderapi.com")
    with pytest.raises(PermissionError):
        make_adapter()


def test_trading_mode_live_is_refused(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    with pytest.raises(PermissionError):
        make_adapter()


# ----------------------------------------------------------------------
# Market data honesty
# ----------------------------------------------------------------------
def test_trendbar_price_scaling():
    adapter, fake = make_adapter()
    candles = adapter.get_historical_data("EURUSD", "1h", 10)
    assert len(candles) == 1
    assert candles[0]["low"] == pytest.approx(1.08000)
    assert candles[0]["close"] == pytest.approx(1.08050)
    assert candles[0]["timestamp"] == 29_500_000 * 60


def test_unsupported_timeframe_raises():
    adapter, fake = make_adapter()
    with pytest.raises(ValueError):
        adapter.get_historical_data("EURUSD", "2h", 10)


def test_ticker_uses_live_spot():
    adapter, fake = make_adapter()
    ticker = adapter.get_ticker("EURUSD")
    assert ticker.bid == pytest.approx(EURUSD_BID)
    assert ticker.ask == pytest.approx(EURUSD_ASK)
