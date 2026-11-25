"""Stratex research desk — staged chart-analysis checklist (TASK-STR-086).

Seven stages, run in order over a rendered chart built from real Binance
Demo Trading (demo-fapi) klines — NOT a broker-terminal screenshot. The
input is a data-rendered chart: OHLCV klines fetched from the public
demo-fapi endpoint (no key, no account, read-only). The persisted report
says so.

Stages:
  1. Market structure — trend/regime (RegimeClassifier), swing highs/lows,
     EMA50/EMA200 alignment.
  2. Data quality — kline completeness, gaps, stale-feed check, venue noted.
     Fail-closed on missing bars.
  3. Timeframe context — same symbol on 1d + 4h + 1h; regime agreement /
     disagreement recorded; a higher-timeframe trend against the trading
     timeframe is flagged, not hidden.
  4. Fundamentals — from a chart alone there is no fundamentals feed: the
     funding/venue facts available are recorded and the on-chain /
     fundamental inputs are marked NOT AVAILABLE, with the gap named.
     No invented fundamentals.
  5. News sentiment — economic-calendar items overlapping the chart window
     (research/economic_calendar.py). No calendar item is recorded as
     none, never as neutral.
  6. Risk levels — ATR(14)-based stop, R:R for the proposed setup,
     position-size math at the desk's 0.5% risk/trade standard, min R:R
     1.2 gate (same gate as the deployed daily-trend config).
  7. Final report — entry, stop, target, R:R, plus per-stage sections,
     persisted as one JSON + one Markdown report under Stratex/research/.

Honest-limits rule (stages 4-5): a "PASS" there means "no contradicting
evidence found in the available feed", never "fundamentals confirm".
That meaning is written into every stage 4/5 section.

Each stage writes its section before the next stage runs: run_pipeline
persists the partial report (JSON + Markdown) after every stage, so a
failure mid-pipeline leaves a partial, attributable report — never a
silent skip.

Dependencies: Python standard library + pandas only (same as the desk's
existing research modules). No python-binance, no API keys, no account
access, no orders, no writes anywhere except the report files.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:  # Desk convention: research modules import as top-level from Stratex/.
    from regime_classifier import RegimeClassifier
except ImportError:  # Fallback when imported as part of the research package.
    from research.regime_classifier import RegimeClassifier

logger = logging.getLogger("staged_chart_checklist")

# --- Desk constants ---------------------------------------------------------
VENUE = "demo-fapi (Binance Demo Trading, public klines, no key)"
DEMO_FAPI_BASE = "https://demo-fapi.binance.com"
KLINE_LIMIT = 250
TRADING_TF = "1h"
CONTEXT_TFS = ("1d", "4h", "1h")
TIMEFRAME_MINUTES = {"1h": 60, "4h": 240, "1d": 1440}
MIN_RR = 1.2
TARGET_RR = 2.0
STOP_ATR_MULT = 1.5
RISK_PER_TRADE_PCT = 0.5
REFERENCE_EQUITY_USD = 10000.0  # Reference figure for sizing math only.
STAGES = (
    "market_structure",
    "data_quality",
    "timeframe_context",
    "fundamentals",
    "news_sentiment",
    "risk_levels",
    "final_report",
)

# Status vocabulary: PASS / FAIL / INCONCLUSIVE / BLOCKED / NOT_AVAILABLE / ERROR
FEED_LIMIT_NOTE = (
    "PASS on this stage means 'no contradicting evidence found in the "
    "available feed', never 'fundamentals/news confirm'."
)


# --- Market-data fetch (read-only, public endpoint, no key) ------------------
def fetch_klines(symbol: str, interval: str, limit: int = KLINE_LIMIT,
                 base_url: str = DEMO_FAPI_BASE, timeout: float = 20.0,
                 opener=None) -> list[dict]:
    """Fetch closed klines from demo-fapi /fapi/v1/klines (public, no key).

    Returns a list of dicts with timestamp/open/high/low/close/volume
    (timestamps as UTC datetimes). Raises RuntimeError on any HTTP or
    transport failure, with the status/body recorded — never an empty
    frame masquerading as data.
    """
    url = (f"{base_url}/fapi/v1/klines?symbol={symbol}"
           f"&interval={interval}&limit={limit}")
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(
            f"demo-fapi klines fetch failed for {symbol} {interval}: "
            f"HTTP {exc.code} {body}") from exc
    except Exception as exc:  # transport error, DNS, timeout, bad JSON
        raise RuntimeError(
            f"demo-fapi klines fetch failed for {symbol} {interval}: "
            f"{type(exc).__name__}: {exc}") from exc
    if isinstance(payload, dict):  # error envelope, e.g. {"code": 0, ...}
        raise RuntimeError(
            f"demo-fapi klines fetch failed for {symbol} {interval}: "
            f"error envelope {json.dumps(payload)[:300]}")
    rows = []
    for k in payload:
        rows.append({
            "timestamp": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
            "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
            "close": float(k[4]), "volume": float(k[5]),
            "close_time": datetime.fromtimestamp(k[6] / 1000, tz=timezone.utc),
        })
    return rows


def klines_to_frame(rows: list[dict], now: datetime | None = None) -> pd.DataFrame:
    """Kline rows -> clean OHLCV frame, sorted, de-duplicated, typed.

    Drops the still-forming candle (close_time in the future), following
    the desk's closed-candle convention in Stratex/data.py.
    """
    now = now or datetime.now(timezone.utc)
    df = pd.DataFrame(rows, columns=[
        "timestamp", "open", "high", "low", "close", "volume", "close_time"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
    df = df[df["close_time"] <= now].copy()
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return df.reset_index(drop=True)


# --- Indicators (pandas only; Wilder smoothing via ewm) ---------------------
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Attach ema_50, ema_200, atr_14, atr_pct, adx_14, bb_width.

    Returns a new frame; the input frame is not mutated.
    """
    out = df.copy()
    close = out["close"]
    out["ema_50"] = close.ewm(span=50, adjust=False).mean()
    out["ema_200"] = close.ewm(span=200, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr_14"] = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
    out["atr_pct"] = out["atr_14"] / close

    up = out["high"] - out["high"].shift(1)
    down = out["low"].shift(1) - out["low"]
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr_smooth = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / 14, adjust=False).mean() / tr_smooth
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / 14, adjust=False).mean() / tr_smooth
    di_sum = (plus_di + minus_di).replace(0, float("nan"))
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    out["adx_14"] = dx.ewm(alpha=1.0 / 14, adjust=False).mean()

    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["bb_width"] = 4.0 * std / mid
    return out


