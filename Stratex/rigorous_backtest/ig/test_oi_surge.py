"""Synthetic tests for the TASK-STR-RD-022 OI-surge harness.

Every test runs on hand-built synthetic data with hand-computed
expectations — no real panel data is touched. Run:
    python3 -m pytest test_oi_surge.py        (or: python3 test_oi_surge.py)

Coverage map (declaration-critical properties):
- causal asof join: a snapshot after the bar close is never used;
  staleness > 30 min suppresses the signal, <= 30 min does not
- dOI construction incl. missing/zero endpoints
- percentile rank: exact hand-computed ranks, the >= 95% coverage
  gate, the first-evaluable gate, no look-ahead (prefix stability)
- extreme detection: rank exactly 0.95 fires, the unique window
  maximum fires, ordinary bars do not
- direction: FOLLOW (up -> LONG, down -> SHORT, flat -> none)
- ATR (Wilder): seed + smoothing step hand-computed
- bracket exits: SL / TP / gap-through fills / stop-before-target
- max-hold: TIME exit at the max-hold bar's close; the max-hold
  bar's bracket check runs BEFORE the time exit
- sequencing: entry at the NEXT bar's open; one position at a time
  (skipped_open); an exit bar is never a signal bar
  (skipped_exit_bar); a final-bar signal is not taken;
  END_OF_DATA close-out
- costs: net_return arithmetic at 16 and 32 bps
- metrics parsing: in-memory zip parse + checksum accept/reject
"""
from __future__ import annotations

import hashlib
import io
import unittest
import zipfile
from datetime import date, datetime, timedelta, timezone

import metrics_feed
import oi_surge
from oi_surge import (COSTS, COSTS_2X, atr_series, compute_doi,
                      generate_signals, net_return, percentile_ranks,
                      simulate)

UTC = timezone.utc
DAY0 = datetime(2022, 1, 1, tzinfo=UTC)


def bar(t: datetime, o: float, h: float, l: float, c: float) -> dict:
    return {"time": t, "open": o, "high": h, "low": l, "close": c}


def daily_bars(closes, half_range=0.5, start=DAY0):
    """Daily bars: open = previous close (first bar: its close),
    high/low = close +/- half_range unless overridden later."""
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        out.append(bar(start + timedelta(days=i), o, c + half_range,
                       c - half_range, c))
    return out


def oi_entries(levels, age=5.0):
    return [(float(v), age) for v in levels]


def controlled_series(n=400, surge_idx=380, surge_mult=1.08,
                      signal_close=101.0):
    """Bars + OI with EXACTLY ONE surge, at surge_idx.

    OI dOI decreases monotonically before the surge (each new bar
    is the window minimum -> tiny rank, never a trigger), jumps by
    surge_mult at surge_idx (unique window maximum -> rank 1.0),
    and decreases monotonically after it. Price closes are flat
    100.0 except the signal bar, whose close is signal_close
    (+1% -> LONG by default). Returns (bars, oi)."""
    levels = [1000.0]
    for t in range(1, n):
        if t < surge_idx:
            levels.append(levels[-1] * (1.0 + (0.010 - 0.00005 * (t - 1))))
        elif t == surge_idx:
            levels.append(levels[-1] * surge_mult)
        else:
            levels.append(levels[-1] * (1.0 - (0.002 + 0.0001 * (t - surge_idx - 1))))
    closes = [100.0] * n
    closes[surge_idx] = signal_close
    bars = daily_bars(closes)
    # entry bar opens at the signal close (open = prev close already)
    return bars, oi_entries(levels)


class TestAsofJoin(unittest.TestCase):
    def test_snapshot_after_close_never_used(self):
        snaps = [(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 100.0),
                 (datetime(2024, 1, 1, 0, 5, tzinfo=UTC), 200.0),
                 (datetime(2024, 1, 1, 0, 10, tzinfo=UTC), 300.0)]
        closes = [datetime(2024, 1, 1, 0, 4, tzinfo=UTC),
                  datetime(2024, 1, 1, 0, 7, tzinfo=UTC),
                  datetime(2024, 1, 1, 0, 10, tzinfo=UTC)]
        out = metrics_feed.oi_at_bar_close(snaps, closes)
        self.assertEqual(out[0], (100.0, 4.0))   # 00:05 print NOT used
        self.assertEqual(out[1], (200.0, 2.0))
        self.assertEqual(out[2], (300.0, 0.0))   # exactly at close: used

    def test_no_snapshot_before_close(self):
        snaps = [(datetime(2024, 1, 1, 1, 0, tzinfo=UTC), 100.0)]
        out = metrics_feed.oi_at_bar_close(
            snaps, [datetime(2024, 1, 1, 0, 30, tzinfo=UTC)])
        self.assertIsNone(out[0])


