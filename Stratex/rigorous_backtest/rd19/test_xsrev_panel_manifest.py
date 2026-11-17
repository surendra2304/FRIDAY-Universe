"""Regression tests for run_xsrev.py's panel-verification loop
(TASK-STR-RD-019; added by the RD-019 runner KeyError fix PR).

The shipped runner read exp["missing"] in the panel-verification
loop (and again in the mismatch message), but the S-RD1 provenance
manifest — the runner's own default --expected-provenance — keys
the field "missing_bars". On a clean panel the runner raised
KeyError: 'missing' on the first symbol, before any simulation.
The synthetic suites never exercised the real-manifest panel loop,
so the defect survived until run-prep proved it on 30/30 symbols
against the real manifest (~/workspace/runprep-rd019/READINESS.md).

These tests drive main() end-to-end with the programme seams
stubbed (load_programme, xsrev.simulate, xsrev.aggregate_daily,
run_xsrev.judge_all) and a fake provenance manifest keyed
"missing_bars" — the real manifest shape (per-symbol keys verified
against the S-RD1 panel_provenance.json: csv_sha256, expected_bars,
first_bar_utc, last_bar_utc, missing_bars, n_gap_spans, rows,
status). Gate A runs for real against this checkout's frozen
declaration. All panel data is fake; no backtest, no real panel,
no holdout access — mechanics coverage of the verification loop
only.

Pre-fix, all three tests fail with KeyError: 'missing' (the third
reaches the defective key through the mismatch message, pinning
that second site too). Post-fix they pass.

Run:  python3 -m pytest -q test_xsrev_panel_manifest.py
(from Stratex/rigorous_backtest/rd19/ inside a full checkout)
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_xsrev  # noqa: E402


def _repo_root() -> Path:
    for parent in HERE.parents:
        if (parent / run_xsrev.DECLARATION_REL).exists():
            return parent
    raise RuntimeError("checkout root not found above the harness dir")


REPO_ROOT = _repo_root()
CSV_SHA = "ab" * 32
FIRST_BAR = "2023-10-01T00:00:00Z"
LAST_BAR = "2026-10-31T23:45:00Z"


def _provenance(missing_bars: int = 0) -> dict:
    """Fake S-RD1 provenance manifest — the real key shape."""
    return {"symbols": {
        sym: {"csv_sha256": CSV_SHA,
              "expected_bars": run_xsrev.EXPECTED_ROWS_15M,
              "first_bar_utc": FIRST_BAR,
              "last_bar_utc": LAST_BAR,
              "missing_bars": missing_bars,
              "n_gap_spans": 0,
              "rows": run_xsrev.EXPECTED_ROWS_15M,
              "status": "ok"}
        for sym in run_xsrev.EXPECTED_SYMBOLS}}


def _fake_prog(panel_missing_bars: int):
    import pandas as pd

    def load_dataset(sym, timeframe, start, end, cache_dir=None):
        manifest = {"rows": run_xsrev.EXPECTED_ROWS_15M,
                    "gap_audit": {"missing_bars": panel_missing_bars},
                    "csv_sha256": CSV_SHA,
                    "first_bar_utc": FIRST_BAR,
                    "last_bar_utc": LAST_BAR}
        df = pd.DataFrame({"open": [], "high": [], "low": [],
                           "close": [], "volume": []})
        return types.SimpleNamespace(manifest=manifest, df=df)

    return types.SimpleNamespace(
        load_dataset=load_dataset,
        CRYPTO30=list(run_xsrev.EXPECTED_SYMBOLS),
        SimTrade=object, check_bar=None, holdout_check=None,
        trade_metrics=None, FOLDS=[], oos_report=None,
        trades_in_window=None)


def _judged_stub():
    per_tag = {"pooled_oos": {"trades": 0, "expectancy_net": None,
                              "profit_factor_net": None},
               "checks": {}, "passes_all": False,
               "temporal_holdout": {
                   "checks": {},
                   "holdout_metrics": {"trades": 0,
                                       "expectancy_net": None}}}
    return ({tag: dict(per_tag) for tag, _ in run_xsrev.COST_LEVELS},
            "insufficient OOS trades", "synthetic judge stub")


def _run_main(monkeypatch, tmp_path, provenance, panel_missing_bars):
    prov_path = tmp_path / "panel_provenance.json"
    prov_path.write_text(json.dumps(provenance), encoding="utf-8")
    monkeypatch.setattr(run_xsrev, "load_programme",
                        lambda repo: _fake_prog(panel_missing_bars))
    monkeypatch.setattr(run_xsrev.xsrev, "aggregate_daily",
                        lambda bars: [{}] * run_xsrev.EXPECTED_DAYS)
    monkeypatch.setattr(
        run_xsrev.xsrev, "simulate",
        lambda panel, costs: ([], {"picks_ranked": 0, "picks_climax": 0,
                                   "picks_gated_out": 0,
                                   "skipped_open": 0}))
    monkeypatch.setattr(
        run_xsrev, "judge_all",
        lambda trades_by_tag, symbols, trial_floor, prog: _judged_stub())
    monkeypatch.setattr(sys, "argv", [
        "run_xsrev.py", "--repo", str(REPO_ROOT),
        "--panel-dir", str(tmp_path / "panel"),
        "--expected-provenance", str(prov_path),
        "--trial-floor", str(run_xsrev.MIN_TRIAL_FLOOR),
        "--declared-run", "--out", str(tmp_path / "out")])
    return run_xsrev.main()


def test_clean_panel_against_missing_bars_manifest_completes(
        monkeypatch, tmp_path, capsys):
    """The regression: a clean panel verified against a manifest
    keyed 'missing_bars' (the real shape) must verify all 30 symbols
    and complete — pre-fix this raised KeyError: 'missing' on the
    first symbol."""
    rc = _run_main(monkeypatch, tmp_path, _provenance(0), 0)
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("15m verified") == len(run_xsrev.EXPECTED_SYMBOLS)
    assert "VERDICT: insufficient OOS trades" in out


def test_provenance_missing_bars_mismatch_aborts_with_message(
        monkeypatch, tmp_path, capsys):
    """Provenance expects 3 missing bars, the panel has 0: the loop
    must ABORT (rc 2) naming both numbers — the message itself reads
    the same manifest key."""
    rc = _run_main(monkeypatch, tmp_path, _provenance(3), 0)
    err = capsys.readouterr().err
    assert rc == 2
    assert "missing 0 != 3" in err


def test_panel_missing_bars_mismatch_aborts_with_message(
        monkeypatch, tmp_path, capsys):
    """Panel has 5 missing bars, provenance expects 0: ABORT (rc 2)
    with the formatted message. On the pre-fix runner the condition
    short-circuits on the panel side and the KeyError surfaces in
    the mismatch message instead — this test pins that site."""
    rc = _run_main(monkeypatch, tmp_path, _provenance(0), 5)
    err = capsys.readouterr().err
    assert rc == 2
    assert "missing 5 != 0" in err


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