def swing_highs_lows(df: pd.DataFrame, window: int = 5) -> dict:
    """Most recent swing high / swing low over a rolling window."""
    if df is None or len(df) < window:
        return {"swing_high": None, "swing_low": None, "window": window}
    highs = df["high"].rolling(window).max()
    lows = df["low"].rolling(window).min()
    return {
        "swing_high": float(highs.iloc[-1]),
        "swing_low": float(lows.iloc[-1]),
        "window": window,
    }


# --- Stage 1: market structure ----------------------------------------------
def stage_market_structure(df: pd.DataFrame) -> dict:
    section = {"stage": 1, "name": "market_structure"}
    if df is None or len(df) == 0:
        section.update(status="ERROR", summary="No klines: cannot assess structure.",
                       details={"bars": 0})
        return section
    feat = add_indicators(df)
    regime = RegimeClassifier.classify_regime(feat)
    last = feat.iloc[-1]
    swings = swing_highs_lows(df)
    close = float(last["close"])
    ema50, ema200 = float(last["ema_50"]), float(last["ema_200"])
    details = {
        "bars": int(len(df)),
        "regime": regime,
        "close": close,
        "ema_50": ema50,
        "ema_200": ema200,
        "ema_alignment": ("bullish" if ema50 > ema200 else
                          "bearish" if ema50 < ema200 else "flat"),
        "adx_14": (None if pd.isna(last["adx_14"]) else float(last["adx_14"])),
        "atr_14": (None if pd.isna(last["atr_14"]) else float(last["atr_14"])),
        "atr_pct": (None if pd.isna(last["atr_pct"]) else float(last["atr_pct"])),
        "bb_width": (None if pd.isna(last["bb_width"]) else float(last["bb_width"])),
        "swing_high": swings["swing_high"],
        "swing_low": swings["swing_low"],
        "last_bar": str(df["timestamp"].iloc[-1]),
    }
    if regime == "UNKNOWN":
        section.update(
            status="INCONCLUSIVE",
            summary=("Regime UNKNOWN (thin or contradictory data) — "
                     "no directional setup from structure alone."),
            details=details)
    else:
        section.update(
            status="PASS",
            summary=f"Regime {regime}; EMA alignment {details['ema_alignment']}.",
            details=details)
    return section


