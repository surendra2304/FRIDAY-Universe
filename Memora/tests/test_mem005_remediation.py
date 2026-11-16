"""TASK-MEM-005-R1 — credential remediation contracts.

Pins the three fixes for the MEM-005 audit findings (F1/F2):

1. MEMORA_API_KEY is no longer the master. Until this change the master
   branch in authenticate_agent fell back to MEMORA_API_KEY, and a copy of
   that value sat in every agent's env file, so any agent could
   authenticate as any other. The master is MEMORA_MASTER_KEY only.
2. MEMORA_API_KEY authenticates the memora identity alone, like every
   other per-agent key.
3. Cross-agent work uses scoped delegation: the caller authenticates with
   its OWN key and names the target via X-On-Behalf-Of; Memora grants the
   target identity only where MEMORA_DELEGATIONS names the
   (caller, target, scope) triple. Default deny, including on routes
   outside the delegation scope map.
"""

import importlib

import pytest
from fastapi import HTTPException
from starlette.requests import Request

FRIDAY_KEY = "friday-own-key-" + "f" * 30
STRATEX_KEY = "stratex-own-key-" + "s" * 30
SENTINEL_KEY = "sentinel-own-key-" + "n" * 30
MEMORA_KEY = "memora-own-key-" + "m" * 30
MASTER_KEY = "distinct-master-" + "k" * 30


