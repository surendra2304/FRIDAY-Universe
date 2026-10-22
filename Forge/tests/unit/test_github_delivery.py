"""
Unit tests for GitHub Delivery Integration.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response

from app.integrations.github_delivery import (
    GitHubDeliveryService,
)


@pytest.mark.asyncio
async def test_github_delivery_simulated_when_no_token():
    service = GitHubDeliveryService()
    service.settings.github_token = None

    result = await service.deliver_task(
        task_id="task_gh_01",
        goal="Create REST microservice",
        tag_name="v1.0.0",
    )
    assert result.status == "delivered"
    assert "forge-task_gh_01" in result.repo_name
    assert "git clone" in result.clone_command
    assert "v1.0.0" in result.release_tag


@pytest.mark.asyncio
async def test_github_delivery_with_api_mock():
    service = GitHubDeliveryService()
    service.settings.github_token = "fake_github_token"

    mock_resp = {
        "name": "forge-task_gh_02",
        "html_url": "https://github.com/org/forge-task_gh_02",
        "clone_url": "https://github.com/org/forge-task_gh_02.git",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = Response(201, json=mock_resp)

        result = await service.deliver_task(
            task_id="task_gh_02",
            goal="Static Portfolio Website",
            tag_name="v1.0.0",
        )
        assert result.status == "delivered"
        assert result.repo_url == "https://github.com/org/forge-task_gh_02"