# --- Stage 2: data quality ---------------------------------------------------
def stage_data_quality(frames: dict, expected: int = KLINE_LIMIT,
                       now: datetime | None = None) -> dict:
    section = {"stage": 2, "name": "data_quality"}
    now = now or datetime.now(timezone.utc)
    per_tf: dict[str, dict] = {}
    trusted = True
    problems: list[str] = []
    for tf, df in frames.items():
        step = TIMEFRAME_MINUTES.get(tf)
        received = 0 if df is None else int(len(df))
        gaps = 0
        stale = None
        last_close = None
        if df is not None and received > 1 and step:
            diffs = df["timestamp"].diff().dt.total_seconds().div(60).dropna()
            gaps = int((diffs != step).sum())
            last_close = df["close_time"].iloc[-1]
            lag_min = (now - last_close.to_pydatetime()).total_seconds() / 60.0
            stale = lag_min > max(15.0, step * 1.5)
        elif df is not None and received:
            last_close = df["close_time"].iloc[-1]
        missing = max(0, expected - received)
        ok = received >= expected and gaps == 0 and stale is not True
        if not ok:
            trusted = False
            if missing:
                problems.append(f"{tf}: {missing} bar(s) missing "
                                f"({received}/{expected})")
            if gaps:
                problems.append(f"{tf}: {gaps} timestamp gap(s)")
            if stale:
                problems.append(f"{tf}: stale feed (last close {last_close})")
        per_tf[tf] = {
            "expected_bars": expected, "received_bars": received,
            "missing_bars": missing, "gaps": gaps,
            "stale": stale,
            "last_close_time": None if last_close is None else str(last_close),
        }
    section["details"] = {"venue": VENUE, "per_timeframe": per_tf,
                          "data_trusted": trusted, "problems": problems}
    if trusted:
        section.update(status="PASS",
                       summary="All timeframes complete, no gaps, feed fresh.")
    else:
        # Fail-closed: missing bars fail the stage and block downstream trust.
        section.update(status="FAIL",
                       summary="Data quality FAIL (fail-closed): "
                               + "; ".join(problems))
    return section


# --- Stage 3: timeframe context ----------------------------------------------
def stage_timeframe_context(regimes: dict) -> dict:
    section = {"stage": 3, "name": "timeframe_context"}
    trade = regimes.get(TRADING_TF)
    higher = {tf: r for tf, r in regimes.items() if tf != TRADING_TF}
    conflict = False
    notes = []
    if trade in ("TREND_UP", "TREND_DOWN"):
        opposite = "TREND_DOWN" if trade == "TREND_UP" else "TREND_UP"
        for tf, regime in higher.items():
            if regime == opposite:
                conflict = True
                notes.append(
                    f"Higher timeframe {tf} is {regime} against trading "
                    f"timeframe {TRADING_TF} {trade} — flagged, not hidden.")
    agreement = (len(set(regimes.values())) == 1) if regimes else False
    details = {"regimes": dict(regimes), "trading_timeframe": TRADING_TF,
               "agreement": agreement, "htf_conflict": conflict, "notes": notes}
    if not regimes or trade is None:
        section.update(status="BLOCKED",
                       summary="No timeframe regimes available.",
                       details=details)
    elif conflict:
        section.update(status="INCONCLUSIVE",
                       summary="Higher-timeframe trend conflicts with the "
                               "trading timeframe — no setup while conflict stands.",
                       details=details)
    elif agreement:
        section.update(status="PASS",
                       summary="All timeframes agree: "
                               + ", ".join(f"{t}={r}" for t, r in regimes.items()) + ".",
                       details=details)
    else:
        section.update(status="PASS",
                       summary="Timeframes disagree without a direct trend "
                               "conflict; disagreement recorded.",
                       details=details)
    return section


