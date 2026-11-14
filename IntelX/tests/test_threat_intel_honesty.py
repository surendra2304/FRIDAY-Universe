"""
tests/test_threat_intel_honesty.py — TASK-REL-017 regression coverage.

Locks in the threat-intel honesty contract for the IntelX routers:

- Endpoints with NO real data source (dark-web scan, dynamic OSINT
  collect, threat forecast generation) return an explicit
  ``no_real_data_source`` state and invent nothing.
- Simulated implementations (universal crawler, adversary emulation,
  hunting query optimizer, OSINT phonebook, MalNet fallback) carry an
  unmistakable ``simulated`` label in the response payload itself.
- Numbers that used to be derived from md5 hashes of the input
  (campaign attribution confidence, pattern-match confidence, campaign
  forecast confidence) are now derived from the actual records or are 0.
- The real threat-intel engines (``/v1/real-threat-intel/*``) are mounted
  and compute over caller-supplied data / the persistent store only.
"""

import pytest


@pytest.fixture
def no_upstream_keys(monkeypatch):
    monkeypatch.delenv("INTELX_API_KEY", raising=False)
    monkeypatch.delenv("MALNET_API_KEY", raising=False)


# ── Tier A: fabricators now return an honest no-source state ──────────────


async def test_darkweb_scan_admits_no_data_source(client):
    resp = await client.post("/api/v1/intelex/darkweb/scan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "no_real_data_source"
    assert body["data_source"] == "none_connected"
    assert body["leaks_found"] == 0
    assert body["new_leaks"] == 0
    assert body["credentials_found"] == 0
    assert body["sources_scanned"] == []


async def test_darkweb_submitted_leak_is_not_auto_verified(client):
    resp = await client.post(
        "/api/v1/intelex/darkweb/leaks",
        json={"source": "operator-report", "description": "alleged dump"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False
    assert body["data_source"] == "operator_submitted"

    report = (await client.get("/api/v1/intelex/darkweb/report")).json()
    assert report["data_source"] == "operator_submitted_records_only"
    assert report["live_feed_connected"] is False


async def test_osint_collect_admits_no_collectors(client):
    resp = await client.post(
        "/api/v1/intelex/osint/collect",
        json={"target": "example.com", "target_type": "domain"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "no_real_data_source"
    assert body["data_source"] == "none_connected"
    assert body["total_findings"] == 0
    assert body["sources_queried"] == 0
    assert body["sources_successful"] == 0
    assert body["errors"]  # every registered source explains itself


async def test_osint_sources_say_no_collector_connected(client):
    sources = (await client.get("/api/v1/intelex/osint/sources")).json()
    assert sources
    assert all(s["collector_connected"] is False for s in sources)

    first = sources[0]
    rel = (
        await client.get(f"/api/v1/intelex/osint/sources/{first['source_id']}/reliability")
    ).json()
    assert "unmeasured" in rel["basis"]


async def test_forecast_generate_admits_no_data_source(client):
    resp = await client.post("/intelex/forecast/generate", params={"threat_type": "ransomware"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "no_real_data_source"
    assert body["data_source"] == "none_connected"
    assert body["predicted_severity"] is None
    assert body["confidence"] is None


# ── Tier B: simulated implementations are labelled in the payload ─────────


async def test_crawler_payloads_labelled_simulated(client):
    start = (
        await client.post(
            "/api/v1/intelex/crawl/start", json={"start_url": "https://example.com"}
        )
    ).json()
    assert start["simulated"] is True
    assert start["data_source"] == "simulated"

    results = (
        await client.get(f"/api/v1/intelex/crawl/{start['crawl_id']}/results")
    ).json()
    assert results["simulated"] is True

    stats = (await client.get(f"/api/v1/intelex/crawl/{start['crawl_id']}/stats")).json()
    assert stats["simulated"] is True

    report = (await client.get("/api/v1/intelex/crawl/report")).json()
    assert report["simulated"] is True


async def test_emulation_payloads_labelled_simulated(client):
    from routers.adversary_emulation_engine import emulation_engine

    profile = (
        await client.post(
            "/api/v1/intelex/emulation/profiles", json={"name": "REL017 probe actor"}
        )
    ).json()
    plan = (
        await client.post(
            "/api/v1/intelex/emulation/plans",
            json={"profile_id": profile["profile_id"], "name": "REL017 plan"},
        )
    ).json()
    phase = next(p for p in emulation_engine._phases if p.plan_id == plan["plan_id"])

    executed = (
        await client.post(f"/api/v1/intelex/emulation/phases/{phase.phase_id}/execute")
    ).json()
    assert executed["simulated"] is True
    assert executed["data_source"] == "simulated_no_target_systems"

    gaps = (
        await client.get(f"/api/v1/intelex/emulation/plans/{plan['plan_id']}/gaps")
    ).json()
    assert gaps["simulated"] is True
    assert "hypothesised" in gaps["basis"]

    report = (await client.get("/api/v1/intelex/emulation/report")).json()
    assert report["simulated"] is True


async def test_hunting_payloads_labelled_simulated(client):
    query = (
        await client.post(
            "/intelex/hunting-optimize/queries",
            params={"name": "REL017 hunt", "query_text": "SELECT 1"},
        )
    ).json()
    run = (
        await client.post(
            f"/intelex/hunting-optimize/queries/{query['query_id']}/run",
            params={"results_count": 3},
        )
    ).json()
    assert run["simulated"] is True
    assert run["data_source"] == "simulated_no_query_executed"

    optimized = (
        await client.post(f"/intelex/hunting-optimize/queries/{query['query_id']}/optimize")
    ).json()
    assert optimized["simulated"] is True

    listing = (await client.get("/intelex/hunting-optimize/queries")).json()
    assert listing["simulated"] is True


# ── Tier C: hash-invented numbers replaced by record-derived values ───────


async def test_campaign_attribution_confidence_starts_at_zero(client):
    from routers.threat_campaign_tracker import campaign_tracker

    created = (
        await client.post(
            "/api/v1/intelex/campaigns",
            json={"name": "REL017 campaign", "threat_actor": "Some Actor"},
        )
    ).json()
    campaign = campaign_tracker._campaigns[created["campaign_id"]]
    assert campaign.attribution_confidence == 0.0
    # No invented default target sectors/regions either.
    assert campaign.target_sectors == []
    assert campaign.target_regions == []

    prediction = (
        await client.post(f"/api/v1/intelex/campaigns/{created['campaign_id']}/predict")
    ).json()
    # No recorded events -> no basis for any confidence.
    assert prediction["confidence"] == 0.0
    assert prediction["basis"] == "heuristic_over_operator_recorded_events_only"


async def test_correlation_actor_has_no_invented_attributes(client):
    from routers.threat_intel_correlation_engine import correlation_engine

    created = (
        await client.post(
            "/api/v1/intelex/correlation/actors", json={"name": "REL017 actor"}
        )
    ).json()
    actor = correlation_engine._actors[created["actor_id"]]
    assert actor.sophistication == "unknown"
    assert actor.target_sectors == []
    assert actor.techniques == []
    assert actor.confidence == 0.0


async def test_pattern_match_confidence_equals_measured_fraction(client):
    ioc_a = (
        await client.post(
            "/api/v1/intelex/correlation/iocs",
            json={"value": "203.0.113.10", "type": "ip"},
        )
    ).json()
    match = (
        await client.post(
            "/api/v1/intelex/correlation/patterns",
            json={
                "pattern_id": "rel017-pattern",
                "pattern_name": "REL017 pattern",
                "iocs": [ioc_a["ioc_id"], "nonexistent-ioc"],
            },
        )
    ).json()
    assert match["score"] == 0.5  # 1 of 2 supplied IoCs exist


async def test_predictive_predictions_carry_basis(client):
    await client.post(
        "/api/v1/intelex/threat/indicators",
        json={
            "value": "203.0.113.99",
            "type": "ip",
            "confidence": 0.9,
            "severity": "high",
        },
    )
    predictions = (await client.get("/api/v1/intelex/threat/predict")).json()
    assert predictions
    assert all(
        p["basis"] == "heuristic_over_operator_supplied_records_only" for p in predictions
    )


async def test_campaign_predictor_confidence_not_invented(client):
    await client.post("/intelx/campaign/phases", params={"name": "recon"})
    await client.post("/intelx/campaign/phases", params={"name": "initial-access"})
    forecast = (
        await client.post("/intelx/campaign/forecast", params={"actor": "REL017 actor"})
    ).json()
    # Registered phases carry no probabilities -> no basis for confidence.
    assert forecast["confidence"] == 0.0
    assert forecast["data_source"] == "operator_registered_phases_only"

    assessment = (
        await client.post("/intelx/campaign/assess", params={"threat_level": "high"})
    ).json()
    assert "static_playbook" in assessment["basis"]


def test_campaign_predictor_confidence_is_mean_of_supplied_probabilities():
    """Confidence must be a transparent function of operator input."""
    from intelx.services.threat_campaign_predictor import ThreatCampaignPredictor

    engine = ThreatCampaignPredictor()
    assert engine.forecast_campaign("APT-TEST").confidence == 0.0
    engine.add_phase("Reconnaissance", "scanning", start_probability=0.8, duration_estimate=7200)
    engine.add_phase("Exploitation", "access", start_probability=0.5, duration_estimate=3600)
    forecast = engine.forecast_campaign("APT-TEST", "Reconnaissance")
    assert forecast.confidence == 0.65  # mean(0.8, 0.5), not 0.15 * 2 phases


# ── Real engines mounted: /v1/real-threat-intel/* ──────────────────────────


async def test_real_threat_router_mounted_and_engines_loaded(client):
    status = (await client.get("/v1/real-threat-intel/status")).json()
    names = {e["name"] for e in status["engines"]}
    assert {"graph", "advanced_threat", "deep_threat", "threat_engine"} <= names


async def test_real_pagerank_computes_over_caller_graph(client):
    resp = await client.post(
        "/v1/real-threat-intel/graph/pagerank",
        json={"graph": {"nodes": ["a", "b", "c"], "edges": [["a", "b"], ["b", "c"], ["c", "a"]]}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_source"] == "caller_supplied_graph"
    assert set(body["result"].keys()) == {"a", "b", "c"}
    assert abs(sum(body["result"].values()) - 1.0) < 0.01


async def test_real_darkweb_formats_only_caller_asserted_data(client):
    empty = (
        await client.post("/v1/real-threat-intel/advanced/darkweb", json={"source_data": {}})
    ).json()
    assert empty["result"] == []
    assert empty["live_feed_connected"] is False

    flagged = (
        await client.post(
            "/v1/real-threat-intel/advanced/darkweb",
            json={"source_data": {"has_credentials": True, "count": 5, "source": "op-report"}},
        )
    ).json()
    assert flagged["data_source"] == "caller_supplied_source_data"
    assert len(flagged["result"]) == 1
    assert flagged["result"][0]["content_type"] == "credentials"


async def test_real_forecast_uses_caller_history(client):
    body = (
        await client.post(
            "/v1/real-threat-intel/deep/forecast",
            json={"threat_type": "ransomware", "historical": []},
        )
    ).json()
    assert body["data_source"] == "caller_supplied_history"
    # Engine's explicit no-history baseline, not a fabricated forecast.
    assert body["result"]["probability"] == 0.3
    assert body["result"]["confidence"] == 0.2


async def test_real_engine_analyze_reads_persistent_store(client):
    body = (await client.post("/v1/real-threat-intel/engine/analyze", json={})).json()
    assert body["data_source"] == "intelx_persistent_indicator_store"
    assert "stats" in body["result"]
    assert "threat_feed" in body["result"]


# ── Mounted real-OSINT surface: remaining unlabelled fallbacks fixed ──────


async def test_phonebook_labelled_simulated_and_no_longer_500(client, no_upstream_keys):
    resp = await client.post(
        "/api/v1/intelx/osint/phonebook", json={"target": "example.com", "type": "domain"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "simulated"
    assert body["simulated"] is True
    assert body["data_source"] == "synthetic_fallback"


async def test_malnet_fallback_labelled_simulated(client, no_upstream_keys):
    body = (
        await client.post(
            "/api/v1/intelx/malnet/correlate", json={"indicator": "203.0.113.7"}
        )
    ).json()
    assert body["simulated"] is True
    assert body["data_source"] == "synthetic_fallback"
    assert body["intelligence"]["simulated"] is True


async def test_maltego_graph_labels_built_in_sample(client):
    sample = (await client.post("/api/v1/intelx/maltego/graph", json={})).json()
    assert sample["data_source"] == "built_in_sample"

    supplied = (
        await client.post(
            "/api/v1/intelx/maltego/graph",
            json={"entities": [{"value": "198.51.100.3", "type": "IPv4Address"}], "relationships": []},
        )
    ).json()
    assert supplied["data_source"] == "caller_supplied"
