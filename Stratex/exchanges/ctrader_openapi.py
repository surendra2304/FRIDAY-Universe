"""
exchanges/ctrader_openapi.py — Spotware cTrader Open API wire layer.

Minimal, dependency-free implementation of the Open API protocol used by
the Pepperstone cTrader adapter (TASK-STR-PEP-001):

- Protobuf wire codec driven by explicit per-message field schemas
  (field numbers/types taken from Spotware's published
  openapi-proto-messages: OpenApiCommonMessages.proto,
  OpenApiModelMessages.proto, OpenApiMessages.proto — retrieved and
  cross-checked 2026-11-19).
- TLS socket transport to the Open API proxy: every frame is a
  4-byte big-endian length prefix followed by a serialized
  ProtoMessage envelope {1: payloadType, 2: payload, 3: clientMsgId}.
- Request/response correlation by clientMsgId, unsolicited events
  routed to a callback, heartbeat keepalive, and a disconnect callback
  so callers can fail closed when the session drops.

This module knows nothing about trading semantics; the adapter in
pepperstone_ctrader_adapter.py owns those. DEMO/LIVE endpoint choice is
also the adapter's responsibility — the transport connects where it is
told to.
"""
from __future__ import annotations

import queue
import socket
import ssl
import struct
import threading
import time
import uuid
from typing import Any, Callable, Optional

from logger import get_logger

logger = get_logger("ctrader_openapi")

# ---------------------------------------------------------------------------
# Common (non-OA) payload types, OpenApiCommonModelMessages.proto
# ---------------------------------------------------------------------------
PAYLOAD_ERROR_RES = 50
PAYLOAD_HEARTBEAT = 51

# ---------------------------------------------------------------------------
# OA payload types, OpenApiModelMessages.proto (ProtoOAPayloadType)
# ---------------------------------------------------------------------------
PT_APPLICATION_AUTH_REQ = 2100
PT_APPLICATION_AUTH_RES = 2101
PT_ACCOUNT_AUTH_REQ = 2102
PT_ACCOUNT_AUTH_RES = 2103
PT_NEW_ORDER_REQ = 2106
PT_CANCEL_ORDER_REQ = 2108
PT_AMEND_POSITION_SLTP_REQ = 2110
PT_CLOSE_POSITION_REQ = 2111
PT_SYMBOLS_LIST_REQ = 2114
PT_SYMBOLS_LIST_RES = 2115
PT_SYMBOL_BY_ID_REQ = 2116
PT_SYMBOL_BY_ID_RES = 2117
PT_ASSET_LIST_REQ = 2112
PT_ASSET_LIST_RES = 2113
PT_TRADER_REQ = 2121
PT_TRADER_RES = 2122
PT_RECONCILE_REQ = 2124
PT_RECONCILE_RES = 2125
PT_EXECUTION_EVENT = 2126
PT_SUBSCRIBE_SPOTS_REQ = 2127
PT_SUBSCRIBE_SPOTS_RES = 2128
PT_SPOT_EVENT = 2131
PT_ORDER_ERROR_EVENT = 2132
PT_DEAL_LIST_REQ = 2133
PT_DEAL_LIST_RES = 2134
PT_GET_TRENDBARS_REQ = 2137
PT_GET_TRENDBARS_RES = 2138
PT_OA_ERROR_RES = 2142
PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES = 2150
PT_REFRESH_TOKEN_REQ = 2173
PT_REFRESH_TOKEN_RES = 2174
PT_GET_POSITION_UNREALIZED_PNL_REQ = 2187
PT_GET_POSITION_UNREALIZED_PNL_RES = 2188

# ProtoOAExecutionType
EXEC_ORDER_ACCEPTED = 2
EXEC_ORDER_FILLED = 3
EXEC_ORDER_REPLACED = 4
EXEC_ORDER_CANCELLED = 5
EXEC_ORDER_EXPIRED = 6
EXEC_ORDER_REJECTED = 7
EXEC_ORDER_PARTIAL_FILL = 11

# ProtoOATradeSide
SIDE_BUY = 1
SIDE_SELL = 2

# ProtoOAOrderType
OT_MARKET = 1
OT_LIMIT = 2
OT_STOP = 3
OT_MARKET_RANGE = 5
OT_STOP_LIMIT = 6

