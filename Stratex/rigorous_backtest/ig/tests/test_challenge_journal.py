"""Tests for TASK-IG-STR-10 challenge_journal (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.challenge_journal import (apply_day, create_challenge,
                                  public_report, verify_journal)


def _mk(tmp_path):
    p = str(tmp_path / "challenge.jsonl")
    return create_challenge("demo-100k", 100000.0, 0.10, 0.05, 0.10,
                            journal_path=p), p


def test_passes_on_target(tmp_path):
    st, p = _mk(tmp_path)
    apply_day(st, "2026-11-16", 4000.0)
    apply_day(st, "2026-11-17", 6500.0)
    assert st["status"] == "passed"
    assert st["balance"] == 110500.0
    assert verify_journal(p) is True


def test_daily_loss_breach(tmp_path):
    st, _ = _mk(tmp_path)
    apply_day(st, "2026-11-16", -5000.0)  # exactly 5% of start
    assert st["status"] == "failed_daily"
    try:
        apply_day(st, "2026-11-17", 100.0)
    except ValueError:
        pass
    else:
        raise AssertionError("terminal challenge must reject more days")


def test_total_drawdown_breach_without_daily_breach(tmp_path):
    st, _ = _mk(tmp_path)
    for i in range(3):
        apply_day(st, "2026-11-1%d" % (6 + i), -3400.0)  # each < 5% daily
    assert st["status"] == "failed_total"
    assert st["balance"] == 100000.0 - 10200.0


def test_public_report_shows_everything(tmp_path):
    st, _ = _mk(tmp_path)
    apply_day(st, "2026-11-16", -1000.0)
    apply_day(st, "2026-11-17", 2000.0)
    rep = public_report(st)
    assert "demo-100k" in rep and "active" in rep
    assert "2026-11-16" in rep and "2026-11-17" in rep
    assert "-1000.00" in rep and "101000.00" in rep


def test_validation():
    for bad in (dict(profit_target_pct=1.5), dict(max_daily_loss_pct=0.0),
                dict(max_total_dd_pct=-0.1)):
        args = dict(name="x", start_balance=1000.0, profit_target_pct=0.1,
                    max_daily_loss_pct=0.05, max_total_dd_pct=0.1)
        args.update(bad)
        try:
            create_challenge(**args)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for %r" % (bad,))
