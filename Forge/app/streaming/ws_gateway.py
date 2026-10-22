"""
WebSocket Bi-Directional Streaming Gateway.
Provides low-latency market tick streaming for Stratex and duplex deliberation for Inference.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from app.core.config import get_settings
from app.streaming.models import (
    DeliberationFrame,
    GatewayMessage,
    MarketTick,
    MessageType,
    StreamChannelType,
)

logger = logging.getLogger("forge.streaming.gateway")


@dataclass
class ClientSession:
    """Represents an active client WebSocket connection in the gateway."""

    connection_id: str
    websocket: WebSocket
    client_id: str
    authenticated: bool = False
    role: str = "guest"
    subscribed_channels: set[str] = field(default_factory=set)
    outbound_queue: asyncio.Queue[GatewayMessage | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=1000)
    )
    worker_task: asyncio.Task[None] | None = None
    connected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_heartbeat: float = field(default_factory=time.time)
    dropped_messages: int = 0


class WebSocketStreamingGateway:
    """
    Central real-time streaming gateway managing client lifecycles,
    channel subscriptions, market tick broadcasts, and duplex agent deliberation.
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        heartbeat_timeout_seconds: float = 60.0,
    ) -> None:
        self.max_queue_size = max_queue_size
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.clients: dict[str, ClientSession] = {}
        self.channel_subscribers: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._deliberation_sequences: dict[str, int] = defaultdict(int)

        # Telemetry metrics
        self.total_messages_received = 0
        self.total_messages_sent = 0
        self.total_ticks_published = 0
        self.total_deliberations_routed = 0
        self.total_dropped_messages = 0

    def is_valid_token(self, token: str | None) -> tuple[bool, str]:
        """
        Validates token against FRIDAY Universe mesh API keys.
        Returns (is_valid, role).
        """
        if not token:
            return False, "anonymous"

        import os
        settings = get_settings()
        friday_key = str(os.getenv("FRIDAY_API_KEY") or getattr(settings, "friday_api_key", "") or "")
        mesh_keys: dict[str, str] = {
            friday_key: "friday_core",
            str(getattr(settings, "ai_universe_api_key", "") or ""): "inference",
            str(getattr(settings, "memora_api_key", "") or ""): "memora",
            str(getattr(settings, "sentinel_api_key", "") or ""): "sentinel",
            str(getattr(settings, "cortex_api_key", "") or ""): "cortex",
            str(getattr(settings, "intelx_api_key", "") or ""): "intelx",
            str(getattr(settings, "futuris_api_key", "") or ""): "futuris",
        }

        # Check for configured mesh keys
        for key, role in mesh_keys.items():
            if key and token == key:
                return True, role

        # Check for Stratex or VyralX keys in environment
        import os
        stratex_key = os.getenv("STRATEX_API_KEY")
        if stratex_key and token == stratex_key:
            return True, "stratex"

        vyralx_key = os.getenv("VYRALX_API_KEY")
        if vyralx_key and token == vyralx_key:
            return True, "vyralx"

        # Check forge secret or master token
        forge_key = os.getenv("FORGE_SECRET_KEY") or os.getenv("FORGE_API_KEY")
        if forge_key and token == forge_key:
            return True, "forge_admin"

        # Allow dev/local tokens in non-production
        if settings.env != "production" and token.startswith("dev-token"):
            return True, "dev_client"

        return False, "guest"

    async def register_connection(
        self,
        websocket: WebSocket,
        client_id: str,
        token: str | None = None,
    ) -> ClientSession | None:
        """
        Authenticates and registers a new WebSocket connection.
        Returns ClientSession on success, None on rejection.
        """
        valid, role = self.is_valid_token(token)
        if not valid:
            logger.warning(
                "Rejecting unauthenticated WebSocket connection from %s",
                client_id,
            )
            await websocket.close(code=1008, reason="Authentication failed")
            return None

        await websocket.accept()
        conn_id = f"conn_{uuid.uuid4().hex[:12]}"
        session = ClientSession(
            connection_id=conn_id,
            websocket=websocket,
            client_id=client_id,
            authenticated=True,
            role=role,
            outbound_queue=asyncio.Queue(maxsize=self.max_queue_size),
        )

        async with self._lock:
            self.clients[conn_id] = session

        # Start outbound queue worker for client
        session.worker_task = asyncio.create_task(
            self._outbound_worker(session)
        )

        # Send ACK frame
        ack = GatewayMessage(
            type=MessageType.AUTH_ACK,
            payload={
                "connection_id": conn_id,
                "role": role,
                "message": f"Connected to Forge Streaming Gateway as {role}",
            },
        )
        await self.send_to_client(conn_id, ack)

        logger.info(
            "WebSocket client registered: %s (role: %s, conn_id: %s)",
            client_id,
            role,
            conn_id,
        )
        return session

    async def disconnect(self, connection_id: str) -> None:
        """Closes and unregisters a client connection."""
        async with self._lock:
            session = self.clients.pop(connection_id, None)
            if not session:
                return

            # Remove from all subscribed channels
            for ch in session.subscribed_channels:
                self.channel_subscribers[ch].discard(connection_id)

        # Cancel worker task
        if session.worker_task and not session.worker_task.done():
            session.worker_task.cancel()

        try:
            await session.websocket.close()
        except Exception:
            pass

        logger.info("Client disconnected: %s (%s)", session.client_id, connection_id)

    async def _outbound_worker(self, session: ClientSession) -> None:
        """Continuously drains the client's outbound queue and transmits over WebSocket."""
        try:
            while True:
                msg = await session.outbound_queue.get()
                if msg is None:
                    break

                try:
                    await session.websocket.send_text(msg.to_json())
                    self.total_messages_sent += 1
                except Exception as exc:
                    logger.warning(
                        "Error sending message to %s (%s): %s",
                        session.client_id,
                        session.connection_id,
                        exc,
                    )
                    break
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up on worker termination
            await self.disconnect(session.connection_id)

    async def send_to_client(
        self, connection_id: str, message: GatewayMessage
    ) -> bool:
        """
        Enqueues a message for a specific client with backpressure handling.
        Returns True if enqueued, False if dropped due to queue overflow.
        """
        session = self.clients.get(connection_id)
        if not session:
            return False

        try:
            session.outbound_queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            session.dropped_messages += 1
            self.total_dropped_messages += 1
            logger.warning(
                "Backpressure triggered: Outbound queue full for %s. Dropping message %s.",
                connection_id,
                message.message_id,
            )
            return False

    async def subscribe(self, connection_id: str, channel: str) -> bool:
        """Subscribes a client to a channel topic."""
        async with self._lock:
            session = self.clients.get(connection_id)
            if not session:
                return False

            session.subscribed_channels.add(channel)
            self.channel_subscribers[channel].add(connection_id)

        ack = GatewayMessage(
            type=MessageType.SUBSCRIPTION_ACK,
            channel=channel,
            payload={"status": "subscribed", "channel": channel},
        )
        await self.send_to_client(connection_id, ack)
        return True

    async def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribes a client from a channel topic."""
        async with self._lock:
            session = self.clients.get(connection_id)
            if not session:
                return False

            session.subscribed_channels.discard(channel)
            self.channel_subscribers[channel].discard(connection_id)
        return True

    async def broadcast_to_channel(
        self, channel: str, message: GatewayMessage
    ) -> int:
        """
        Broadcasts a message to all active subscribers of a channel.
        Returns the number of clients message was enqueued to.
        """
        async with self._lock:
            subscriber_ids = list(self.channel_subscribers.get(channel, []))

        count = 0
        for conn_id in subscriber_ids:
            if await self.send_to_client(conn_id, message):
                count += 1
        return count

    # -----------------------------------------------------------------------
    # Stratex Low-Latency Market Tick Streaming
    # -----------------------------------------------------------------------

    async def publish_market_tick(self, tick: MarketTick) -> int:
        """
        Broadcasts high-frequency financial tick data to Stratex and market subscribers.
        Delivers to both generic 'market_ticks' and symbol-specific 'market_ticks:<SYMBOL>' channels.
        """
        self.total_ticks_published += 1
        msg = GatewayMessage(
            type=MessageType.MARKET_TICK,
            channel=StreamChannelType.MARKET_TICKS.value,
            payload=tick.to_dict(),
        )

        # Broadcast to generic and symbol channels concurrently
        delivered_general = await self.broadcast_to_channel(
            StreamChannelType.MARKET_TICKS.value, msg
        )
        delivered_symbol = await self.broadcast_to_channel(
            f"{StreamChannelType.MARKET_TICKS.value}:{tick.symbol.upper()}", msg
        )
        return delivered_general + delivered_symbol

    # -----------------------------------------------------------------------
    # Inference Duplex Agent Deliberation
    # -----------------------------------------------------------------------

    async def route_deliberation(self, frame: DeliberationFrame) -> int:
        """
        Routes bi-directional multi-agent reasoning turns between Inference and Forge.
        Guarantees turn sequencing and delivers to session channel 'deliberation:<session_id>'.
        """
        self.total_deliberations_routed += 1
        session_id = frame.session_id

        async with self._lock:
            self._deliberation_sequences[session_id] += 1
            seq = self._deliberation_sequences[session_id]

        msg = GatewayMessage(
            type=MessageType.DELIBERATION_TURN,
            channel=f"{StreamChannelType.AGENT_DELIBERATION.value}:{session_id}",
            payload=frame.to_dict(),
            correlation_id=session_id,
            sequence_number=seq,
        )

        delivered_full = await self.broadcast_to_channel(
            f"{StreamChannelType.AGENT_DELIBERATION.value}:{session_id}", msg
        )
        delivered_short = await self.broadcast_to_channel(
            f"deliberation:{session_id}", msg
        )
        delivered_general = await self.broadcast_to_channel(
            StreamChannelType.AGENT_DELIBERATION.value, msg
        )
        return delivered_full + delivered_short + delivered_general

    # -----------------------------------------------------------------------
    # Incoming Message Dispatch & Heartbeat Handling
    # -----------------------------------------------------------------------

    async def handle_incoming_frame(
        self, connection_id: str, raw_text: str
    ) -> None:
        """Parses and handles incoming WebSocket messages from clients."""
        self.total_messages_received += 1
        session = self.clients.get(connection_id)
        if not session:
            return

        session.last_heartbeat = time.time()

        try:
            msg = GatewayMessage.from_json(raw_text)
        except Exception as exc:
            err = GatewayMessage(
                type=MessageType.ERROR,
                payload={"error": f"Invalid JSON frame: {exc}"},
            )
            await self.send_to_client(connection_id, err)
            return

        if msg.type == MessageType.PING:
            pong = GatewayMessage(
                type=MessageType.PONG,
                payload={"reply": "pong", "client_id": session.client_id},
            )
            await self.send_to_client(connection_id, pong)

        elif msg.type == MessageType.SUBSCRIBE:
            ch = msg.channel or msg.payload.get("channel", "")
            if ch:
                await self.subscribe(connection_id, ch)

        elif msg.type == MessageType.UNSUBSCRIBE:
            ch = msg.channel or msg.payload.get("channel", "")
            if ch:
                await self.unsubscribe(connection_id, ch)

        elif msg.type == MessageType.MARKET_TICK:
            # Client publishing a tick (e.g. Stratex market feed)
            data = msg.payload
            tick = MarketTick(
                symbol=data.get("symbol", "UNKNOWN"),
                price=float(data.get("price", 0.0)),
                volume=float(data.get("volume", 0.0)),
                bid=data.get("bid"),
                ask=data.get("ask"),
            )
            await self.publish_market_tick(tick)

        elif msg.type == MessageType.DELIBERATION_TURN:
            # Client submitting deliberation turn
            data = msg.payload
            frame = DeliberationFrame(
                session_id=data.get("session_id", str(uuid.uuid4())),
                sender_agent=data.get("sender_agent", session.client_id),
                target_agent=data.get("target_agent", "inference"),
                content=data.get("content", ""),
                turn_index=data.get("turn_index", 0),
                is_final=data.get("is_final", False),
            )
            await self.route_deliberation(frame)

    def get_metrics(self) -> dict[str, Any]:
        """Telemetry diagnostics of gateway traffic, active connections, and dropped frames."""
        active_channels = {
            ch: len(subs)
            for ch, subs in self.channel_subscribers.items()
            if subs
        }
        return {
            "active_connections": len(self.clients),
            "active_channels": len(active_channels),
            "channel_subscribers": active_channels,
            "total_messages_received": self.total_messages_received,
            "total_messages_sent": self.total_messages_sent,
            "total_ticks_published": self.total_ticks_published,
            "total_deliberations_routed": self.total_deliberations_routed,
            "total_dropped_messages": self.total_dropped_messages,
        }


# Global Singleton Gateway
_STREAMING_GATEWAY: WebSocketStreamingGateway | None = None


def get_streaming_gateway() -> WebSocketStreamingGateway:
    """Returns the shared WebSocket Streaming Gateway instance."""
    global _STREAMING_GATEWAY
    if _STREAMING_GATEWAY is None:
        _STREAMING_GATEWAY = WebSocketStreamingGateway()
    return _STREAMING_GATEWAY