# ProtoOAPositionStatus
POS_OPEN = 1
POS_CLOSED = 2

# ProtoOATrendbarPeriod
TRENDBAR_PERIODS = {
    "1m": 1, "2m": 2, "3m": 3, "4m": 4, "5m": 5, "10m": 6, "15m": 7,
    "30m": 8, "1h": 9, "4h": 10, "12h": 11, "1d": 12, "1wk": 13, "1M": 14,
}

# Open API relative price encoding: prices/distances in 1/100000 of a unit.
PRICE_SCALE = 100000


# ---------------------------------------------------------------------------
# Protobuf wire codec (schema-driven)
#
# A schema maps field name -> (field_number, kind) or
# (field_number, kind, subschema). Kinds:
#   i64 / u64 / varint / bool  -> wire type 0 (varint); i64 is signed
#   double                     -> wire type 1 (64-bit)
#   string / bytes / message   -> wire type 2 (length-delimited)
#   r_i64 / r_u64 / r_varint   -> repeated varint (packed tolerated on decode)
#   r_string / r_message       -> repeated length-delimited
# ---------------------------------------------------------------------------

def _encode_varint(value: int) -> bytes:
    value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _decode_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated varint")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")


def _to_signed(value: int) -> int:
    if value >= (1 << 63):
        return value - (1 << 64)
    return value


def encode_message(schema: dict, values: dict) -> bytes:
    out = bytearray()
    for name, spec in schema.items():
        if name not in values:
            continue
        value = values[name]
        if value is None:
            continue
        num, kind = spec[0], spec[1]
        sub = spec[2] if len(spec) > 2 else None
        if kind in ("i64", "u64", "varint", "bool"):
            out += _encode_varint((num << 3) | 0)
            out += _encode_varint(int(value))
        elif kind == "double":
            out += _encode_varint((num << 3) | 1)
            out += struct.pack("<d", float(value))
        elif kind == "string":
            data = str(value).encode("utf-8")
            out += _encode_varint((num << 3) | 2)
            out += _encode_varint(len(data))
            out += data
        elif kind == "bytes":
            data = bytes(value)
            out += _encode_varint((num << 3) | 2)
            out += _encode_varint(len(data))
            out += data
        elif kind == "message":
            data = encode_message(sub, value)
            out += _encode_varint((num << 3) | 2)
            out += _encode_varint(len(data))
            out += data
        elif kind in ("r_i64", "r_u64", "r_varint"):
            for item in value:
                out += _encode_varint((num << 3) | 0)
                out += _encode_varint(int(item))
        elif kind == "r_string":
            for item in value:
                data = str(item).encode("utf-8")
                out += _encode_varint((num << 3) | 2)
                out += _encode_varint(len(data))
                out += data
        elif kind == "r_message":
            for item in value:
                data = encode_message(sub, item)
                out += _encode_varint((num << 3) | 2)
                out += _encode_varint(len(data))
                out += data
        else:
            raise ValueError(f"unknown field kind {kind!r} for {name}")
    return bytes(out)


