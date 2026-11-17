#!/usr/bin/env python3
"""Panel verification gate for TASK-STR-DISC-004 — the SRS 5-check
pattern applied PER SYMBOL to the frozen 15-symbol ORB/VWAP panel.

Panel verdict is PASS only if EVERY symbol passes ALL FIVE checks;
any NOT_RUN makes the panel INCOMPLETE, never PASS. Exit 0 = PASS,
exit 5 = FAIL or INCOMPLETE. Writes verification_report.json into
the panel dir, and (on PASS) the frozen data_provenance.json.

  1. Gap audit — every NYSE session in 2023-01-01..2026-10-31 has
     exactly its expected bars (26 full / 10 early-close) at exactly
     the expected bar-starts; no bars on non-sessions; no duplicate
     timestamps. (Expected: 961 sessions, 24,842 bars per symbol.)
  2. Feed check — per-symbol median daily volume >= 10,000,000
     shares (split-adjusted, as served). Below that the panel is
     consistent with a single-venue (IEX-like) feed and FAILS.
  3. Split check — no overnight open/prev-close or close/prev-close
     ratio in the split bands [2.70, 3.30] / [0.303, 0.367] (SRS 3:1
     bands) or [9.0, 11.0] / [0.09, 0.111] (10:1 bands — this
     universe's in-window splits are 10:1). Extreme non-split
     overnight moves (> 50%) are findings to eyeball, not failures.
  4. Cross-source spot check — Yahoo Finance daily bars (chart API
     v8, interval=1d, keyless; the data-spec addendum v3 instrument),
     one retrieved file per symbol: <SYM>_yahoo_daily.json. Before
     comparison the file is put on the panel's split-adjusted basis
     by the declared transform (rows before a declared split's
     ex-date divided by its factor; declared splits: NVDA 10:1 ex
     2024-06-10, AVGO 10:1 ex 2024-10-14, NFLX 10:1 ex 2025-11-17).
     Deterministic sampling: 3 evenly spaced sessions per fold
     W1–W5. Closes within $0.02, highs/lows within $0.05; a sampled
     session absent from the file is a finding -> FAIL; >= 10
     compared required. No file -> NOT_RUN. With --pins, a retrieved
     file whose hash differs from its pin is a FAIL, not a re-pin.
  5. Freeze — SHA-256 of every symbol's panel file; if the pull's
     data_provenance_draft.json is present, a panel whose hash
     differs from the draft is a FAIL, not a re-pin.

Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nyse_calendar  # noqa: E402
import orb_vwap  # noqa: E402

ET = ZoneInfo("America/New_York")
SPAN_START = date(2023, 1, 1)
SPAN_END = date(2026, 10, 31)
EXPECTED_SESSIONS = 961
EXPECTED_BARS = 24842
VOLUME_FLOOR = 10_000_000
SPLIT_BANDS = [(2.70, 3.30), (0.303, 0.367), (9.0, 11.0), (0.09, 0.111)]
DECLARED_SPLITS: dict[str, list[tuple[date, float]]] = {
    "NVDA": [(date(2024, 6, 10), 10.0)],
    "AVGO": [(date(2024, 10, 14), 10.0)],
    "NFLX": [(date(2025, 11, 17), 10.0)],
}
CLOSE_TOL = 0.02
HL_TOL = 0.05


def panel_file(panel_dir: Path, symbol: str) -> Path:
    return panel_dir / f"{symbol}_15min_sip_2023-01-01_2026-10-31.csv"


def daily_aggregates(bars: list[dict]) -> dict:
    days: dict = {}
    for day, s_bars in orb_vwap.group_sessions(bars).items():
        days[day] = {
            "open": s_bars[0]["open"], "close": s_bars[-1]["close"],
            "high": max(b["high"] for b in s_bars),
            "low": min(b["low"] for b in s_bars),
            "volume": sum(b["volume"] for b in s_bars),
            "starts": [b["start_et"].time() for b in s_bars],
            "n": len(s_bars),
        }
    return days


def check_1_gap_audit(bars: list[dict], days: dict) -> dict:
    expected_sessions = nyse_calendar.sessions_between(SPAN_START, SPAN_END)
    problems = []
    stamps = [b["start_et"] for b in bars]
    if len(stamps) != len(set(stamps)):
        problems.append("duplicate timestamps present")
    panel_days = set(days)
    expected_set = set(expected_sessions)
    if panel_days != expected_set:
        missing = sorted(expected_set - panel_days)
        extra = sorted(panel_days - expected_set)
        if missing:
            problems.append(f"{len(missing)} sessions missing, e.g. {missing[:3]}")
        if extra:
            problems.append(f"{len(extra)} non-session dates present, e.g. {extra[:3]}")
    for day in expected_sessions:
        if day not in days:
            continue
        exp_starts = nyse_calendar.expected_bar_starts(day)
        if days[day]["starts"] != exp_starts:
            problems.append(f"{day}: bar-starts != expected "
                            f"({days[day]['n']} bars, expected {len(exp_starts)})")
            if len(problems) > 5:
                break
    return {"status": "FAIL" if problems else "PASS",
            "sessions": len(days), "expected_sessions": EXPECTED_SESSIONS,
            "bars": len(bars), "expected_bars": EXPECTED_BARS,
            "problems": problems[:10]}


def check_2_feed_volume(days: dict) -> dict:
    vols = [d["volume"] for d in days.values()]
    med = statistics.median(vols) if vols else 0.0
    return {"status": "PASS" if med >= VOLUME_FLOOR else "FAIL",
            "median_daily_volume": med, "floor": VOLUME_FLOOR}


def check_3_splits(days: dict) -> dict:
    ordered = sorted(days)
    hits, findings = [], []
    for prev, cur in zip(ordered, ordered[1:]):
        pc = days[prev]["close"]
        if pc <= 0:
            continue
        for label, val in (("open", days[cur]["open"]),
                           ("close", days[cur]["close"])):
            ratio = val / pc
            if any(lo <= ratio <= hi for lo, hi in SPLIT_BANDS):
                hits.append(f"{cur} {label}/prev-close={ratio:.3f} in split band")
            elif abs(ratio - 1.0) > 0.50:
                findings.append(f"{cur} {label}/prev-close={ratio:.3f} "
                                "(>50% overnight move — eyeball)")
    return {"status": "FAIL" if hits else "PASS",
            "band_hits": hits[:10], "findings": findings[:10]}


def load_yahoo(path: Path, symbol: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = payload["chart"]["result"][0]
    stamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    rows: dict = {}
    for i, ts in enumerate(stamps):
        day = datetime.fromtimestamp(ts, ET).date()
        o, h, l, c = (quote["open"][i], quote["high"][i],
                      quote["low"][i], quote["close"][i])
        if None in (o, h, l, c):
            continue
        for ex_date, factor in DECLARED_SPLITS.get(symbol, []):
            if day < ex_date:
                o, h, l, c = o / factor, h / factor, l / factor, c / factor
        rows[day] = {"open": o, "high": h, "low": l, "close": c}
    return rows


def check_4_cross_source(symbol: str, days: dict, cross_dir: Path,
                         pins: dict | None) -> dict:
    fpath = cross_dir / f"{symbol}_yahoo_daily.json"
    if not fpath.exists():
        return {"status": "NOT_RUN",
                "reason": f"no cross-source file at {fpath}"}
    digest = hashlib.sha256(fpath.read_bytes()).hexdigest()
    out: dict = {"file": fpath.name, "sha256": digest}
    if pins is not None:
        pinned = pins.get(symbol)
        if pinned is None:
            out.update(status="FAIL", reason="no pin recorded for symbol")
            return out
        if pinned != digest:
            out.update(status="FAIL",
                       reason="retrieved file hash != pin (FAIL, not re-pin)")
            return out
    try:
        yahoo = load_yahoo(fpath, symbol)
    except Exception as exc:  # noqa: BLE001 — reported as FAIL
        out.update(status="FAIL", reason=f"unparseable cross-source file: {exc}")
        return out
    compared = 0
    problems = []
    for _fid, s, e in orb_vwap.FOLDS:
        lo, hi = date.fromisoformat(s), date.fromisoformat(e)
        fold_days = sorted(d for d in days if lo <= d < hi)
        if not fold_days:
            continue
        step = len(fold_days) / 3
        for i in range(3):
            day = fold_days[int(i * step)]
            if day not in yahoo:
                problems.append(f"{day}: sampled session absent from "
                                "cross-source file")
                continue
            compared += 1
            p, y = days[day], yahoo[day]
            if abs(p["close"] - y["close"]) > CLOSE_TOL:
                problems.append(f"{day}: close panel={p['close']} "
                                f"yahoo={y['close']:.4f}")
            if abs(p["high"] - y["high"]) > HL_TOL:
                problems.append(f"{day}: high panel={p['high']} "
                                f"yahoo={y['high']:.4f}")
            if abs(p["low"] - y["low"]) > HL_TOL:
                problems.append(f"{day}: low panel={p['low']} "
                                f"yahoo={y['low']:.4f}")
    out["compared"] = compared
    if compared < 10:
        problems.append(f"only {compared} sessions compared (< 10 required)")
    out["problems"] = problems[:10]
    out["status"] = "FAIL" if problems else "PASS"
    return out


def check_5_freeze(panel_dir: Path, symbol: str, draft: dict | None) -> dict:
    fpath = panel_file(panel_dir, symbol)
    digest = hashlib.sha256(fpath.read_bytes()).hexdigest()
    out: dict = {"file": fpath.name, "sha256": digest}
    if draft is not None:
        want = (draft.get("symbols", {}).get(symbol, {}) or {}).get("sha256")
        if want is not None and want != digest:
            out.update(status="FAIL",
                       reason="panel hash != download-time draft (FAIL, not re-pin)")
            return out
    out["status"] = "PASS"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel-dir", required=True)
    ap.add_argument("--cross-dir", default=None,
                    help="dir holding <SYM>_yahoo_daily.json "
                         "(default: the panel dir)")
    ap.add_argument("--pins", default=None,
                    help="JSON file {symbol: sha256} pinning the "
                         "cross-source files")
    args = ap.parse_args()
    panel_dir = Path(args.panel_dir)
    cross_dir = Path(args.cross_dir) if args.cross_dir else panel_dir
    pins = None
    if args.pins:
        pins = json.loads(Path(args.pins).read_text(encoding="utf-8"))
    draft = None
    draft_path = panel_dir / "data_provenance_draft.json"
    if draft_path.exists():
        draft = json.loads(draft_path.read_text(encoding="utf-8"))

    report: dict = {"task": "TASK-STR-DISC-004", "symbols": {}}
    overall = "PASS"
    for symbol in orb_vwap.UNIVERSE:
        fpath = panel_file(panel_dir, symbol)
        if not fpath.exists():
            report["symbols"][symbol] = {"status": "FAIL",
                                         "reason": f"panel file missing: {fpath.name}"}
            overall = "FAIL"
            continue
        bars = orb_vwap.load_panel(fpath, symbol)
        days = daily_aggregates(bars)
        checks = {
            "check_1_gap_audit": check_1_gap_audit(bars, days),
            "check_2_feed_volume": check_2_feed_volume(days),
            "check_3_split": check_3_splits(days),
            "check_4_cross_source": check_4_cross_source(
                symbol, days, cross_dir, pins),
            "check_5_freeze": check_5_freeze(panel_dir, symbol, draft),
        }
        statuses = [c["status"] for c in checks.values()]
        sym_status = ("FAIL" if "FAIL" in statuses else
                      "INCOMPLETE" if "NOT_RUN" in statuses else "PASS")
        report["symbols"][symbol] = {"status": sym_status, "checks": checks}
        if sym_status == "FAIL":
            overall = "FAIL"
        elif sym_status == "INCOMPLETE" and overall == "PASS":
            overall = "INCOMPLETE"
        print(f"{symbol}: {sym_status} "
              f"({', '.join(k.split('_')[1] + '=' + v['status'] for k, v in checks.items())})")
    report["overall"] = overall
    (panel_dir / "verification_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(f"OVERALL: {overall} -> {panel_dir / 'verification_report.json'}")
    if overall == "PASS":
        freeze = {"task": "TASK-STR-DISC-004",
                  "frozen_by": "verify_orb_panel.py (check 5)",
                  "request": (draft or {}).get("request"),
                  "pulled_at_utc": (draft or {}).get("pulled_at_utc"),
                  "symbols": {s: report["symbols"][s]["checks"]
                              ["check_5_freeze"]["sha256"]
                              for s in orb_vwap.UNIVERSE}}
        (panel_dir / "data_provenance.json").write_text(
            json.dumps(freeze, indent=2), encoding="utf-8")
        print(f"freeze -> {panel_dir / 'data_provenance.json'}")
    return 0 if overall == "PASS" else 5


if __name__ == "__main__":
    sys.exit(main())