class TestDoi(unittest.TestCase):
    def test_hand_computed(self):
        doi = compute_doi([100.0, 110.0, 99.0, None, 50.0, 0.0, 10.0])
        self.assertIsNone(doi[0])
        self.assertAlmostEqual(doi[1], 0.10)
        self.assertAlmostEqual(doi[2], -0.10)
        self.assertIsNone(doi[3])          # missing current
        self.assertIsNone(doi[4])          # missing previous
        self.assertAlmostEqual(doi[5], -1.0)
        self.assertIsNone(doi[6])          # previous == 0


class TestPercentileRanks(unittest.TestCase):
    def setUp(self):
        self.times = [datetime(2023, 6, 1, tzinfo=UTC) + timedelta(days=i)
                      for i in range(30)]

    def test_exact_rank(self):
        doi = [0.001 * ((i * 7) % 13) for i in range(30)]
        doi[25] = 0.012  # window (5,25] = idx 6..25 (20 bars)
        ranks = percentile_ranks(self.times, doi, window_days=20,
                                 min_coverage=0.95,
                                 first_evaluable=self.times[0])
        win = [doi[j] for j in range(6, 26)]
        expected = sum(1 for v in win if v <= doi[25]) / len(win)
        self.assertAlmostEqual(ranks[25], expected)
        self.assertEqual(ranks[25], 1.0)  # 0.012 is the window maximum

    def test_rank_point_95_boundary(self):
        # 20 defined window values; exactly 19 of them <= current.
        doi = [None] * 5 + [0.001 * k for k in range(1, 21)] + [None] * 5
        doi[24] = 0.0185  # window idx 5..24: 0.001..0.019, 0.020 -> 0.0185
        times = self.times
        ranks = percentile_ranks(times, doi, window_days=20,
                                 min_coverage=0.95,
                                 first_evaluable=times[0])
        win = [doi[j] for j in range(5, 25)]
        expected = sum(1 for v in win if v <= doi[24]) / len(win)
        self.assertAlmostEqual(ranks[24], expected)
        self.assertAlmostEqual(ranks[24], 0.95)

    def test_coverage_gate(self):
        doi = [0.001] * 30
        doi[25] = 0.5
        doi[10] = None
        doi[11] = None  # window idx 6..25 now has 18/20 defined < 95%
        ranks = percentile_ranks(self.times, doi, window_days=20,
                                 min_coverage=0.95,
                                 first_evaluable=self.times[0])
        self.assertIsNone(ranks[25])

    def test_first_evaluable_gate(self):
        doi = [0.001] * 30
        doi[25] = 0.5
        ranks = percentile_ranks(
            self.times, doi, window_days=20, min_coverage=0.95,
            first_evaluable=datetime(2023, 7, 1, tzinfo=UTC))
        self.assertIsNone(ranks[25])  # 2023-06-26 < 2023-07-01

    def test_no_lookahead_prefix_stability(self):
        doi = [0.002 * ((i * 11) % 17) - 0.01 for i in range(30)]
        full = percentile_ranks(self.times, doi, window_days=20,
                                min_coverage=0.9,
                                first_evaluable=self.times[0])
        prefix = percentile_ranks(self.times[:20], doi[:20],
                                  window_days=20, min_coverage=0.9,
                                  first_evaluable=self.times[0])
        for i in range(20):
            self.assertEqual(full[i], prefix[i],
                             f"rank changed at {i} when future data arrived")


class TestAtr(unittest.TestCase):
    def test_seed_and_smoothing_hand_computed(self):
        bars = []
        # TRs: bar0 = 2.0 (range only), bars 1..13 = 1.0, bar14 = 3.0
        bars.append(bar(DAY0, 100.0, 101.0, 99.0, 100.0))
        for i in range(1, 14):
            bars.append(bar(DAY0 + timedelta(days=i), 100.0, 100.5, 99.5, 100.0))
        bars.append(bar(DAY0 + timedelta(days=14), 100.0, 102.0, 99.0, 100.0))
        atr = atr_series(bars, period=14)
        self.assertIsNone(atr[12])
        self.assertAlmostEqual(atr[13], 15.0 / 14.0)
        self.assertAlmostEqual(atr[14], ((15.0 / 14.0) * 13 + 3.0) / 14.0)