# --- Stage 4: fundamentals (feed-limited by design) --------------------------
def stage_fundamentals(symbol: str, funding_rate: float | None = None,
                       funding_error: str | None = None) -> dict:
    section = {"stage": 4, "name": "fundamentals"}
    available = {
        "symbol": symbol,
        "venue": VENUE,
        "contract_type": "USDT-M perpetual (Binance USD-margined futures)",
        "funding_rate": funding_rate,
        "funding_rate_source": ("demo-fapi /fapi/v1/premiumIndex"
                                if funding_rate is not None else None),
    }
    not_available = [
        "on-chain flows", "exchange reserves / netflows",
        "open interest history", "liquidation map",
        "project/token fundamentals (revenue, unlocks, roadmap)",
        "order-book depth snapshot",
    ]
    if funding_error:
        available["funding_rate_error"] = funding_error
    section["details"] = {
        "available_facts": available,
        "not_available_from_chart": not_available,
        "verdict": "NO_CONTRADICTING_EVIDENCE",
        "verdict_meaning": FEED_LIMIT_NOTE,
    }
    section.update(
        status="PASS",
        summary=("No contradicting fundamental evidence in the available "
                 "feed. On-chain/fundamental inputs are NOT AVAILABLE from "
                 "a chart — the gap is named above, nothing is synthesised."))
    return section


# --- Stage 5: news sentiment (feed-limited by design) -------------------------
def _load_calendar_events(calendar_store: str | None,
                          refresh: bool) -> tuple[list[dict], str]:
    """Best-effort load of economic-calendar events.

    Returns (events, note). Never raises: a feed failure is recorded,
    not hidden.
    """
    try:
        from economic_calendar import EconomicCalendar
    except ImportError as exc:
        return [], f"economic_calendar module unavailable ({exc}); feed not read."
    store = calendar_store or "economic_calendar.jsonl"
    try:
        cal = EconomicCalendar(store_path=store)
        if refresh:
            try:
                cal.refresh(days_ahead=7)
            except Exception as exc:  # keep serving the last stored events
                return ([e.to_dict() for e in cal.upcoming(days=7)],
                        f"calendar refresh failed ({exc}); serving stored events.")
        return ([e.to_dict() for e in cal.upcoming(days=7)],
                "calendar read from store"
                + (" (refreshed)" if refresh else " (no refresh attempted)") + ".")
    except Exception as exc:
        return [], f"calendar store unreadable ({exc})."


def stage_news_sentiment(symbol: str, window_start: datetime | None = None,
                         window_end: datetime | None = None,
                         calendar_store: str | None = None,
                         refresh_calendar: bool = False,
                         events: list[dict] | None = None) -> dict:
    section = {"stage": 5, "name": "news_sentiment"}
    note = ""
    if events is None:
        events, note = _load_calendar_events(calendar_store, refresh_calendar)
    now = datetime.now(timezone.utc)
    start = window_start or now
    end = window_end or now
    overlapping = []
    for event in events:
        try:
            day = datetime.fromisoformat(event.get("date", "")).date()
        except ValueError:
            continue
        if start.date() <= day <= end.date():
            overlapping.append(event)
    high_impact = [e for e in overlapping if e.get("impact") == "high"]
    details = {
        "window": f"{start.date()} to {end.date()}",
        "events_in_window": overlapping,
        "high_impact_in_window": high_impact,
        "calendar_note": note,
        "verdict": ("HIGH_IMPACT_EVENT_IN_WINDOW" if high_impact
                    else "NO_CONTRADICTING_EVIDENCE"),
        "verdict_meaning": FEED_LIMIT_NOTE,
    }
    if high_impact:
        names = ", ".join(e.get("name", "?") for e in high_impact)
        section.update(
            status="INCONCLUSIVE",
            summary=f"High-impact event(s) in window: {names} — no setup "
                    "into the event without coordinator clearance.",
            details=details)
    elif overlapping:
        section.update(
            status="PASS",
            summary=(f"{len(overlapping)} calendar item(s) in window, none "
                     "high-impact — no contradicting evidence in the feed."),
            details=details)
    else:
        section.update(
            status="PASS",
            summary=("No calendar items overlap the chart window — recorded "
                     "as none, not as neutral."),
            details=details)
    return section


# --- Stage 6: risk levels ------------------------------------------------------
def check_min_rr(rr: float, minimum: float = MIN_RR) -> bool:
    return rr >= minimum


