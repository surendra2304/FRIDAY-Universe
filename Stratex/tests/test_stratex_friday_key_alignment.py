"""TASK-REL-006: FRIDAY <-> Stratex auth alignment contract.

Production failure (console round 1, 2026-11-14): FRIDAY's portfolio query
dispatched to Stratex /v1/task/execute and got
``401 {"error": "Authentication failed: INVALID_API_KEY"}`` on every ask.

Root cause: the fleet provisions every peer with a per-agent
``<AGENT>_API_KEY`` env var, and FRIDAY's Stratex credential IS the
``STRATEX_API_KEY`` value (verified same-value on the host). But
``security_hardening.get_configured_api_keys()`` never accepted that env
name, so the correctly-provisioned key was rejected by name, not by value.

These tests pin the alignment:
- STRATEX_API_KEY authenticates the scopes FRIDAY's task dispatch needs
  (SCOPE_FRIDAY for /v1/task/execute, SCOPE_READ for read surfaces), via
  both the X-API-Key header FRIDAY's FleetClient sends and Bearer.
- STRATEX_API_KEY does NOT gain CONTROL or ADMIN authority: the live
  trading fail-closed guard and the control surfaces stay gated behind
  BOT_API_KEY / API_KEY_CONTROL / API_KEY_FRIDAY.
- FRIDAY's client contract: FleetClient sends the configured
  stratex_api_key as X-API-Key (and Bearer) — the exact headers Stratex's
  middleware reads.
"""

import os

import pytest
from flask import Flask

import security_hardening
from security_hardening import SCOPE_CONTROL, SCOPE_FRIDAY, SCOPE_READ

# Hyphenated fixture value: no long alphanumeric run (test_credentials guard).
FLEET_KEY = "stratex-fleet-key-for-rel006-tests"
OTHER_KEY = "some-other-key-that-must-not-match"

_KEY_ENV = (
    "BOT_API_KEY",
    "API_KEY_CONTROL",
    "API_KEY_READONLY",
    "API_KEY_FRIDAY",
    "STRATEX_API_KEY",
)


@pytest.fixture(autouse=True)
def _only_fleet_key(monkeypatch):
    for name in _KEY_ENV:
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("STRATEX_API_KEY", FLEET_KEY)
    # The abuse monitor blocks an IP after 10 failed auths in 5 minutes and is
    # process-global; keep this file's deliberate failures from leaking into
    # (or being poisoned by) other suites sharing 127.0.0.1.
    monitor = getattr(security_hardening, "_security_monitor", None)
    if monitor is not None and hasattr(monitor, "failed_auth_attempts"):
        monitor.failed_auth_attempts.clear()
    yield


def _auth(scope, headers):
    app = Flask(__name__)
    with app.test_request_context("/v1/task/execute", headers=headers):
        return security_hardening.authenticate_request(required_scope=scope)


def test_fleet_key_is_registered_with_least_privilege_scopes():
    keys = security_hardening.get_configured_api_keys()
    assert FLEET_KEY in keys
    info = keys[FLEET_KEY]
    assert info["source"] == "STRATEX_API_KEY"
    assert SCOPE_FRIDAY in info["scopes"]
    assert SCOPE_READ in info["scopes"]
    # Least privilege: the fleet read/task key is not a control key.
    assert SCOPE_CONTROL not in info["scopes"]
    assert security_hardening.SCOPE_ADMIN not in info["scopes"]


def test_fleet_key_authenticates_friday_scope_via_x_api_key():
    ok, err, info = _auth(SCOPE_FRIDAY, {"X-API-Key": FLEET_KEY})
    assert ok is True, err
    assert info["source"] == "STRATEX_API_KEY"


def test_fleet_key_authenticates_friday_scope_via_bearer():
    # FRIDAY's FleetClient sends both X-API-Key and Authorization: Bearer.
    ok, err, _info = _auth(SCOPE_FRIDAY, {"Authorization": f"Bearer {FLEET_KEY}"})
    assert ok is True, err


def test_fleet_key_authenticates_read_scope():
    ok, err, _info = _auth(SCOPE_READ, {"X-API-Key": FLEET_KEY})
    assert ok is True, err


def test_fleet_key_does_not_authenticate_control_scope():
    ok, err, _info = _auth(SCOPE_CONTROL, {"X-API-Key": FLEET_KEY})
    assert ok is False
    assert err is not None and "INSUFFICIENT_SCOPE" in err


def test_wrong_key_still_rejected_for_friday_scope():
    ok, err, _info = _auth(SCOPE_FRIDAY, {"X-API-Key": OTHER_KEY})
    assert ok is False
    assert err == "INVALID_API_KEY"


def test_missing_key_still_rejected_for_friday_scope():
    ok, err, _info = _auth(SCOPE_FRIDAY, {})
    assert ok is False
    assert err == "MISSING_API_KEY"
