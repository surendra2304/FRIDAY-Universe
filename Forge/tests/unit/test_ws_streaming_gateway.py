"""
Unit and integration tests for the WebSocket Bi-Directional Streaming Gateway.
Validates:
- Handshake authentication and mesh token validation
- Rejection of unauthenticated clients with code 1008
- Ping/pong heartbeats
- Channel subscription & unsubscription
- Stratex low-latency market tick streaming (general & symbol-specific channels)
- Inference duplex agent deliberation routing & turn sequencing
- Slow-consumer backpressure mitigation & queue dropping
- Telemetry metrics reporting
- REST endpoints for ticks, deliberation, and metrics
"""

from __future__ import annotations

import asyncio
import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.main import app
from app.streaming.models import (
    GatewayMessage,
    MessageType,
)
from app.streaming.ws_gateway import (
    ClientSession,
    WebSocketStreamingGateway,
)

_TEST_INFERENCE_KEY = "test_inference_mesh_key_abc123"
_TEST_STRATEX_KEY = "test_stratex_mesh_key_xyz789"
_TEST_DEV_TOKEN = "dev-token-test-node"


@pytest.fixture(autouse=True)
def setup_mesh_keys(monkeypatch):
    """Configures mesh keys and non-production environment for streaming tests."""
    settings = get_settings()
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "ai_universe_api_key", _TEST_INFERENCE_KEY)
    monkeypatch.setenv("STRATEX_API_KEY", _TEST_STRATEX_KEY)


def test_auth_rejection_invalid_token():
    """Clients with invalid or missing tokens are rejected with WebSocket code 1008."""
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/gateway?client_id=bad_actor&token=invalid_secret"):
            pass
    assert exc_info.value.code == 1008


def test_auth_acceptance_dev_token():
    """Clients connecting with dev tokens in non-production are authenticated as dev_client."""
    client = TestClient(app)

    with client.websocket_connect(f"/ws/gateway?client_id=agent_dev&token={_TEST_DEV_TOKEN}") as ws:
        ack_raw = ws.receive_text()
        ack = json.loads(ack_raw)
        assert ack["type"] == MessageType.AUTH_ACK.value
        assert ack["payload"]["role"] == "dev_client"
        assert "Connected to Forge Streaming Gateway" in ack["payload"]["message"]


def test_auth_acceptance_mesh_roles():
    """Inference and Stratex mesh keys are identified with appropriate agent roles."""
    client = TestClient(app)

    # Test Inference mesh auth
    with client.websocket_connect(f"/ws/gateway?client_id=inference_agent&token={_TEST_INFERENCE_KEY}") as ws:
        ack = json.loads(ws.receive_text())
        assert ack["payload"]["role"] == "inference"

    # Test Stratex mesh auth
    with client.websocket_connect(f"/ws/gateway?client_id=stratex_feed&token={_TEST_STRATEX_KEY}") as ws:
        ack = json.loads(ws.receive_text())
        assert ack["payload"]["role"] == "stratex"


def test_ping_pong_heartbeat():
    """Sending a PING frame returns a PONG frame with client telemetry."""
    client = TestClient(app)

    with client.websocket_connect(f"/ws/gateway?client_id=ping_client&token={_TEST_DEV_TOKEN}") as ws:
        _ = ws.receive_text()  # Consume AUTH_ACK

        ping_msg = {"type": "ping"}
        ws.send_text(json.dumps(ping_msg))

        resp_raw = ws.receive_text()
        resp = json.loads(resp_raw)
        assert resp["type"] == MessageType.PONG.value
        assert resp["payload"]["reply"] == "pong"
        assert resp["payload"]["client_id"] == "ping_client"


def test_channel_subscription_and_unsubscription():
    """Clients can subscribe and unsubscribe from streaming channels."""
    client = TestClient(app)

    with client.websocket_connect(f"/ws/gateway?client_id=sub_client&token={_TEST_DEV_TOKEN}") as ws:
        _ = ws.receive_text()  # Consume AUTH_ACK

        # Subscribe to market ticks
        sub_msg = {"type": "subscribe", "channel": "market_ticks"}
        ws.send_text(json.dumps(sub_msg))

        sub_ack = json.loads(ws.receive_text())
        assert sub_ack["type"] == MessageType.SUBSCRIPTION_ACK.value
        assert sub_ack["channel"] == "market_ticks"
        assert sub_ack["payload"]["status"] == "subscribed"

        # Unsubscribe
        unsub_msg = {"type": "unsubscribe", "channel": "market_ticks"}
        ws.send_text(json.dumps(unsub_msg))


