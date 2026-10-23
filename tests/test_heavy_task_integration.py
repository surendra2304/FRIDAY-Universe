"""Monorepo-level wiring tests for global heavyweight-job coordination."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_forge_futuris_and_sentinel_use_the_shared_lease_primitive():
    forge = _source("Forge/app/verification/engine.py")
    futuris = _source("Futuris/futuris/core/pipeline.py")
    sentinel = _source("Sentinel/sentinel/core/orchestrator/executor.py")

    assert "from mesh.heavy_task import" in forge
    assert "_run_with_heavy_lease" in forge
    assert "forge:verification-battery" in forge
    assert "coordinator.run(" in futuris
    assert 'task_id="futuris:model-fit"' in futuris
    assert "from mesh.heavy_task import" in sentinel
    assert "_requires_shared_heavy_lease" in sentinel
    assert 'task_id="sentinel:security-scan"' in sentinel


def test_compose_shares_private_authenticated_redis_between_workloads():
    compose_text = _source("docker-compose.oracle.yml")
    compose = yaml.safe_load(compose_text)
    services = compose["services"]
    redis = services["friday-heavy-task-redis"]

    assert redis["image"] == "redis:7-alpine"
    assert "ports" not in redis
    assert "FRIDAY_UNIVERSE_REDIS_PASSWORD" in redis["environment"]
    assert "--requirepass" in " ".join(redis["command"])
    assert "heavy_task_redis_data:/data" in redis["volumes"]

    # Only the public FRIDAY gateway is mapped to the host. All specialist APIs
    # must stay private and reachable through their standardized port 8000.
    assert services["friday"]["ports"] == ["10000:10000"]
    internal_urls = {
        "CORTEX_URL": "http://cortex:8000",
        "FORGE_URL": "http://forge:8000",
        "FUTURIS_URL": "http://futuris:8000",
        "INFERENCE_URL": "http://inference:8000",
        "INTELX_URL": "http://intelx:8000",
        "MEMORA_URL": "http://memora:8000",
        "SENTINEL_URL": "http://sentinel:8000",
        "STRATEX_URL": "http://stratex:8000",
        "VYRALX_URL": "http://vyralx:8000",
    }
    friday_env = services["friday"]["environment"]
    assert isinstance(friday_env, list)
    for variable, url in internal_urls.items():
        assert f"{variable}={url}" in friday_env

    for specialist in (
        "cortex", "forge", "futuris", "inference", "intelx",
        "memora", "sentinel", "stratex", "vyralx",
    ):
        assert "ports" not in services[specialist]

    for service_name, dockerfile in (
        ("forge", "Forge/Dockerfile"),
        ("futuris", "Futuris/Dockerfile"),
        ("sentinel", "Sentinel/Dockerfile"),
    ):
        service = services[service_name]
        assert service["build"]["context"] == "."
        assert service["build"]["dockerfile"] == dockerfile
        assert service["environment"]["FRIDAY_UNIVERSE_REQUIRE_DISTRIBUTED_HEAVY_TASKS"] == "true"
        assert service["environment"]["FRIDAY_UNIVERSE_HEAVY_TASK_REDIS_URL"].startswith(
            "redis://:"
        )
        assert service["depends_on"]["friday-heavy-task-redis"]["condition"] == "service_healthy"


def test_heavy_task_images_include_mesh_but_never_copy_env_secrets():
    for path in ("Forge/Dockerfile", "Futuris/Dockerfile", "Sentinel/Dockerfile"):
        dockerfile = _source(path)
        assert "mesh" in dockerfile
    ignore = _source(".dockerignore")
    assert "**/.env" in ignore
    assert "**/.env.*" in ignore


def test_remote_deploy_is_not_automatically_triggered_by_push():
    workflow = _source(".github/workflows/deploy-monorepo.yml")
    assert "workflow_dispatch:" in workflow
    assert "on:\n  push:" not in workflow
    assert "  pull_request:" not in workflow
