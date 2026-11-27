"""Tests for the Tor Metrics source (TASK-INT-047).

Hermetic: the Onionoo fetcher is an injected fake; no live Tor Metrics
call is made. Fixture JSON follows the real Onionoo protocol shape
(version / relays_published / relays+bridges arrays; summary fields
n/f/a/r; bandwidth + uptime histories keyed by period).
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from intelx.api.v1 import osint_tools
from intelx.connectors import tor_metrics as tm
from intelx.connectors.named_sources import NAMED_SOURCES
from intelx.core.report import filter_and_ground_findings, render_report_markdown

FP1 = "9695DFC35FFEB0271C66A957B7B0E1A6B6C3B01"
FP2 = "A1B2C3D4E5F60718293A4B5C6D7E8F90A1B2C3D4"

SUMMARY_DOC = {
    "version": "9.0",
    "relays_published": "2026-11-27 04:00:00",
    "bridges_published": "2026-11-27 04:00:00",
    "relays": [
        {
            "n": "moria1",
            "f": FP1,
            "a": ["128.31.0.34"],
            "r": True,
        },
        {
            "n": "dizum",
            "f": FP2,
            "a": ["194.109.206.212"],
            "r": True,
        },
        {
            "n": "offline-relay",
            "f": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
            "a": [],
            "r": False,
        },
    ],
    "bridges": [
        {"n": "Unnamed", "f": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", "r": True},
    ],
}

BANDWIDTH_DOC = {
    "version": "9.0",
    "relays_published": "2026-11-27 04:00:00",
    "bridges_published": "2026-11-27 04:00:00",
    "relays": [
        {
            "f": FP1,
            "n": "moria1",
            "write_history": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 1.0,
                    "values": [1200000, 1350000, 1100000],
                },
                "1_week": {
                    "first": "2026-11-20 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 1.0,
                    "values": [1350000, 1100000],
                },
            },
            "read_history": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 1.0,
                    "values": [900000, 950000, 880000],
                },
            },
        }
    ],
    "bridges": [],
}

WEIGHTS_DOC = {
    "version": "9.0",
    "relays_published": "2026-11-27 04:00:00",
    "bridges_published": "2026-11-27 04:00:00",
    "relays": [
        {
            "f": FP1,
            "n": "moria1",
            "consensus_weight": 123456,
            "consensus_weight_fraction": 0.0021,
        }
    ],
    "bridges": [],
}

CLIENTS_DOC = {
    "version": "9.0",
    "relays_published": "2026-11-27 04:00:00",
    "bridges_published": "2026-11-27 04:00:00",
    "relays": [
        {"country": "us", "average_clients": 500000},
        {"country": "de", "average_clients": 250000},
        {"country": "ir", "average_clients": 120000},
    ],
    "bridges": [],
}

UPTIME_DOC = {
    "version": "9.0",
    "relays_published": "2026-11-27 04:00:00",
    "bridges_published": "2026-11-27 04:00:00",
    "relays": [
        {
            "f": FP1,
            "n": "moria1",
            "uptime": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 1.0,
                    "values": [100, 100, 99],
                },
            },
        }
    ],
    "bridges": [],
}


def make_fetch(docs: dict[str, dict]):
    """A fake fetcher serving one Onionoo document per path prefix."""

    async def fetch(url: str):
        for prefix, doc in docs.items():
            if prefix in url:
                return 200, url, json.dumps(doc).encode("utf-8")
        return 404, url, b"{}"

    return fetch


# ---------------------------------------------------------------------------
# Summary / search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_relays_returns_running_summaries():
    client = tm.TorMetricsClient(fetch=make_fetch({"/summary": SUMMARY_DOC}))
    relays = await client.search_relays("moria", limit=10)
    # 3 relays + 1 bridge in the fixture summary document.
    assert len(relays) == 4
    assert relays[0].nickname == "moria1"
    assert relays[0].fingerprint == FP1
    assert relays[0].addresses == ["128.31.0.34"]
    assert relays[0].running is True
    assert relays[2].nickname == "offline-relay"
    assert relays[2].running is False
    assert relays[3].nickname == "Unnamed"
    assert relays[3].running is True


@pytest.mark.asyncio
async def test_search_relays_empty_query_fails_closed():
    client = tm.TorMetricsClient(fetch=make_fetch({"/summary": SUMMARY_DOC}))
    with pytest.raises(tm.TorMetricsUnavailable):
        await client.search_relays("   ")


@pytest.mark.asyncio
async def test_search_relays_unknown_returns_empty_not_synthetic():
    empty = dict(SUMMARY_DOC, relays=[], bridges=[])
    client = tm.TorMetricsClient(fetch=make_fetch({"/summary": empty}))
    assert await client.search_relays("nosuchrelay") == []


@pytest.mark.asyncio
async def test_search_relays_non_200_fails_closed():
    async def failing(url: str):
        return 503, url, b""

    client = tm.TorMetricsClient(fetch=failing)
    with pytest.raises(tm.TorMetricsUnavailable):
        await client.search_relays("moria")


@pytest.mark.asyncio
async def test_search_relays_unparseable_json_fails_closed():
    async def bad_json(url: str):
        return 200, url, b"{not json"

    client = tm.TorMetricsClient(fetch=bad_json)
    with pytest.raises(tm.TorMetricsUnavailable):
        await client.search_relays("moria")


@pytest.mark.asyncio
async def test_search_relays_document_without_version_fails_closed():
    async def no_version(url: str):
        return 200, url, json.dumps({"relays": []}).encode("utf-8")

    client = tm.TorMetricsClient(fetch=no_version)
    with pytest.raises(tm.TorMetricsUnavailable):
        await client.search_relays("moria")


# ---------------------------------------------------------------------------
# Per-relay documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relay_bandwidth_prefers_1_month_history():
    client = tm.TorMetricsClient(fetch=make_fetch({"/bandwidth": BANDWIDTH_DOC}))
    bw = await client.relay_bandwidth(FP1)
    assert bw.fingerprint == FP1
    assert bw.nickname == "moria1"
    assert bw.write_history is not None
    assert bw.write_history.period == "1_month"
    assert bw.write_history.values == [1200000, 1350000, 1100000]
    assert bw.read_history is not None
    assert bw.read_history.values == [900000, 950000, 880000]


@pytest.mark.asyncio
async def test_relay_bandwidth_unknown_fingerprint_fails_closed():
    client = tm.TorMetricsClient(fetch=make_fetch({"/bandwidth": BANDWIDTH_DOC}))
    with pytest.raises(tm.TorMetricsUnavailable):
        await client.relay_bandwidth("0000000000000000000000000000000000000000")


@pytest.mark.asyncio
async def test_relay_weights_reports_consensus_weight():
    client = tm.TorMetricsClient(fetch=make_fetch({"/weights": WEIGHTS_DOC}))
    weights = await client.relay_weights(FP1)
    assert weights.consensus_weight == 123456
    assert weights.consensus_weight_fraction == 0.0021


@pytest.mark.asyncio
async def test_relay_weights_missing_weight_is_none_not_fabricated():
    doc = {
        "version": "9.0",
        "relays_published": "2026-11-27 04:00:00",
        "bridges_published": "2026-11-27 04:00:00",
        "relays": [{"f": FP1, "n": "moria1"}],
        "bridges": [],
    }
    client = tm.TorMetricsClient(fetch=make_fetch({"/weights": doc}))
    weights = await client.relay_weights(FP1)
    assert weights.consensus_weight is None
    assert weights.consensus_weight_fraction is None


@pytest.mark.asyncio
async def test_relay_uptime_reports_history():
    client = tm.TorMetricsClient(fetch=make_fetch({"/uptime": UPTIME_DOC}))
    uptime = await client.relay_uptime(FP1)
    assert uptime.uptime is not None
    assert uptime.uptime.period == "1_month"
    assert uptime.uptime.values == [100, 100, 99]


# ---------------------------------------------------------------------------
# Clients (censorship metric) + snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_clients_returns_country_breakdown():
    client = tm.TorMetricsClient(fetch=make_fetch({"/clients": CLIENTS_DOC}))
    countries = await client.network_clients()
    assert [c.country for c in countries] == ["us", "de", "ir"]
    assert countries[0].average_clients == 500000
    assert countries[2].average_clients == 120000


@pytest.mark.asyncio
async def test_network_snapshot_combines_census_and_clients():
    docs = {"/summary": SUMMARY_DOC, "/clients": CLIENTS_DOC}
    client = tm.TorMetricsClient(fetch=make_fetch(docs))
    snapshot = await client.network_snapshot("moria", limit=10)
    assert snapshot.query == "moria"
    assert snapshot.running_relays == 2
    assert snapshot.running_bridges == 1
    assert len(snapshot.relays) == 3
    assert snapshot.total_average_clients == 870000
    assert snapshot.countries[0].country == "us"
    assert snapshot.version == "9.0"
    assert snapshot.relays_published == "2026-11-27 04:00:00"
    assert len(snapshot.source_urls) == 2
    assert snapshot.source_urls[0].startswith("https://onionoo.torproject.org/summary")


@pytest.mark.asyncio
async def test_network_snapshot_empty_query_fails_closed():
    client = tm.TorMetricsClient(fetch=make_fetch({"/summary": SUMMARY_DOC}))
    with pytest.raises(tm.TorMetricsUnavailable):
        await client.network_snapshot("   ")


# ---------------------------------------------------------------------------
# Citation seam: source + claims for the report pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_source_record_shape_for_report_pipeline():
    docs = {"/summary": SUMMARY_DOC, "/clients": CLIENTS_DOC}
    client = tm.TorMetricsClient(fetch=make_fetch(docs))
    snapshot = await client.network_snapshot("moria", limit=10)
    source = snapshot.to_source()
    assert source["id"] == "tor-metrics:moria"
    assert source["domain"] == "onionoo.torproject.org"
    assert source["trust_tier"] == "STANDARD"
    assert source["published_at"] == "2026-11-27 04:00:00"
    assert source["retrieved_at"]
    assert source["url"].startswith("https://onionoo.torproject.org/summary")
    assert source["injection_risk"] is False
    assert "moria1" in source["text"]
    assert "500000" in source["text"]


@pytest.mark.asyncio
async def test_snapshot_claims_ground_findings_in_report_pipeline():
    docs = {"/summary": SUMMARY_DOC, "/clients": CLIENTS_DOC}
    client = tm.TorMetricsClient(fetch=make_fetch(docs))
    snapshot = await client.network_snapshot("moria", limit=10)
    source = snapshot.to_source()
    claims = snapshot.to_claims()
    assert claims
    assert all(c["source_id"] == source["id"] for c in claims)
    assert all(c["status"] == "ACTIVE" for c in claims)
    assert any("2 relays" in c["text"] for c in claims)
    assert any("us" in c["text"] and "500000" in c["text"] for c in claims)
    # The report pipeline grounds a finding that cites these claims.
    claims_by_id = {c["id"]: c for c in claims}
    findings = [
        {
            "statement": "Two relays matching 'moria' are running.",
            "claim_ids": [claims[0]["id"]],
        }
    ]
    grounded, unverified = filter_and_ground_findings(findings, claims_by_id)
    assert len(grounded) == 1
    assert unverified == []
    # And the renderer cites the source.
    markdown = render_report_markdown(
        objective="Tor network status for moria",
        executive_answer="Two relays are running.",
        grounded_findings=grounded,
        unverified_findings=[],
        claims=claims,
        sources=[source],
    )
    assert "[S:tor-metrics-moria]" in markdown or "tor-metrics:moria" in markdown


# ---------------------------------------------------------------------------
# Registry + route
# ---------------------------------------------------------------------------


def test_tor_metrics_registered_as_keyless_named_source():
    entry = next(s for s in NAMED_SOURCES if s.name == "Tor Metrics")
    assert entry.kind == "api_keyless"
    assert entry.home_url == "https://metrics.torproject.org"
    assert "Onionoo" in entry.access_note


@pytest.mark.asyncio
async def test_tor_metrics_route_503_while_flag_off(monkeypatch):
    monkeypatch.setattr(osint_tools.get_settings(), "ENABLE_TOR_METRICS", False)
    with pytest.raises(HTTPException) as exc_info:
        await osint_tools.tor_metrics(q="moria")
    assert exc_info.value.status_code == 503
