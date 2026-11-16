"""
TASK-IG2-MEM-03 wiring — the structured user model over HTTP.

The service contracts are locked by test_ig2_mem03_user_model.py. What
was missing — and what this suite locks — is the PRODUCTION CALLER:
the mounted /v1/user-model router. Before this wiring,
UserModelService was referenced only by its own module and its tests
(its render block is also embedded in the capture inject pack by
PR #755; this suite covers the model's own surface).

Locked here:
- fields are set, versioned and consulted over HTTP with the
  authenticated identity as the actor; an update reports the value it
  replaced;
- a correction recorded over HTTP lands as a standing_rule at
  confidence 1.0;
- absence is honest over the wire too: consult of an unknown field is
  found=false and an empty profile renders as "nothing assumed";
- invalid field kinds are refused with the reason;
- the routes are mounted on the real app.
"""
from core.identity.service import IdentityService


def _setup(test_db):
    IdentityService.register_agent(test_db, "friday")


def test_profile_update_consult_render_over_http(client, test_db):
    _setup(test_db)

    # Absence first: nothing recorded, nothing invented.
    resp = client.get("/v1/user-model/profile")
    assert resp.status_code == 200, resp.text
    assert resp.json()["exists"] is False and resp.json()["fields"] == {}
    resp = client.get("/v1/user-model/consult", params={"field": "briefing_time"})
    assert resp.json()["found"] is False and resp.json()["value"] is None
    resp = client.get("/v1/user-model/render")
    assert "nothing assumed" in resp.json()["profile"]

    resp = client.put(
        "/v1/user-model/field",
        json={"field": "briefing_time", "value": "08:50 IST", "kind": "preference",
              "source_ref": "owner-statement"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated"] is True and body["previous_value"] is None and body["version"] == 1, body

    resp = client.get("/v1/user-model/consult", params={"field": "briefing_time"})
    body = resp.json()
    assert body["found"] is True and body["value"] == "08:50 IST" and body["kind"] == "preference"

    # A change reports exactly what it replaced and bumps the version.
    resp = client.put(
        "/v1/user-model/field",
        json={"field": "briefing_time", "value": "09:00 IST", "kind": "preference"},
    )
    body = resp.json()
    assert body["updated"] is True and body["previous_value"] == "08:50 IST"
    assert body["changed"] is True and body["version"] == 2

    resp = client.get("/v1/user-model/profile")
    body = resp.json()
    assert body["exists"] is True and body["version"] == 2
    assert body["fields"]["briefing_time"]["value"] == "09:00 IST"
    assert body["fields"]["briefing_time"]["history"][0]["value"] == "08:50 IST"


def test_correction_over_http_lands_as_standing_rule(client, test_db):
    _setup(test_db)
    resp = client.post(
        "/v1/user-model/corrections",
        json={"field": "report_style", "value": "Outcomes, not progress reports.",
              "source_ref": "owner-correction-2026-11-15"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] is True
    resp = client.get("/v1/user-model/consult", params={"field": "report_style"})
    body = resp.json()
    assert body["found"] is True and body["kind"] == "standing_rule"
    assert body["confidence"] == 1.0
    # Standing rules render ahead of preferences in the injection block.
    client.put(
        "/v1/user-model/field",
        json={"field": "primary_channel", "value": "chat", "kind": "preference"},
    )
    rendered = client.get("/v1/user-model/render").json()["profile"]
    assert rendered.index("report_style") < rendered.index("primary_channel")


def test_invalid_kind_is_refused_with_reason(client, test_db):
    _setup(test_db)
    resp = client.put(
        "/v1/user-model/field",
        json={"field": "mood", "value": "calm", "kind": "guess"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] is False
    assert resp.json()["reason"] == "unknown_kind:guess"
    assert client.get("/v1/user-model/profile").json()["exists"] is False


def test_user_model_routes_are_mounted():
    from apps.api.main import app

    paths = set(app.openapi()["paths"])
    assert {
        "/v1/user-model/profile",
        "/v1/user-model/consult",
        "/v1/user-model/render",
        "/v1/user-model/field",
        "/v1/user-model/corrections",
    } <= paths