def stage_risk_levels(df: pd.DataFrame, direction: str,
                      data_trusted: bool = True) -> dict:
    section = {"stage": 6, "name": "risk_levels"}
    if not data_trusted:
        section.update(
            status="BLOCKED",
            summary="Data quality failed — risk levels are not computed on "
                    "untrusted data.",
            details={"direction": direction, "data_trusted": False})
        return section
    if direction not in ("LONG", "SHORT"):
        section.update(
            status="BLOCKED",
            summary=f"No directional setup ({direction}) — no risk levels.",
            details={"direction": direction, "data_trusted": data_trusted})
        return section
    if df is None or len(df) < 15:
        section.update(status="ERROR",
                       summary="Too few bars to compute ATR(14).",
                       details={"direction": direction, "bars": 0 if df is None else len(df)})
        return section
    feat = add_indicators(df)
    last = feat.iloc[-1]
    atr = float(last["atr_14"])
    entry = float(last["close"])
    if not (math.isfinite(atr) and atr > 0):
        section.update(status="ERROR", summary="ATR(14) not finite — no levels.",
                       details={"direction": direction, "atr_14": atr})
        return section
    stop_dist = STOP_ATR_MULT * atr
    target_dist = TARGET_RR * stop_dist
    if direction == "LONG":
        stop, target = entry - stop_dist, entry + target_dist
    else:
        stop, target = entry + stop_dist, entry - target_dist
    rr = abs(target - entry) / abs(entry - stop)
    risk_usd = REFERENCE_EQUITY_USD * RISK_PER_TRADE_PCT / 100.0
    size = risk_usd / stop_dist
    details = {
        "direction": direction,
        "entry": entry, "stop": stop, "target": target,
        "atr_14": atr, "stop_distance": stop_dist,
        "target_distance": target_dist, "risk_reward": rr,
        "min_rr_gate": MIN_RR, "gate_pass": check_min_rr(rr),
        "risk_per_trade_pct": RISK_PER_TRADE_PCT,
        "reference_equity_usd": REFERENCE_EQUITY_USD,
        "reference_risk_usd": risk_usd,
        "reference_position_size": size,
        "sizing_note": ("Position size = (reference equity x risk%) / stop "
                        "distance; reference equity is a sizing reference "
                        "only, not an account balance."),
    }
    if not check_min_rr(rr):
        section.update(status="FAIL",
                       summary=f"R:R {rr:.2f} below the {MIN_RR} minimum gate.",
                       details=details)
    else:
        section.update(status="PASS",
                       summary=(f"{direction} entry {entry:.2f}, stop {stop:.2f}, "
                                f"target {target:.2f}, R:R {rr:.2f} "
                                f"(gate {MIN_RR}: pass)."),
                       details=details)
    return section


# --- Direction + stage 7: final report ----------------------------------------
def direction_from_regime(regime: str) -> str:
    if regime == "TREND_UP":
        return "LONG"
    if regime == "TREND_DOWN":
        return "SHORT"
    return "NO_SETUP"


def stage_final_report(sections: dict, symbol: str, input_note: str) -> dict:
    section = {"stage": 7, "name": "final_report"}
    risk = sections.get("risk_levels", {})
    risk_details = risk.get("details", {}) if isinstance(risk, dict) else {}
    verdict = "BLOCKED"
    if risk.get("status") == "PASS":
        verdict = "SETUP"
    elif risk.get("status") == "BLOCKED":
        # NO_SETUP only when the block is "no directional setup"; a block
        # on untrusted data (or any other reason) stays BLOCKED.
        verdict = ("NO_SETUP" if risk_details.get("direction") == "NO_SETUP"
                   and risk_details.get("data_trusted", True) else "BLOCKED")
    elif sections.get("market_structure", {}).get("status") in ("PASS", "INCONCLUSIVE"):
        verdict = "NO_SETUP"
    per_stage = {name: {"status": s.get("status"), "summary": s.get("summary")}
                 for name, s in sections.items() if isinstance(s, dict)}
    details = {
        "symbol": symbol,
        "input": input_note,
        "verdict": verdict,
        "entry": risk_details.get("entry"),
        "stop": risk_details.get("stop"),
        "target": risk_details.get("target"),
        "risk_reward": risk_details.get("risk_reward"),
        "direction": risk_details.get("direction"),
        "per_stage": per_stage,
        "feed_limits": (
            "Stages 4-5 are feed-limited by design: a chart carries no "
            "fundamentals feed and no news feed. PASS there means 'no "
            "contradicting evidence found in the available feed', never "
            "'fundamentals confirm'."),
    }
    if verdict == "SETUP":
        summary = (f"SETUP {risk_details.get('direction')} {symbol}: entry "
                   f"{risk_details.get('entry'):.2f}, stop "
                   f"{risk_details.get('stop'):.2f}, target "
                   f"{risk_details.get('target'):.2f}, "
                   f"R:R {risk_details.get('risk_reward'):.2f}.")
    elif verdict == "NO_SETUP":
        summary = "NO_SETUP — stages ran; no directional setup met the gates."
    else:
        summary = "BLOCKED — the pipeline could not complete; see per-stage reasons."
    section.update(status="PASS" if verdict in ("SETUP", "NO_SETUP") else "BLOCKED",
                   summary=summary, details=details)
    return section