def decode_message(schema: dict, data: bytes) -> dict:
    by_num: dict[int, tuple[str, tuple]] = {}
    for name, spec in schema.items():
        by_num[spec[0]] = (name, spec)
    result: dict[str, Any] = {}
    pos = 0
    while pos < len(data):
        tag, pos = _decode_varint(data, pos)
        num = tag >> 3
        wire = tag & 0x07
        entry = by_num.get(num)
        kind = entry[1][1] if entry else None
        sub = entry[1][2] if entry and len(entry[1]) > 2 else None
        if wire == 0:
            raw, pos = _decode_varint(data, pos)
            if entry is None:
                continue
            if kind == "i64":
                value: Any = _to_signed(raw)
            elif kind == "bool":
                value = bool(raw)
            else:
                value = raw
            if kind and kind.startswith("r_"):
                result.setdefault(entry[0], []).append(value)
            else:
                result[entry[0]] = value
        elif wire == 1:
            if pos + 8 > len(data):
                raise ValueError("truncated 64-bit field")
            raw_bytes = data[pos:pos + 8]
            pos += 8
            if entry is None:
                continue
            result[entry[0]] = struct.unpack("<d", raw_bytes)[0]
        elif wire == 2:
            length, pos = _decode_varint(data, pos)
            if pos + length > len(data):
                raise ValueError("truncated length-delimited field")
            chunk = data[pos:pos + length]
            pos += length
            if entry is None:
                continue
            if kind == "string" or kind == "r_string":
                value = chunk.decode("utf-8", errors="replace")
            elif kind == "message" or kind == "r_message":
                value = decode_message(sub, chunk)
            elif kind in ("r_i64", "r_u64", "r_varint"):
                # Packed repeated varints.
                values = []
                p = 0
                while p < len(chunk):
                    v, p = _decode_varint(chunk, p)
                    values.append(_to_signed(v) if kind == "r_i64" else v)
                result.setdefault(entry[0], []).extend(values)
                continue
            else:  # bytes and anything else length-delimited
                value = chunk
            if kind and kind.startswith("r_"):
                result.setdefault(entry[0], []).append(value)
            else:
                result[entry[0]] = value
        elif wire == 5:
            pos += 4  # 32-bit: not used by our schemas; skip
        else:
            raise ValueError(f"unsupported wire type {wire}")
    return result


# ---------------------------------------------------------------------------
# Message schemas (field numbers per Spotware's published .proto files)
# ---------------------------------------------------------------------------

_PT = (1, "varint")  # every OA payload carries its payloadType in field 1

TRADE_DATA_SCHEMA = {
    "symbol_id": (1, "i64"),
    "volume": (2, "i64"),  # in cents: 1000 == 10.00 units
    "trade_side": (3, "varint"),
    "open_timestamp": (4, "i64"),
    "label": (5, "string"),
    "guaranteed_stop_loss": (6, "bool"),
    "comment": (7, "string"),
}

POSITION_SCHEMA = {
    "position_id": (1, "i64"),
    "trade_data": (2, "message", TRADE_DATA_SCHEMA),
    "position_status": (3, "varint"),
    "swap": (4, "i64"),
    "price": (5, "double"),
    "stop_loss": (6, "double"),
    "take_profit": (7, "double"),
    "utc_last_update_timestamp": (8, "i64"),
    "commission": (9, "i64"),
    "margin_rate": (10, "double"),
    "used_margin": (13, "u64"),
    "money_digits": (15, "varint"),
    "trailing_stop_loss": (16, "bool"),
}

ORDER_SCHEMA = {
    "order_id": (1, "i64"),
    "trade_data": (2, "message", TRADE_DATA_SCHEMA),
    "order_type": (3, "varint"),
    "order_status": (4, "varint"),
    "execution_price": (7, "double"),
    "executed_volume": (8, "i64"),
    "limit_price": (13, "double"),
    "stop_price": (14, "double"),
    "stop_loss": (15, "double"),
    "take_profit": (16, "double"),
    "client_order_id": (17, "string"),
    "position_id": (19, "i64"),
    "relative_stop_loss": (20, "i64"),
    "relative_take_profit": (21, "i64"),
}

CLOSE_POSITION_DETAIL_SCHEMA = {
    "entry_price": (1, "double"),
    "gross_profit": (2, "i64"),
    "swap": (3, "i64"),
    "commission": (4, "i64"),
    "balance": (5, "i64"),
    "closed_volume": (7, "i64"),
    "money_digits": (9, "varint"),
    "pnl_conversion_fee": (10, "i64"),
}

DEAL_SCHEMA = {
    "deal_id": (1, "i64"),
    "order_id": (2, "i64"),
    "position_id": (3, "i64"),
    "volume": (4, "i64"),
    "filled_volume": (5, "i64"),
    "symbol_id": (6, "i64"),
    "create_timestamp": (7, "i64"),
    "execution_timestamp": (8, "i64"),
    "execution_price": (10, "double"),
    "trade_side": (11, "varint"),
    "deal_status": (12, "varint"),
    "commission": (14, "i64"),
    "close_position_detail": (16, "message", CLOSE_POSITION_DETAIL_SCHEMA),
    "money_digits": (17, "varint"),
}