class TestSignals(unittest.TestCase):
    def test_surge_fires_long_on_up_bar(self):
        bars, oi = controlled_series()
        sigs = generate_signals(bars, oi)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].bar_index, 380)
        self.assertEqual(sigs[0].side, "LONG")
        self.assertGreaterEqual(sigs[0].rank, 0.95)

    def test_surge_fires_short_on_down_bar(self):
        bars, oi = controlled_series(signal_close=99.0)
        sigs = generate_signals(bars, oi)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].side, "SHORT")

    def test_surge_flat_bar_no_signal(self):
        bars, oi = controlled_series(signal_close=100.0)
        self.assertEqual(generate_signals(bars, oi), [])

    def test_stale_snapshot_suppresses(self):
        bars, oi = controlled_series()
        oi[380] = (oi[380][0], 31.0)  # 31 min old at the surge bar close
        self.assertEqual(generate_signals(bars, oi), [])
        bars, oi = controlled_series()
        oi[380] = (oi[380][0], 30.0)  # exactly at the cap: evaluable
        self.assertEqual(len(generate_signals(bars, oi)), 1)

    def test_no_lookahead_signal_prefix_stability(self):
        bars, oi = controlled_series()
        before = [s.as_dict() for s in generate_signals(bars, oi)]
        oi2 = list(oi)
        oi2[395] = (oi2[395][0] * 50.0, 5.0)  # future OI explosion
        after = [s.as_dict() for s in generate_signals(bars, oi2)
                 if s.bar_index < 395]
        self.assertEqual(before, [s for s in after if s["bar_index"] < 395])


class TestBracketExits(unittest.TestCase):
    def _pos(self, side="LONG", entry=100.0, stop=98.0, target=104.0):
        return {"side": side, "entry": entry, "stop": stop, "target": target}

    def test_stop_touch(self):
        px, r = oi_surge._check_exit(self._pos(), bar(DAY0, 100.0, 101.0, 97.5, 99.0))
        self.assertEqual((px, r), (98.0, "SL"))

    def test_target_touch(self):
        px, r = oi_surge._check_exit(self._pos(), bar(DAY0, 100.0, 104.5, 99.0, 103.0))
        self.assertEqual((px, r), (104.0, "TP"))

    def test_gap_through_stop_fills_at_open(self):
        px, r = oi_surge._check_exit(self._pos(), bar(DAY0, 97.0, 97.5, 96.0, 97.2))
        self.assertEqual((px, r), (97.0, "SL"))

    def test_gap_through_target_fills_at_open(self):
        px, r = oi_surge._check_exit(self._pos(), bar(DAY0, 105.0, 106.0, 104.5, 105.5))
        self.assertEqual((px, r), (105.0, "TP"))

    def test_stop_before_target_same_bar(self):
        px, r = oi_surge._check_exit(self._pos(), bar(DAY0, 100.0, 105.0, 97.0, 100.0))
        self.assertEqual((px, r), (98.0, "SL"))

    def test_short_mirror(self):
        pos = self._pos(side="SHORT", entry=100.0, stop=102.0, target=96.0)
        px, r = oi_surge._check_exit(pos, bar(DAY0, 100.0, 102.5, 99.0, 101.0))
        self.assertEqual((px, r), (102.0, "SL"))
        px, r = oi_surge._check_exit(pos, bar(DAY0, 100.0, 101.0, 95.5, 97.0))
        self.assertEqual((px, r), (96.0, "TP"))


