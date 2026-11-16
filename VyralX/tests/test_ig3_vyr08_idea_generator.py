"""TASK-IG3-VYR-08: viral YouTube idea generator (cluster
B125, IG source DdbljkbH5b2 — carousel automation 7).

Behaviour pinned here:

* analysis works on operator-supplied niche records only —
  the module makes no platform calls;
* engagement is computed ONLY from supplied numbers; a
  record without metrics carries None, never an estimate;
* ideas recombine the niche's proven keywords, carry the
  source titles they derive from, and rank deterministically
  (evidence first, hook score as tie-break);
* an idea whose sources are unmeasured says so in its basis;
* the router answers through the app pattern and app.main
  mounts it (AUDIT-2 production-caller standard).

On clean main every test fails: the module does not exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import idea_generator as ig

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")

_RECORDS = [
    {"title": "Jungle Hotel Animals: Cozy Cartoon Stories",
     "channel": "ToonNest", "views": 1_200_000,
     "likes": 48_000, "comments": 2_400},
    {"title": "Animals Run a Hotel — Cartoon Stories for Kids",
     "channel": "PawToons", "views": 800_000,
     "likes": 24_000, "comments": 800},
    {"title": "Cozy Jungle Stories: The Bear Chef's Big Day",
     "channel": "ToonNest", "views": 500_000,
     "likes": 10_000, "comments": 500},
    {"title": "Hotel Stories but the Staff Are All Animals",
     "channel": "WildReels"},
]


def test_analysis_extracts_keywords_and_measures_only_what_exists():
    analysis = ig.analyse_performers(_RECORDS)
    assert analysis["performer_count"] == 4
    assert analysis["measured_count"] == 3
    rates = {p["title"]: p["engagement_rate"]
             for p in analysis["performers"]}
    assert rates["Jungle Hotel Animals: Cozy Cartoon Stories"] == \
        round((48_000 + 2_400) / 1_200_000, 4)
    # The unmeasured record is reported as unmeasured.
    assert rates["Hotel Stories but the Staff Are All Animals"] \
        is None
    table = {k["keyword"]: k["performer_count"]
             for k in analysis["keywords"]}
    assert table["animals"] == 3
    assert table["hotel"] == 3
    assert table["stories"] == 4
    with pytest.raises(ValueError):
        ig.analyse_performers([])
    with pytest.raises(ValueError):
        ig.analyse_performers([{"views": 10}])


def test_generate_ideas_ranks_by_evidence_with_provenance():
    result = ig.generate_ideas(_RECORDS, max_ideas=5)
    ideas = result["ideas"]
    assert 0 < len(ideas) <= 5
    assert [i["rank"] for i in ideas] == list(range(1, len(ideas) + 1))
    scores = [i["evidence_score"] for i in ideas]
    assert scores == sorted(scores, reverse=True)
    for idea in ideas:
        assert idea["derived_from"], "every idea names its sources"
        assert idea["hook"]["score"] >= 0
        assert set(idea["keywords"]) <= {
            k["keyword"] for k in
            ig.analyse_performers(_RECORDS)["keywords"]}
    assert result["status"] == "pending_review"
    assert result["publish"] is False
    # Deterministic: same records, same ideas, same order.
    again = ig.generate_ideas(_RECORDS, max_ideas=5)
    assert [i["title"] for i in again["ideas"]] == \
        [i["title"] for i in ideas]


def test_unmeasured_sources_are_flagged_not_fabricated():
    records = [{"title": "Deep Sea Animals Hotel Stories"},
               {"title": "Animals Hotel Deep Sea Adventures"}]
    result = ig.generate_ideas(records, max_ideas=3)
    for idea in result["ideas"]:
        assert idea["measured_support"] == 0
        assert "unmeasured" in idea["basis"]


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(ig.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/idea-generator/policy")
    assert res.status_code == 200
    assert res.json()["publish"] is False
    assert "no platform" in res.json()["input"]

    res = client.post("/api/v1/idea-generator/analyse",
                      json={"records": _RECORDS})
    assert res.status_code == 200
    assert res.json()["performer_count"] == 4

    res = client.post("/api/v1/idea-generator/generate",
                      json={"records": _RECORDS, "max_ideas": 3})
    assert res.status_code == 200
    assert len(res.json()["ideas"]) == 3

    res = client.post("/api/v1/idea-generator/generate",
                      json={"records": []})
    assert res.status_code == 422

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.idea_generator import router as " \
        "idea_generator_router" in main_src
    assert "app.include_router(idea_generator_router" in main_src
