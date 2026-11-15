"""TASK-COR-009: every rejection on POST /v1/task/execute must be attributable
from Cortex's own log — caller (source_agent / client), action, gate, reason.

Production evidence behind this suite: FRIDAY's ReflexBrain escalates
unrepairable local faults to the fleet (AssistanceBroker.recall_from_peers +
request_help_from_peers), broadcasting the generic actions ``memory_recall``
and ``source_repair`` to every mesh peer. Cortex's execute endpoint is a
governed web-operations surface: it authenticates FRIDAY successfully, then
its property-scope gate rejects both actions with a bare 403. The journal
showed 54 such 403s (100% of the route's traffic in the retained window)
with *nothing* in the log naming the caller, the action or the gate — the
auth-success line was the only clue. These tests pin the structured
``task_execute_rejected`` WARNING (and the client/path attribution on the
auth-layer warning) so a future 403 on this route is self-explaining.

Wire behaviour is unchanged: same statuses, same detail strings.
"""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

import cortex_api.auth as auth_module
from cortex_api.main import app

TEST_KEY = "cor009-test-friday-service-key-0123456789"

_EVIDENCE = {"incident": {"kind": "test_failure", "source": "cor009"}, "test_node_id": "tests/test_x.py::test_y"}


def _body(action: str, payload: dict) -> dict:
    return {
        "task_id": f"cor009_{action}_{uuid.uuid4().hex[:8]}",
        "source_agent": "friday",
        "target_agent": "cortex",
        "action": action,
        "payload": payload,
    }


@pytest.fixture()
def client(monkeypatch):
    """Real auth dependency (no override) with a test FRIDAY service key."""
    monkeypatch.setattr(auth_module, "FRIDAY_API_KEY", TEST_KEY)
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def _rejection_lines(caplog) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "cortex-friday-gateway" and "task_execute_rejected" in r.getMessage()
    ]


def test_scope_rejection_for_memory_recall_is_attributed(client, caplog):
    """The production recall step: valid key, out-of-scope action -> 403 + log."""
    with caplog.at_level(logging.WARNING, logger="cortex-friday-gateway"):
        r = client.post(
            "/v1/task/execute",
            json=_body("memory_recall", {**_EVIDENCE, "capability": "source_repair", "question": "test_failure in cor009"}),
            headers={"X-Friday-Api-Key": TEST_KEY},
        )
    assert r.status_code == 403, r.text
    assert "Operation 'memory_recall' is not permitted on property 'site_storefront'" in r.json()["detail"]
    lines = _rejection_lines(caplog)
    assert len(lines) == 1, f"expected one structured rejection line, got: {lines}"
    line = lines[0]
    for fragment in (
        "source_agent=friday",
        "action=memory_recall",
        "property_id=site_storefront",
        "operation=memory_recall",
        "gate=property_scope",
        "status=403",
        "not permitted on property 'site_storefront'",
    ):
        assert fragment in line, f"{fragment!r} missing from rejection line: {line}"


def test_scope_rejection_for_source_repair_is_attributed(client, caplog):
    """The production help step: same gate, second action."""
    with caplog.at_level(logging.WARNING, logger="cortex-friday-gateway"):
        r = client.post(
            "/v1/task/execute",
            json=_body("source_repair", dict(_EVIDENCE)),
            headers={"X-Friday-Api-Key": TEST_KEY},
        )
    assert r.status_code == 403, r.text
    lines = _rejection_lines(caplog)
    assert len(lines) == 1
    assert "action=source_repair" in lines[0]
    assert "gate=property_scope" in lines[0]


def test_approval_rejection_is_attributed(client, caplog):
    """An in-scope but high-impact operation without approval -> 403 + log."""
    with caplog.at_level(logging.WARNING, logger="cortex-friday-gateway"):
        r = client.post(
            "/v1/task/execute",
            json=_body("execute_operation", {"operation": "payment_initiate", "property_id": "site_storefront"}),
            headers={"X-Friday-Api-Key": TEST_KEY},
        )
    assert r.status_code == 403, r.text
    assert "requires explicit supervisor approval" in r.json()["detail"]
    lines = _rejection_lines(caplog)
    assert len(lines) == 1
    assert "gate=approval" in lines[0]
    assert "operation=payment_initiate" in lines[0]
    assert "source_agent=friday" in lines[0]


def test_invalid_key_rejection_names_client(client, caplog):
    """Auth-layer 403: the warning must say where the attempt came from."""
    with caplog.at_level(logging.WARNING, logger="cortex-auth"):
        r = client.post(
            "/v1/task/execute",
            json=_body("memory_recall", dict(_EVIDENCE)),
            headers={"X-Friday-Api-Key": "wrong-key-wrong-key-wrong-key-0000"},
        )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "Invalid FRIDAY service token."
    warnings = [r.getMessage() for r in caplog.records if r.name == "cortex-auth" and r.levelno == logging.WARNING]
    assert any("invalid API key rejected" in m for m in warnings), warnings
    assert any("client=testclient" in m and "path=/v1/task/execute" in m for m in warnings), warnings


def test_in_scope_action_succeeds_without_rejection_log(client, caplog):
    """Guard: the happy path is untouched and logs no rejection."""
    with caplog.at_level(logging.WARNING, logger="cortex-friday-gateway"):
        r = client.post(
            "/v1/task/execute",
            json=_body("health_summary", {}),
            headers={"X-Friday-Api-Key": TEST_KEY},
        )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "COMPLETED"
    assert _rejection_lines(caplog) == []


def test_missing_key_still_401(client):
    """Guard: authentication behaviour is unchanged by the logging fix."""
    r = client.post("/v1/task/execute", json=_body("memory_recall", dict(_EVIDENCE)))
    assert r.status_code == 401, r.text
    assert "Missing X-Friday-Api-Key header" in r.json()["detail"]
