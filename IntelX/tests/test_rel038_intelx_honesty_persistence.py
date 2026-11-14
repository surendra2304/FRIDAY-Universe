"""TASK-REL-038 — IntelX honesty + research persistence regression coverage.

Three contracts pinned here:

1. The intel sharing manager and the threat-intel exchange protocol never
   claim a transmission that did not happen: records are local-only, with
   the reason attached, and legacy stored statuses ("sent"/"completed")
   are presented honestly, never as-is.
2. Completed ``research_live`` runs are durably persisted (query, findings,
   synthesis status, receipts, timestamp) and retrievable verbatim by run
   id — via the store, the GET endpoints and the ``research_recall`` task
   action — with bounded retention.
3. A source the hardened fetcher refuses (e.g. a Google News redirector
   link answering 403) is skipped with the precise reason recorded, not a
   bare exception class name.
"""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from intelx.app.factory import create_app
from intelx.core.auth import hash_api_key
from intelx.core.enums import ApiKeyRole
from intelx.db.models import ApiKey
from intelx.db.session import get_sessionmaker

# ── 1a. Intel sharing manager ─────────────────────────────────────────────

from routers.intel_sharing_manager import IntelExchange, IntelSharingManager


def test_share_intel_is_queued_local_only_never_sent():
    mgr = IntelSharingManager()
    exchange_id = mgr.share_intel("intelx", "partner-org", "IoC", "1.2.3.4")
    (entry,) = mgr.get_exchanges()
    assert entry["exchange_id"] == exchange_id
    assert entry["status"] == "queued_local_only"
    assert entry["transmitted"] is False
    assert "NOT transmitted" in entry["delivery_note"]
    # Nothing was sent, so no send timestamp may exist.
    assert mgr._exchanges[exchange_id].sent_at == 0.0


def test_share_intel_acknowledge_is_local_bookkeeping():
    mgr = IntelSharingManager()
    exchange_id = mgr.share_intel("intelx", "partner-org", "IoC", "evil.example")
    assert mgr.acknowledge_exchange(exchange_id) is True
    (entry,) = mgr.get_exchanges()
    assert entry["status"] == "acknowledged_locally"
    assert entry["transmitted"] is False
    report = mgr.get_report()
    assert report["acknowledged_locally"] == 1
    assert report["transmitted"] == 0


def test_share_intel_legacy_sent_status_is_presented_honestly():
    mgr = IntelSharingManager()
    legacy = IntelExchange(
        exchange_id="ex_legacy", sender="intelx", recipient="partner-org",
        intel_type="IoC", content="5.6.7.8",
    )
    legacy.status = "sent"  # written by the pre-fix code path
    mgr._exchanges[legacy.exchange_id] = legacy
    (entry,) = mgr.get_exchanges()
    assert entry["status"] == "queued_local_only"
    assert entry["legacy_status"] == "sent"
    assert entry["transmitted"] is False
    # Filtering by the honest status finds the legacy record too.
    assert len(mgr.get_exchanges(status="queued_local_only")) == 1
    assert mgr.get_exchanges(status="sent") == []


