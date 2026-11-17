"""Synthetic tests for the order-flow harness. All data fabricated;
every expectation hand-computed. Run: python3 -m pytest test_orderflow.py
(or plain unittest)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orderflow import (aggregate_aggtrades, flow_imbalance, simulate,
                       WARMUP_BARS)

MS15 = 900_000

def mkbar(idx, o=100.0, h=100.5, l=99.5, c=100.0, delta=0.0, qty=100.0):
    return {"t": idx * MS15, "o": o, "h": h, "l": l, "c": c,
            "delta": delta, "qty": qty, "nprints": 10}

def flat_series(n, **kw):
    return [mkbar(i, **kw) for i in range(n)]

class TestAggregation(unittest.TestCase):
    def test_sign_convention(self):
        # is_buyer_maker False -> taker BUY (+); True -> taker SELL (-)
        rows = [(0, 2.0, False), (1000, 3.0, True), (2000, 1.0, False)]
        out = aggregate_aggtrades(rows, "15m")
        cell = out[0]
        self.assertEqual(cell["qty"], 6.0)
        self.assertEqual(cell["delta"], 2.0 - 3.0 + 1.0)
        self.assertEqual(cell["nprints"], 3)

    def test_bar_boundaries(self):
        # print at exactly bar open belongs to that bar; at exactly the
        # next bar's open belongs to the next bar.
        rows = [(MS15 - 1, 1.0, False), (MS15, 2.0, False),
                (2 * MS15 - 1, 4.0, False), (2 * MS15, 8.0, False)]
        out = aggregate_aggtrades(rows, "15m")
        self.assertEqual(out[0]["qty"], 1.0)
        self.assertEqual(out[MS15]["qty"], 6.0)
        self.assertEqual(out[2 * MS15]["qty"], 8.0)

    def test_1h_grid(self):
        rows = [(3_599_999, 1.0, False), (3_600_000, 2.0, False)]
        out = aggregate_aggtrades(rows, "1h")
        self.assertEqual(out[0]["qty"], 1.0)
        self.assertEqual(out[3_600_000]["qty"], 2.0)

class TestImbalance(unittest.TestCase):
    def test_hand_computed(self):
        bars = flat_series(3)
        bars[0]["delta"], bars[1]["delta"], bars[2]["delta"] = 50.0, -20.0, 10.0
        ci = flow_imbalance(bars, 2, 3, MS15)
        self.assertAlmostEqual(ci, 40.0 / 300.0)

    def test_incomplete_window_is_none(self):
        bars = flat_series(3)
        self.assertIsNone(flow_imbalance(bars, 1, 3, MS15))

    def test_zero_qty_is_none(self):
        bars = flat_series(3)
        for b in bars: b["qty"] = 0.0
        self.assertIsNone(flow_imbalance(bars, 2, 3, MS15))

    def test_missing_flow_is_none(self):
        bars = flat_series(3)
        bars[1]["delta"] = None
        self.assertIsNone(flow_imbalance(bars, 2, 3, MS15))

    def test_window_spanning_gap_is_none(self):
        # bars 0,1,3 on the grid (bar 2 missing, the 1h-hole shape):
        # a window that spans the gap is incomplete by declaration
        bars = flat_series(3)
        bars[2]["t"] = 3 * MS15
        bars[0]["delta"] = bars[1]["delta"] = bars[2]["delta"] = 50.0
        self.assertIsNone(flow_imbalance(bars, 2, 3, MS15))

class TestThrust(unittest.TestCase):
    def _series_with_flow(self, delta, n_flow=16, total=300):
        bars = flat_series(total)
        for i in range(WARMUP_BARS, WARMUP_BARS + n_flow):
            bars[i]["delta"] = delta
        return bars

    def test_long_entry_and_target(self):
        # CI first reaches theta at signal bar 273: its 16-bar window
        # holds 14 flow bars (420/1600 = 0.2625); at bar 272 it is
        # 13 flow bars (390/1600 = 0.24375 < 0.25). Entry is the OPEN
        # of bar 274 -- never the signal bar itself (no look-ahead).
        bars = flat_series(WARMUP_BARS + 15)
        for i in range(WARMUP_BARS, WARMUP_BARS + 14):
            bars[i]["delta"] = 30.0
        entry_idx = WARMUP_BARS + 14
        bars[entry_idx] = mkbar(entry_idx, o=100.0, h=103.5, l=99.5, c=103.0)
        trades = simulate(bars, "15m", "flow_thrust")
        self.assertEqual(len(trades), 1)
        tr = trades[0]
        self.assertEqual(tr["side"], 1)
        self.assertEqual(tr["entry_time"], entry_idx * MS15)
        self.assertEqual(tr["entry_price"], 100.0)   # open of bar AFTER signal bar
        self.assertEqual(tr["exit_price"], 103.0)    # TP = entry + 3.0*ATR(1.0)
        self.assertEqual(tr["exit_reason"], "TARGET")
        self.assertAlmostEqual(tr["ret_net"], 0.03 - 0.0016)
        self.assertAlmostEqual(tr["ret_net_2x"], 0.03 - 0.0032)

    def test_below_threshold_no_trade(self):
        bars = self._series_with_flow(20.0)  # CI = 0.20 < 0.25
        self.assertEqual(simulate(bars, "15m", "flow_thrust"), [])

    def test_short_stop_before_target_worst_case(self):
        bars = flat_series(WARMUP_BARS + 15)
        for i in range(WARMUP_BARS, WARMUP_BARS + 14):
            bars[i]["delta"] = -30.0
        entry_idx = WARMUP_BARS + 14
        # one bar touches BOTH stop (102) and target (97): stop wins
        bars[entry_idx] = mkbar(entry_idx, o=100.0, h=102.5, l=96.5, c=100.0)
        trades = simulate(bars, "15m", "flow_thrust")
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["side"], -1)
        self.assertEqual(trades[0]["exit_reason"], "STOP")
        self.assertEqual(trades[0]["exit_price"], 102.0)

    def test_warmup_blocks_early_signals(self):
        bars = flat_series(300)
        for i in range(0, 200):  # extreme flow entirely inside warmup
            bars[i]["delta"] = 90.0
        self.assertEqual(simulate(bars, "15m", "flow_thrust"), [])

    def test_signal_on_final_bar_cannot_enter(self):
        # The window first crosses theta only at the FINAL bar (weak
        # flow + one huge print bar): (15*24 + 300)/1600 = 0.4125,
        # while one bar earlier it is 360/1600 = 0.225. No bar exists
        # after it to enter on -> zero trades.
        bars = flat_series(WARMUP_BARS + 16)
        for i in range(WARMUP_BARS, WARMUP_BARS + 15):
            bars[i]["delta"] = 24.0
        bars[WARMUP_BARS + 15]["delta"] = 300.0
        self.assertEqual(simulate(bars, "15m", "flow_thrust"), [])

    def test_one_position_at_a_time(self):
        bars = self._series_with_flow(30.0, n_flow=60, total=400)
        trades = simulate(bars, "15m", "flow_thrust")
        for a, b in zip(trades, trades[1:]):
            self.assertGreater(b["entry_time"], a["exit_time"])

class TestAbsorption(unittest.TestCase):
    def _setup(self, flow_delta, break_bar):
        bars = flat_series(320)
        for i in range(WARMUP_BARS, WARMUP_BARS + 16):
            bars[i]["delta"] = flow_delta
        bars[WARMUP_BARS + 15] = break_bar(WARMUP_BARS + 15)
        return bars

    def test_long_on_new_low_with_positive_flow(self):
        bars = self._setup(10.0, lambda i: mkbar(i, o=100.0, h=100.5, l=99.0, c=99.6, delta=10.0))
        entry_idx = WARMUP_BARS + 16
        bars[entry_idx] = mkbar(entry_idx, o=100.0, h=102.5, l=99.5, c=102.0)
        trades = simulate(bars, "15m", "flow_absorption")
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["side"], 1)
        # TP = entry + 2.0*ATR; ATR(signal bar) = 14.5/14 (see above)
        self.assertAlmostEqual(trades[0]["exit_price"], 100.0 + 2.0 * (14.5 / 14))
        self.assertEqual(trades[0]["exit_reason"], "TARGET")

    def test_no_trade_when_flow_confirms_the_break(self):
        # new low AND net selling (CI<0): flow confirms price -> no absorption trade
        bars = self._setup(-10.0, lambda i: mkbar(i, o=100.0, h=100.5, l=99.0, c=99.6, delta=-10.0))
        self.assertEqual(simulate(bars, "15m", "flow_absorption"), [])

    def test_short_on_new_high_with_negative_flow(self):
        bars = self._setup(-10.0, lambda i: mkbar(i, o=100.0, h=101.0, l=99.5, c=100.4, delta=-10.0))
        entry_idx = WARMUP_BARS + 16
        bars[entry_idx] = mkbar(entry_idx, o=100.0, h=100.5, l=97.5, c=98.0)
        trades = simulate(bars, "15m", "flow_absorption")
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["side"], -1)
        self.assertEqual(trades[0]["exit_reason"], "TARGET")
        self.assertAlmostEqual(trades[0]["exit_price"], 100.0 - 2.0 * (14.5 / 14))

    def test_time_exit_at_max_hold_close(self):
        bars = self._setup(10.0, lambda i: mkbar(i, o=100.0, h=100.5, l=99.0, c=99.6, delta=10.0))
        # entry bar + following bars stay inside [98.5, 102]: time exit
        trades = simulate(bars, "15m", "flow_absorption")
        self.assertEqual(len(trades), 1)
        tr = trades[0]
        self.assertEqual(tr["exit_reason"], "TIME")
        self.assertEqual(tr["exit_price"], 100.0)  # flat close
        held_bars = (tr["exit_time"] - tr["entry_time"]) // MS15 + 1
        self.assertEqual(held_bars, 24)  # 15m absorption max hold

if __name__ == "__main__":
    unittest.main(verbosity=2)
