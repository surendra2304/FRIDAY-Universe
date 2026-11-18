"""TASK-STR-EXP-001 — Stratex self-experiment loop.

Pins:
1. GATES: kill switch (STRATEX_SELF_EXPERIMENTS must be exactly "on";
   default off), host-load gate, work-probe gate, daily cap.
2. PRE-DECLARATION: a run with no declaration, or with a proposal
   whose hash differs from its declaration, is refused.
3. COUNTER: seeded at 3,899 from the recorded programme counter,
   persistent, monotonic, refuses a below-seed file; increments
   before judgement (the cycle's trial number is seed+1).
4. JUDGE: the frozen bars — full bar PROVEN, second tier
   FORWARD_TEST, everything else FAIL; holdout absence caps a
   combination at FORWARD_TEST.
5. ADMISSION: a passing combination is written to the admissions
   registry in the FWD-003 shape with the frozen lane terms; the
   merged registry view classifies it FORWARD_TEST through the
   daemon's OWN governance function; collisions with governed
   entries are refused; admissions are reversible.
6. BOUNDS: risk-touch payloads are refused at declaration and at
   admission; a FAIL verdict can never be admitted.
7. LESSONS: every verdict banks a private procedural lesson; FAIL
   also banks a universal one (owner rule R); pending deliveries are
   retried.
8. STORE: provenance hashes are verified at load; the shipped
   fixture's figures reproduce the research record (bollinger_trend
   p50_sd2.0: 420 OOS trades, PF 1.4562, expectancy +3.5448%).
9. GREEDY: every candidate evaluation is a counted trial.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from self_experiments import bounds, catalogue
from self_experiments.admissions import (
    AdmissionError,
    AdmissionsRegistry,
    merged_registry,
)
from self_experiments.bounds import RiskTouchRefused, assert_no_risk_touch
from self_experiments.counter import CounterError, TrialCounter
from self_experiments.judge import judge
from self_experiments.ledger import DeclarationRequired, ExperimentLedger
from self_experiments.lessons import FabricLessonWriter
from self_experiments.loop import SelfExperimentLoop
from self_experiments.runner import PooledMetrics, pooled_metrics
from self_experiments.store import StreamStore, StoreError

FIXTURE_STORE = (
    Path(__file__).parent / "fixtures" / "selfexp_stream_store"
)

BOLLINGER = "bollinger_trend/p50_sd2.0@crypto30/1d"
SHOCK = "shock_breakout/k1.0@crypto30/1d"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingWriter:
    """A lesson writer that records deliveries instead of sending."""

    def __init__(self, succeed: bool = True):
        self.calls: list[tuple[str, dict, bool]] = []
        self.succeed = succeed

    def deliver(self, content, metadata, *, universal):
        self.calls.append((content, metadata, universal))
        return self.succeed


def make_loop(tmp_path, store=None, writer=None, **kwargs):
    kwargs.setdefault("work_probe", lambda: True)
    return SelfExperimentLoop(
        store=store or StreamStore(FIXTURE_STORE),
        data_dir=tmp_path / "loop_data",
        lesson_writer=writer or RecordingWriter(),
        **kwargs,
    )


def calm_load(monkeypatch):
    monkeypatch.setattr(os, "getloadavg", lambda: (0.1, 0.1, 0.1))


def synthetic_store(tmp_path, streams: dict[str, list[float]]):
    """A minimal verified store built in tmp_path from raw returns.

    streams: {stream_id-ish name: returns}; each stream gets the five
    folds by slicing its returns, panel crypto30, timeframe 1d, no
    holdout (so PROVEN is unreachable — FORWARD_TEST is the ceiling).
    """
    store_dir = tmp_path / "synthetic_store"
    (store_dir / "streams").mkdir(parents=True)
    manifest = {"streams": {}}
    families = ["fam_a", "fam_b", "fam_c", "fam_d"]
    for idx, (name, returns) in enumerate(sorted(streams.items())):
        family = families[idx % len(families)]
        stream_id = f"{family}/{name}@crypto30/1d"
        per = max(1, len(returns) // 5)
        folds = {
            f"W{i+1}": returns[i * per : (i + 1) * per] for i in range(4)
        }
        folds["W5"] = returns[4 * per :]
        payload = {
            "stream_id": stream_id,
            "family": family,
            "variant": name,
            "panel": "crypto30",
            "timeframe": "1d",
            "cluster": "trend",
            "admission": "TIER_ADMITTED",
            "costs_rt_bps": 16.0,
            "folds": folds,
            "fold_windows": {
                f"W{i+1}": ["2024-07-01", "2026-07-01"] for i in range(5)
            },
            "holdout": None,
            "recorded_trades": len(returns),
            "recorded_expectancy": (
                sum(returns) / len(returns) if returns else 0.0
            ),
            "recorded_pf": 1.1,
            "source_record": {
                "file": "synthetic.json",
                "sha256": "0" * 64,
                "round": "TEST",
            },
        }
        rel = f"streams/{name}.json"
        blob = json.dumps(payload).encode("utf-8")
        (store_dir / rel).write_bytes(blob)
        manifest["streams"][stream_id] = {
            "file": rel,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "source_record": payload["source_record"],
        }
    (store_dir / "manifest.json").write_text(json.dumps(manifest))
    return StreamStore(store_dir)


def metrics(**overrides) -> PooledMetrics:
    base = dict(
        members=("a", "b"),
        trades=500,
        wins=220,
        expectancy=0.01,
        pf=1.30,
        gross_profit=130.0,
        gross_loss=100.0,
        per_fold={f"W{i}": {"trades": 100, "expectancy": 0.01} for i in range(1, 6)},
        positive_folds=5,
        folds_with_trades=5,
        holdout_trades=100,
        holdout_expectancy=0.01,
        t_stat=6.0,
        p_one_sided=1e-9,
    )
    base.update(overrides)
    return PooledMetrics(**base)


# ---------------------------------------------------------------------------
# Store provenance + fixture fidelity
# ---------------------------------------------------------------------------


def test_fixture_store_verifies_and_matches_the_record():
    store = StreamStore(FIXTURE_STORE)
    bollinger = store.stream(BOLLINGER)
    # The research record (config_strategy FWD-003 reason + RD-002
    # synthesis): 420 OOS trades, PF 1.4562, expectancy +3.5448%.
    assert bollinger.recorded_trades == 420
    assert bollinger.recorded_pf == pytest.approx(1.4562, abs=1e-4)
    assert bollinger.recorded_expectancy == pytest.approx(0.035448, abs=1e-6)
    assert bollinger.admission == "FORWARD_TEST"
    shock = store.stream(SHOCK)
    assert shock.recorded_trades == 732
    assert shock.recorded_pf == pytest.approx(1.3179, abs=1e-4)
    # Pooled metrics over the stored trades reproduce the same figures.
    pooled = pooled_metrics([bollinger])
    assert pooled.trades == 420
    assert pooled.pf == pytest.approx(1.4562, abs=1e-4)


def test_store_refuses_tampered_stream(tmp_path):
    import shutil

    target = tmp_path / "store"
    shutil.copytree(FIXTURE_STORE, target)
    victim = target / "streams" / (
        "bollinger_trend__p50_sd2.0__at__crypto30__1d.json"
    )
    data = json.loads(victim.read_text())
    data["folds"]["W1"][0] = 9.99  # rewrite history
    victim.write_text(json.dumps(data))
    with pytest.raises(StoreError):
        StreamStore(target)


# ---------------------------------------------------------------------------
# Counter
# ---------------------------------------------------------------------------


def test_counter_seed_persistence_and_monotonicity(tmp_path):
    path = tmp_path / "counter.json"
    counter = TrialCounter(path)
    assert counter.value == 3899
    recorded = json.loads(path.read_text())
    assert recorded["seed"] == 3899
    assert "3,899" in recorded["seed_source"]
    assert counter.next() == 3900
    assert TrialCounter(path).value == 3900  # persists across instances


def test_counter_refuses_below_seed_file(tmp_path):
    path = tmp_path / "counter.json"
    path.write_text(json.dumps({"value": 12}))
    with pytest.raises(CounterError):
        TrialCounter(path)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def test_kill_switch_default_off_and_exact_on(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATEX_SELF_EXPERIMENTS", raising=False)
    loop = make_loop(tmp_path)
    assert loop.run_one_cycle().reason == "kill_switch_off"
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "off")
    assert loop.run_one_cycle().reason == "kill_switch_off"
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "yes")
    assert loop.run_one_cycle().reason == "kill_switch_off"
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    loop2 = make_loop(tmp_path / "b", work_probe=lambda: False)
    assert loop2.run_one_cycle().reason == "work_in_progress"


def test_load_gate_and_work_probe(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    monkeypatch.setattr(os, "getloadavg", lambda: (999.0, 999.0, 999.0))
    loop = make_loop(tmp_path)
    assert loop.run_one_cycle().reason == "host_load_gate"
    calm_load(monkeypatch)
    loop2 = make_loop(tmp_path / "b", work_probe=lambda: False)
    assert loop2.run_one_cycle().reason == "work_in_progress"


def test_daily_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    loop = make_loop(tmp_path, daily_cap=1)
    first = loop.run_one_cycle()
    assert first.status == "ran"
    assert loop.run_one_cycle().reason == "daily_cap_reached"


# ---------------------------------------------------------------------------
# Pre-declaration enforcement
# ---------------------------------------------------------------------------


def test_run_without_declaration_is_refused(tmp_path):
    loop = make_loop(tmp_path)
    proposal = catalogue.all_proposals(loop.store)[0]
    with pytest.raises(DeclarationRequired):
        loop.run_declared("decl_9999_deadbeef", proposal)


def test_run_with_tampered_proposal_is_refused(tmp_path):
    loop = make_loop(tmp_path)
    proposal = catalogue.all_proposals(loop.store)[0]
    declaration_id = loop.ledger.declare(proposal.to_dict())
    tampered = catalogue.Proposal(
        experiment_type=proposal.experiment_type,
        members=(proposal.members[0],),  # quietly drop a member
        panel=proposal.panel,
        timeframe=proposal.timeframe,
        hypothesis=proposal.hypothesis,
    )
    with pytest.raises(DeclarationRequired):
        loop.run_declared(declaration_id, tampered)


# ---------------------------------------------------------------------------
# Judge — the frozen bars
# ---------------------------------------------------------------------------


def test_judge_full_bar_proven():
    verdict = judge(metrics(), n_global=3900)
    assert verdict.verdict == "PROVEN"


def test_judge_second_tier_forward_test():
    verdict = judge(metrics(pf=1.10, p_one_sided=0.4), n_global=3900)
    assert verdict.verdict == "FORWARD_TEST"


def test_judge_below_tier_fails():
    assert judge(metrics(pf=1.03), 3900).verdict == "FAIL"
    assert judge(metrics(expectancy=-0.001), 3900).verdict == "FAIL"
    assert judge(metrics(trades=150), 3900).verdict == "FAIL"


def test_judge_holdout_absence_caps_at_forward_test():
    verdict = judge(
        metrics(holdout_trades=None, holdout_expectancy=None), n_global=3900
    )
    assert verdict.verdict == "FORWARD_TEST"
    assert verdict.checks["holdout_present"] is False


def test_judge_bonferroni_uses_global_counter():
    # p = 1e-4 clears the second tier but not 0.05/3900 = 1.28e-5.
    verdict = judge(metrics(p_one_sided=1e-4), n_global=3900)
    assert verdict.verdict == "FORWARD_TEST"
    assert verdict.checks["bonferroni"] is False


# ---------------------------------------------------------------------------
# End-to-end cycle on the real fixture
# ---------------------------------------------------------------------------


def test_full_cycle_declares_runs_admits_and_banks(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    writer = RecordingWriter()
    loop = make_loop(tmp_path, writer=writer)
    report = loop.run_one_cycle()
    assert report.status == "ran"
    assert report.n_global == 3900  # seed 3,899 + this trial
    assert report.verdict in ("PROVEN", "FORWARD_TEST")
    assert report.admission_key

    kinds = [r["kind"] for r in loop.ledger.rows()]
    assert kinds[0] == "declaration"  # declared BEFORE anything ran
    assert "evaluation" in kinds and "result" in kinds
    assert "admission" in kinds

    entry = loop.admissions.get(report.admission_key)
    assert entry["status"] == "FORWARD_TEST"
    assert entry["forward_protocol"] is True
    assert entry["forward_lane"] == "FORWARD_TEST"
    assert entry["risk_per_trade_pct"] == bounds.LANE_RISK_PER_TRADE_PCT
    assert entry["max_heat_pct"] == bounds.LANE_MAX_HEAT_PCT
    assert entry["execution"] == "PENDING_ENSEMBLE_MODULE"
    assert entry["declaration_id"] == report.declaration_id
    assert len(entry["lane_assets"]) == 30  # CRYPTO30_SYMBOLS

    # A passing verdict banks a private lesson only (no universal copy).
    assert len(writer.calls) == 1
    assert writer.calls[0][2] is False


def test_merged_registry_classifies_admission_via_daemon_governance(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.admission_key
    base = {"bollinger_trend": {"status": "FORWARD_TEST"}}
    merged = merged_registry(base, loop.admissions)
    assert "bollinger_trend" in merged  # base untouched

    import strategies.strategy_registry as registry

    monkeypatch.setattr(
        registry, "PRODUCTION_STRATEGY_REGISTRY", merged
    )
    assert (
        registry.governance_status_for(report.admission_key)
        == "FORWARD_TEST"
    )


def test_admission_revoke_is_reversible(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    removed = loop.admissions.revoke(report.admission_key)
    assert removed is not None
    assert loop.admissions.get(report.admission_key) is None


# ---------------------------------------------------------------------------
# Bounds — risk parameters are untouchable
# ---------------------------------------------------------------------------


def test_risk_touch_refused_at_declaration(tmp_path):
    ledger = ExperimentLedger(tmp_path)
    with pytest.raises(RiskTouchRefused):
        ledger.declare(
            {
                "experiment_type": "combination_pair",
                "members": ["a", "b"],
                "risk_per_trade_pct": 0.5,  # synthetic risk touch
            }
        )
    with pytest.raises(RiskTouchRefused):
        assert_no_risk_touch({"nested": [{"max_stop_pct": 0.9}]})


def test_risk_touch_refused_at_admission(tmp_path):
    registry = AdmissionsRegistry(
        tmp_path / "admissions.json",
        lane_assets_resolver=lambda panel: ["BTCUSDT"],
    )
    store = StreamStore(FIXTURE_STORE)
    members = [store.stream(BOLLINGER), store.stream(SHOCK)]
    m = pooled_metrics(members)
    verdict = judge(m, 3900)
    with pytest.raises(RiskTouchRefused):
        registry.admit(
            members=members,
            metrics=m,
            verdict=verdict,
            declaration_id="decl_x",
            n_global=3900,
            panel="crypto30",
            timeframe="1d",
            extra={"leverage": 5},
        )


def test_fail_verdict_can_never_be_admitted(tmp_path):
    registry = AdmissionsRegistry(
        tmp_path / "admissions.json",
        lane_assets_resolver=lambda panel: ["BTCUSDT"],
    )
    store = StreamStore(FIXTURE_STORE)
    members = [store.stream(BOLLINGER), store.stream(SHOCK)]
    m = pooled_metrics(members)
    from self_experiments.judge import Verdict

    with pytest.raises(AdmissionError):
        registry.admit(
            members=members,
            metrics=m,
            verdict=Verdict(verdict="FAIL"),
            declaration_id="decl_x",
            n_global=3900,
            panel="crypto30",
            timeframe="1d",
        )


def test_merged_registry_refuses_to_shadow_governed_entry(tmp_path):
    registry = AdmissionsRegistry(
        tmp_path / "admissions.json",
        lane_assets_resolver=lambda panel: ["BTCUSDT"],
    )
    store = StreamStore(FIXTURE_STORE)
    members = [store.stream(BOLLINGER), store.stream(SHOCK)]
    m = pooled_metrics(members)
    key = registry.admit(
        members=members,
        metrics=m,
        verdict=judge(m, 3900),
        declaration_id="decl_x",
        n_global=3900,
        panel="crypto30",
        timeframe="1d",
    )
    with pytest.raises(AdmissionError):
        merged_registry({key: {"status": "VALIDATED"}}, registry)


# ---------------------------------------------------------------------------
# Lessons — rule R and pending retry
# ---------------------------------------------------------------------------


def test_fail_lesson_goes_private_and_universal(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    # Two losing streams: any combination of them fails the tier.
    store = synthetic_store(
        tmp_path,
        {
            "loser_a": [-0.02, 0.01] * 150,
            "loser_b": [-0.03, 0.005] * 150,
        },
    )
    writer = RecordingWriter()
    loop = make_loop(tmp_path / "loop", store=store, writer=writer)
    report = loop.run_one_cycle()
    assert report.status == "ran"
    assert report.verdict == "FAIL"
    assert report.admission_key == ""
    universals = [c for c in writer.calls if c[2] is True]
    privates = [c for c in writer.calls if c[2] is False]
    assert len(privates) == 1 and len(universals) == 1  # rule R


def test_pending_lessons_are_retried(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    store = synthetic_store(
        tmp_path, {"loser_a": [-0.02, 0.01] * 150, "loser_b": [-0.03] * 300}
    )
    writer = RecordingWriter(succeed=False)
    loop = make_loop(tmp_path / "loop", store=store, writer=writer)
    loop.run_one_cycle()
    rows = loop._read_lessons()
    assert rows and rows[0]["deliveries"]["private"] is False
    writer.succeed = True
    delivered = loop.flush_pending_lessons()
    assert delivered == 1
    rows = loop._read_lessons()
    assert rows[0]["deliveries"]["private"] is True
    assert rows[0]["deliveries"]["universal"] is True


def test_real_fabric_writer_call_shape():
    calls = []

    class FakeFabric:
        def record(self, **kwargs):
            calls.append(kwargs)

    from mesh.memory_fabric import MemoryScope

    writer = FabricLessonWriter(fabric=FakeFabric())
    assert writer.deliver("content", {"k": 1}, universal=False) is True
    assert writer.deliver("content", {"k": 1}, universal=True) is True
    assert calls[0]["owner_agent"] == "STRATEX"
    assert calls[0]["memory_type"] == "procedural"
    assert calls[0]["source"] == "stratex_self_experiment"
    assert calls[0]["scope"] == MemoryScope.AGENT
    assert calls[1]["scope"] == MemoryScope.UNIVERSAL


# ---------------------------------------------------------------------------
# Catalogue + greedy accounting
# ---------------------------------------------------------------------------


def test_catalogue_declares_all_brief_families():
    by_name = catalogue.TYPES_BY_NAME
    assert by_name["parameter_variant"].implemented is False
    assert by_name["exit_sizing_gate_variant"].implemented is False
    proposals = catalogue.all_proposals(StreamStore(FIXTURE_STORE))
    assert proposals  # the fixture group yields proposals
    assert all(
        by_name[p.experiment_type].implemented for p in proposals
    )  # the loop never proposes an unimplemented type
    assert proposals[0].experiment_type == "combination_cluster_champions"
    assert len(proposals[0].members) == 3  # one champion per cluster present


def test_greedy_counts_every_evaluation(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    calm_load(monkeypatch)
    # Four streams with mixed records; greedy must evaluate candidates.
    store = synthetic_store(
        tmp_path,
        {
            "s1": [0.03, -0.01] * 150,
            "s2": [0.02, -0.005] * 150,
            "s3": [-0.01, 0.004] * 150,
            "s4": [0.01, -0.002] * 150,
        },
    )
    loop = make_loop(tmp_path / "loop", store=store)
    greedy = [
        p
        for p in catalogue.all_proposals(store)
        if p.experiment_type == "combination_greedy_forward"
    ]
    assert greedy
    declaration_id = loop.ledger.declare(greedy[0].to_dict())
    before = loop.counter.value
    report = loop.run_declared(declaration_id, greedy[0])
    evaluations = [
        r for r in loop.ledger.rows() if r["kind"] == "evaluation"
    ]
    assert evaluations  # the search actually evaluated candidates
    assert loop.counter.value - before == len(evaluations)
    assert report.n_global == loop.counter.value
