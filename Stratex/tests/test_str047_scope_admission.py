"""TASK-STR-047: scope admission check for the 7 RD-025 PROVEN ensemble books.

Pins the checkpoint-1 scope facts, all read from the in-repo records on
main (no network, no bridge, no live venue):

  * the 7 RD-025 books (trials 3905, 3906, 3927, 3928, 3929, 3933, 3978)
    pass the checkable legs of the frozen PROVEN bar
    (Stratex/self_experiments/bounds.py: expectancy > 0, PF >= 1.2,
    >= 200 OOS trades, >= 4/5 positive folds);
  * the two statistical legs (Bonferroni one-sided p < 0.05 / N_global,
    pooled holdout expectancy > 0) are RECORDED per book in the registry
    reason text ("Bonferroni pass at round N=3,979, holdout pass") —
    carried from the RD-025 verdict, not recomputed here (the full
    RD-002 trade lists do not ship in the repo; see
    test_exp002_ensemble_book.py section 8 for the same boundary);
  * every book is a FORWARD_TEST registry entry with lane-executable
    terms (forward_protocol True, lane_assets set, 0.1% risk / 2% heat,
    max_stop_pct override stamped) whose figures agree with the
    canonical BOOKS dict in strategies/ensemble_books.py;
  * every member module file is present and findable on sys.path
    (the daemon fail-closes a book whose member module is missing);
  * the loop first-light book 3900 is OUT of scope: source LOOP, not
    RD-025, and it records no Bonferroni/holdout pass;
  * the title correction: 6 of the 7 books carry shock_breakout k1.5;
    3978's shock leg is shock_breakout k1.0 @ 1w (SHW), not k1.5.

What this test does NOT do: evaluate any book, touch the daemon, or
change the S1 allowlist. The live wiring leg (STRATEX_STRATEGY_ALLOWLIST
append on S1 + first-scan evidence) needs coordinator clearance and is
not taken here.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config_strategy import PRODUCTION_STRATEGY_REGISTRY  # noqa: E402
from strategies.ensemble_books import BOOKS  # noqa: E402

RD025_BOOKS = (
    "ensemble_book_3905",
    "ensemble_book_3906",
    "ensemble_book_3927",
    "ensemble_book_3928",
    "ensemble_book_3929",
    "ensemble_book_3933",
    "ensemble_book_3978",
)

# Frozen PROVEN bar, checkable legs (Stratex/self_experiments/bounds.py):
# expectancy > 0, PF >= 1.2 (FULL_BAR_PF), >= 200 OOS trades
# (MIN_OOS_TRADES), >= 4/5 positive folds (FULL_BAR_MIN_POSITIVE_FOLDS).
MIN_PF = 1.2
MIN_TRADES = 200
MIN_POSITIVE_FOLDS = "4/5"


@pytest.mark.parametrize("key", RD025_BOOKS)
def test_rd025_book_passes_frozen_bar_checkable_legs(key):
    book = BOOKS[key]
    assert book.verdict == "PROVEN"
    assert book.source == "RD-025"
    assert book.expectancy > 0
    assert book.pf >= MIN_PF
    assert book.trades >= MIN_TRADES
    assert book.folds == MIN_POSITIVE_FOLDS


@pytest.mark.parametrize("key", RD025_BOOKS)
def test_rd025_book_records_bonferroni_and_holdout(key):
    entry = PRODUCTION_STRATEGY_REGISTRY[key]
    reason = entry["reason"]
    assert "Bonferroni pass" in reason
    assert "holdout pass" in reason


@pytest.mark.parametrize("key", RD025_BOOKS)
def test_rd025_book_registered_forward_test_agreeing_with_books(key):
    book = BOOKS[key]
    entry = PRODUCTION_STRATEGY_REGISTRY[key]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["forward_protocol"] is True
    assert entry["forward_lane"] == "FORWARD_TEST"
    assert entry["lane_assets"]
    assert entry["risk_per_trade_pct"] == 0.001
    assert entry["max_heat_pct"] == 0.02
    assert entry["max_stop_pct"] == book.max_stop_pct
    assert entry["oos_trades"] == book.trades
    assert entry["oos_profit_factor"] == book.pf
    assert entry["oos_win_rate_prior"] == book.win_rate
    assert entry["oos_folds"] == book.folds


@pytest.mark.parametrize("key", RD025_BOOKS)
def test_rd025_book_member_modules_present(key):
    book = BOOKS[key]
    assert book.members
    for member in book.members:
        assert importlib.util.find_spec(member.module) is not None, (
            f"{key}: member module {member.module} not findable on sys.path"
        )


def test_loop_book_3900_out_of_scope():
    book = BOOKS["ensemble_book_3900"]
    assert book.source == "LOOP"
    assert book.key not in RD025_BOOKS
    entry = PRODUCTION_STRATEGY_REGISTRY["ensemble_book_3900"]
    assert "Bonferroni pass" not in entry["reason"]


def test_shock_legs_k15_except_3978_k10_weekly():
    for key in RD025_BOOKS:
        members = BOOKS[key].members
        shock = [m for m in members if m.key == "shock_breakout"]
        assert len(shock) == 1, f"{key}: expected exactly one shock leg"
        if key == "ensemble_book_3978":
            assert shock[0].module == "strategy_shock_breakout_1wk"
            assert shock[0].cell == "k1.0"
            assert shock[0].timeframe == "1w"
        else:
            assert shock[0].module == "strategy_shock_breakout_k15"
            assert shock[0].cell == "k1.5"
            assert shock[0].timeframe == "1d"