def test_market_tick_streaming_stratex():
    """
    Stratex market ticks are delivered to both general 'market_ticks'
    and symbol-specific 'market_ticks:SYMBOL' subscribers.
    """
    client = TestClient(app)

    with client.websocket_connect(f"/ws/gateway?client_id=ticker_client&token={_TEST_DEV_TOKEN}") as ws:
        _ = ws.receive_text()  # AUTH_ACK

        # Subscribe to general ticks
        ws.send_text(json.dumps({"type": "subscribe", "channel": "market_ticks"}))
        _ = ws.receive_text()  # SUBSCRIPTION_ACK

        # Subscribe to specific symbol BTC/USD
        ws.send_text(json.dumps({"type": "subscribe", "channel": "market_ticks:BTC/USD"}))
        _ = ws.receive_text()  # SUBSCRIPTION_ACK

        # Publish a tick via REST API endpoint
        tick_payload = {
            "symbol": "BTC/USD",
            "price": 68450.50,
            "volume": 2.75,
            "bid": 68449.00,
            "ask": 68451.00,
        }
        resp = client.post("/api/streaming/ticks", json=tick_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "published"
        assert data["symbol"] == "BTC/USD"
        assert data["delivered_subscribers"] >= 1

        # The client should receive tick messages
        tick_frame_raw = ws.receive_text()
        tick_frame = json.loads(tick_frame_raw)
        assert tick_frame["type"] == MessageType.MARKET_TICK.value
        assert tick_frame["payload"]["symbol"] == "BTC/USD"
        assert tick_frame["payload"]["price"] == 68450.50
        assert tick_frame["payload"]["volume"] == 2.75


def test_inference_duplex_deliberation_routing():
    """
    Deliberation frames between Inference and Forge are routed to session channels
    with monotonic turn sequencing.
    """
    client = TestClient(app)
    session_id = "delib_test_sess_001"
    channel = f"deliberation:{session_id}"

    with client.websocket_connect(f"/ws/gateway?client_id=delib_client&token={_TEST_DEV_TOKEN}") as ws:
        _ = ws.receive_text()  # AUTH_ACK

        # Subscribe to the deliberation session channel
        ws.send_text(json.dumps({"type": "subscribe", "channel": channel}))
        _ = ws.receive_text()  # SUBSCRIPTION_ACK

        # Route first deliberation turn via REST
        delib_1 = {
            "session_id": session_id,
            "sender_agent": "inference",
            "target_agent": "forge",
            "content": "Synthesizing architectural AST...",
            "turn_index": 0,
            "is_final": False,
        }
        resp1 = client.post("/api/streaming/deliberation", json=delib_1)
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "routed"

        frame1_raw = ws.receive_text()
        frame1 = json.loads(frame1_raw)
        assert frame1["type"] == MessageType.DELIBERATION_TURN.value
        assert frame1["sequence_number"] == 1
        assert frame1["payload"]["content"] == "Synthesizing architectural AST..."

        # Route second deliberation turn
        delib_2 = {
            "session_id": session_id,
            "sender_agent": "forge",
            "target_agent": "inference",
            "content": "AST synthesized. Tests generated and verified.",
            "turn_index": 1,
            "is_final": True,
        }
        resp2 = client.post("/api/streaming/deliberation", json=delib_2)
        assert resp2.status_code == 200

        frame2_raw = ws.receive_text()
        frame2 = json.loads(frame2_raw)
        assert frame2["sequence_number"] == 2
        assert frame2["payload"]["is_final"] is True


def test_client_publish_tick_and_deliberation_over_websocket():
    """Clients can publish market ticks and deliberation turns directly over WebSocket."""
    client = TestClient(app)

    with client.websocket_connect(f"/ws/gateway?client_id=publisher&token={_TEST_DEV_TOKEN}") as ws:
        _ = ws.receive_text()  # AUTH_ACK

        # Publish market tick directly through WebSocket frame
        ws.send_text(json.dumps({
            "type": "market_tick",
            "payload": {
                "symbol": "ETH/USD",
                "price": 3520.00,
                "volume": 12.5,
            },
        }))

        # Publish deliberation turn directly through WebSocket frame
        ws.send_text(json.dumps({
            "type": "deliberation_turn",
            "payload": {
                "session_id": "ws_direct_session",
                "sender_agent": "stratex",
                "target_agent": "forge",
                "content": "Order execution strategy ready",
                "turn_index": 0,
            },
        }))

        # Synchronize via ping/pong so server loop processes all prior frames
        ws.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == MessageType.PONG.value

        # Verify gateway metrics reflect incoming frames
        metrics = client.get("/api/streaming/metrics").json()
        assert metrics["total_messages_received"] >= 3
        assert metrics["total_ticks_published"] >= 1
        assert metrics["total_deliberations_routed"] >= 1


def test_invalid_json_frame_returns_error():
    """Sending non-JSON or malformed frames returns an error frame."""
    client = TestClient(app)

    with client.websocket_connect(f"/ws/gateway?client_id=malformed&token={_TEST_DEV_TOKEN}") as ws:
        _ = ws.receive_text()  # AUTH_ACK

        ws.send_text("THIS IS NOT JSON")
        err_raw = ws.receive_text()
        err = json.loads(err_raw)
        assert err["type"] == MessageType.ERROR.value
        assert "Invalid JSON" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_backpressure_and_queue_dropping():
    """
    When client outbound queue reaches capacity, backpressure triggers,
    dropping messages and incrementing dropped message counters.
    """
    gateway = WebSocketStreamingGateway(max_queue_size=2)

    # Mock ClientSession with queue size 2
    session = ClientSession(
        connection_id="mock_conn_1",
        websocket=None,  # type: ignore
        client_id="slow_consumer",
        authenticated=True,
        outbound_queue=asyncio.Queue(maxsize=2),
    )
    gateway.clients["mock_conn_1"] = session

    msg1 = GatewayMessage(type=MessageType.INFO, payload={"data": 1})
    msg2 = GatewayMessage(type=MessageType.INFO, payload={"data": 2})
    msg3 = GatewayMessage(type=MessageType.INFO, payload={"data": 3})

    # First two should succeed
    assert await gateway.send_to_client("mock_conn_1", msg1) is True
    assert await gateway.send_to_client("mock_conn_1", msg2) is True
    assert session.outbound_queue.full()

    # Third should trigger backpressure drop
    assert await gateway.send_to_client("mock_conn_1", msg3) is False
    assert session.dropped_messages == 1
    assert gateway.total_dropped_messages == 1

    # Non-existent client returns False
    assert await gateway.send_to_client("ghost_client", msg1) is False


def test_streaming_metrics_endpoint():
    """REST telemetry endpoint returns accurate gateway health and statistics."""
    client = TestClient(app)

    resp = client.get("/api/streaming/metrics")
    assert resp.status_code == 200
    metrics = resp.json()

    assert "active_connections" in metrics
    assert "active_channels" in metrics
    assert "channel_subscribers" in metrics
    assert "total_messages_received" in metrics
    assert "total_messages_sent" in metrics
    assert "total_ticks_published" in metrics
    assert "total_deliberations_routed" in metrics
    assert "total_dropped_messages" in metrics


@pytest.mark.asyncio
async def test_gateway_disconnect_cleanup_and_channel_unsub():
    """Disconnecting a client cleans up internal session registry and channel subscriber sets."""
    gateway = WebSocketStreamingGateway()
    session = ClientSession(
        connection_id="cleanup_conn_1",
        websocket=None,  # type: ignore
        client_id="terminating_client",
        authenticated=True,
    )
    gateway.clients["cleanup_conn_1"] = session

    # Subscribe to channel
    await gateway.subscribe("cleanup_conn_1", "market_ticks:SOL/USD")
    assert "cleanup_conn_1" in gateway.channel_subscribers["market_ticks:SOL/USD"]

    # Disconnect
    await gateway.disconnect("cleanup_conn_1")
    assert "cleanup_conn_1" not in gateway.clients
    assert "cleanup_conn_1" not in gateway.channel_subscribers["market_ticks:SOL/USD"]


@pytest.mark.asyncio
async def test_subscribe_unsubscribe_unknown_client():
    """Subscribing or unsubscribing an unknown connection returns False without exceptions."""
    gateway = WebSocketStreamingGateway()
    assert await gateway.subscribe("unknown_conn", "test_channel") is False
    assert await gateway.unsubscribe("unknown_conn", "test_channel") is False


def test_token_validation_mesh_matrix(monkeypatch):
    """Directly verifies is_valid_token for various FRIDAY Universe mesh services."""
    gateway = WebSocketStreamingGateway()
    settings = get_settings()

    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setenv("FRIDAY_API_KEY", "friday_secret_111")
    monkeypatch.setattr(settings, "memora_api_key", "memora_secret_222")
    monkeypatch.setattr(settings, "sentinel_api_key", "sentinel_secret_333")
    monkeypatch.setenv("FORGE_API_KEY", "forge_master_444")
    monkeypatch.setenv("VYRALX_API_KEY", "vyralx_key_555")

    # Valid mesh checks
    assert gateway.is_valid_token("friday_secret_111") == (True, "friday_core")
    assert gateway.is_valid_token("memora_secret_222") == (True, "memora")
    assert gateway.is_valid_token("sentinel_secret_333") == (True, "sentinel")
    assert gateway.is_valid_token("forge_master_444") == (True, "forge_admin")
    assert gateway.is_valid_token("vyralx_key_555") == (True, "vyralx")

    # Invalid tokens
    assert gateway.is_valid_token("") == (False, "anonymous")
    assert gateway.is_valid_token(None) == (False, "anonymous")
    assert gateway.is_valid_token("random_stranger_key") == (False, "guest")