TRADER_SCHEMA = {
    "ctid_trader_account_id": (1, "i64"),
    "balance": (2, "i64"),  # scaled by 10^money_digits
    "balance_version": (3, "i64"),
    "deposit_asset_id": (8, "i64"),
    "leverage_in_cents": (10, "varint"),
    "trader_login": (14, "i64"),
    "account_type": (15, "varint"),  # 1=HEDGED, 2=NETTED, 3=SPREAD_BETTING
    "broker_name": (16, "string"),
    "is_limited_risk": (18, "bool"),
    "money_digits": (20, "varint"),
}

LIGHT_SYMBOL_SCHEMA = {
    "symbol_id": (1, "i64"),
    "symbol_name": (2, "string"),
    "enabled": (3, "bool"),
    "base_asset_id": (4, "i64"),
    "quote_asset_id": (5, "i64"),
}

SYMBOL_SCHEMA = {
    "symbol_id": (1, "i64"),
    "digits": (2, "varint"),
    "pip_position": (3, "varint"),
    "enable_short_selling": (4, "bool"),
    "max_volume": (9, "i64"),  # cents
    "min_volume": (10, "i64"),  # cents
    "step_volume": (11, "i64"),  # cents
    "sl_distance": (16, "varint"),
    "tp_distance": (17, "varint"),
    "lot_size": (30, "i64"),  # cents per 1.0 lot
}

ASSET_SCHEMA = {
    "asset_id": (1, "i64"),
    "name": (2, "string"),
    "display_name": (3, "string"),
    "digits": (4, "varint"),
}

CTID_ACCOUNT_SCHEMA = {
    "ctid_trader_account_id": (1, "u64"),
    "is_live": (2, "bool"),
    "trader_login": (3, "i64"),
    "broker_title_short": (6, "string"),
}

TRENDBAR_SCHEMA = {
    "volume": (3, "i64"),
    "period": (4, "varint"),
    "low": (5, "i64"),  # relative encoding: price * 100000
    "delta_open": (6, "u64"),
    "delta_close": (7, "u64"),
    "delta_high": (8, "u64"),
    "utc_timestamp_in_minutes": (9, "varint"),
}

POSITION_PNL_SCHEMA = {
    "position_id": (1, "i64"),
    "gross_unrealized_pnl": (2, "i64"),
    "net_unrealized_pnl": (3, "i64"),
}

