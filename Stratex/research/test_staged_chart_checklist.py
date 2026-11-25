"""Tests for TASK-STR-086 staged chart-analysis checklist.

Stdlib unittest only (+ pandas, as the module under test). No network:
all market data is synthetic; the demo-fapi fetch path is tested with a
mocked opener. Run from Stratex/research/:

    python3 -m unittest test_staged_chart_checklist -v
"""

from __future__ import annotations

import io
import json
import math
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

import staged_chart_checklist as scc  # noqa: E402
from staged_chart_checklist import (  # noqa: E402
    add_indicators,
    check_min_rr,
    direction_from_regime,
    fetch_klines,
    klines_to_frame,
    run_pipeline,
    stage_data_quality,
    stage_final_report,
    stage_fundamentals,
    stage_market_structure,
    stage_news_sentiment,
    stage_risk_levels,
    stage_timeframe_context,
    swing_highs_lows,
)

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
STEP_MIN = {"1h": 60, "4h": 240, "1d": 1440}


def make_rows(n=250, interval="1h", start_price=100.0, drift=0.0005,
              wave=0.0, end_at=None):
    """Synthetic kline rows ending at `end_at` (default NOW).

    `drift` is the per-bar compounded return (keep |drift| small: the
    desk RegimeClassifier flags bb_width > 0.08 as HIGH_VOLATILITY, so
    a realistic hourly drift is ~0.05%/bar). `wave` adds a sine wobble
    for range-bound fixtures.
    """
    step = timedelta(minutes=STEP_MIN[interval])
    end = end_at or NOW
    rows = []
    prev_close = None
    for i in range(n):
        ts = end - (n - 1 - i) * step
        close = start_price * (1.0 + drift) ** i
        if wave:
            close = close * (1.0 + wave * math.sin(i / 2.0))
        rows.append({
            "timestamp": ts,
            "open": prev_close if prev_close is not None else close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": 1000.0,
            "close_time": ts + step - timedelta(milliseconds=1),
        })
        prev_close = close
    return rows


def make_frame(**kwargs):
    # "now" a day past the fixture end so the closed-candle filter in
    # klines_to_frame keeps every synthetic bar.
    return klines_to_frame(make_rows(**kwargs),
                           now=NOW + timedelta(days=1))


class TestIndicators(unittest.TestCase):
    def test_indicators_present_and_finite(self):
        feat = add_indicators(make_frame())
        last = feat.iloc[-1]
        for col in ("ema_50", "ema_200", "atr_14", "atr_pct", "adx_14", "bb_width"):
            self.assertTrue(math.isfinite(float(last[col])), col)

    def test_uptrend_regime(self):
        self.assertEqual(
            stage_market_structure(make_frame(drift=0.0005))["details"]["regime"],
            "TREND_UP")

    def test_downtrend_regime(self):
        self.assertEqual(
            stage_market_structure(make_frame(drift=-0.0005))["details"]["regime"],
            "TREND_DOWN")

    def test_flat_regime_is_range_or_low_volatility(self):
        section = stage_market_structure(make_frame(drift=0.0, wave=0.002))
        self.assertIn(section["details"]["regime"], ("RANGE", "LOW_VOLATILITY"))

    def test_thin_data_is_unknown(self):
        section = stage_market_structure(make_frame(n=30))
        self.assertEqual(section["details"]["regime"], "UNKNOWN")
        self.assertEqual(section["status"], "INCONCLUSIVE")

    def test_swing_highs_lows(self):
        swings = swing_highs_lows(make_frame())
        self.assertGreater(swings["swing_high"], swings["swing_low"])


class TestDataQuality(unittest.TestCase):
    def test_complete_feed_passes(self):
        frames = {tf: make_frame(interval=tf) for tf in ("1d", "4h", "1h")}
        section = stage_data_quality(frames, expected=250, now=NOW)
        self.assertEqual(section["status"], "PASS")
        self.assertTrue(section["details"]["data_trusted"])

    def test_missing_bars_fail_closed(self):
        frames = {"1h": make_frame(n=240)}
        section = stage_data_quality(frames, expected=250, now=NOW)
        self.assertEqual(section["status"], "FAIL")
        self.assertFalse(section["details"]["data_trusted"])
        self.assertIn("missing", section["summary"].lower())

    def test_gap_detected(self):
        df = make_frame()
        df = df.drop(index=[100]).reset_index(drop=True)  # one bar removed
        section = stage_data_quality({"1h": df}, expected=249, now=NOW)
        self.assertEqual(section["details"]["per_timeframe"]["1h"]["gaps"], 1)
        self.assertEqual(section["status"], "FAIL")

    def test_stale_feed_detected(self):
        frames = {"1h": make_frame(end_at=NOW - timedelta(days=2))}
        section = stage_data_quality(frames, expected=250, now=NOW)
        self.assertTrue(section["details"]["per_timeframe"]["1h"]["stale"])
        self.assertEqual(section["status"], "FAIL")

    def test_empty_frame_fails(self):
        section = stage_data_quality({"1h": None}, expected=250, now=NOW)
        self.assertEqual(section["status"], "FAIL")
        self.assertFalse(section["details"]["data_trusted"])