async def test_share_intel_route_reports_local_only(client):
    resp = await client.post(
        "/intelex/sharing/exchanges",
        params={"sender": "intelx", "recipient": "partner-org",
                "intel_type": "IoC", "content": "9.9.9.9"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued_local_only"
    assert body["transmitted"] is False


# ── 1b. Threat intel exchange protocol ────────────────────────────────────

from intelx.services.threat_intel_exchange_protocol import (
    ExchangeRecord,
    ThreatIntelExchangeProtocol,
)


def _protocol_with_partners():
    proto = ThreatIntelExchangeProtocol()
    src = proto.register_partner("intelx")
    dst = proto.register_partner("partner", trust_level=0.9)
    return proto, src, dst


def test_exchange_records_local_only_not_completed():
    proto, src, dst = _protocol_with_partners()
    pkg = proto.create_package({"ioc": "1.2.3.4"}, source="intelx")
    record = proto.exchange(src.partner_id, dst.partner_id, [pkg.package_id])
    assert record.status == "recorded_local_only"
    assert record.transmitted is False
    assert "NOT" in record.delivery_note and "delivered" in record.delivery_note
    report = proto.get_report()
    assert report["recorded_local_only_exchanges"] == 1
    assert report["transmitted_exchanges"] == 0
    assert "completed_exchanges" not in report


def test_exchange_with_missing_package_is_validation_failed():
    proto, src, dst = _protocol_with_partners()
    record = proto.exchange(src.partner_id, dst.partner_id, ["pkg_missing"])
    assert record.status == "validation_failed"
    assert record.errors
    report = proto.get_report()
    assert report["validation_failed_exchanges"] == 1
    assert report["recorded_local_only_exchanges"] == 0


def test_exchange_legacy_completed_status_counted_honestly():
    proto, src, dst = _protocol_with_partners()
    proto._exchanges.append(
        ExchangeRecord(
            exchange_id="ex_legacy", source_partner="a", target_partner="b",
            package_count=1, status="completed",  # pre-fix stored value
        )
    )
    report = proto.get_report()
    assert report["recorded_local_only_exchanges"] == 1
    assert report["transmitted_exchanges"] == 0


# ── 2. Live research persistence ──────────────────────────────────────────

from intelx.api import live_research_store as store


def _envelope(status="SUCCESS", synthesis_status="succeeded"):
    return {
        "task_id": "task_rel038",
        "target_agent": "intelx",
        "status": status,
        "summary": "Retrieved 1 source document(s).",
        "result": {
            "status": status,
            "query": "what is the airspeed of a laden swallow",
            "synthesis_status": synthesis_status,
            "answer_kind": "source_excerpts",
            "findings": [
                {
                    "statement": "A laden swallow passage, verbatim.",
                    "status": "source_excerpt",
                    "quote": "A laden swallow passage, verbatim.",
                    "truncated": False,
                    "citations": [
                        {"source_id": "abc", "source_title": "Swallow Facts",
                         "source_url": "https://example.com/swallows"}
                    ],
                }
            ],
            "sources": [
                {"id": "abc", "title": "Swallow Facts",
                 "url": "https://example.com/swallows"}
            ],
            "durable_run": False,
        },
        "receipt": {
            "requested_action": "research_live",
            "target": "intelx",
            "authorization_decision": "AUTHORIZED",
            "failure_reason": None,
            "verification_evidence": {"pipeline": "friday.research", "durable_run": False},
        },
    }


async def test_live_research_persist_and_fetch_verbatim():
    persisted = await store.persist_live_research(
        "task_rel038", "what is the airspeed of a laden swallow", _envelope()
    )
    assert persisted is not None
    run_id, write_ms = persisted
    assert run_id
    assert write_ms >= 0

    record = await store.fetch_live_research(run_id)
    assert record is not None
    assert record["run_id"] == run_id
    assert record["durable_run"] is True
    # Verbatim: the stored payload is the pipeline result, findings intact,
    # now truthfully self-describing as durable.
    assert record["result"]["findings"][0]["statement"] == "A laden swallow passage, verbatim."
    assert record["result"]["durable_run"] is True
    assert record["result"]["run_id"] == run_id
    assert record["synthesis_status"] == "succeeded"
    assert record["receipt"]["verification_evidence"]["durable_run"] is True
    assert record["created_at"]


async def test_live_research_degraded_run_is_persisted_too():
    persisted = await store.persist_live_research(
        "task_rel038_deg", "query that degraded", _envelope(status="DEGRADED", synthesis_status="failed")
    )
    assert persisted is not None
    record = await store.fetch_live_research(persisted[0])
    assert record["status"] == "DEGRADED"
    assert record["synthesis_status"] == "failed"


async def test_live_research_retention_is_bounded(monkeypatch):
    monkeypatch.setattr(store, "MAX_STORED_RUNS", 10)
    for i in range(12):
        env = _envelope()
        env["result"]["query"] = f"retention probe {i}"
        persisted = await store.persist_live_research(f"task_ret_{i}", f"retention probe {i}", env)
        assert persisted is not None
    runs = await store.list_live_research(limit=100)
    assert len(runs) == 10
    queries = {r["query"] for r in runs}
    assert "retention probe 0" not in queries
    assert "retention probe 11" in queries


async def test_live_research_unknown_run_returns_none():
    assert await store.fetch_live_research("lr_does_not_exist") is None


@pytest.fixture
async def friday_client():
    """ASGI client with a seeded FRIDAY key (same pattern as the mesh
    receipt contract tests)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        f_hash = hash_api_key("rel038-archive-key")
        stmt = select(ApiKey).where(ApiKey.key_hash == f_hash)
        if not (await session.execute(stmt)).scalar_one_or_none():
            from datetime import UTC, datetime

            session.add(
                ApiKey(
                    key_hash=f_hash,
                    name="rel038-archive",
                    role=ApiKeyRole.MEMBER,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
    app = create_app()
    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer " + "rel038-archive-key"}
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac, headers


async def test_live_research_archive_endpoints_and_recall(friday_client):
    client, headers = friday_client
    persisted = await store.persist_live_research(
        "task_rel038_api", "archived swallow query", _envelope()
    )
    run_id = persisted[0]

    resp = await client.get(f"/v1/research/live/{run_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["findings"][0]["statement"] == "A laden swallow passage, verbatim."
    assert body["durable_run"] is True

    resp = await client.get("/v1/research/live", headers=headers)
    assert resp.status_code == 200
    assert any(r["run_id"] == run_id for r in resp.json()["runs"])

    resp = await client.post(
        "/v1/task/execute",
        json={"task_id": "task_rel038_recall", "action": "research_recall",
              "payload": {"run_id": run_id}},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["result"]["findings"][0]["quote"] == "A laden swallow passage, verbatim."

    resp = await client.get("/v1/research/live/lr_missing", headers=headers)
    assert resp.status_code == 404


# ── 3. Precise fetch-skip reasons in the brief pipeline ───────────────────

from intelx.api.live_research_task import collect_live_brief


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class _FakeHTTPStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.response = _FakeResponse(status_code)


class _FakeSearch:
    def __init__(self, results):
        self._results = results

    async def fetch(self, query, max_results=10):
        return self._results


def _candidate(url, title="Candidate"):
    return SimpleNamespace(url=url, title=title)


async def test_google_news_403_skip_reason_is_precise():
    class RaisingFetch:
        async def fetch(self, url, max_bytes=1_000_000):
            raise _FakeHTTPStatusError(403)

    search = _FakeSearch([
        _candidate("https://news.google.com/rss/articles/CBMi123", "News item")
    ])
    result = await collect_live_brief("swallow airspeed research", search, RaisingFetch())
    (failure,) = result["source_failures"]
    assert failure["reason"] == "google_news_redirect_http_403"
    assert failure["status_code"] == 403


async def test_http_status_skip_reason_includes_code():
    class StatusFetch:
        async def fetch(self, url, max_bytes=1_000_000):
            return SimpleNamespace(
                status_code=403, content_type="text/html",
                final_url=url, content=b"",
            )

    search = _FakeSearch([_candidate("https://example.com/blocked", "Blocked")])
    result = await collect_live_brief("swallow airspeed research", search, StatusFetch())
    (failure,) = result["source_failures"]
    assert failure["reason"] == "http_403"
    assert failure["status_code"] == 403