class TestSimulate(unittest.TestCase):
    def test_entry_at_next_bar_open_and_time_exit(self):
        bars, oi = controlled_series()
        trades, stats = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(len(trades), 1)
        tr = trades[0]
        self.assertEqual(tr.entry_price, bars[381]["open"])  # 101.0
        self.assertEqual(tr.entry_time, bars[381]["time"])
        # quiet bars never touch the bracket -> TIME at bar 385 close
        self.assertEqual(tr.exit_reason, "TIME")
        self.assertEqual(tr.exit_time, bars[385]["time"])
        self.assertEqual(tr.exit_price, bars[385]["close"])
        self.assertEqual(stats["taken"], 1)

    def test_bracket_beats_time_on_final_hold_bar(self):
        bars, oi = controlled_series()
        bars[385] = bar(bars[385]["time"], 101.0, 120.0, 100.5, 101.0)
        trades, _ = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(trades[0].exit_reason, "TP")
        self.assertEqual(trades[0].exit_time, bars[385]["time"])

    def test_stop_exit(self):
        bars, oi = controlled_series()
        bars[382] = bar(bars[382]["time"], 101.0, 101.5, 90.0, 100.0)
        trades, _ = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].exit_reason, "SL")
        self.assertEqual(trades[0].exit_time, bars[382]["time"])
        self.assertLess(trades[0].exit_price, trades[0].entry_price)

    def test_skipped_open_and_exit_bar_not_signal(self):
        bars, oi = controlled_series()
        # second surge at bar 383 while the position is open
        levels = [v for (v, _a) in oi]
        levels[383] = levels[382] * 1.09
        levels[384] = levels[383] * 0.99
        bars[383] = bar(bars[383]["time"], 101.0, 101.5, 100.5, 102.0)
        bars[384] = bar(bars[384]["time"], 102.0, 102.5, 101.5, 101.0)
        oi = oi_entries(levels)
        trades, stats = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(stats["skipped_open"], 1)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].exit_reason, "TIME")

    def test_exit_bar_signal_skipped_then_next_bar_enters(self):
        bars, oi = controlled_series()
        levels = [v for (v, _a) in oi]
        # surge again at 383 (the SL exit bar) and at 384
        levels[383] = levels[382] * 1.09
        levels[384] = levels[383] * 1.09
        levels[385] = levels[384] * 0.99
        oi = oi_entries(levels)
        bars[383] = bar(bars[383]["time"], 100.0, 100.5, 90.0, 99.0)  # SL exit + SHORT signal (return < 0)
        bars[384] = bar(bars[384]["time"], 99.0, 99.5, 97.5, 98.0)    # SHORT signal (return < 0)
        trades, stats = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(stats["skipped_exit_bar"], 1)
        self.assertEqual(trades[0].exit_reason, "SL")
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[1].side, "SHORT")
        self.assertEqual(trades[1].entry_time, bars[385]["time"])
        self.assertEqual(trades[1].entry_price, bars[385]["open"])

    def test_end_of_data(self):
        bars, oi = controlled_series(n=382, surge_idx=380)
        trades, _ = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].exit_reason, "END_OF_DATA")
        self.assertEqual(trades[0].exit_price, bars[381]["close"])

    def test_final_bar_signal_not_taken(self):
        bars, oi = controlled_series(n=381, surge_idx=380)
        trades, stats = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(trades, [])
        self.assertEqual(stats["final_bar_signals"], 1)

    def test_degenerate_atr_no_trade(self):
        bars = daily_bars([100.0] * 400, half_range=0.0)
        _b, oi = controlled_series()
        trades, _ = simulate(bars, oi, "TESTUSDT", "1d")
        self.assertEqual(trades, [])


class TestCosts(unittest.TestCase):
    def test_net_return_long_16bps(self):
        r = 0.0008
        expected = (101.0 * (1 - r) - 100.0 * (1 + r)) / (100.0 * (1 + r))
        self.assertAlmostEqual(net_return("LONG", 100.0, 101.0, COSTS),
                               expected, places=12)

    def test_net_return_short_32bps(self):
        r = 0.0016
        expected = (100.0 * (1 - r) - 99.0 * (1 + r)) / (100.0 * (1 - r))
        self.assertAlmostEqual(net_return("SHORT", 100.0, 99.0, COSTS_2X),
                               expected, places=12)

    def test_round_trip_bps(self):
        self.assertEqual(COSTS.describe()["round_trip_bps"], 16.0)
        self.assertEqual(COSTS_2X.describe()["round_trip_bps"], 32.0)


class TestMetricsFeed(unittest.TestCase):
    def _zip_bytes(self, text: str) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("BTCUSDT-metrics-2024-01-01.csv", text)
        return buf.getvalue()

    def test_parse_zip(self):
        text = ("create_time,symbol,sum_open_interest,sum_open_interest_value,"
                "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
                "count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
                "2024-01-01 00:05:00,BTCUSDT,100.5,1,1,1,1,1\n"
                "2024-01-01 00:00:00,BTCUSDT,99.5,1,1,1,1,1\n")
        rows = metrics_feed.parse_metrics_zip(self._zip_bytes(text))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], 99.5)  # sorted by time
        self.assertEqual(rows[1][1], 100.5)

    def test_checksum_accept_reject(self):
        raw = b"fake-zip-bytes"
        good = f"{hashlib.sha256(raw).hexdigest()}  file.zip"
        bad = f"{'0' * 64}  file.zip"
        self.assertTrue(metrics_feed.verify_checksum(raw, good))
        self.assertFalse(metrics_feed.verify_checksum(raw, bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