# --- Report rendering / persistence --------------------------------------------
def render_markdown(report: dict) -> str:
    lines = [
        f"# Staged chart-analysis checklist — {report.get('symbol')}",
        "",
        f"Generated: {report.get('generated_at')} (UTC) | "
        f"Task: TASK-STR-086 | Worker: Muse TP6",
        "",
        f"Input: {report.get('input_note')}",
        "",
        f"**Verdict: {report.get('verdict', 'BLOCKED')}**",
        "",
        "## Per-stage summary",
        "",
        "| Stage | Name | Status | Summary |",
        "|---:|---|---|---|",
    ]
    for name in STAGES:
        s = report.get("sections", {}).get(name, {})
        lines.append(f"| {s.get('stage', '?')} | {name} | {s.get('status', 'NOT_RUN')} "
                     f"| {s.get('summary', 'not run')} |")
    lines += ["", "## Stage detail", ""]
    for name in STAGES:
        s = report.get("sections", {}).get(name)
        if not s:
            lines += [f"### {name}", "", "NOT RUN.", ""]
            continue
        lines += [f"### {name} — {s.get('status')}", "",
                  str(s.get("summary", "")), "",
                  "```json",
                  json.dumps(s.get("details", {}), indent=2, default=str),
                  "```", ""]
    if report.get("fetch_error"):
        lines += ["## Fetch failure", "", report["fetch_error"], ""]
    lines += ["## Caveats", "",
              "- Stages 4-5 are feed-limited by design; PASS there means "
              "'no contradicting evidence found in the available feed'.",
              "- The chart input is a data-rendered chart from real klines, "
              "not a screenshot of a broker terminal.",
              "- Demo account only; no live trading; no orders placed.",
              ""]
    return "\n".join(lines)


def default_report_paths(symbol: str, out_dir: str | None = None) -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = Path(out_dir) if out_dir else Path(__file__).resolve().parent
    stem = f"TASK-STR-086-STAGED-REPORT-{symbol}-{stamp}"
    return base / f"{stem}.json", base / f"{stem}.md"


