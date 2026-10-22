"""
FastAPI Routes for the WebSocket Streaming Gateway.
Includes /ws/gateway WebSocket connection handler and telemetry endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.streaming.models import DeliberationFrame, MarketTick
from app.streaming.ws_gateway import get_streaming_gateway

logger = logging.getLogger("forge.streaming.routes")

streaming_router = APIRouter(tags=["WebSocket Streaming Gateway"])


class MarketTickPublishRequest(BaseModel):
    symbol: str = Field(..., description="Financial ticker symbol, e.g. BTC/USD")
    price: float = Field(..., description="Current trade price")
    volume: float = Field(..., description="Volume in transaction")
    bid: float | None = None
    ask: float | None = None


class DeliberationPublishRequest(BaseModel):
    session_id: str = Field(..., description="Unique deliberation dialogue session")
    sender_agent: str = Field(..., description="Agent originating the turn")
    target_agent: str = Field(default="inference", description="Target recipient agent")
    content: str = Field(..., description="Deliberation reasoning or code argument")
    turn_index: int = Field(default=0, ge=0)
    is_final: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


@streaming_router.websocket("/ws/gateway")
async def websocket_gateway_endpoint(
    websocket: WebSocket,
    client_id: str = Query(default="anonymous"),
    token: str | None = Query(default=None),
) -> None:
    """
    Bi-Directional WebSocket Streaming Gateway endpoint.
    Handles handshake authentication, ping/pong heartbeats, Stratex ticks,
    and duplex agent deliberation.
    """
    gateway = get_streaming_gateway()
    session = await gateway.register_connection(
        websocket=websocket,
        client_id=client_id,
        token=token,
    )

    if session is None:
        return

    try:
        while True:
            raw_text = await websocket.receive_text()
            await gateway.handle_incoming_frame(session.connection_id, raw_text)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for client %s", client_id)
    except Exception as exc:
        logger.warning("WebSocket error for client %s: %s", client_id, exc)
    finally:
        await gateway.disconnect(session.connection_id)


@streaming_router.get(
    "/api/streaming/metrics",
    summary="Get WebSocket Gateway Telemetry & Traffic Metrics",
)
async def get_gateway_metrics() -> dict[str, Any]:
    gateway = get_streaming_gateway()
    return gateway.get_metrics()


@streaming_router.post(
    "/api/streaming/ticks",
    summary="Publish Market Tick via REST to all WebSocket Subscribers",
)
async def publish_market_tick_api(req: MarketTickPublishRequest) -> dict[str, Any]:
    gateway = get_streaming_gateway()
    tick = MarketTick(
        symbol=req.symbol,
        price=req.price,
        volume=req.volume,
        bid=req.bid,
        ask=req.ask,
    )
    delivered = await gateway.publish_market_tick(tick)
    return {
        "status": "published",
        "symbol": tick.symbol,
        "delivered_subscribers": delivered,
        "timestamp": tick.timestamp,
    }


@streaming_router.post(
    "/api/streaming/deliberation",
    summary="Route Agent Deliberation Frame via REST to WebSocket Subscribers",
)
async def publish_deliberation_api(req: DeliberationPublishRequest) -> dict[str, Any]:
    gateway = get_streaming_gateway()
    frame = DeliberationFrame(
        session_id=req.session_id,
        sender_agent=req.sender_agent,
        target_agent=req.target_agent,
        content=req.content,
        turn_index=req.turn_index,
        is_final=req.is_final,
        metadata=req.metadata,
    )
    delivered = await gateway.route_deliberation(frame)
    return {
        "status": "routed",
        "session_id": frame.session_id,
        "turn_index": frame.turn_index,
        "delivered_subscribers": delivered,
    }
