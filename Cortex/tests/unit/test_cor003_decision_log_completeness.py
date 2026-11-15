"""TASK-COR-003 — decision-log completeness.

Every decision Cortex records must carry a complete provenance record:
the inputs considered, the options weighed, the decider, and the outcome
(plus a timestamp). These tests exercise the *stored* records — not the
API responses (that disclosure side is TASK-COR-002) — across the three
logging paths:

- ``real_decision_engine`` — the persisted ``decision_history.json`` log;
- ``decision_recommendation_system`` — the in-memory recommendation log;
- ``cortex_core.governed_operations`` — the governed recommendation chain.

On clean main every test here fails: the persisted record kept only six
summary fields, the recommendation record had no timestamp/decider/input
snapshot, and the governed engine discarded its Observation inputs.
"""

from __future__ import annotations

import json

import pytest
from cortex_api.decision_recommendation_system import DecisionRecommendationSystem
from cortex_api.real_decision_engine import DecisionEngine
from cortex_core.governed_operations import GovernedOperationsEngine
from cortex_core.web_property import WebProperty


# ── real_decision_engine: the persisted decision log ─────────────────────────

def _decide_once(engine: DecisionEngine):
    return engine.decide(
        question="cor003: pick a deployment window",
        options=[
            {"name": "weekday", "scores": {"risk": 80, "speed": 60},
             "risks": ["user traffic"], "benefits": ["fast rollback"]},
            {"name": "weekend", "scores": {"risk": 40, "speed": 90},
             "risks": [], "benefits": ["low traffic", "long window"]},
        ],
        criteria=[
            {"name": "risk", "weight": 0.6, "description": "lower is safer"},
            {"name": "speed", "weight": 0.4},
        ],
        decider="cor003-test",
    )


def test_persisted_decision_record_is_complete(tmp_path):
    state = tmp_path / "decision_history.json"
    engine = DecisionEngine(state_file=str(state))
    result = _decide_once(engine)

    (record,) = json.loads(state.read_text())
    assert record["decision_id"] == result.decision_id
    assert record["timestamp"] > 0
    # decider
    assert record["decider"] == "cor003-test"
    # inputs considered: criteria with weights, options with their scores
    assert {c["name"] for c in record["inputs"]["criteria"]} == {"risk", "speed"}
    assert {c["name"]: c["weight"] for c in record["inputs"]["criteria"]} == {
        "risk": 0.6, "speed": 0.4}
    options = {o["name"]: o for o in record["inputs"]["options"]}
    assert options["weekday"]["scores"] == {"risk": 80, "speed": 60}
    assert options["weekend"]["benefits"] == ["low traffic", "long window"]
    # options weighed: the full ranking, not just the winner
    assert {r["option"] for r in record["options_weighed"]["ranking"]} == {
        "weekday", "weekend"}
    assert record["options_weighed"]["total_scores"].keys() == {
        "weekday", "weekend"}
    assert record["reasoning"]
    # outcome: the selection, with an outcome slot awaiting the observed result
    assert record["outcome"]["selected"] == record["best_option"]
    assert record["outcome"]["status"] == "decided"
    assert record["outcome"]["observed_result"] is None


def test_record_outcome_roundtrip(tmp_path):
    state = tmp_path / "decision_history.json"
    engine = DecisionEngine(state_file=str(state))
    result = _decide_once(engine)

    assert engine.record_outcome(result.decision_id, "deployed cleanly",
                                 success=True) is True
    assert engine.record_outcome("dec_missing", "n/a") is False

    reloaded = DecisionEngine(state_file=str(state))
    (record,) = reloaded.get_history()
    assert record["outcome"]["status"] == "outcome_recorded"
    assert record["outcome"]["observed_result"] == "deployed cleanly"
    assert record["outcome"]["success"] is True
    assert record["outcome"]["recorded_at"] > 0


def test_legacy_six_field_record_still_loads_and_upgrades(tmp_path):
    state = tmp_path / "decision_history.json"
    legacy = [{
        "decision_id": "dec_legacy", "question": "old decision",
        "best_option": "weekday", "risk_level": "low",
        "confidence": 0.75, "timestamp": 1700000000.0,
    }]
    state.write_text(json.dumps(legacy))

    engine = DecisionEngine(state_file=str(state))
    assert engine.get_history()[0]["decision_id"] == "dec_legacy"
    # The patterns reader relies on the legacy top-level keys.
    assert engine.get_decision_patterns()["total_decisions"] == 1
    # An outcome can be attached to a legacy record in place.
    assert engine.record_outcome("dec_legacy", "worked", success=True) is True
    (record,) = json.loads(state.read_text())
    assert record["outcome"]["observed_result"] == "worked"


# ── decision_recommendation_system: the in-memory recommendation log ─────────