SCHEMAS: dict[int, dict] = {
    PT_APPLICATION_AUTH_REQ: {
        "payload_type": _PT, "client_id": (2, "string"), "client_secret": (3, "string"),
    },
    PT_APPLICATION_AUTH_RES: {"payload_type": _PT},
    PT_ACCOUNT_AUTH_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"), "access_token": (3, "string"),
    },
    PT_ACCOUNT_AUTH_RES: {"payload_type": _PT, "ctid_trader_account_id": (2, "i64")},
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ: {
        "payload_type": _PT, "access_token": (2, "string"),
    },
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES: {
        "payload_type": _PT, "access_token": (2, "string"),
        "permission_scope": (3, "varint"),
        "ctid_trader_account": (4, "r_message", CTID_ACCOUNT_SCHEMA),
    },
    PT_REFRESH_TOKEN_REQ: {"payload_type": _PT, "refresh_token": (2, "string")},
    PT_REFRESH_TOKEN_RES: {
        "payload_type": _PT, "access_token": (2, "string"), "token_type": (3, "string"),
        "expires_in": (4, "i64"), "refresh_token": (5, "string"),
    },
    PT_TRADER_REQ: {"payload_type": _PT, "ctid_trader_account_id": (2, "i64")},
    PT_TRADER_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "trader": (3, "message", TRADER_SCHEMA),
    },
    PT_RECONCILE_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "return_protection_orders": (3, "bool"),
    },
    PT_RECONCILE_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "position": (3, "r_message", POSITION_SCHEMA),
        "order": (4, "r_message", ORDER_SCHEMA),
    },
    PT_SYMBOLS_LIST_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "include_archived_symbols": (3, "bool"),
    },
    PT_SYMBOLS_LIST_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "symbol": (3, "r_message", LIGHT_SYMBOL_SCHEMA),
    },
    PT_SYMBOL_BY_ID_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "symbol_id": (3, "r_i64"),
    },
    PT_SYMBOL_BY_ID_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "symbol": (3, "r_message", SYMBOL_SCHEMA),
    },
    PT_ASSET_LIST_REQ: {"payload_type": _PT, "ctid_trader_account_id": (2, "i64")},
    PT_ASSET_LIST_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "asset": (3, "r_message", ASSET_SCHEMA),
    },
    PT_NEW_ORDER_REQ: {
        "payload_type": _PT,
        "ctid_trader_account_id": (2, "i64"),
        "symbol_id": (3, "i64"),
        "order_type": (4, "varint"),
        "trade_side": (5, "varint"),
        "volume": (6, "i64"),  # cents
        "limit_price": (7, "double"),
        "stop_price": (8, "double"),
        "time_in_force": (9, "varint"),
        "stop_loss": (11, "double"),  # absolute; NOT supported for MARKET orders
        "take_profit": (12, "double"),  # absolute; NOT supported for MARKET orders
        "comment": (13, "string"),
        "label": (16, "string"),
        "position_id": (17, "i64"),
        "client_order_id": (18, "string"),
        "relative_stop_loss": (19, "i64"),  # 1/100000 of price; for MARKET orders
        "relative_take_profit": (20, "i64"),
        "guaranteed_stop_loss": (21, "bool"),
        "trailing_stop_loss": (22, "bool"),
    },
    PT_EXECUTION_EVENT: {
        "payload_type": _PT,
        "ctid_trader_account_id": (2, "i64"),
        "execution_type": (3, "varint"),
        "position": (4, "message", POSITION_SCHEMA),
        "order": (5, "message", ORDER_SCHEMA),
        "deal": (6, "message", DEAL_SCHEMA),
        "error_code": (9, "string"),
        "is_server_event": (10, "bool"),
    },
    PT_CANCEL_ORDER_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"), "order_id": (3, "i64"),
    },
    PT_AMEND_POSITION_SLTP_REQ: {
        "payload_type": _PT,
        "ctid_trader_account_id": (2, "i64"),
        "position_id": (3, "i64"),
        "stop_loss": (4, "double"),
        "take_profit": (5, "double"),
        "guaranteed_stop_loss": (7, "bool"),
        "trailing_stop_loss": (8, "bool"),
    },
    PT_CLOSE_POSITION_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "position_id": (3, "i64"), "volume": (4, "i64"),
    },
    PT_SUBSCRIBE_SPOTS_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "symbol_id": (3, "r_i64"), "subscribe_to_spot_timestamp": (4, "bool"),
    },
    PT_SUBSCRIBE_SPOTS_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "subscribed_symbol_id": (3, "r_i64"),
    },
    PT_SPOT_EVENT: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "symbol_id": (3, "i64"),
        "bid": (4, "u64"),  # 1/100000 of price
        "ask": (5, "u64"),
        "timestamp": (8, "i64"),
    },
    PT_ORDER_ERROR_EVENT: {
        "payload_type": _PT,
        "error_code": (2, "string"),
        "order_id": (3, "i64"),
        "ctid_trader_account_id": (5, "i64"),  # field 5 per proto (sic)
        "position_id": (6, "i64"),
        "description": (7, "string"),
    },
    PT_DEAL_LIST_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "from_timestamp": (3, "i64"), "to_timestamp": (4, "i64"), "max_rows": (5, "varint"),
    },
    PT_DEAL_LIST_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "deal": (3, "r_message", DEAL_SCHEMA), "has_more": (4, "bool"),
    },
    PT_GET_TRENDBARS_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "from_timestamp": (3, "i64"), "to_timestamp": (4, "i64"),
        "period": (5, "varint"), "symbol_id": (6, "i64"), "count": (7, "varint"),
    },
    PT_GET_TRENDBARS_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "period": (3, "varint"), "trendbar": (5, "r_message", TRENDBAR_SCHEMA),
        "symbol_id": (6, "i64"),
    },
    PT_GET_POSITION_UNREALIZED_PNL_REQ: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
    },
    PT_GET_POSITION_UNREALIZED_PNL_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "position_unrealized_pnl": (3, "r_message", POSITION_PNL_SCHEMA),
        "money_digits": (4, "varint"),
    },
    PT_OA_ERROR_RES: {
        "payload_type": _PT, "ctid_trader_account_id": (2, "i64"),
        "error_code": (3, "string"), "description": (4, "string"),
    },
}