class TestTimeframeContext(unittest.TestCase):
    def test_agreement(self):
        section = stage_timeframe_context(
            {"1d": "TREND_UP", "4h": "TREND_UP", "1h": "TREND_UP"})
        self.assertEqual(section["status"], "PASS")
        self.assertTrue(section["details"]["agreement"])

    def test_htf_conflict_flagged_not_hidden(self):
        section = stage_timeframe_context(
            {"1d": "TREND_DOWN", "4h": "TREND_UP", "1h": "TREND_UP"})
        self.assertTrue(section["details"]["htf_conflict"])
        self.assertEqual(section["status"], "INCONCLUSIVE")
        self.assertIn("flagged", section["summary"].lower()
                      + " ".join(section["details"]["notes"]).lower())


class TestFundamentalsAndNews(unittest.TestCase):
    def test_fundamentals_gap_named_no_invention(self):
        section = stage_fundamentals("BTCUSDT")
        details = section["details"]
        self.assertTrue(details["not_available_from_chart"])
        self.assertIsNone(details["available_facts"]["funding_rate"])
        self.assertEqual(details["verdict"], "NO_CONTRADICTING_EVIDENCE")
        self.assertIn("never", details["verdict_meaning"])

    def test_news_no_events_recorded_as_none_not_neutral(self):
        section = stage_news_sentiment("BTCUSDT", NOW, NOW, events=[])
        self.assertEqual(section["details"]["events_in_window"], [])
        self.assertIn("recorded as none", section["summary"].lower())
        self.assertEqual(section["details"]["verdict"],
                         "NO_CONTRADICTING_EVIDENCE")
        self.assertEqual(section["status"], "PASS")

    def test_news_high_impact_flagged(self):
        events = [{"date": "2026-11-25", "time": "13:30",
                   "name": "Consumer Price Index", "kind": "macro",
                   "impact": "high"}]
        section = stage_news_sentiment("BTCUSDT", NOW, NOW, events=events)
        self.assertEqual(section["status"], "INCONCLUSIVE")
        self.assertEqual(section["details"]["verdict"],
                         "HIGH_IMPACT_EVENT_IN_WINDOW")


class TestRiskLevels(unittest.TestCase):
    def test_long_levels_and_rr(self):
        df = make_frame(drift=0.0005)
        section = stage_risk_levels(df, "LONG", data_trusted=True)
        self.assertEqual(section["status"], "PASS")
        d = section["details"]
        self.assertAlmostEqual(d["risk_reward"], 2.0, places=6)
        self.assertTrue(d["gate_pass"])
        self.assertLess(d["stop"], d["entry"])
        self.assertGreater(d["target"], d["entry"])
        self.assertGreater(d["reference_position_size"], 0)

    def test_short_levels(self):
        df = make_frame(drift=-0.0005)
        section = stage_risk_levels(df, "SHORT", data_trusted=True)
        d = section["details"]
        self.assertGreater(d["stop"], d["entry"])
        self.assertLess(d["target"], d["entry"])
        self.assertAlmostEqual(d["risk_reward"], 2.0, places=6)

    def test_min_rr_gate(self):
        self.assertTrue(check_min_rr(1.2))
        self.assertTrue(check_min_rr(2.0))
        self.assertFalse(check_min_rr(1.19))

    def test_blocked_without_direction(self):
        section = stage_risk_levels(make_frame(), "NO_SETUP", data_trusted=True)
        self.assertEqual(section["status"], "BLOCKED")

    def test_blocked_on_untrusted_data(self):
        section = stage_risk_levels(make_frame(), "LONG", data_trusted=False)
        self.assertEqual(section["status"], "BLOCKED")
        self.assertIn("untrusted", section["summary"].lower())


