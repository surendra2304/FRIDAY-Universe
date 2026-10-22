"""Unit tests for the consumer-agnostic webhook dispatcher."""

import asyncio
from unittest.mock import AsyncMock, call, patch

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.api.webhooks import _retry_after_seconds, webhook_dispatcher
from app.main import app
from app.memory.db import DatabaseManager


@pytest.mark.asyncio
async def test_webhook_dispatch_success_for_any_2xx_response() -> None:
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = Response(206, json={"status": "accepted"})
        delivered = await webhook_dispatcher.dispatch_event(
            webhook_url="https://example.com/webhook",
            task_id="task_webhook_1",
            event="stage_completed",
            data={"stage": "Architecture", "progress": 35},
        )

    assert delivered
    assert mock_post.await_count == 1
    _, kwargs = mock_post.call_args
    payload = kwargs.get("json", {})
    assert payload["event"] == "stage_completed"
    assert payload["task_id"] == "task_webhook_1"
    assert payload["source"] == "forge"


@pytest.mark.asyncio
async def test_webhook_dispatch_no_url() -> None:
    delivered = await webhook_dispatcher.dispatch_event(
        webhook_url=None,
        task_id="task_no_hook",
        event="task_started",
    )
    assert delivered is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https:///missing-host",
        "https://user:secret@example.com/webhook",
        "https://example.com:not-a-port/webhook",
    ],
)
async def test_webhook_rejects_invalid_urls_without_network_calls(url: str) -> None:
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        delivered = await webhook_dispatcher.dispatch_event(
            webhook_url=url,
            task_id="task_invalid_url",
            event="task_started",
        )

    assert not delivered
    mock_post.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_retries_transport_errors_and_fails_gracefully() -> None:
    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=RuntimeError("simulated transport failure"),
        ) as mock_post,
        patch("app.api.webhooks.asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch("app.api.webhooks.random.uniform", return_value=0.0),
    ):
        delivered = await webhook_dispatcher.dispatch_event(
            webhook_url="https://unreachable.domain/webhook",
            task_id="task_fail",
            event="task_failed",
            max_retries=3,
        )

    assert delivered is False
    assert mock_post.await_count == 3
    assert sleep.await_args_list == [call(0.2), call(0.4)]


@pytest.mark.asyncio
async def test_webhook_retries_transient_statuses_and_honors_retry_after() -> None:
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("app.api.webhooks.asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch("app.api.webhooks.random.uniform", return_value=0.0),
    ):
        mock_post.side_effect = [
            Response(503),
            Response(429, headers={"Retry-After": "1.25"}),
            Response(204),
        ]
        delivered = await webhook_dispatcher.dispatch_event(
            webhook_url="https://receiver.example/events",
            task_id="task_transient",
            event="task_completed",
            max_retries=3,
        )

    assert delivered
    assert mock_post.await_count == 3
    assert sleep.await_args_list == [call(0.2), call(1.25)]


@pytest.mark.asyncio
async def test_permanent_client_error_fails_fast_without_retry() -> None:
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("app.api.webhooks.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        mock_post.return_value = Response(400, text="invalid payload")
        delivered = await webhook_dispatcher.dispatch_event(
            webhook_url="https://receiver.example/events",
            task_id="task_bad_request",
            event="task_completed",
            max_retries=3,
        )

    assert not delivered
    mock_post.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_propagates_without_retrying() -> None:
    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ) as mock_post,
        patch("app.api.webhooks.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        with pytest.raises(asyncio.CancelledError):
            await webhook_dispatcher.dispatch_event(
                webhook_url="https://receiver.example/events",
                task_id="task_cancel",
                event="task_completed",
                max_retries=3,
            )

    mock_post.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.parametrize("attempts", [0, -1, 1.5, True, 9])
@pytest.mark.asyncio
async def test_webhook_rejects_invalid_attempt_limits(attempts) -> None:
    with pytest.raises(ValueError, match="max_retries"):
        await webhook_dispatcher.dispatch_event(
            webhook_url="https://receiver.example/events",
            task_id="task_bad_attempts",
            event="task_completed",
            max_retries=attempts,
        )


def test_retry_after_parses_seconds_and_caps_wait() -> None:
    assert _retry_after_seconds("1.5") == 1.5
    assert _retry_after_seconds("100000") == 10.0
    assert _retry_after_seconds("-1") is None
    assert _retry_after_seconds("not-a-date") is None


@pytest.mark.asyncio
async def test_task_creation_with_webhook_url(isolated_db_manager: DatabaseManager) -> None:
    # Use the isolated test database rather than the process-global data/forge.db.
    await isolated_db_manager.init_db()

    with patch.object(
        webhook_dispatcher, "dispatch_event", new_callable=AsyncMock
    ) as mock_dispatch:
        mock_dispatch.return_value = True
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/tasks",
                json={
                    "goal": "Build a static portfolio website",
                    "webhook_url": "https://callback.service/events",
                },
            )

    assert response.status_code == 201
    data = response.json()
    assert data["metadata"]["webhook_url"] == "https://callback.service/events"
    assert mock_dispatch.called