ENVELOPE_SCHEMA = {
    "payload_type": (1, "varint"),
    "payload": (2, "bytes"),
    "client_msg_id": (3, "string"),
}

COMMON_ERROR_SCHEMA = {
    "payload_type": (1, "varint"),
    "error_code": (2, "string"),
    "description": (3, "string"),
}


class TransportError(RuntimeError):
    """Base class for Open API transport failures."""


class TransportTimeout(TransportError):
    """A request received no correlated response inside its timeout."""


class TransportDisconnected(TransportError):
    """The session is down (or dropped mid-request); state is unknown."""


class OpenApiErrorRes(TransportError):
    """The proxy answered with an error payload (OA or common error)."""

    def __init__(self, error_code: str, description: str = "", payload_type: int = 0):
        super().__init__(f"Open API error {error_code}: {description}".strip())
        self.error_code = error_code
        self.description = description
        self.payload_type = payload_type


class _PendingStream:
    """Queue of correlated responses for one clientMsgId."""

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.error: Optional[BaseException] = None


class OpenApiTransport:
    """Length-prefixed ProtoMessage transport over TLS.

    One in-flight stream per clientMsgId; unsolicited messages (spot
    events, server execution events, disconnect events) go to the
    on_event callback as (payload_type, payload_bytes). The reader
    thread owns the socket; on EOF/error every pending waiter fails
    with TransportDisconnected and on_disconnect fires exactly once
    per connection.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        connect_timeout: float = 10.0,
        on_event: Optional[Callable[[int, bytes], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
    ):
        self.host = host
        self.port = int(port)
        self.connect_timeout = connect_timeout
        self._on_event = on_event
        self._on_disconnect = on_disconnect
        self._sock: Optional[ssl.SSLSocket] = None
        self._send_lock = threading.Lock()
        self._pending: dict[str, _PendingStream] = {}
        self._pending_lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._connected = False

    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        return self._connected and self._sock is not None

    def connect(self) -> None:
        if self.is_connected:
            return
        self.close()
        self._stop.clear()
        raw = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        context = ssl.create_default_context()
        self._sock = context.wrap_socket(raw, server_hostname=self.host)
        self._sock.settimeout(None)
        self._connected = True
        self._reader = threading.Thread(
            target=self._reader_loop, name="ctrader-openapi-reader", daemon=True
        )
        self._reader.start()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="ctrader-openapi-heartbeat", daemon=True
        )
        self._heartbeat_thread.start()
        logger.info(f"[CTRADER_OA] Connected to {self.host}:{self.port}")

    def close(self) -> None:
        self._stop.set()
        sock, self._sock = self._sock, None
        was_connected = self._connected
        self._connected = False
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
        if was_connected:
            self._fail_all_pending(TransportDisconnected("transport closed"))

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _send_envelope(self, payload_type: int, payload: bytes, client_msg_id: str = "") -> None:
        if not self.is_connected:
            raise TransportDisconnected("not connected")
        envelope = {"payload_type": payload_type, "payload": payload}
        if client_msg_id:
            envelope["client_msg_id"] = client_msg_id
        frame = encode_message(ENVELOPE_SCHEMA, envelope)
        with self._send_lock:
            try:
                self._sock.sendall(struct.pack(">I", len(frame)) + frame)  # type: ignore[union-attr]
            except Exception as e:
                self._handle_drop(f"send failed: {e}")
                raise TransportDisconnected(f"send failed: {e}") from e

    def open_stream(self, payload_type: int, fields: dict) -> tuple[str, _PendingStream]:
        """Send a request and return (client_msg_id, stream) for its responses.

        Most requests produce exactly one correlated message; order
        requests produce a stream of ProtoOAExecutionEvent messages
        sharing the request's clientMsgId.
        """
        schema = SCHEMAS[payload_type]
        body = dict(fields)
        body["payload_type"] = payload_type
        payload = encode_message(schema, body)
        msg_id = uuid.uuid4().hex
        stream = _PendingStream()
        with self._pending_lock:
            self._pending[msg_id] = stream
        try:
            self._send_envelope(payload_type, payload, msg_id)
        except Exception:
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise
        return msg_id, stream

    def close_stream(self, msg_id: str) -> None:
        with self._pending_lock:
            self._pending.pop(msg_id, None)

    def next_in_stream(
        self, stream: _PendingStream, timeout: float
    ) -> tuple[int, dict]:
        """Next correlated message, decoded; raises on error payloads."""
        try:
            item = stream.queue.get(timeout=timeout)
        except queue.Empty:
            if stream.error is not None:
                raise stream.error
            raise TransportTimeout(f"no response within {timeout:.1f}s") from None
        if isinstance(item, BaseException):
            raise item
        payload_type, payload = item
        return payload_type, self._decode_response(payload_type, payload)

    def request(self, payload_type: int, fields: dict, *, timeout: float = 15.0) -> dict:
        """Single request -> single decoded response (the common case)."""
        msg_id, stream = self.open_stream(payload_type, fields)
        try:
            _pt, decoded = self.next_in_stream(stream, timeout)
            return decoded
        finally:
            self.close_stream(msg_id)

    @staticmethod
    def _decode_response(payload_type: int, payload: bytes) -> dict:
        if payload_type == PT_OA_ERROR_RES:
            err = decode_message(SCHEMAS[PT_OA_ERROR_RES], payload)
            raise OpenApiErrorRes(
                str(err.get("error_code", "UNKNOWN")), str(err.get("description", "")),
                payload_type,
            )
        if payload_type == PAYLOAD_ERROR_RES:
            err = decode_message(COMMON_ERROR_SCHEMA, payload)
            raise OpenApiErrorRes(
                str(err.get("error_code", "UNKNOWN")), str(err.get("description", "")),
                payload_type,
            )
        schema = SCHEMAS.get(payload_type)
        if schema is None:
            raise TransportError(f"no schema for payload type {payload_type}")
        return decode_message(schema, payload)

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------
    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(10.0):
            if not self.is_connected:
                return
            try:
                payload = encode_message({"payload_type": (1, "varint")}, {"payload_type": PAYLOAD_HEARTBEAT})
                self._send_envelope(PAYLOAD_HEARTBEAT, payload)
            except Exception:
                return

    def _reader_loop(self) -> None:
        buf = bytearray()
        try:
            while not self._stop.is_set():
                chunk = self._sock.recv(65536)  # type: ignore[union-attr]
                if not chunk:
                    raise TransportDisconnected("broker closed the connection (EOF)")
                buf += chunk
                while len(buf) >= 4:
                    (length,) = struct.unpack(">I", bytes(buf[:4]))
                    if len(buf) < 4 + length:
                        break
                    frame = bytes(buf[4:4 + length])
                    del buf[:4 + length]
                    self._dispatch(frame)
        except Exception as e:
            if not self._stop.is_set():
                self._handle_drop(str(e))

    def _dispatch(self, frame: bytes) -> None:
        try:
            envelope = decode_message(ENVELOPE_SCHEMA, frame)
        except Exception as e:
            logger.warning(f"[CTRADER_OA] Undecodable frame dropped: {e}")
            return
        payload_type = int(envelope.get("payload_type", 0))
        payload = envelope.get("payload", b"") or b""
        msg_id = envelope.get("client_msg_id") or ""
        if payload_type == PAYLOAD_HEARTBEAT:
            return
        if msg_id:
            with self._pending_lock:
                stream = self._pending.get(msg_id)
            if stream is not None:
                stream.queue.put((payload_type, payload))
                return
        if self._on_event is not None:
            try:
                self._on_event(payload_type, payload)
            except Exception as e:
                logger.warning(f"[CTRADER_OA] Event handler failed: {e}")

    # ------------------------------------------------------------------
    def _fail_all_pending(self, error: BaseException) -> None:
        with self._pending_lock:
            streams = list(self._pending.values())
            self._pending.clear()
        for stream in streams:
            stream.error = error
            stream.queue.put(error)

    def _handle_drop(self, reason: str) -> None:
        if not self._connected:
            return
        self._connected = False
        logger.error(f"[CTRADER_OA] Connection dropped: {reason}")
        self._fail_all_pending(TransportDisconnected(reason))
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        if self._on_disconnect is not None:
            try:
                self._on_disconnect(reason)
            except Exception:
                pass
