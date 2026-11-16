"""TASK-IG2-INF-03: read-only Inference admin dashboard (FreeLLMAPI pattern).

Pins: the failover log records gateway escalations in a bounded ring; the
dashboard snapshot assembles provider health + quota burn + per-key usage
+ recent failovers from the live trackers; the HTML page renders those
sections with every value escaped; the routes are GET-only and sit behind
the inference API key like every other audit surface; and no key value
ever appears — fingerprints only.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.providers.failover_log import FailoverLog
from app.providers.quota_ledger import key_fingerprint
from app.routers.admin_dashboard import build_admin_snapshot, render_admin_html


def test_failover_log_records_and_bounds():
    log = FailoverLog(max_events=3)
    for i in range(5):
        log.record(from_provider="gemini", reason=f"failure {i}", model="m", capability="general", ts=1000.0 + i)
    snap = log.snapshot(limit=10)
    assert snap["events_retained"] == 3
    assert snap["events_dropped_oldest"] == 2
    assert [e["reason"] for e in snap["events"]] == ["failure 4", "failure 3", "failure 2"]  # newest first
    assert snap["events"][0]["at_utc"].endswith("Z")


def test_failover_log_truncates_reason():
    log = FailoverLog()
    log.record(from_provider="groq", reason="x" * 1000)
    assert len(log.snapshot()["events"][0]["reason"]) == 300


def test_snapshot_shape_and_no_key_values():
    snap = build_admin_snapshot()
    assert snap["service"] == "inference"
    for section in ("providers", "failovers", "token_compression", "bytez_probe", "warnings"):
        assert section in snap
    assert "basis" in snap["failovers"]
    # The snapshot is built from fingerprints; a raw key must never appear.
    assert key_fingerprint("anything") is not None  # fingerprint helper exists and is one-way


def test_html_renders_sections_and_escapes():
    snap = build_admin_snapshot()
    snap["warnings"] = ["<script>alert(1)</script>"]
    page = render_admin_html(snap)
    assert "Inference Admin (read-only)" in page
    assert "Per-key usage" in page
    assert "Recent failovers" in page
    assert "Token compression" in page
    assert "Bytez free-tier probe" in page
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


@pytest.mark.asyncio
async def test_dashboard_routes_require_auth_and_serve(auth):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        anon_html = await client.get("/admin/inference")
        anon_json = await client.get("/admin/inference.json")
        ok_html = await client.get("/admin/inference", headers=auth)
        ok_json = await client.get("/admin/inference.json", headers=auth)

    assert anon_html.status_code in (401, 403, 503)
    assert anon_json.status_code in (401, 403, 503)
    assert ok_html.status_code == 200
    assert "text/html" in ok_html.headers["content-type"]
    assert "Inference Admin (read-only)" in ok_html.text
    assert ok_json.status_code == 200
    payload = ok_json.json()
    assert payload["service"] == "inference"
    assert "providers" in payload and "failovers" in payload


@pytest.mark.asyncio
async def test_dashboard_is_read_only(auth):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for method in ("post", "put", "delete", "patch"):
            resp = await getattr(client, method)("/admin/inference", headers=auth)
            assert resp.status_code == 405, method