@pytest.fixture()
def auth(monkeypatch):
    """Load apps.api.dependencies with a controlled credential environment."""
    monkeypatch.delenv("MEMORA_ALLOW_ANONYMOUS_DEV", raising=False)
    monkeypatch.delenv("MEMORA_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("FRIDAY_API_KEY", FRIDAY_KEY)
    monkeypatch.setenv("STRATEX_API_KEY", STRATEX_KEY)
    monkeypatch.setenv("SENTINEL_API_KEY", SENTINEL_KEY)
    monkeypatch.setenv("MEMORA_API_KEY", MEMORA_KEY)
    monkeypatch.delenv("MEMORA_MASTER_KEY", raising=False)
    monkeypatch.delenv("MEMORA_DELEGATIONS", raising=False)
    module = importlib.import_module("apps.api.dependencies")
    return importlib.reload(module)


def _request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


def _actor(auth, method, path, agent, key, on_behalf_of=None):
    return auth.get_actor_header(
        _request(method, path),
        x_agent_name=agent,
        x_api_key=key,
        authorization=None,
        x_on_behalf_of=on_behalf_of,
    )


# ---------------------------------------------------------------------------
# 1. The master split
# ---------------------------------------------------------------------------


def test_memora_api_key_no_longer_impersonates(auth):
    """The audit's decisive cell (b): MEMORA_API_KEY presented as friday
    read friday's PRIVATE records. It must now fail as a bad credential."""
    with pytest.raises(HTTPException) as exc:
        auth.authenticate_agent(
            x_agent_name="friday", x_api_key=MEMORA_KEY, authorization=None
        )
    assert exc.value.status_code == 401


def test_memora_api_key_authenticates_memora_alone(auth):
    assert (
        auth.authenticate_agent(
            x_agent_name="memora", x_api_key=MEMORA_KEY, authorization=None
        )
        == "memora"
    )


def test_memora_api_key_stays_non_master_when_master_is_set(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_MASTER_KEY", MASTER_KEY)
    with pytest.raises(HTTPException) as exc:
        auth.authenticate_agent(
            x_agent_name="stratex", x_api_key=MEMORA_KEY, authorization=None
        )
    assert exc.value.status_code == 401


def test_distinct_master_key_remains_break_glass(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_MASTER_KEY", MASTER_KEY)
    assert (
        auth.authenticate_agent(
            x_agent_name="friday", x_api_key=MASTER_KEY, authorization=None
        )
        == "friday"
    )
    assert (
        auth.authenticate_agent(
            x_agent_name="stratex", x_api_key=MASTER_KEY, authorization=None
        )
        == "stratex"
    )


def test_per_agent_keys_unchanged(auth):
    assert (
        auth.authenticate_agent(
            x_agent_name="friday", x_api_key=FRIDAY_KEY, authorization=None
        )
        == "friday"
    )
    with pytest.raises(HTTPException) as exc:
        auth.authenticate_agent(
            x_agent_name="stratex", x_api_key=FRIDAY_KEY, authorization=None
        )
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# 2. Scoped delegation
# ---------------------------------------------------------------------------


def test_no_delegation_header_returns_principal(auth):
    assert _actor(auth, "GET", "/v1/memories/search", "friday", FRIDAY_KEY) == "friday"


def test_delegation_to_self_needs_no_grant(auth):
    assert (
        _actor(auth, "GET", "/v1/memories/search", "friday", FRIDAY_KEY, "friday")
        == "friday"
    )


def test_delegation_denied_without_policy(auth):
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "GET", "/v1/memories/search", "friday", FRIDAY_KEY, "stratex")
    assert exc.value.status_code == 403


def test_delegation_read_grant_allows_search(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read,learn")
    assert (
        _actor(auth, "GET", "/v1/memories/search", "friday", FRIDAY_KEY, "stratex")
        == "stratex"
    )


def test_delegation_learn_grant_allows_learn_outcome(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read,learn")
    assert (
        _actor(
            auth, "POST", "/v1/memories/learn-outcome", "friday", FRIDAY_KEY, "stratex"
        )
        == "stratex"
    )


def test_delegation_read_grant_denies_mutate(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read,learn")
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "DELETE", "/v1/memories/abc123", "friday", FRIDAY_KEY, "stratex")
    assert exc.value.status_code == 403


def test_delegation_read_grant_denies_write(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read,learn")
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "POST", "/v1/memories", "friday", FRIDAY_KEY, "stratex")
    assert exc.value.status_code == 403


def test_delegation_denied_for_unlisted_pair(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read,learn")
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "GET", "/v1/memories/search", "friday", FRIDAY_KEY, "sentinel")
    assert exc.value.status_code == 403


def test_delegation_rejected_on_unmapped_route(auth, monkeypatch):
    """Delegation must not leak onto admin/other surfaces via the header."""
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read,learn,write,mutate,events")
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "GET", "/v1/agents", "friday", FRIDAY_KEY, "stratex")
    assert exc.value.status_code == 403


def test_master_credential_cannot_delegate(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_MASTER_KEY", MASTER_KEY)
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read")
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "GET", "/v1/memories/search", "friday", MASTER_KEY, "stratex")
    assert exc.value.status_code == 403


def test_delegation_unknown_target_rejected(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read")
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "GET", "/v1/memories/search", "friday", FRIDAY_KEY, "rogue")
    assert exc.value.status_code == 403


def test_delegation_still_requires_the_callers_own_key(auth, monkeypatch):
    """Another agent's key under friday's name fails authentication before
    delegation is even considered."""
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read")
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "GET", "/v1/memories/search", "friday", STRATEX_KEY, "stratex")
    assert exc.value.status_code == 401


def test_delegation_events_scope(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>sentinel:events")
    assert (
        _actor(auth, "GET", "/v1/events", "friday", FRIDAY_KEY, "sentinel")
        == "sentinel"
    )
    with pytest.raises(HTTPException) as exc:
        _actor(auth, "GET", "/v1/memories/search", "friday", FRIDAY_KEY, "sentinel")
    assert exc.value.status_code == 403


def test_delegation_context_route_is_read_scope(auth, monkeypatch):
    monkeypatch.setenv("MEMORA_DELEGATIONS", "friday>stratex:read")
    assert (
        _actor(auth, "POST", "/v1/context", "friday", FRIDAY_KEY, "stratex")
        == "stratex"
    )


# ---------------------------------------------------------------------------
# 3. Scope map + policy parser units
# ---------------------------------------------------------------------------


def test_scope_map(auth):
    scope = auth.delegation_scope_for
    assert scope("GET", "/v1/memories/search") == "read"
    assert scope("POST", "/v1/memories/query") == "read"
    assert scope("GET", "/v1/memories/experience") == "read"
    assert scope("GET", "/v1/memories/abc") == "read"
    assert scope("GET", "/v1/memories/abc/graph") == "read"
    assert scope("POST", "/v1/memories") == "write"
    assert scope("POST", "/v1/memories/learn-outcome") == "learn"
    assert scope("POST", "/v1/memories/learn-experience") == "learn"
    assert scope("POST", "/v1/memories/record-interaction") == "learn"
    assert scope("POST", "/v1/memories/abc/share") == "mutate"
    assert scope("POST", "/v1/memories/abc/forget") == "mutate"
    assert scope("DELETE", "/v1/memories/abc") == "mutate"
    assert scope("GET", "/memories") == "read"
    assert scope("POST", "/memories") == "write"
    assert scope("POST", "/memories/abc/transition") == "mutate"
    assert scope("GET", "/v1/events") == "events"
    assert scope("POST", "/v1/events/ack") == "events"
    assert scope("POST", "/v1/context") == "read"
    assert scope("GET", "/v1/agents") is None
    assert scope("POST", "/v1/tasks") is None
    assert scope("GET", "/health") is None


def test_policy_parser(auth, monkeypatch):
    monkeypatch.setenv(
        "MEMORA_DELEGATIONS",
        "friday>stratex:read,learn; friday>intelx:read;garbage;friday>stratex:events;cortex>sentinel:bogus",
    )
    grants = auth.delegation_grants()
    assert grants[("friday", "stratex")] == {"read", "learn", "events"}
    assert grants[("friday", "intelx")] == {"read"}
    assert ("cortex", "sentinel") not in grants


def test_policy_parser_empty(auth, monkeypatch):
    monkeypatch.delenv("MEMORA_DELEGATIONS", raising=False)
    assert auth.delegation_grants() == {}