class TestDirectionAndFinalReport(unittest.TestCase):
    def test_direction_mapping(self):
        self.assertEqual(direction_from_regime("TREND_UP"), "LONG")
        self.assertEqual(direction_from_regime("TREND_DOWN"), "SHORT")
        self.assertEqual(direction_from_regime("RANGE"), "NO_SETUP")
        self.assertEqual(direction_from_regime("UNKNOWN"), "NO_SETUP")

    def test_final_report_no_setup(self):
        sections = {
            "market_structure": {"status": "PASS", "summary": "ok"},
            "risk_levels": {"status": "BLOCKED", "summary": "no setup",
                            "details": {"direction": "NO_SETUP",
                                        "data_trusted": True}},
        }
        section = stage_final_report(sections, "BTCUSDT", "test input")
        self.assertEqual(section["details"]["verdict"], "NO_SETUP")


class TestFetchKlines(unittest.TestCase):
    def test_http_error_surfaces_status(self):
        def opener(url, timeout=None):
            raise urllib.error.HTTPError(
                url, 451, "Unavailable For Legal Reasons", {},
                io.BytesIO(b'{"code": 0, "msg": "restricted location"}'))
        with self.assertRaises(RuntimeError) as ctx:
            fetch_klines("BTCUSDT", "1h", opener=opener)
        self.assertIn("451", str(ctx.exception))

    def test_error_envelope_surfaces(self):
        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return b'{"code": 0, "msg": "Service unavailable"}'
        with self.assertRaises(RuntimeError):
            fetch_klines("BTCUSDT", "1h", opener=lambda u, timeout=None: Resp())


class TestPipeline(unittest.TestCase):
    def _synthetic_fetch(self, symbol, interval, limit=250):
        # End one step before real now so every bar is closed.
        end_at = datetime.now(timezone.utc) - timedelta(
            minutes=STEP_MIN[interval])
        return make_rows(n=limit, interval=interval, drift=0.0005,
                         end_at=end_at)

    def test_full_pipeline_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_pipeline("BTCUSDT", fetch_fn=self._synthetic_fetch,
                                  out_dir=tmp)
            self.assertEqual(set(report["sections"]), set(scc.STAGES))
            self.assertEqual(report["verdict"], "SETUP")
            self.assertEqual(report["sections"]["risk_levels"]["status"], "PASS")
            self.assertIsNone(report["fetch_error"])
            files = list(Path(tmp).glob("TASK-STR-086-STAGED-REPORT-BTCUSDT-*"))
            self.assertEqual(len(files), 2)  # one JSON + one Markdown
            md = next(p for p in files if p.suffix == ".md").read_text()
            self.assertIn("SETUP", md)
            self.assertIn("data-rendered chart", md)
            js = json.loads(next(p for p in files if p.suffix == ".json").read_text())
            self.assertEqual(js["verdict"], "SETUP")

    def test_pipeline_fetch_failure_leaves_partial_attributable_report(self):
        def failing_fetch(symbol, interval, limit=250):
            raise RuntimeError(
                "demo-fapi klines fetch failed for BTCUSDT 1h: HTTP 451")
        with tempfile.TemporaryDirectory() as tmp:
            report = run_pipeline("BTCUSDT", fetch_fn=failing_fetch, out_dir=tmp)
            self.assertEqual(report["verdict"], "BLOCKED")
            self.assertIn("451", report["fetch_error"])
            # No silent skip: every stage has a recorded section.
            self.assertEqual(set(report["sections"]), set(scc.STAGES))
            self.assertEqual(report["sections"]["market_structure"]["status"],
                             "ERROR")
            self.assertEqual(report["sections"]["data_quality"]["status"], "FAIL")
            self.assertEqual(report["sections"]["risk_levels"]["status"], "BLOCKED")
            self.assertEqual(report["sections"]["final_report"]["status"], "BLOCKED")
            # Stages 4-5 still record what is knowable without klines.
            self.assertEqual(report["sections"]["fundamentals"]["status"], "PASS")
            files = list(Path(tmp).glob("TASK-STR-086-STAGED-REPORT-BTCUSDT-*"))
            self.assertEqual(len(files), 2)
            md = next(p for p in files if p.suffix == ".md").read_text()
            self.assertIn("451", md)

    def test_pipeline_conflicting_timeframes_no_setup(self):
        def mixed_fetch(symbol, interval, limit=250):
            drift = -0.0005 if interval == "1d" else 0.0005
            end_at = datetime.now(timezone.utc) - timedelta(
                minutes=STEP_MIN[interval])
            return make_rows(n=limit, interval=interval, drift=drift,
                             end_at=end_at)
        with tempfile.TemporaryDirectory() as tmp:
            report = run_pipeline("BTCUSDT", fetch_fn=mixed_fetch, out_dir=tmp)
            self.assertTrue(report["sections"]["timeframe_context"]
                            ["details"]["htf_conflict"])
            self.assertEqual(report["verdict"], "NO_SETUP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
