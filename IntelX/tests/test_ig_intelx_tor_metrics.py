"""Tests for the Tor Metrics source (TASK-INT-047, TASK-INT-047-FIX-01).

Hermetic: the Onionoo fetcher is an injected fake; no live Tor Metrics
call is made. Fixture JSON follows the real Onionoo 8.0 protocol shape
(verified live 2026-11-27): /summary fields n/f/a/r; /bandwidth,
/weights and /uptime entries keyed by ``fingerprint`` (no ``f``/``n``);
consensus_weight(_fraction) and average_clients as period-keyed
history maps; /clients as per-bridge fingerprint + average_clients
histories with NO country field and an empty ``relays`` array.
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
            # Live Onionoo 8.0 shape (TASK-INT-047-FIX-01): entries are
            # keyed by ``fingerprint`` and carry NO ``n`` nickname and
            # NO short ``f`` key. Histories are period-keyed maps.
            "fingerprint": FP1,
            "write_history": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 1.0,
                    "values": [1200000, 1350000, 1100000],
                },
                "6_months": {
                    "first": "2026-05-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 1.0,
                    "values": [1000000, 1100000],
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
            # Live Onionoo 8.0 shape (TASK-INT-047-FIX-01):
            # ``fingerprint`` key; consensus_weight(_fraction) are
            # period-keyed history maps, not plain numbers.
            "fingerprint": FP1,
            "consensus_weight": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 14400,
                    "factor": 0.02,
                    "values": [990, 999],
                },
            },
            "consensus_weight_fraction": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 14400,
                    "factor": 1e-10,
                    "values": [880, 887],
                },
            },
        }
    ],
    "bridges": [],
}

CLIENTS_DOC = {
    "version": "9.0",
    "relays_published": "2026-11-27 04:00:00",
    "bridges_published": "2026-11-27 04:00:00",
    # Live Onionoo 8.0 shape (TASK-INT-047-FIX-01): ``relays`` is empty;
    # bridge entries carry ONLY ``fingerprint`` + ``average_clients``
    # (a period-keyed history map). NO country field exists.
    "relays": [],
    "bridges": [
        {
            "fingerprint": FP1,
            "average_clients": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 0.5,
                    "values": [100, 200],
                },
            },
        },
        {
            "fingerprint": FP2,
            "average_clients": {
                "1_month": {
                    "first": "2026-10-28 00:00:00",
                    "last": "2026-11-27 00:00:00",
                    "interval": 86400,
                    "factor": 1.0,
                    "values": [50, 60],
                },
            },
        },
    ],
}

UPTIME_DOC = {
    "version": "9.0",
    "relays_published": "2026-11-27 04:00:00",
    "bridges_published": "2026-11-27 04:00:00",
    "relays": [
        {
            # Live Onionoo 8.0 shape (TASK-INT-047-FIX-01): entries are
            # keyed by ``fingerprint`` and carry NO ``n`` nickname.
            "fingerprint": FP1,
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
    # Live /bandwidth carries no nickname field (TASK-INT-047-FIX-01).
    assert bw.nickname == ""
    assert bw.write_history is not None
    assert bw.write_history.period == "1_month"
    assert bw.write_history.values == [1200000, 1350000, 1100000]
    assert bw.read_history is not None
    assert bw.read_history.values == [900000, 950000, 880000]


@pytest.mark.asyncio
async def test_relay_bandwidth_matches_fingerprint_key_not_short_f():
    # TASK-INT-047-FIX-01: live /bandwidth entries are keyed by
    # ``fingerprint``; the old client matched the short ``f`` key
    # (which exists only in /summary) and raised for every relay.
    client = tm.TorMetricsClient(fetch=make_fetch({"/bandwidth": BANDWIDTH_DOC}))
    bw = await client.relay_bandwidth(FP1)
    assert bw.fingerprint == FP1
    assert bw.write_history is not None


@pytest.mark.asyncio
async def test_relay_bandwidth_short_f_key_still_matches():
    # Tolerance: an entry keyed by the old short ``f`` still matches.
    doc = {
        "version": "9.0",
        "relays_published": "2026-11-27 04:00:00",
        "bridges_published": "2026-11-27 04:00:00",
        "relays": [{"f": FP1, "n": "moria1", "write_history": BANDWIDTH_DOC["relays"][0]["write_history"]}],
        "bridges": [],
    }
    client = tm.TorMetricsClient(fetch=make_fetch({"/bandwidth": doc}))
    bw = await client.relay_bandwidth(FP1)
    assert bw.fingerprint == FP1
    assert bw.nickname == "moria1"


@pytest.mark.asyncio
async def test_relay_bandwidth_unknown_fingerprint_fails_closed():
    client = tm.TorMetricsClient(fetch=make_fetch({"/bandwidth": BANDWIDTH_DOC}))
    with pytest.raises(tm.TorMetricsUnavailable):
        await client.relay_bandwidth("0000000000000000000000000000000000000000")


@pytest.mark.asyncio
async def test_relay_weights_reports_consensus_weight():
    # TASK-INT-047-FIX-01: live consensus_weight(_fraction) are
    # period-keyed history maps; the scalars are the latest values
    # scaled by the history factor (999 * 0.02 = 20; 887 * 1e-10).
    client = tm.TorMetricsClient(fetch=make_fetch({"/weights": WEIGHTS_DOC}))
    weights = await client.relay_weights(FP1)
    assert weights.consensus_weight == 20
    assert weights.consensus_weight_fraction == pytest.approx(8.87e-08)
    # The full histories are preserved, not discarded.
    assert weights.consensus_weight_history is not None
    assert weights.consensus_weight_history.period == "1_month"
    assert weights.consensus_weight_history.values == [990, 999]
    assert weights.consensus_weight_fraction_history is not None
    assert weights.consensus_weight_fraction_history.values == [880, 887]


@pytest.mark.asyncio
async def test_relay_weights_plain_number_shape_still_passes_through():
    # Tolerance: a plain-number weight (the pre-fix assumed shape)
    # still parses instead of failing.
    doc = {
        "version": "9.0",
        "relays_published": "2026-11-27 04:00:00",
        "bridges_published": "2026-11-27 04:00:00",
        "relays": [{"fingerprint": FP1, "consensus_weight": 123456, "consensus_weight_fraction": 0.0021}],
        "bridges": [],
    }
    client = tm.TorMetricsClient(fetch=make_fetch({"/weights": doc}))
    weights = await client.relay_weights(FP1)
    assert weights.consensus_weight == 123456
    assert weights.consensus_weight_fraction == 0.0021
    assert weights.consensus_weight_history is None


@pytest.mark.asyncio
async def test_relay_weights_missing_weight_is_none_not_fabricated():
    doc = {
        "version": "9.0",
        "relays_published": "2026-11-27 04:00:00",
        "bridges_published": "2026-11-27 04:00:00",
        "relays": [{"fingerprint": FP1}],
        "bridges": [],
    }
    client = tm.TorMetricsClient(fetch=make_fetch({"/weights": doc}))
    weights = await client.relay_weights(FP1)
    assert weights.consensus_weight is None
    assert weights.consensus_weight_fraction is None


@pytest.mark.asyncio
async def test_relay_uptime_matches_fingerprint_key():
    # TASK-INT-047-FIX-01: live /uptime entries are keyed by
    # ``fingerprint`` (no ``f``, no ``n``).
    client = tm.TorMetricsClient(fetch=make_fetch({"/uptime": UPTIME_DOC}))
    uptime = await client.relay_uptime(FP1)
    assert uptime.fingerprint == FP1
    assert uptime.nickname == ""
    assert uptime.uptime is not None
    assert uptime.uptime.period == "1_month"
    assert uptime.uptime.values == [100, 100, 99]


def test_parse_history_prefers_1_month_over_6_months():
    # TASK-INT-047-FIX-01: live history maps now carry a ``6_months``
    # period; it must be parseable but lose to ``1_month``.
    raw = {
        "6_months": {
            "first": "2026-05-28 00:00:00",
            "last": "2026-11-27 00:00:00",
            "interval": 86400,
            "factor": 2.0,
            "values": [10, 20],
        },
        "1_month": {
            "first": "2026-10-28 00:00:00",
            "last": "2026-11-27 00:00:00",
            "interval": 86400,
            "factor": 1.0,
            "values": [1, 2, 3],
        },
    }
    hist = tm._parse_history(raw)
    assert hist is not None
    assert hist.period == "1_month"
    assert hist.values == [1, 2, 3]
    # And 6_months alone parses (period recorded).
    hist6 = tm._parse_history({"6_months": raw["6_months"]})
    assert hist6 is not None
    assert hist6.period == "6_months"
    assert hist6.values == [10, 20]
    assert hist6.factor == 2.0


# ---------------------------------------------------------------------------
# Clients (censorship metric) + snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_clients_returns_bridge_clients():
    # TASK-INT-047-FIX-01: live /clients carries per-BRIDGE average
    # clients only (fingerprint + average_clients history map, no
    # country field, relays empty). Scalars are latest values scaled
    # by the history factor: 200 * 0.5 = 100; 60 * 1.0 = 60.
    client = tm.TorMetricsClient(fetch=make_fetch({"/clients": CLIENTS_DOC}))
    rows = await client.network_clients()
    assert [r.fingerprint for r in rows] == [FP1, FP2]
    assert rows[0].average_clients == 100
    assert rows[1].average_clients == 60


@pytest.mark.asyncio
async def test_network_clients_empty_when_no_bridges():
    doc = {
        "version": "9.0",
        "relays_published": "2026-11-27 04:00:00",
        "bridges_published": "2026-11-27 04:00:00",
        "relays": [],
        "bridges": [],
    }
    client = tm.TorMetricsClient(fetch=make_fetch({"/clients": doc}))
    assert await client.network_clients() == []


@pytest.mark.asyncio
async def test_network_snapshot_combines_census_and_clients():
    docs = {"/summary": SUMMARY_DOC, "/clients": CLIENTS_DOC}
    client = tm.TorMetricsClient(fetch=make_fetch(docs))
    snapshot = await client.network_snapshot("moria", limit=10)
    assert snapshot.query == "moria"
    assert snapshot.running_relays == 2
    assert snapshot.running_bridges == 1
    assert len(snapshot.relays) == 3
    # TASK-INT-047-FIX-01: total is the sum of per-bridge average
    # clients (100 + 60 = 160); no per-country breakdown exists in
    # the live /clients document, so countries is empty.
    assert snapshot.total_average_clients == 160
    assert snapshot.countries == []
    assert [b.fingerprint for b in snapshot.bridge_clients] == [FP1, FP2]
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
    # TASK-INT-047-FIX-01: the total is bridge users (160), and the
    # text says so honestly (no per-country breakdown in /clients).
    assert "160" in source["text"]
    assert "bridges" in source["text"]
    assert "No per-country breakdown" in source["text"]


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
    # TASK-INT-047-FIX-01: the clients claim is the bridge-users total
    # (160), not a per-country row — /clients has no country field.
    assert any("via bridges" in c["text"] and "160" in c["text"] for c in claims)
    assert not any("countries" in c["text"] for c in claims)
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
