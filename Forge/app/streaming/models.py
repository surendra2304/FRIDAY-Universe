"""
Data models and message schemas for the WebSocket Streaming Gateway.
Supports Stratex high-frequency market tick streaming and Inference duplex deliberation.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class StreamChannelType(str, Enum):
    MARKET_TICKS = "market_ticks"
    AGENT_DELIBERATION = "agent_deliberation"
    SYSTEM_EVENTS = "system_events"
    PIPELINE_FEED = "pipeline_feed"


class MessageType(str, Enum):
    AUTH = "auth"
    AUTH_ACK = "auth_ack"
    PING = "ping"
    PONG = "pong"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIPTION_ACK = "subscription_ack"
    MARKET_TICK = "market_tick"
    DELIBERATION_TURN = "deliberation_turn"
    INFO = "info"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MarketTick:
    """High-frequency financial market tick data for Stratex."""

    symbol: str
    price: float
    volume: float
    bid: float | None = None
    ask: float | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DeliberationFrame:
    """Duplex deliberation turn between autonomous reasoning agents (Inference, Forge, etc.)."""

    session_id: str
    sender_agent: str
    target_agent: str
    content: str
    turn_index: int = 0
    is_final: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GatewayMessage:
    """Standardized envelope transported across WebSocket connections."""

    type: MessageType
    channel: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    sequence_number: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GatewayMessage:
        return cls(
            type=MessageType(data.get("type", MessageType.ERROR.value)),
            channel=data.get("channel", ""),
            payload=data.get("payload", {}),
            message_id=data.get("message_id", str(uuid.uuid4())),
            correlation_id=data.get("correlation_id"),
            sequence_number=data.get("sequence_number", 0),
            timestamp=data.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
        )

    @classmethod
    def from_json(cls, raw_json: str) -> GatewayMessage:
        data = json.loads(raw_json)
        return cls.from_dict(data)
