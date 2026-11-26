"""TASK-INF-042: verified free-tier route catalogue — guardrails.

The six claimed $0 routes from the DTVYncBj6E1 carousel (package I-10 /
VyralX V-06) were checked live against the vendors' own pricing/terms
pages on 2026-11-25. Net result: ZERO verify as free API capacity —
Sora 2 is discontinued, MiniMax / NanoBanana / Wan 2.6 are paid-only,
and the two verified-free entries (SadTalker, Gamma) are not API routes
at all. MiniMax is therefore NOT wired: the task's "wired if verified
free" condition fails, and the candidate spec stays BLOCKED_NO_CREDENTIALS.

These tests pin that state. They are stdlib-only (json + pathlib +
the benchmarks loader, which is itself stdlib-only at import time) and
read the real files from the repo tree — no mocks, no network.

A verdict changes only on a new dated first-party read, recorded in
Inference/config/free_tier_routes.json and in
docs/collaboration/TASK-INF-042-FREE-TIER-ROUTE-CATALOGUE.md.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOGUE = REPO / "Inference" / "config" / "free_tier_routes.json"
MINIMAX_SPEC = REPO / "Inference" / "benchmarks" / "candidates" / "minimax.json"
SUBSTITUTION_TABLE = REPO / "Inference" / "docs" / "FREE_SUBSTITUTION_TABLE.md"
PROVIDERS_DIR = REPO / "Inference" / "app" / "providers"

ALLOWED_VERDICTS = {"verified-free", "paid-only", "rejected"}
# The six free alternatives named verbatim in the carousel (§2 of the table).
EXPECTED_IDS = ["sora-2", "minimax", "nanobanana", "wan-2-6", "sadtalker", "gamma"]


def _load_catalogue():
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    assert data["catalogue"] == "TASK-INF-042"
    assert data["verified_on"] == "2026-11-25"
    assert data["verified_by"] == "Muse 4"
    return data


def test_catalogue_covers_all_six_carousel_routes():
    routes = _load_catalogue()["routes"]
    assert [r["id"] for r in routes] == EXPECTED_IDS


def test_every_route_has_a_verdict_in_the_allowed_vocabulary():
    for route in _load_catalogue()["routes"]:
        assert route["verdict"] in ALLOWED_VERDICTS, route["id"]
        assert route["verdict_detail"].strip(), route["id"]
        assert route["first_party_url"].startswith("https://"), route["id"]
        assert route["evidence"]["checked"] == "2026-11-25", route["id"]
        assert route["evidence"]["findings"], route["id"]
        assert route["free_route"] and route["paid_counterpart"], route["id"]


def test_nothing_is_wired():
    # The catalogue is knowledge, not capacity. No entry may ever be
    # marked wired without a new dated first-party read re-verifying it.
    for route in _load_catalogue()["routes"]:
        assert route["wired"] is False, route["id"]


def test_no_verified_free_route_is_an_api_route():
    # The two verified-free entries (SadTalker: free software; Gamma:
    # consumer plan) are not API routes, so nothing verified-free can
    # be promoted into Inference fallback capacity by mistake.
    for route in _load_catalogue()["routes"]:
        if route["verdict"] == "verified-free":
            assert route["api_route"] is False, route["id"]
    verified_free_api = [r["id"] for r in _load_catalogue()["routes"]
                         if r["verdict"] == "verified-free" and r["api_route"]]
    assert verified_free_api == []


def test_minimax_is_paid_only_and_not_wired():
    spec = json.loads(MINIMAX_SPEC.read_text(encoding="utf-8"))
    assert spec["free_tier_verdict"] == "paid-only"
    assert "platform.minimax.io/docs/pricing/overview" in spec["free_tier_evidence"]
    assert "BLOCKED_NO_CREDENTIALS" in spec["notes"]
    route = next(r for r in _load_catalogue()["routes"] if r["id"] == "minimax")
    assert route["verdict"] == spec["free_tier_verdict"]
    assert route["wired"] is False


def test_minimax_spec_still_loads_through_the_pipeline():
    # CandidateSpec.from_dict ignores unknown keys, so the two new
    # verdict fields must not break the IG-INF-03 loader.
    sys.path.insert(0, str(REPO / "Inference" / "benchmarks"))
    from candidate_eval import CandidateSpec

    spec = CandidateSpec.load(MINIMAX_SPEC)
    assert spec.candidate == "minimax-m3"
    assert spec.model_id == "MiniMax-M3"
    assert spec.provider == "minimax"
    assert spec.api_key_env == "MINIMAX_API_KEY"


def test_no_minimax_provider_adapter_exists():
    # Standing design (FREE_SUBSTITUTION_TABLE §2): MiniMax stays
    # spec-only — no provider adapter in Inference.
    assert not list(PROVIDERS_DIR.glob("minimax*.py"))
    for name in ("gateway.py", "unified_manager.py", "capabilities.py"):
        text = (PROVIDERS_DIR / name).read_text(encoding="utf-8")
        assert "minimax" not in text.lower(), name


def test_substitution_table_keeps_the_verbatim_carousel_rows():
    # §2 is the carousel's own claims, recorded as written. The live
    # verdicts live in §4 and in the JSON catalogue — §2 must not have
    # been rewritten to hide the original $0 claims.
    text = SUBSTITUTION_TABLE.read_text(encoding="utf-8")
    for name in ("Sora 2", "MiniMax", "NanoBanana", "Wan 2.6", "SadTalker", "Gamma AI"):
        assert name in text, name
    assert "Zero rows are verified free capacity" in text
    assert "## 4. Live verdicts (TASK-INF-042, 2026-11-25)" in text
    assert "0 of 6 routes verify as free" in text
    assert "MiniMax is NOT wired" in text


def test_sora_2_is_rejected_not_paid_only():
    # Discontinued is stronger than paid-only: there is no Sora 2 route
    # at any price, so the verdict must stay "rejected", never "paid-only".
    route = next(r for r in _load_catalogue()["routes"] if r["id"] == "sora-2")
    assert route["verdict"] == "rejected"
    assert "discontinued" in route["verdict_detail"]
    assert route["api_route"] is False