def write_report(report: dict, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")


# --- Pipeline orchestration ------------------------------------------------------
def run_pipeline(symbol: str, fetch_fn=None, out_dir: str | None = None,
                 calendar_store: str | None = None,
                 refresh_calendar: bool = False,
                 funding_rate: float | None = None,
                 funding_error: str | None = None,
                 json_path: Path | None = None, md_path: Path | None = None,
                 now: datetime | None = None) -> dict:
    """Run all seven stages in order, persisting after each stage.

    A stage that raises records an ERROR section and the pipeline
    continues where the remaining stages can still run; stages that
    need missing data record BLOCKED with the reason. The partial
    report is written to disk after every stage, so a crash leaves an
    attributable partial report, never a silent skip.
    """
    fetch_fn = fetch_fn or fetch_klines
    now = now or datetime.now(timezone.utc)
    if json_path is None or md_path is None:
        json_path, md_path = default_report_paths(symbol, out_dir)
    input_note = ("Data-rendered chart from real demo-fapi klines "
                  f"(venue: {VENUE}); symbol {symbol}; timeframes "
                  f"{', '.join(CONTEXT_TFS)}, trading timeframe {TRADING_TF}. "
                  "Not a broker-terminal screenshot.")
    report: dict = {
        "task": "TASK-STR-086",
        "symbol": symbol,
        "generated_at": now.isoformat(),
        "input_note": input_note,
        "verdict": "BLOCKED",
        "fetch_error": None,
        "sections": {},
    }

    def persist():
        try:
            write_report(report, json_path, md_path)
        except Exception as exc:  # report write must not mask stage results
            logger.warning(f"[STR-086] report persist failed: {exc}")

    def run_stage(name: str, fn, *args, **kwargs):
        try:
            section = fn(*args, **kwargs)
        except Exception as exc:
            section = {"stage": STAGES.index(name) + 1, "name": name,
                       "status": "ERROR",
                       "summary": f"Stage raised {type(exc).__name__}: {exc}",
                       "details": {"error": str(exc)}}
        report["sections"][name] = section
        persist()
        return section

    # Fetch first: every data stage needs klines.
    frames: dict[str, pd.DataFrame] = {}
    fetch_error = None
    for tf in CONTEXT_TFS:
        try:
            frames[tf] = klines_to_frame(fetch_fn(symbol, tf, KLINE_LIMIT))
        except Exception as exc:
            fetch_error = (fetch_error or "") + f"[{tf}] {exc}; "
            frames[tf] = None
    if fetch_error:
        report["fetch_error"] = fetch_error.strip()
    trade_df = frames.get(TRADING_TF)

    s1 = run_stage("market_structure", stage_market_structure, trade_df)
    s2 = run_stage("data_quality", stage_data_quality, frames, KLINE_LIMIT, now)
    regimes: dict[str, str] = {}
    if trade_df is not None and len(trade_df):
        for tf, df in frames.items():
            if df is None or len(df) == 0:
                continue
            try:
                regimes[tf] = RegimeClassifier.classify_regime(add_indicators(df))
            except Exception as exc:
                regimes[tf] = "UNKNOWN"
                logger.warning(f"[STR-086] regime classify failed for {tf}: {exc}")
    s3 = run_stage("timeframe_context", stage_timeframe_context, regimes)
    s4 = run_stage("fundamentals", stage_fundamentals, symbol,
                   funding_rate, funding_error)
    window_start = trade_df["timestamp"].iloc[0].to_pydatetime() if (
        trade_df is not None and len(trade_df)) else now
    window_end = trade_df["timestamp"].iloc[-1].to_pydatetime() if (
        trade_df is not None and len(trade_df)) else now
    s5 = run_stage("news_sentiment", stage_news_sentiment, symbol,
                   window_start, window_end, calendar_store, refresh_calendar)
    direction = direction_from_regime(
        s1.get("details", {}).get("regime", "UNKNOWN"))
    if s3.get("details", {}).get("htf_conflict"):
        direction = "NO_SETUP"
    trusted = bool(s2.get("details", {}).get("data_trusted", False))
    s6 = run_stage("risk_levels", stage_risk_levels, trade_df, direction, trusted)
    s7 = run_stage("final_report", stage_final_report,
                   {k: v for k, v in report["sections"].items()}, symbol, input_note)
    report["verdict"] = s7["details"]["verdict"]
    persist()
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="TASK-STR-086 staged chart-analysis checklist (read-only).")
    parser.add_argument("symbol", nargs="?", default="BTCUSDT")
    parser.add_argument("--out-dir", default=None,
                        help="Directory for the JSON + Markdown report "
                             "(default: Stratex/research/).")
    parser.add_argument("--calendar-store", default=None)
    parser.add_argument("--refresh-calendar", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    report = run_pipeline(
        args.symbol, out_dir=args.out_dir,
        calendar_store=args.calendar_store,
        refresh_calendar=args.refresh_calendar)
    print(f"Verdict: {report['verdict']}")
    for name in STAGES:
        s = report["sections"].get(name, {})
        print(f"  stage {s.get('stage', '?')} {name}: {s.get('status')}")
    if report.get("fetch_error"):
        print(f"Fetch error: {report['fetch_error']}")
        return 2
    return 0 if report["verdict"] in ("SETUP", "NO_SETUP") else 2


if __name__ == "__main__":
    sys.exit(main())