def _recommend_once(system: DecisionRecommendationSystem):
    cost = system.add_criterion("cost", weight=2.0, direction="minimize")
    quality = system.add_criterion("quality", weight=1.0, direction="maximize")
    alt_a = system.add_alternative("A", risk_score=0.2, return_projection=0.9)
    alt_b = system.add_alternative("B", risk_score=0.8, return_projection=0.4)
    system.score_alternative(alt_a.alternative_id, cost.criterion_id, 0.2)
    system.score_alternative(alt_a.alternative_id, quality.criterion_id, 0.9)
    system.score_alternative(alt_b.alternative_id, cost.criterion_id, 0.8)
    # B is deliberately left unscored on quality: that cell defaults to 0.5.
    rec = system.recommend("cor003: choose a vendor", decider="cor003-test")
    return rec, alt_b, quality


def test_recommendation_record_is_complete():
    system = DecisionRecommendationSystem()
    rec, alt_b, quality = _recommend_once(system)

    assert rec.created_at > 0
    assert rec.decider == "cor003-test"
    snapshot = rec.inputs_snapshot
    assert {c["name"] for c in snapshot["criteria"]} == {"cost", "quality"}
    alternatives = {a["name"]: a for a in snapshot["alternatives"]}
    assert alternatives["A"]["criteria_scores"] != {}
    # The one unscored cell is named in the record as defaulted.
    assert snapshot["defaulted_cells"] == [
        f"{alt_b.alternative_id}:{quality.criterion_id}"]
    # Options weighed: full ranking present on the record.
    assert {r["name"] for r in rec.alternatives_ranking} == {"A", "B"}
    # Outcome slot: selection recorded, observed result awaited.
    assert rec.outcome["selected"] == rec.best_alternative
    assert rec.outcome["observed_result"] is None


def test_recommendation_record_outcome_can_be_attached():
    system = DecisionRecommendationSystem()
    rec, _, _ = _recommend_once(system)

    assert system.record_outcome(rec.recommendation_id, "vendor A delivered",
                                 success=True) is True
    assert system.record_outcome("missing", "n/a") is False
    assert rec.outcome["status"] == "outcome_recorded"
    assert rec.outcome["observed_result"] == "vendor A delivered"
    assert rec.outcome["recorded_at"] > 0


# ── governed_operations: the governed recommendation chain ───────────────────

def _governed_engine() -> GovernedOperationsEngine:
    engine = GovernedOperationsEngine()
    engine.registry.register(
        WebProperty(
            property_id="site_cor003",
            name="COR-003 test site",
            allowed_domains=["example.com"],
            allowed_operations=["banner_injection"],
            target_environment="staging",
            approval_policy={},
            rollback_policy={},
            state_snapshot={},
        )
    )
    return engine


def test_governed_decision_record_is_complete():
    engine = _governed_engine()
    observation = engine.observe(
        "site_cor003", {"visitors": 1200, "conversion_rate": 3.1,
                        "source": "cor003-test"})
    rec = engine.recommend(
        observation, proposed_action="banner_injection",
        params={"variant": "annual_discount_banner"},
        rationale="Lift conversions", confidence=0.8,
        expected_outcomes={"conversion_lift_pct": 5.0})
    approval = engine.authorize(rec.recommendation_id,
                                approver_id="usr_supervisor",
                                reason="Worth the test")
    execution = engine.execute(approval.approval_id, "cor003-idem-1",
                               tool_bus=None, dry_run=True)
    engine.measure(execution.execution_id,
                   observed_telemetry={"conversion_lift_pct": 6.0})

    record = engine.decision_record(rec.recommendation_id)
    assert record is not None
    # inputs considered: the actual telemetry behind the decision
    assert record["inputs"]["telemetry"]["visitors"] == 1200
    assert record["inputs"]["observation_id"] == observation.observation_id
    # the option proposed, with its rationale
    assert record["option_considered"]["proposed_action"] == "banner_injection"
    assert record["option_considered"]["rationale"] == "Lift conversions"
    # decider
    assert record["decision"]["decider"] == "usr_supervisor"
    assert record["decision"]["approved"] is True
    assert record["decision"]["decided_at"]
    # outcome: execution + measured observed outcomes
    (exec_record,) = record["outcome"]["executions"]
    assert exec_record["status"] == "SIMULATED"
    (measurement,) = exec_record["measurements"]
    assert measurement["observed_outcomes"] == {"conversion_lift_pct": 6.0}


def test_governed_decision_record_rejection_and_unknown():
    engine = _governed_engine()
    observation = engine.observe("site_cor003", {"visitors": 10})
    rec = engine.recommend(
        observation, proposed_action="banner_injection", params={},
        rationale="Try it", confidence=0.5, expected_outcomes={})
    engine.reject(rec.recommendation_id, approver_id="usr_supervisor",
                  reason="Risk too high")

    record = engine.decision_record(rec.recommendation_id)
    assert record["decision"]["approved"] is False
    assert record["decision"]["decider"] == "usr_supervisor"
    assert record["decision"]["reason"] == "Risk too high"
    assert record["outcome"]["executions"] == []
    assert engine.decision_record("rec_missing") is None
