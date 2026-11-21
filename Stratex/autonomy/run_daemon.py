"""
autonomy/run_daemon.py — Autonomous 24/7 Stratex Production Daemon Runner.

Orchestrates:
1. Real-time bidirectional Telegram polling listener with Gemini AI chat.
2. 24/7 Multi-asset multi-timeframe quantitative scanning loop with strategy execution.
3. Execution on Binance Futures (Crypto) & OANDA (Forex/Indices/Commodities).
"""
from __future__ import annotations

import copy
import datetime
import os
import time
import signal
import json
import threading
from typing import Dict, Optional

from autonomy.multi_venue_engine import create_multi_venue_engine
from strategies.strategy_registry import strategy_registry
from autonomy.cloud_data_feed import get_cloud_data_feed
from logger import get_logger
from notifications.telegram_bot import get_telegram_bot

logger = get_logger("stratex_daemon")

# TASK-STR-FWD-016: the sleeve shock leg and its judged timeframe. The
# contradiction guard's timeframe-precedence exemption and the
# deferred-entry retry are scoped to exactly this strategy at exactly
# this timeframe (see _resolve_contradictions and
# _maybe_defer_sleeve_candidate).
SLEEVE_SHOCK_STRATEGY = "strategy_sleeve_shock_breakout"
# TASK-STR-FWD-035: the venue label for the weekly timeframe is "1w"
# (Stratex/api/validation.py TIMEFRAMES; the Binance weekly interval),
# not "1wk". The daemon env list historically carried "1wk", which
# silently mismatched every venue-labelled consumer: the registry gate
# for the FWD-030 module (its entry says "1w"), the book 3978 SHW
# member, and the API validation set.
SLEEVE_TIMEFRAME = "1w"


# TASK-STR-FWD-035: legacy weekly label. The daemon never emits "1wk"
# anymore; this map exists only so a stale STRATEX_TIMEFRAMES value and
# position records opened before this fix still resolve to the venue
# label instead of silently falling through to a wrong timeframe.
_LEGACY_TIMEFRAME_LABELS = {"1wk": "1w"}


def _normalize_timeframe_label(tf: str) -> str:
    """Map a timeframe label to the venue label ("1wk" -> "1w")."""
    return _LEGACY_TIMEFRAME_LABELS.get(tf.strip(), tf.strip())


def _parse_timeframes(tf_env: str) -> list:
    """Parse STRATEX_TIMEFRAMES into venue labels.

    TASK-STR-FWD-035: a stale env still saying "1wk" is normalized to
    "1w" (venue label) and warned about — never silently reintroduced.
    """
    raw = [t.strip() for t in tf_env.split(",") if t.strip()]
    legacy = sorted({t for t in raw if t in _LEGACY_TIMEFRAME_LABELS})
    if legacy:
        logger.warning(
            "[STRATEX] TASK-STR-FWD-035: legacy timeframe label(s) "
            f"{legacy} in STRATEX_TIMEFRAMES normalized to 1w "
            "(venue label); update the env to the venue labels."
        )
    return [_normalize_timeframe_label(t) for t in raw] or ["1d"]


def heat_capped_risk_amount(
    equity: float,
    risk_per_trade_pct: float,
    open_risk_usd: float,
    max_heat_pct: float,
) -> float:
    """Risk budget (USD) for a new trade under the aggregate heat cap.

    TASK-STR-FWD-006: the budget is the per-trade risk
    (``risk_per_trade_pct`` of venue equity) limited by the remaining
    heat budget (``max_heat_pct`` of venue equity minus the strategy's
    already-open stop-risk). A return value <= 0 means the strategy is
    at its heat cap and must open nothing new.
    """
    equity = max(0.0, float(equity or 0.0))
    per_trade = equity * float(risk_per_trade_pct)
    remaining = equity * float(max_heat_pct) - float(open_risk_usd or 0.0)
    return min(per_trade, remaining)


def trailing_stop_path(
    side: str,
    entry_price: float,
    atr_entry: float,
    sl_atr: float,
    trail_atr: float,
    bars: list,
) -> dict:
    """Judged trailing-stop path over closed bars (TASK-STR-FWD-023).

    A faithful port of the RD-002 harness's trailing simulation
    (rigorous_backtest/rd/fastsim.py ``_simulate_trail``) for the TRAIL
    spec the FORWARD_TEST donchian/turtle entries were judged under
    (families2 TRAIL = {"type": "trail", "sl_atr": 2.0,
    "trail_atr": 2.5} — no fixed TP, no arm threshold):

    - the stop starts at entry -/+ sl_atr * atr_entry, where atr_entry
      is the ATR(14) at the SIGNAL bar, frozen for the life of the
      trade (the harness never re-reads ATR after entry);
    - bars are consumed in order starting at the entry bar; within a
      bar the stop is checked BEFORE the running extreme is updated —
      a bar's own high never lifts the stop its low is tested against
      (no intrabar lookahead);
    - a bar that gaps through the stop exits at the bar open; a bar
      whose low (LONG) / high (SHORT) reaches the stop exits at the
      stop level;
    - after the checks, the extreme moves to the bar's high (LONG) /
      low (SHORT) and the stop ratchets to extreme -/+ trail_atr *
      atr_entry — favourable direction only, by construction.

    ``bars`` is a list of dicts with open/high/low keys (the daemon's
    candle shape), CLOSED bars only, starting at the entry bar.
    Returns {"stop", "best", "exit_index", "exit_price",
    "exit_reason"}: exit_index is the index into ``bars`` of the first
    breaching bar, or None when the position is still open at the last
    bar; exit_reason is "TRAIL" once the stop has ratcheted past its
    initial level, else "SL" (the harness's own labelling).
    """
    is_long = str(side).upper() in ("LONG", "BUY")
    entry_price = float(entry_price)
    atr_entry = float(atr_entry)
    if is_long:
        stop = entry_price - float(sl_atr) * atr_entry
        best = entry_price
    else:
        stop = entry_price + float(sl_atr) * atr_entry
        best = entry_price
    initial_stop = stop
    exit_index = exit_price = exit_reason = None
    for j, bar in enumerate(bars):
        o = float(bar["open"])
        h = float(bar["high"])
        low = float(bar["low"])
        if is_long:
            if o <= stop:
                exit_index, exit_price = j, o
                exit_reason = "TRAIL" if stop > initial_stop else "SL"
                break
            if low <= stop:
                exit_index, exit_price = j, stop
                exit_reason = "TRAIL" if stop > initial_stop else "SL"
                break
            if h > best:
                best = h
            stop = max(stop, best - float(trail_atr) * atr_entry)
        else:
            if o >= stop:
                exit_index, exit_price = j, o
                exit_reason = "TRAIL" if stop < initial_stop else "SL"
                break
            if h >= stop:
                exit_index, exit_price = j, stop
                exit_reason = "TRAIL" if stop < initial_stop else "SL"
                break
            if low < best:
                best = low
            stop = min(stop, best + float(trail_atr) * atr_entry)
    return {
        "stop": stop,
        "best": best,
        "exit_index": exit_index,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
    }


class StratexTradingEngine:
    """Main trading engine that coordinates signal generation and execution.
    ALL RESTRICTIONS REMOVED FOR DEMO TESTING - UNLIMITED TRADING.
    """

    def __init__(self, multi_venue_engine):
        self.engine = multi_venue_engine
        self.cloud_feed = get_cloud_data_feed()
        # Continuous scanning - no interval delay
        self.scan_interval = float(os.getenv("SCAN_INTERVAL_SECONDS", "0"))
        # No position limits
        self.max_positions = int(os.getenv("STRATEX_MAX_TOTAL_POSITIONS", "9999"))
        # Confidence floor for entries. Was parsed and never used — the env
        # file sets 0.55 but the daemon ignored it.
        self.min_confidence = float(os.getenv("STRATEX_MIN_CONFIDENCE", "0.55"))
        # No minimum R:R filter
        self.min_rr = float(os.getenv("STRATEX_MIN_RR", "1.5"))
        # Risk per trade. The daemon sizes with this number; the ENGINE must
        # receive it too or it falls back to its own 0.02 default (4x larger).
        # TASK-STR-FWD-006 (decided package, TASK-STR-RD-011 settlement):
        # 0.1% of VENUE equity per trade for pooled multi-symbol books —
        # the old 1%-of-composite figure was ~2% of the venue account a
        # trade actually sits on. Sizing reads the venue equity at entry
        # time (see the sizing block in _execute_signal).
        self.risk_per_trade = float(os.getenv("STRATEX_RISK_PER_TRADE_PCT", "0.001"))
        # Aggregate portfolio-heat cap per strategy (TASK-STR-FWD-006):
        # the sum of stop-risk over all simultaneously open positions of
        # one strategy may never exceed this fraction of venue equity.
        # Stated next to the per-trade cap so the pair cannot drift apart
        # again (the RD-011 finding was exactly that drift).
        self.max_heat_pct = float(os.getenv("STRATEX_MAX_HEAT_PCT_PER_STRATEGY", "0.02"))
        # Per-position notional cap, denominated on VENUE equity like
        # every other sizing figure (TASK-STR-FWD-006).
        self.max_position_pct = float(os.getenv("STRATEX_MAX_POSITION_PCT", "0.10"))
        # No stop distance limits
        self.min_stop_pct = float(os.getenv("STRATEX_MIN_STOP_PCT", "0.005"))
        self.max_stop_pct = float(os.getenv("STRATEX_MAX_STOP_PCT", "0.030"))
        # No confluence requirement - single strategy can trade
        self.entry_confluence = int(os.getenv("STRATEX_ENTRY_CONFLUENCE", "2"))
        # No ADX filter
        self.adx_threshold = float(os.getenv("STRATEX_ADX_THRESHOLD", "25"))
        # Fees: Binance USD-M taker is 0.04% per side (0.08% round trip).
        self.fee_rate_roundtrip = float(os.getenv("STRATEX_FEE_ROUNDTRIP", "0.0008"))
        # Round-trip FRICTION charged inside the expectancy gate. The gate
        # must price the full judged cost stack, not fees alone:
        # TASK-STR-RD-002's cost model (rigorous_backtest/rd2/costs2.py)
        # is 5 bps/side taker fee + 3 bps/side spread/slippage = 16 bps
        # round trip, and config_strategy records total_friction_bps=16.0
        # for both forward entrants. At the old fees-only 8 bps the gate
        # approved trades whose judged expectancy is negative once
        # spread/slippage is charged (TASK-STR-RD-010). Operators may
        # raise this via STRATEX_FRICTION_ROUNDTRIP; the default is the
        # judged model, not the cheaper demo fee schedule.
        self.friction_rate_roundtrip = float(
            os.getenv("STRATEX_FRICTION_ROUNDTRIP", "0.0016")
        )
        # Expectancy floor in R after fees. 0.0 let every marginal setup
        # through; fees and spread then ate the remainder (14d: -4.5k commissions).
        self.min_expectancy_r = float(os.getenv("STRATEX_MIN_EXPECTANCY_R", "0.10"))
        # Track confluenced signals per symbol this cycle.
        self._confluence_signals: dict[tuple[str, str, str], list[tuple[str, dict, str]]] = {}
        # Latched closed bar per (venue, symbol, strategy, tf)
        self._last_signal_bar: dict[tuple[str, str, str, str], object] = {}
        # TASK-STR-FWD-016: sleeve candidates blocked by an existing open
        # position are deferred (not consumed) and retried on later cycles
        # while their weekly bucket is still the last closed bucket.
        # _deferred_sleeve_entries is keyed (venue, symbol) and carries
        # the stamped execution payload plus the bucket identity (the
        # last closed bucket's open timestamp, stringified — the same
        # value the bar latch keys on). _last_closed_bucket records, for
        # the CURRENT scan cycle only, the last closed weekly bucket per
        # (venue, symbol); scan_and_execute resets it every cycle, and
        # the retry pass expires an entry only on positive evidence from
        # it that the bucket rolled over. Both attributes are also
        # lazily created by _sleeve_deferral_state() for engines built
        # without __init__.
        self._deferred_sleeve_entries: dict[tuple[str, str], dict] = {}
        self._last_closed_bucket: dict[tuple[str, str], str] = {}
        # ADX only for trend/breakout (disabled with threshold=0)
        self.adx_strategies = {
            s.strip()
            for s in os.getenv(
                "STRATEX_ADX_STRATEGIES",
                "strategy_fast_ema_cross,strategy_trend_daily,strategy_scalping_breakout,"
                "strategy_momentum,strategy_adx_trend,trend_continuation,channel_breakout,"
                "atr_breakout,volume_breakout,higher_highs",
            ).split(",")
            if s.strip()
        }

        # Auto-pruned strategies stay pruned across restarts: _maybe_prune_
        # strategies() persists this set via _persist_denylist(), and it is
        # read back here (TASK-STR-SAFETY-001: previously the file was
        # written but never loaded, so pruned strategies returned on every
        # restart).
        self.strategy_denylist = self._load_denylist()
        self.strategy_allowlist = {
            s.strip()
            for s in os.getenv("STRATEX_STRATEGY_ALLOWLIST", "").split(",")
            if s.strip()
        }
        # Measured win rates per strategy (from the backtest), which replace the
        # module constants that were never evidence.
        self.strategy_priors: Dict[str, float] = {}
        priors_file = os.getenv(
            "STRATEX_STRATEGY_PRIORS_FILE",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "state", "strategy_priors.json"),
        )
        try:
            with open(priors_file, "r", encoding="utf-8") as fh:
                raw_priors = json.load(fh)
            self.strategy_priors = {
                k: float(v) for k, v in raw_priors.items() if isinstance(v, (int, float))
            }
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[STRATEX] Could not load strategy priors: {e}")

        # Crypto: the registry only validates BTC/ETH/SOL, so scanning the other
        # twelve symbols was pure API load with zero possible trades.
        # Default universe = the judged CRYPTO30 panel (TASK-STR-FWD-002;
        # config_strategy.CRYPTO30_SYMBOLS). The live .env sets the same
        # list explicitly; the default only matters for fresh checkouts.
        crypto_env = os.getenv("STRATEX_CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,LTCUSDT,LINKUSDT,DOTUSDT,TRXUSDT,AVAXUSDT,NEARUSDT,ATOMUSDT,UNIUSDT,ETCUSDT,BCHUSDT,FILUSDT,APTUSDT,ARBUSDT,OPUSDT,INJUSDT,SUIUSDT,XLMUSDT,HBARUSDT,ALGOUSDT,VETUSDT,SANDUSDT,MANAUSDT,AAVEUSDT")
        # Symbol universe per venue
        self.symbols = {
            "binance_futures": [s.strip() for s in crypto_env.split(",") if s.strip()],
            "oanda": [
                "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
                "EURGBP", "EURJPY", "EURAUD", "EURCAD", "EURCHF",
                "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF",
                "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY",
                "XAUUSD", "XAGUSD", "US30", "US500", "USTEC", "DE30", "UK100",
                "USOIL", "UKOIL", "BCOUSD", "NATGAS",
            ],
        }

        tf_env = os.getenv("STRATEX_TIMEFRAMES", "1d,4h")
        self.timeframes = _parse_timeframes(tf_env)
        self.running = True
        self.last_scan = 0
        self.scan_count = 0
        # TASK-STR-EXP-004: self-experiment wiring state. The flag is
        # maintained around every scan (it is the daemon-activity
        # probe's input); the handle stays None unless the loop is
        # wired on at run() time — see _start_self_experiments.
        self._scan_in_progress = False
        self._selfexp_handle = None
        # TASK-STR-FWD-015: heartbeat pulse state. The scan loop only
        # publishes an in-memory snapshot; a dedicated pulse thread is
        # the sole writer of daemon_heartbeat.json during run(), so
        # the file's freshness no longer depends on scan-cycle length.
        # (Also lazily initialised by _heartbeat_state() for engines
        # constructed without __init__.)
        self.heartbeat_pulse_seconds = self._heartbeat_pulse_seconds_from_env()
        self._heartbeat_lock = threading.Lock()
        self._heartbeat_write_lock = threading.Lock()
        self._heartbeat_snapshot = None
        self._heartbeat_wake = threading.Event()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None
        self._last_trend_manage = 0.0
        # TASK-STR-FWD-021: overlay manager throttles (separate for the
        # pre-gate exits pass and the post-gate entries pass).
        self._last_overlay_exits = 0.0
        self._last_overlay_entries = 0.0
        # TASK-STR-FWD-022: WF-selection hook throttle.
        self._last_wf_select_check = 0.0
        # TASK-STR-FWD-023: trailing-exit manager throttle + the
        # persisted per-position trailing records (loaded lazily by
        # _trailing_state(); also safe on engines built without
        # __init__, which the test suites construct).
        self._last_trailing_manage = 0.0
        self._trailing_positions: dict | None = None  # None = not yet loaded
        # TASK-STR-DAEMON-002: the daily-summary throttle survives
        # restarts — loaded from state/ so a restart inside the same
        # UTC day does not re-send the summary (DAEMON-001 triple-send).
        self._last_summary_date = self._load_last_summary_date()
        # TASK-STR-PHASE2-001 measurement hooks (best-effort, never fatal):
        # shadow-trade tracker for OBSERVE_ONLY strategies, the hourly
        # equity-snapshot throttle, and the untracked-position sweep cadence.
        self._shadow = None
        try:
            from measurement.shadow import ShadowTracker

            self._shadow = ShadowTracker()
        except Exception as e:
            logger.warning(f"[STRATEX] Shadow tracker unavailable: {e}")
        self._last_equity_snapshot = 0.0
        self._reconcile_pass = 0
        # TASK-STR-FWD-003: attest this daemon's demo venues to the
        # registry so the FORWARD_TEST lane can execute — on those
        # venues only. Detection is by venue-adapter base URL; an
        # unrecognised endpoint is NOT demo (fail-closed).
        try:
            strategy_registry.set_demo_venues(self._detect_demo_venues())
        except Exception as e:
            logger.warning(f"[STRATEX] Demo-venue attestation failed: {e}")
        self._log_governance_summary()

    def _detect_demo_venues(self) -> set:
        """Venue names whose adapters point at demo endpoints.

        demo-fapi / Binance testnet / OANDA practice hosts count as
        demo; anything else (including a missing base_url) does not.
        """
        demo = set()
        venues = getattr(self.engine, "venues", None) or {}
        for name, adapter in venues.items():
            url = str(getattr(adapter, "base_url", "") or "").lower()
            if any(marker in url for marker in ("demo", "testnet", "fxpractice", "practice")):
                demo.add(name)
        return demo

    def _log_governance_summary(self) -> None:
        """Log the governed strategy sets once at startup (audit evidence).

        The daemon's executable set is whatever config_strategy governance
        marks VALIDATED — nothing else may place orders (TASK-STR-SAFETY-001).
        TASK-STR-FWD-003 adds the FORWARD_TEST lane: those strategies may
        place orders on attested demo venues only (see _detect_demo_venues).
        """
        try:
            executable, forward_test, observe_only, excluded = [], [], [], []
            for spec in strategy_registry.snapshot():
                if spec.status == "VALIDATED":
                    executable.append(spec.name)
                elif spec.status == "FORWARD_TEST":
                    forward_test.append(spec.name)
                elif spec.status == "OBSERVE_ONLY":
                    observe_only.append(spec.name)
                else:
                    excluded.append(f"{spec.name}({spec.status})")
            logger.info(
                "[STRATEX] Governance (config_strategy): "
                f"executable={sorted(executable)} "
                f"forward_test={sorted(forward_test)} "
                f"demo_venues={sorted(strategy_registry.demo_venues())} "
                f"observe_only={sorted(observe_only)} "
                f"excluded={sorted(excluded)}"
            )
            # TASK-STR-FWD-018: a governed strategy missing from a
            # non-empty STRATEX_STRATEGY_ALLOWLIST is skipped by the
            # scan loop BEFORE evaluation, silently — the FORWARD_TEST
            # lane sat in exactly that state from its 2026-11-15 wiring
            # until this diagnostic (governance line listed it as
            # armed; zero evaluations, zero signals, zero fills).
            # Name the blocked strategies loudly at startup so an
            # allowlist/governance mismatch can never again read as an
            # armed-but-quiet lane.
            allowlist = getattr(self, "strategy_allowlist", set())
            if allowlist:
                blocked = sorted(
                    name
                    for name in executable + forward_test
                    if name not in allowlist
                )
                if blocked:
                    logger.warning(
                        "[STRATEX] Governance WARNING: governed strategies "
                        "are NOT in STRATEX_STRATEGY_ALLOWLIST and will "
                        f"never be evaluated: {blocked}"
                    )
        except Exception as e:
            logger.warning(f"[STRATEX] Governance summary failed: {e}")

    def _sleeve_deferral_state(self):
        """TASK-STR-FWD-016: (deferred sleeve entries, bucket map).

        __init__ creates both attributes; the lazy path exists for
        engines constructed without __init__ (unit tests build the
        engine with __new__ — the _heartbeat_state precedent).
        """
        deferred = getattr(self, "_deferred_sleeve_entries", None)
        if deferred is None:
            deferred = self._deferred_sleeve_entries = {}
        buckets = getattr(self, "_last_closed_bucket", None)
        if buckets is None:
            buckets = self._last_closed_bucket = {}
        return deferred, buckets

    def _resolve_contradictions(self, confluenced: list) -> list:
        """Contradiction guard, with sleeve timeframe precedence.

        A (venue, symbol) carrying confluenced BUY *and* SELL entries in
        the same cycle is conflicted. The default resolution is
        unchanged from the original guard: EVERY entry for the symbol
        is dropped — contradictory aggregation has no edge, only noise.

        One scoped exemption (TASK-STR-FWD-016): when one side is
        exclusively the sleeve shock leg (SLEEVE_SHOCK_STRATEGY on its
        judged SLEEVE_TIMEFRAME) and the opposing side is exclusively
        lower-timeframe, non-sleeve signals, the sleeve side survives
        and the opposing side is dropped for this symbol-cycle. The two
        are pre-judged, independent hypotheses that are *supposed* to
        disagree after a weekly shock (the sleeve continues the shock;
        dow_effect reverses the trailing daily move) — deleting both
        silently starved the sleeve leg to zero lifetime executions
        while dow lost the same entries uncredited. Every other
        conflict shape keeps the delete-both behaviour exactly.

        Every resolution is journalled per symbol — symbol, both
        strategies, both sides, both timeframes, and the resolution
        (both-dropped / precedence-dropped-<strategy>) — so a dropped
        forward entrant is attributable from the journal alone. The
        aggregate Conflict line is kept for continuity.
        """
        by_symbol: dict[tuple[str, str], dict[str, tuple]] = {}
        for entry in confluenced:
            by_symbol.setdefault((entry[0], entry[1]), {})[entry[2]] = entry
        conflicted = {k for k, v in by_symbol.items() if len(v) > 1}
        if not conflicted:
            return confluenced

        def _names(entry) -> str:
            return "+".join(sorted({s[0] for s in entry[3]}))

        def _tfs(entry) -> str:
            return "+".join(sorted({s[2] for s in entry[3]}))

        drop: set[tuple[str, str, str]] = set()
        for venue, symbol in sorted(conflicted):
            by_side = by_symbol[(venue, symbol)]
            sleeve_side = None
            for side, entry in by_side.items():
                strategies = {s[0] for s in entry[3]}
                tfs = {s[2] for s in entry[3]}
                if strategies == {SLEEVE_SHOCK_STRATEGY} and tfs == {SLEEVE_TIMEFRAME}:
                    sleeve_side = side
            kept = False
            if sleeve_side is not None and len(by_side) == 2:
                other_side = next(s for s in by_side if s != sleeve_side)
                other = by_side[other_side]
                other_strategies = {s[0] for s in other[3]}
                other_tfs = {s[2] for s in other[3]}
                if (
                    SLEEVE_SHOCK_STRATEGY not in other_strategies
                    and SLEEVE_TIMEFRAME not in other_tfs
                ):
                    kept = True
                    drop.add((venue, symbol, other_side))
                    logger.info(
                        f"[STRATEX] Conflict {venue}:{symbol}: "
                        f"{SLEEVE_SHOCK_STRATEGY} {sleeve_side} "
                        f"({SLEEVE_TIMEFRAME}) vs {_names(other)} "
                        f"{other_side} ({_tfs(other)}) — timeframe "
                        f"precedence: precedence-dropped-{_names(other)} "
                        f"{other_side}; sleeve side proceeds"
                    )
            if not kept:
                for side in by_side:
                    drop.add((venue, symbol, side))
                desc = " vs ".join(
                    f"{_names(e)} {s} ({_tfs(e)})"
                    for s, e in sorted(by_side.items())
                )
                logger.info(
                    f"[STRATEX] Conflict {venue}:{symbol}: {desc} "
                    f"— both dropped"
                )
        logger.info(
            f"[STRATEX] Conflict: {len(conflicted)} symbol(s) produced both "
            f"BUY and SELL confluence; resolved per-symbol above"
        )
        return [
            c for c in confluenced if (c[0], c[1], c[2]) not in drop
        ]

    def _maybe_defer_sleeve_candidate(
        self, venue: str, symbol: str, sigs: list
    ) -> bool:
        """TASK-STR-FWD-016: defer a position-blocked sleeve candidate.

        Called from the execution loop when a confluenced entry did not
        execute. If the entry carries a sleeve candidate and an open
        position exists on the symbol, the candidate is retained for
        the retry pass instead of being consumed: the leg's judged
        contract is entry *during* the bucket that follows the shock
        bucket, so a candidate blocked today stays valid while its
        weekly bucket is still the last closed bucket. The existing
        position is never preempted or closed by this mechanism.
        Returns True when a candidate was deferred.
        """
        deferred, buckets = self._sleeve_deferral_state()
        sleeve_sigs = [s for s in sigs if s[0] == SLEEVE_SHOCK_STRATEGY]
        if not sleeve_sigs:
            return False
        if not self.engine.has_open_position(venue, symbol):
            return False
        bucket = buckets.get((venue, symbol))
        if bucket is None:
            return False
        strat_name, result, tf = sleeve_sigs[0]
        # Stamp exactly as the execution loop stamps a live attempt.
        payload = dict(result)
        payload["strategy"] = strat_name
        payload["venue"] = venue
        payload["symbol"] = symbol
        payload["timeframe"] = tf
        existing = deferred.get((venue, symbol))
        deferred[(venue, symbol)] = {
            "payload": payload,
            "timeframe": tf,
            "side": result.get("side"),
            "bucket": bucket,
        }
        if existing is None or existing.get("bucket") != bucket:
            logger.info(
                f"[STRATEX] Sleeve deferred: {strat_name} "
                f"{result.get('side')} {venue}:{symbol} {tf} blocked by "
                f"an existing open position; will retry while weekly "
                f"bucket {bucket} is the last closed bucket (deferred)"
            )
        return True

    def _retry_deferred_sleeve_entries(self, results: dict) -> None:
        """TASK-STR-FWD-016: retry deferred sleeve candidates.

        Runs once per scan cycle, after the main execution loop. An
        entry is retried only while its weekly bucket is positively
        observed (this cycle's scan) to still be the last closed
        bucket; on rollover evidence it expires instead, journalled.
        A still-open position on the symbol leaves the entry deferred
        — the existing position is never preempted or closed. A failed
        execution attempt leaves the entry in place for the next cycle
        (the failing gate journals its own reason); it expires only at
        bucket rollover.
        """
        deferred, buckets = self._sleeve_deferral_state()
        if not deferred:
            return
        for (venue, symbol), entry in list(deferred.items()):
            try:
                seen_bucket = buckets.get((venue, symbol))
                if seen_bucket is None:
                    # Symbol not scanned this cycle: no evidence either
                    # way — neither retry nor expire on stale data.
                    continue
                if seen_bucket != entry["bucket"]:
                    logger.info(
                        f"[STRATEX] Sleeve deferred expired: "
                        f"{SLEEVE_SHOCK_STRATEGY} {entry['side']} "
                        f"{venue}:{symbol} {entry['timeframe']} — weekly "
                        f"bucket {entry['bucket']} is no longer the last "
                        f"closed bucket (now {seen_bucket}); entry never "
                        f"filled"
                    )
                    del deferred[(venue, symbol)]
                    continue
                if self.engine.has_open_position(venue, symbol):
                    continue
                can_open, _reason = self.engine.can_open_position(venue)
                if not can_open:
                    continue
                payload = dict(entry["payload"])
                if self._execute_signal(
                    venue, symbol, payload, entry["timeframe"]
                ):
                    results["executed"] += 1
                    logger.info(
                        f"[STRATEX] Sleeve deferred filled: "
                        f"{SLEEVE_SHOCK_STRATEGY} {entry['side']} "
                        f"{venue}:{symbol} {entry['timeframe']} "
                        f"(bucket {entry['bucket']})"
                    )
                    del deferred[(venue, symbol)]
            except Exception as e:
                logger.warning(
                    f"[STRATEX] Deferred sleeve retry failed for "
                    f"{venue}:{symbol}: {e}"
                )

    def scan_and_execute(self) -> dict:
        """Run one scan cycle across all symbols and timeframes."""
        results = {"scanned": 0, "signals": 0, "executed": 0, "errors": 0}
        scanned_symbols = set()
        scanned_1d = 0
        self._confluence_signals = {}
        # TASK-STR-FWD-016: the last-closed weekly bucket map is
        # re-observed during this cycle's scan; last cycle's observations
        # must not leak into the deferred-entry retry pass.
        self._last_closed_bucket = {}
        # TASK-STR-FWD-003: forward-protocol strategies (the VALIDATED
        # entrants and the FORWARD_TEST lane) trade their JUDGED
        # geometry — the generic min-RR pre-filter must not silently
        # veto a judged configuration (the lane's adx_ema_bare is RR
        # 1.0 by construction). The expectancy gate in _execute_signal
        # and the phase-3 kill criteria still govern them.
        forward_names = set(self._forward_protocol_entries())

        # Detect broker-side exits first: a position closed by SL/TP must be
        # booked even when the daily loss limit stops us from scanning.
        self._reconcile_positions()

        # Daily trend positions exit on an EMA20 close cross, not a fixed target.
        # Runs before the loss-limit gate so a losing book can still be exited.
        self._manage_trend_positions()

        # TASK-STR-FWD-002: judged bracket_time exits (dow_effect max_bars)
        # have no broker-native equivalent; enforce them here, also before
        # the loss-limit gate so exits are never blocked by it.
        self._manage_forward_time_exits()

        # TASK-STR-FWD-021: RD-014 overlay positions are managed toward
        # their judged target weights. Risk-reducing actions (closes,
        # reductions, brake flattening) run here, before the loss-limit
        # gate, so a losing overlay book can always be reduced; entries
        # and increases run in the second pass below, after the gate.
        self._manage_overlay_positions(allow_entries=False)
        # TASK-STR-FWD-023: judged trailing-stop exits (the donchian /
        # turtle TRAIL spec) are likewise daemon-side; enforce them here,
        # also before the loss-limit gate so exits are never blocked by it.
        self._manage_trailing_exits()

        # TASK-STR-FWD-006: phase-3 kill criteria on the scan cadence,
        # marked to market — evaluated here (after close reconciliation,
        # before any entry decision) so a breached strategy is denylisted
        # before it can open anything new this cycle. This previously ran
        # once per UTC day in the auto-prune slot below, and not at all
        # on days the daemon restarted.
        self._maybe_apply_forward_guard()

        # TASK-STR-FWD-022: refresh walk-forward selection picks whose
        # epoch has rolled (places no orders; the entrant modules read
        # the persisted pick on their own evaluation path).
        self._maybe_run_wf_selection()
        # TASK-STR-FWD-024: refresh the cross-sectional panel
        # memberships (xs_momentum / xs_lowvol) on their judged
        # rebalance cadence. The ranking runs HERE, in the service
        # hook — never inside a per-symbol signal evaluation — and
        # only persists state; entries fire later in this same scan
        # through the ordinary per-symbol path when a membership's
        # signal bar is the frame's last closed bar.
        self._maybe_run_panel_rankings()

        # Check daily loss limit. get_risk_summary() runs the daily reset and
        # seeds daily_start_equity on first call, so the breaker below has a
        # baseline to measure against.
        risk = self.engine.get_risk_summary()
        # Kept for the per-cycle daemon heartbeat (see _write_daemon_heartbeat).
        self._last_risk_summary = risk
        # Belt and braces: re-evaluate the realized-PnL breach directly in
        # case bookings happened through a path that skipped the check.
        if not risk.get("daily_loss_limit_hit", False):
            start_eq = float(getattr(self.engine, "daily_start_equity", 0.0) or 0.0)
            day_pnl = float(getattr(self.engine, "daily_realized_pnl", 0.0) or 0.0)
            cap = float(getattr(self.engine, "max_daily_loss_pct", 0.0) or 0.0) * start_eq
            if cap > 0 and day_pnl <= -cap:
                self.engine.daily_loss_limit_hit = True
                risk["daily_loss_limit_hit"] = True
        if risk.get("daily_loss_limit_hit", False):
            logger.warning("[STRATEX] Daily loss limit hit, skipping scan")
            return results

        # TASK-STR-FWD-021: overlay entries/increases, only once the
        # daily-loss gate above has passed.
        self._manage_overlay_positions(allow_entries=True)

        # Prefetch candles for all symbols
        self._prefetch_candles()

        for venue, symbols in self.symbols.items():
            if venue not in self.engine.venues:
                continue
                
            for symbol in symbols:
                for tf in self.timeframes:
                    try:
                        # Get candles. The daily trend strategy needs 200 bars for
                        # its EMA200 regime filter; intraday strategies keep 100.
                        # TASK-STR-FWD-002: the forward entrants were judged
                        # with a 260-bar warmup, so 1d/4h frames must carry
                        # at least 262 closed bars (300 daily bars fetched;
                        # 600 4h bars fetched so the warmup holds with
                        # headroom for the still-forming bar).
                        # Sleeve extension: the 1w timeframe is a DERIVED
                        # timeframe — 1,120 daily bars are fetched and
                        # aggregated into the judged weekly buckets by
                        # strategy_sleeve_shock_breakout.weekly_candles
                        # (Binance native weekly klines are Monday-
                        # anchored and are NOT the judged bars).
                        candle_limit = 300 if tf == "1d" else 600 if tf == "4h" else 160 if tf == SLEEVE_TIMEFRAME else 100
                        min_bars = 262 if tf in ("1d", "4h") else 106 if tf == SLEEVE_TIMEFRAME else 50
                        fetch_tf = "1d" if tf == SLEEVE_TIMEFRAME else tf
                        fetch_limit = 1120 if tf == SLEEVE_TIMEFRAME else candle_limit
                        candles = self.engine.get_candles(venue, symbol, fetch_tf, fetch_limit)
                        if tf == SLEEVE_TIMEFRAME and candles:
                            candles = self._weekly_aggregate(symbol, candles)
                        if not candles or len(candles) < min_bars:
                            continue

                        # Convert to DataFrame
                        df = self._candles_to_df(candles)
                        if df is None or len(df) < min_bars:
                            continue

                        # Bar-latch key: the last CLOSED bar's timestamp. A
                        # 15s scan sees the same closed 1m/5m bar ~4-12 times;
                        # without latching, a strategy signal on that bar
                        # re-fired every scan and pyramided entries.
                        try:
                            last_bar_ts = df.index[-2] if len(df.index) > 1 else df.index[-1]
                        except Exception:
                            last_bar_ts = None

                        # TASK-STR-FWD-016: record this cycle's last
                        # closed weekly bucket per symbol; the deferred
                        # sleeve retry pass keys bucket rollover off it.
                        if tf == SLEEVE_TIMEFRAME and last_bar_ts is not None:
                            _bucket_map = getattr(
                                self, "_last_closed_bucket", None
                            )
                            if _bucket_map is None:
                                _bucket_map = self._last_closed_bucket = {}
                            _bucket_map[(venue, symbol)] = str(last_bar_ts)

                        # Track symbols actually scanned this cycle.
                        scanned_symbols.add((venue, symbol))
                        if tf == "1d":
                            scanned_1d += 1

                        # Run all strategies
                        for strat_name in strategy_registry.get_all_strategy_names():
                            # Measured-loser and structurally broken strategies are
                            # removed before execution: they cost CPU and lose money.
                            if self.strategy_allowlist:
                                if strat_name not in self.strategy_allowlist:
                                    continue
                            elif strat_name in self.strategy_denylist:
                                continue

                            # Governance gate (TASK-STR-SAFETY-001): the
                            # registry's status comes from config_strategy's
                            # PRODUCTION_STRATEGY_REGISTRY — the same source
                            # the testnet engine honours. Only VALIDATED
                            # strategies may reach order placement.
                            gov_status = strategy_registry.governance_status(strat_name)
                            if gov_status == "OBSERVE_ONLY":
                                # Parked strategies (post-incident supertrend,
                                # adx_ema) still evaluate so they accumulate
                                # forward evidence — but a signal from this
                                # branch is logged only and NEVER enters the
                                # confluence/execution path below.
                                obs = strategy_registry.execute_strategy(
                                    strat_name, df, tf, symbol, allow_observe=True
                                )
                                results["scanned"] += 1
                                if obs.get("status") == "SIGNAL" and obs.get("side", "HOLD") != "HOLD":
                                    logger.info(
                                        f"[STRATEX] [OBSERVE_ONLY] {strat_name} signal "
                                        f"{obs.get('side')} {venue}:{symbol} {tf} — "
                                        f"logged for evidence, never executed"
                                    )
                                # Shadow-trade logging (TASK-STR-PHASE2-001):
                                # the signal now also opens/updates a paper
                                # lifecycle with ESTIMATED fees, so observe-
                                # only strategies accumulate forward evidence
                                # instead of evaporating into log lines.
                                if getattr(self, "_shadow", None) is not None:
                                    try:
                                        bar = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
                                        self._shadow.update(
                                            venue,
                                            symbol,
                                            float(bar["high"]),
                                            float(bar["low"]),
                                            float(bar["close"]),
                                        )
                                        if obs.get("status") == "SIGNAL" and obs.get("side", "HOLD") != "HOLD":
                                            self._shadow.on_signal(
                                                strat_name,
                                                venue,
                                                symbol,
                                                obs.get("side"),
                                                float(bar["close"]),
                                                stop_loss=obs.get("stop_loss"),
                                                take_profit=obs.get("take_profit"),
                                                timeframe=tf,
                                            )
                                    except Exception:
                                        pass
                                continue
                            if gov_status not in ("VALIDATED", "FORWARD_TEST"):
                                # DISABLED / UNREGISTERED: not evaluated for
                                # execution at all. FORWARD_TEST (the
                                # TASK-STR-FWD-003 lane) proceeds like
                                # VALIDATED here, but the registry's
                                # executable()/execute_strategy() checks
                                # below confine it to attested DEMO venues
                                # — fail-closed, venue by venue.
                                continue

                            ok, reason = strategy_registry.executable(strat_name, tf, symbol, venue=venue)
                            if not ok:
                                continue

                            # Static geometry that can never satisfy the R:R gate
                            # is skipped before running it: on 15 symbols x 3
                            # timeframes these executions dominated scan time.
                            # Forward-protocol strategies are exempt (see
                            # forward_names above): their geometry is the
                            # judged object under test.
                            spec = strategy_registry.get(strat_name)
                            if (
                                spec is not None
                                and spec.rr_ratio
                                and spec.rr_ratio < self.min_rr
                                and strat_name not in forward_names
                            ):
                                continue

                            result = strategy_registry.execute_strategy(strat_name, df, tf, symbol, venue=venue)
                            results["scanned"] += 1

                            logger.info(f"[STRATEX] Strategy {strat_name} on {venue}:{symbol} {tf}: {result.get('status')} - {result.get('side', 'N/A')}")

                            if result.get("status") == "SIGNAL" and result.get("side", "HOLD") != "HOLD":
                                # One signal per (strategy, symbol, tf, bar):
                                # the same closed bar must not re-arm entry on
                                # every 15s scan pass.
                                latch_key = (strat_name, venue, symbol, tf, str(last_bar_ts))
                                if latch_key in self._last_signal_bar:
                                    continue
                                self._last_signal_bar[latch_key] = True
                                # Bound the latch dict (24h of 1m bars x universe
                                # is large; a stale key never refires anyway).
                                if len(self._last_signal_bar) > 20000:
                                    self._last_signal_bar.clear()
                                results["signals"] += 1

                                # Fail-closed quality gate. Missing metrics used to
                                # pass because `if win_rate and ...` treats 0 as
                                # "no opinion"; that let strategies with a 0.0
                                # prior trade on R:R alone.
                                rr_raw = result.get("rr_ratio")
                                wr_raw = self.strategy_priors.get(strat_name)
                                if wr_raw is None:
                                    wr_raw = result.get("win_rate_prior")
                                if wr_raw is None:
                                    wr_raw = result.get("confidence")

                                try:
                                    rr = float(rr_raw)
                                except (TypeError, ValueError):
                                    rr = 0.0
                                try:
                                    win_rate = float(wr_raw)  # noqa: F841 — scan gate log below; expectancy re-read in _execute_signal
                                except (TypeError, ValueError):
                                    win_rate = 0.0  # noqa: F841

                                # TASK-STR-FWD-023: a strategy whose
                                # registry entry declares the judged
                                # trailing exit has no fixed R:R BY
                                # CONSTRUCTION (families2 TRAIL: no TP),
                                # so the metric's absence must not veto
                                # it. The exemption is keyed to the
                                # registry declaration only — every
                                # undeclared strategy keeps the
                                # fail-closed skip below.
                                if rr <= 0 and self._trailing_spec_for_strategy(strat_name) is None:
                                    logger.info(
                                        f"[STRATEX] Skip {strat_name} {symbol}: "
                                        f"no R:R metric"
                                    )
                                    continue
                                if rr < self.min_rr and strat_name not in forward_names:
                                    logger.info(
                                        f"[STRATEX] Skip {strat_name} {symbol}: "
                                        f"R:R {rr:.2f} < {self.min_rr}"
                                    )
                                    continue
                                # Confidence floor (was parsed but never
                                # applied; the env sets 0.55).
                                conf = 0.0
                                try:
                                    conf = float(result.get("confidence") or 0)
                                except (TypeError, ValueError):
                                    conf = 0.0
                                if conf > 0 and conf < self.min_confidence:
                                    logger.info(
                                        f"[STRATEX] Skip {strat_name} {symbol}: "
                                        f"confidence {conf:.2f} < {self.min_confidence:.2f}"
                                    )
                                    continue

                                sl_dbg = float(result.get("stop_loss") or 0)
                                tp_dbg = float(result.get("take_profit") or 0)

                                logger.info(
                                    f"[STRATEX] Signal detected: {strat_name} "
                                    f"{result['side']} {venue}:{symbol} {tf} "
                                    f"@ SL={sl_dbg:.5f} TP={tp_dbg:.5f}"
                                )
                                # Confluence is keyed by venue+symbol+side and
                                # counted by DISTINCT strategy. One oscillator
                                # firing on 3 timeframes is one opinion, not 3.
                                key_side = (venue, symbol, result["side"])
                                if key_side not in self._confluence_signals:
                                    self._confluence_signals[key_side] = []
                                self._confluence_signals[key_side].append((strat_name, result, tf))

                    except Exception as e:
                        results["errors"] += 1
                        logger.warning(f"[STRATEX] Error scanning {venue}:{symbol} {tf}: {e}")

        results["symbols"] = len(scanned_symbols)
        results["symbols_1d"] = scanned_1d

        # Confluence filtering: require N DISTINCT strategies on the same
        # venue+symbol+side. Deduplicate by strategy name before counting.
        confluenced = []
        for (c_venue, c_symbol, c_side), sigs in self._confluence_signals.items():
            distinct = {s[0] for s in sigs}
            if len(distinct) >= self.entry_confluence:
                confluenced.append((c_venue, c_symbol, c_side, sigs, distinct))
        self._confluence_signals = {}

        # Contradiction guard (TASK-STR-FWD-016): a symbol with
        # confluenced BUY *and* SELL in the same cycle is resolved by
        # _resolve_contradictions — delete-both by default, with the
        # scoped sleeve timeframe-precedence exemption, journalled
        # per symbol.
        confluenced = self._resolve_contradictions(confluenced)

        if confluenced:
            logger.info(
                f"[STRATEX] Confluence: {len(confluenced)} symbol(s) met "
                f"{self.entry_confluence}+ distinct strategy agreement"
            )

        # Execute confluenced signals. Rank candidates by their own R:R first,
        # then by the shortest timeframe: a scalp should not wait on 1h context.
        tf_order = {"1m": 0, "5m": 1, "15m": 2, "1h": 3, "4h": 4, "1d": 5}
        for c_venue, c_symbol, c_side, sigs, distinct in confluenced:
            can_open, reason = self.engine.can_open_position(c_venue)
            if not can_open:
                logger.info(
                    f"[STRATEX] Cannot open {c_venue}:{c_symbol}: {reason}"
                )
                continue

            ranked = sorted(
                sigs,
                key=lambda s: (
                    -float(s[1].get("rr_ratio") or 0),
                    tf_order.get(s[2], 9),
                ),
            )

            executed = False
            sleeve_executed = False
            for strat_name, result, tf in ranked:
                if result.get("observe_only"):
                    # Defence in depth (TASK-STR-SAFETY-001): an OBSERVE_ONLY
                    # signal must never reach order placement, even if a
                    # future code path lets one into the confluence set.
                    logger.warning(
                        f"[STRATEX] Blocked OBSERVE_ONLY candidate {strat_name} "
                        f"from execution on {c_venue}:{c_symbol}"
                    )
                    continue
                if result.get("forward_test") and c_venue not in strategy_registry.demo_venues():
                    # Defence in depth (TASK-STR-FWD-003): a FORWARD_TEST
                    # candidate may only execute on an attested demo
                    # venue. The registry already enforced this at
                    # evaluation; re-check at the point of order
                    # placement so no future path can route a lane
                    # signal to a live venue.
                    logger.warning(
                        f"[STRATEX] Blocked FORWARD_TEST candidate {strat_name} "
                        f"from execution on non-demo venue {c_venue}:{c_symbol}"
                    )
                    continue
                # Copy so per-candidate stamping cannot leak between attempts.
                payload = dict(result)
                payload["strategy"] = strat_name
                payload["venue"] = c_venue
                payload["symbol"] = c_symbol
                payload["timeframe"] = tf
                if self._execute_signal(c_venue, c_symbol, payload, tf):
                    results["executed"] += 1
                    executed = True
                    if strat_name == SLEEVE_SHOCK_STRATEGY:
                        sleeve_executed = True
                        # A live sleeve execution supersedes any deferred
                        # entry for this symbol (same bucket signal).
                        self._sleeve_deferral_state()[0].pop(
                            (c_venue, c_symbol), None
                        )
                    logger.info(
                        f"[STRATEX] Executed {strat_name} on {c_venue}:{c_symbol} "
                        f"{c_side} {tf} (confluence: "
                        f"{','.join(sorted(distinct))})"
                    )
                    break

            if not sleeve_executed:
                # TASK-STR-FWD-016: a sleeve candidate blocked by an
                # existing open position is deferred, not consumed.
                self._maybe_defer_sleeve_candidate(c_venue, c_symbol, sigs)

            if not executed:
                logger.info(
                    f"[STRATEX] No executable candidate for {c_venue}:{c_symbol} "
                    f"{c_side} (evaluated {len(ranked)})"
                )

        # TASK-STR-FWD-016: retry deferred sleeve entries while their
        # weekly bucket is still the last closed bucket.
        self._retry_deferred_sleeve_entries(results)

        self._maybe_send_daily_summary(results)

        # Periodic auto-prune (once per day, on the same day boundary as summary)
        import datetime
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        if hasattr(self, "_last_prune_date"):
            if self._last_prune_date != today:
                self._maybe_prune_strategies()
                # TASK-STR-FWD-006: the phase-3 forward guard no longer
                # runs in this daily slot — it is evaluated on the scan
                # cadence at the top of scan_and_execute (marked to
                # market). Only the legacy pruner remains daily.
                self._last_prune_date = today
                # Weekly scorecard (TASK-STR-PHASE2-001): regenerated from
                # the fill ledger only, at most once a week.
                try:
                    from measurement import scorecard as _scorecard

                    _scorecard.maybe_regenerate_weekly()
                except Exception:
                    pass
        else:
            self._last_prune_date = today

        # Hourly equity snapshot (TASK-STR-PHASE2-001): the append-only
        # equity curve phase 1 found missing. Venue-gated totals only.
        try:
            if time.time() - getattr(self, "_last_equity_snapshot", 0.0) >= 3600:
                self._last_equity_snapshot = time.time()
                from measurement import fill_ledger as _fl

                _fl.append_equity_snapshot(self.engine.equity_snapshot(trigger="hourly"))
        except Exception:
            pass

        self.scan_count += 1
        return results

    def _daily_summary_state_path(self) -> str:
        """Path of the persisted daily-summary throttle (TASK-STR-DAEMON-002).

        Same state-dir convention as the daemon heartbeat:
        STRATEX_STATE_DIR overrides, otherwise
        Stratex/state/daily_summary_state.json. The file holds
        {"last_summary_date": "YYYY-MM-DD"} — the UTC day the summary
        was last sent. state/ is gitignored; the file is runtime state
        only, regenerated on first send.
        """
        override = os.getenv("STRATEX_STATE_DIR")
        base = override if override else os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state"
        )
        return os.path.join(base, "daily_summary_state.json")

    def _load_last_summary_date(self) -> str:
        """Last UTC day a daily summary was sent, "" when unknown.

        Never raises: a missing or corrupt file degrades to "" (send
        once, then persist) — the pre-DAEMON-002 behaviour.
        """
        try:
            with open(self._daily_summary_state_path(), "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                date = raw.get("last_summary_date", "")
                if isinstance(date, str):
                    return date
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[STRATEX] Could not load daily-summary state: {e}")
        return ""

    def _persist_last_summary_date(self, date: str) -> None:
        """Persist the UTC day a daily summary was sent. Never raises."""
        try:
            path = self._daily_summary_state_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"last_summary_date": date}, fh, indent=2)
        except Exception as e:
            logger.debug(f"Daily-summary state persist failed: {e}")

    def _maybe_send_daily_summary(self, results: dict) -> None:
        """Send a Telegram daily summary once per UTC day (throttled)."""
        try:
            import datetime

            today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
            # TASK-STR-DAEMON-002: the throttle survives restarts — the
            # date is loaded from state/ when the engine is built
            # (including engines constructed without __init__, which the
            # test suites build via __new__).
            last = getattr(self, "_last_summary_date", None)
            if last is None:
                last = self._load_last_summary_date()
                self._last_summary_date = last
            if last == today:
                return
            self._last_summary_date = today
            self._persist_last_summary_date(today)

            bot = getattr(self.engine, "telegram_bot", None)
            if bot is None:
                try:
                    from notifications.telegram_bot import get_telegram_bot
                    bot = get_telegram_bot()
                except Exception:
                    return
            if not getattr(bot, "is_configured", False):
                return

            risk = self.engine.get_risk_summary() or {}
            equity = float(risk.get("total_equity", 0) or 0)
            realized = float(risk.get("realized_pnl", 0) or self.engine.realized_pnl or 0)
            positions_open = len(self.engine.positions)
            daily_loss_hit = bool(risk.get("daily_loss_limit_hit", False))

            paused = False
            try:
                from trading_pause import is_trading_paused
                paused = bool(is_trading_paused())
            except Exception:
                paused = False

            symbols_scanned = int(results.get("symbols", 0) or 0)
            signals_found = int(results.get("signals", 0) or 0)

            msg = (
                f"📊 <b>DAILY SUMMARY — {today}</b>\n\n"
                f"• <b>Date</b>: <code>{today}</code>\n"
                f"• <b>Symbols scanned</b>: <code>{symbols_scanned}</code>\n"
                f"• <b>Signals found</b>: <code>{signals_found}</code>\n"
                f"• <b>Positions open</b>: <code>{positions_open}</code>\n"
                f"• <b>Equity</b>: <code>${equity:,.2f}</code>\n"
                f"• <b>Realized PnL</b>: <code>${realized:+,.2f}</code>\n"
                f"• <b>Daily loss limit hit</b>: <code>{daily_loss_hit}</code>\n"
                f"• <b>Paused</b>: <code>{paused}</code>"
            )
            bot.send_message(msg)
        except Exception as e:
            logger.debug(f"[STRATEX] Daily summary failed: {e}")

    def _reconcile_positions(self):
        """Detect broker-side (SL/TP) exits and book the realized PnL once."""
        live_cache: Dict[str, Optional[list]] = {}
        try:
            for key, pos in list(self.engine.positions.items()):
                venue, _, symbol = key.partition(":")
                if not venue or not symbol:
                    logger.debug(f"[STRATEX] Malformed tracked position key: {key}")
                    continue

                adapter = self.engine.venues.get(venue)
                if adapter is None:
                    continue

                try:
                    # One live-position fetch per venue per reconciliation pass.
                    if venue not in live_cache:
                        try:
                            if hasattr(adapter, "get_positions_or_none"):
                                live_cache[venue] = adapter.get_positions_or_none()
                            else:
                                live_cache[venue] = adapter.get_positions()
                        except Exception as e:
                            logger.debug(
                                f"[STRATEX] Live position fetch failed for {venue}: {e}"
                            )
                            live_cache[venue] = None

                    live_positions = live_cache[venue]
                    if live_positions is None:
                        # Unknown state (API failure) is NOT flat. Never book on it.
                        logger.debug(
                            f"[STRATEX] Unknown position state for {venue}; "
                            f"skipping reconciliation"
                        )
                        continue

                    if any(p.symbol == symbol for p in live_positions):
                        continue

                    opened_at = self.engine.position_opened_at.get(key)
                    # TASK-STR-FWD-007: attribution decides who books this
                    # close. Positions the daemon itself opened always
                    # carry an entry in position_strategy (set by
                    # place_order at open). Positions adopted at startup
                    # (adopt_existing_positions) or detected untracked
                    # never do — they belong to another engine sharing
                    # the venue (e.g. the OANDA sleeve runner, the
                    # FX-MR-v4 trader), and that engine books its own
                    # closes from broker truth. Booking them here as
                    # well — strategy "unknown", PnL possibly from a
                    # ticker estimate — double-counted the close in the
                    # ledgers and in the daemon's realized_pnl.
                    strat_attribution = self.engine.position_strategy.get(key)
                    daemon_opened = strat_attribution not in (
                        None, "", "unknown", "UNATTRIBUTED",
                    )
                    pnl_info: Optional[dict] = None
                    if hasattr(adapter, "get_realized_pnl"):
                        try:
                            pnl_info = adapter.get_realized_pnl(symbol, since_ms=opened_at)
                        except TypeError:
                            pnl_info = adapter.get_realized_pnl(symbol)
                        except Exception as e:
                            logger.debug(
                                f"[STRATEX] Realized PnL lookup failed for {key}: {e}"
                            )
                            pnl_info = None

                    if pnl_info:
                        net = float(pnl_info.get("net", 0.0) or 0.0)
                        gross = float(pnl_info.get("gross", net) or 0.0)
                        fees = float(pnl_info.get("fees", 0.0) or 0.0)
                        trades = int(pnl_info.get("trades", 0) or 0)
                        exit_price = float(pnl_info.get("last_price", 0.0) or 0.0)
                    else:
                        # Fallback estimate from ticker (fee-blind).
                        ticker = self.engine.get_ticker(venue, symbol)
                        exit_price = ticker.last if ticker and ticker.last > 0 else pos.mark_price
                        gross = (exit_price - pos.entry_price) * pos.quantity
                        if pos.side in ("SHORT", "SELL"):
                            gross = -gross
                        fees = 0.0
                        net = gross
                        trades = 1

                    if exit_price <= 0:
                        exit_price = pos.mark_price

                    # Pop first: at most one booking per position, even if the
                    # booking or the Telegram send below raises.
                    self.engine.positions.pop(key, None)
                    self.engine.position_opened_at.pop(key, None)

                    if daemon_opened:
                        self.engine.realized_pnl += net
                        self.engine.daily_realized_pnl += net
                        # Route through the breaker check instead of mutating the
                        # counters directly: broker-side losses must count toward
                        # the daily loss limit too.
                        self.engine._check_daily_loss_limit()
                    self.engine.save_state()

                    # Write per-strategy ledger entry for analytics and auto-pruning.
                    # Attribution is popped first so both ledger writes below
                    # see it even if one of them fails.
                    strat = self.engine.position_strategy.pop(key, "unknown")
                    tf = self.engine.position_timeframe.pop(key, "n/a")
                    # TASK-STR-FWD-003: FORWARD_TEST lane fills are
                    # tagged in both ledgers so scorecards never blend
                    # the lane with the VALIDATED entrants.
                    lane = self._lane_for_strategy(strat)
                    entry_price = pos.entry_price
                    if not daemon_opened:
                        # TASK-STR-FWD-007: not the daemon's trade — the
                        # owning engine books this close itself. No ledger
                        # rows from here (either ledger), no realized_pnl
                        # accrual above; tracking cleanup below still runs.
                        logger.info(
                            f"[STRATEX] Position closed at broker: {key} — "
                            f"not opened by the daemon (attribution: "
                            f"{strat_attribution or 'none'}); leaving the "
                            f"close booking to the owning engine"
                        )
                    if daemon_opened:
                        try:
                            risk_per_unit = abs(entry_price - pos.mark_price) if pos.mark_price else 0.0
                            r_multiple = round(net / risk_per_unit, 2) if risk_per_unit > 0 else 0.0
                            ledger_entry = {
                                "symbol": symbol,
                                "strategy": strat,
                                "timeframe": tf,
                                "side": pos.side,
                                "quantity": pos.quantity,
                                "entry_price": entry_price,
                                "exit_price": exit_price,
                                "gross_pnl": gross,
                                "fees": fees,
                                "net_pnl": net,
                                "r_multiple": r_multiple,
                                "trades": trades,
                                "exit_reason": "SL_TP_BROKER",
                                "source": "MULTI_VENUE_RECONCILIATION",
                                # BUGFIX (TASK-STR-PHASE2-001): this used to read
                                # position_opened_at AFTER it was popped above,
                                # so entry_timestamp was always 0. Use the value
                                # captured before the pop.
                                "entry_timestamp": (opened_at or 0) / 1000.0,
                                "exit_timestamp": time.time(),
                                "timestamp": time.time(),
                            }
                            if lane:
                                ledger_entry["lane"] = lane
                            ledger_path = os.path.join(
                                os.path.dirname(os.path.dirname(__file__)), "testnet_trade_ledger.jsonl"
                            )
                            with open(ledger_path, "a", encoding="utf-8") as fh:
                                fh.write(json.dumps(ledger_entry) + "\n")
                        except Exception as e:
                            logger.warning(f"Ledger write failed for {key}: {e}")

                        # TASK-STR-PHASE2-001: the measurement fill ledger is
                        # the source of truth for performance (the legacy write
                        # above is kept for the auto-pruner). Broker figures
                        # when the adapter reported realized PnL; otherwise the
                        # row is labelled fees_source=estimate. append_fill
                        # itself latches a reconciliation alert on failure.
                        try:
                            from measurement import fill_ledger as _fl

                            fill_row = {
                                "strategy": strat,
                                "engine": "daemon",
                                "venue": venue,
                                "symbol": symbol,
                                "side": pos.side,
                                "qty": pos.quantity,
                                "entry_price": entry_price,
                                "exit_price": exit_price,
                                "entry_time": (opened_at or 0) / 1000.0,
                                "exit_time": time.time(),
                                "gross_pnl": gross,
                                "fees": fees,
                                "fees_source": "broker" if pnl_info else "estimate",
                                "net_pnl": net,
                                "exit_reason": "SL_TP_BROKER",
                                "order_id": str(getattr(pos, "position_id", "") or ""),
                            }
                            if lane:
                                fill_row["lane"] = lane
                            _fl.append_fill(fill_row)
                            _fl.append_equity_snapshot(
                                self.engine.equity_snapshot(trigger="fill")
                            )
                        except Exception as e:
                            logger.warning(f"Fill ledger write failed for {key}: {e}")

                    # Protective orders outlive a broker-side SL/TP hit; clear them.
                    if hasattr(adapter, "cancel_protective_orders"):
                        try:
                            cancelled = adapter.cancel_protective_orders(symbol)
                            if cancelled:
                                logger.info(
                                    f"[STRATEX] Cancelled {cancelled} leftover "
                                    f"protective order(s) on {symbol}"
                                )
                        except Exception as e:
                            logger.debug(
                                f"[STRATEX] Protective order cleanup failed for {key}: {e}"
                            )

                    logger.info(
                        f"[STRATEX] Position closed at broker: {key} "
                        f"net=${net:+.2f} gross=${gross:+.2f} fees=${fees:.2f} "
                        f"trades={trades}"
                    )

                    # Send Telegram
                    if self.engine.telegram_bot and self.engine.telegram_bot.is_configured:
                        emoji = "💰" if net >= 0 else "🔻"
                        self.engine.telegram_bot.send_message(
                            f"{emoji} <b>POSITION CLOSED</b>\n\n"
                            f"• <b>Venue</b>: <code>{venue}</code>\n"
                            f"• <b>Symbol</b>: <code>{symbol}</code>\n"
                            f"• <b>Side</b>: <code>{pos.side}</code>\n"
                            f"• <b>Qty</b>: <code>{pos.quantity}</code>\n"
                            f"• <b>Entry</b>: <code>{pos.entry_price:.5f}</code>\n"
                            f"• <b>Exit</b>: <code>{exit_price:.5f}</code>\n"
                            f"• <b>Realized PnL</b>: {emoji} <code>${net:+.2f}</code>\n"
                            f"• <b>Fees</b>: <code>{fees:.2f}</code>\n"
                            f"• <b>Trades</b>: <code>{trades}</code>\n"
                            f"• <b>Ticket</b>: <code>{pos.position_id}</code>"
                        )
                    # Position is flat at the broker: start the re-entry
                    # cooldown so a stale signal cannot instantly re-open it.
                    self.engine.mark_exit(venue, symbol)
                except Exception as e:
                    logger.debug(f"Reconciliation error for {key}: {e}")
        except Exception as e:
            logger.debug(f"Reconciliation error: {e}")

        # Untracked-position sweep (TASK-STR-PHASE2-001): every ~20th pass,
        # compare broker positions against tracked ones. A position the
        # daemon does not track — opened by another process sharing the
        # account, or left by a crashed run that adoption missed — is
        # tagged UNATTRIBUTED and alerted, never silently folded into PnL.
        self._reconcile_pass = getattr(self, "_reconcile_pass", 0) + 1
        if self._reconcile_pass % 20 == 0:
            try:
                from measurement import fill_ledger as _fl

                # TASK-STR-FWD-007: track sweep completeness so a CLEAN
                # sweep can clear the latched alert. A venue whose read
                # failed (live is None) makes the sweep incomplete — it
                # cannot prove the venue clean and must not clear. An
                # empty list is a successful read of a flat venue.
                sweep_complete = True
                untracked_found = 0
                for venue, adapter in self.engine.venues.items():
                    try:
                        getter = getattr(adapter, "get_positions_or_none", None)
                        live = getter() if callable(getter) else adapter.get_positions()
                    except Exception:
                        live = None
                    if live is None:
                        sweep_complete = False
                        continue
                    for p in live:
                        k = f"{venue}:{p.symbol}"
                        if k in self.engine.positions:
                            continue
                        untracked_found += 1
                        _fl.raise_alert(
                            "untracked_position",
                            f"{k} open at broker but not tracked by the daemon",
                        )
                        # TASK-STR-FWD-008: tag only the FIRST sighting.
                        # The sweep used to append an UNATTRIBUTED tag on
                        # every pass for the same position — the sleeve's
                        # USDJPY position collected dozens, including
                        # re-tags after its close was already booked —
                        # and it stamped UNATTRIBUTED over positions the
                        # tag stream already attributes. Skip the write
                        # when a fingerprint-matching tag already
                        # describes the position or the fill ledger
                        # already closed it. The alert above still fires:
                        # detection is unchanged, only the stream spam
                        # stops.
                        try:
                            _side = str(getattr(p, "side", "") or "")
                            _qty = float(getattr(p, "quantity", 0.0) or 0.0)
                            _entry = float(getattr(p, "entry_price", 0.0) or 0.0)
                            _described = _fl.latest_position_tag(
                                venue, p.symbol, side=_side, qty=_qty,
                                entry_price=_entry,
                            ) is not None
                            _closed = _fl.position_closed_in_ledger(
                                venue, p.symbol, side=_side, qty=_qty,
                                entry_price=_entry,
                            )
                        except Exception:
                            _described, _closed = False, False
                        if not _described and not _closed:
                            _fl.append_position_tag({
                                "engine": "daemon",
                                "venue": venue,
                                "venue_env": getattr(adapter, "base_url", ""),
                                "symbol": p.symbol,
                                "strategy": "UNATTRIBUTED",
                                "side": p.side,
                                "qty": p.quantity,
                                "entry_price": p.entry_price,
                                "note": "untracked_detected",
                            })
                if sweep_complete and untracked_found == 0:
                    # The condition this sweep raises on is gone; clear
                    # the latch. Before this, nothing ever called
                    # clear_alert for this kind, so the alert stayed
                    # ACTIVE forever (live evidence 2026-11-16: frozen
                    # at its last raise while the position was tracked).
                    _fl.clear_alert("untracked_position")
                # TASK-STR-FWD-017: unrecorded_close resolver, same shape
                # as the untracked_position clear above. Nothing ever
                # cleared this kind, so one rejection latched it forever
                # and later rejections silently merged into the same
                # latch. The events that raise it — append_fill
                # rejections and closed-without-a-row detections — are
                # not observable by this sweep directly, but every one
                # of them bumps the latch's raise count, so "clean" is
                # judged on the count: unchanged since the previous
                # COMPLETE sweep means no close went unrecorded in the
                # interval. An incomplete sweep proves nothing and
                # leaves the resolver untouched (never clears, baseline
                # preserved); the first complete sweep after startup
                # only sets the baseline, so a pre-existing latch clears
                # on the second consecutive clean sweep.
                if sweep_complete:
                    _uc = _fl.active_alerts().get("unrecorded_close") or {}
                    _uc_seen = getattr(
                        self, "_unrecorded_close_seen_count", None
                    )
                    if not _uc:
                        self._unrecorded_close_seen_count = None
                    elif (
                        _uc_seen is not None
                        and int(_uc.get("count", 0) or 0) == _uc_seen
                    ):
                        _fl.clear_alert("unrecorded_close")
                        self._unrecorded_close_seen_count = None
                    else:
                        self._unrecorded_close_seen_count = int(
                            _uc.get("count", 0) or 0
                        )
            except Exception as e:
                logger.debug(f"Untracked-position sweep failed: {e}")

    def _manage_trend_positions(self) -> None:
        """Exit a trend position when the completed daily close crosses EMA(20).

        The 2019-2026 study showed the exit rule carries the edge: a fixed 3R
        target was breakeven over seven years and negative since 2024, while
        the EMA20 exit stayed positive (PF 1.95 full sample, 1.09 OOS). The
        exchange-side stop stays armed as hard protection until the close fills.

        Only the market order is sent here. The reconciler sees the now-flat
        position on its next pass, books realized PnL from userTrades and sends
        the POSITION CLOSED alert, so PnL can never be double counted.
        """
        now = time.time()
        if now - self._last_trend_manage < 60:
            return
        self._last_trend_manage = now

        for key, pos in list(self.engine.positions.items()):
            venue, _, symbol = key.partition(":")
            if not venue or not symbol:
                continue
            adapter = self.engine.venues.get(venue)
            if adapter is None:
                continue
            try:
                # The EMA20-cross exit is the documented edge of the DAILY
                # trend strategy only. Applied to every position it became a
                # permanent kill switch: any symbol whose price sits below its
                # daily EMA20 (e.g. ETH at -8%) had EVERY new position force-
                # closed within a minute of entry, confiscating scalps before
                # they could develop (live: 16 ETH closes at +$0.01-0.04 each
                # against ~$0.60 round-trip fees). Scalps keep their own
                # exchange-side SL/TP; they do not get a daily-bar exit.
                strat = self.engine.position_strategy.get(key, "")
                tf = self.engine.position_timeframe.get(key, "")
                # TASK-STR-FWD-002 fix: the previous condition
                # (strat != trend_daily AND tf != 1d -> skip) let EVERY 1d
                # position through, so governed 1d positions (dow_effect)
                # would have been force-exited by this EMA20 rule instead
                # of their judged bracket_time exits. The EMA20 exit is
                # strategy_trend_daily's own rule — scope it to that
                # strategy only.
                if strat != "strategy_trend_daily":
                    continue

                candles = self.engine.get_candles(venue, symbol, "1d", 60)
                if not candles:
                    continue
                # Keep only completed daily bars: the last one is still forming.
                closed = [
                    c for c in candles
                    if float(c.get("timestamp", 0)) + 86400 <= now
                ]
                if len(closed) < 25:
                    continue

                closes = [float(c["close"]) for c in closed]
                ema20 = closes[0]
                alpha = 2.0 / 21.0
                for px in closes[1:]:
                    ema20 = alpha * px + (1.0 - alpha) * ema20
                last_close = closes[-1]

                is_long = str(pos.side).upper() in ("LONG", "BUY")
                trigger = (
                    last_close < ema20 if is_long else last_close > ema20
                )
                if not trigger:
                    continue

                close_side = "SELL" if is_long else "BUY"
                result = adapter.place_order(
                    symbol, close_side, "MARKET", pos.quantity
                )
                if result is None:
                    logger.warning(
                        f"[STRATEX] Trend exit rejected for {venue}:{symbol}"
                    )
                    continue
                if hasattr(adapter, "cancel_protective_orders"):
                    adapter.cancel_protective_orders(symbol)
                logger.info(
                    f"[STRATEX] Trend exit {venue}:{symbol} ({pos.side}): "
                    f"daily close {last_close:.4f} crossed EMA20 {ema20:.4f}"
                )
            except Exception as e:
                logger.warning(f"[STRATEX] Trend exit check failed for {key}: {e}")

    # ------------------------------------------------------------------
    # TASK-STR-FWD-002: phase-3 forward protocol (time exits + guard)
    # ------------------------------------------------------------------

    _BAR_SECONDS = {
        "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600,
        "4h": 14400, "1d": 86400, "1w": 604800,
    }

    def _weekly_aggregate(self, symbol: str, daily_candles: list) -> list:
        """Rebuild judged weekly buckets from daily candles (sleeve leg).

        Delegates to strategy_sleeve_shock_breakout.weekly_candles,
        which owns the judged bar construction (7-day buckets anchored
        per symbol at the RD-002 series starts)."""
        try:
            import strategy_sleeve_shock_breakout as _shock

            return _shock.weekly_candles(daily_candles, symbol)
        except Exception as e:
            logger.warning(f"[STRATEX] Weekly aggregation failed for {symbol}: {e}")
            return []

    def _forward_protocol_entries(self) -> dict:
        """{module_name: registry entry} for forward_protocol strategies."""
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY

            return {
                "strategy_" + key: entry
                for key, entry in PRODUCTION_STRATEGY_REGISTRY.items()
                if entry.get("forward_protocol")
            }
        except Exception as e:
            logger.warning(f"[STRATEX] Forward protocol registry read failed: {e}")
            return {}

    def _lane_for_strategy(self, strat: str) -> str | None:
        """TASK-STR-FWD-003: the fill-ledger lane tag for a strategy.

        Returns "FORWARD_TEST" when config_strategy governance classifies
        the strategy FORWARD_TEST, else None (VALIDATED entrants and
        legacy strategies keep their historical row shape — no lane key).
        """
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY

            key = strat[len("strategy_"):] if strat.startswith("strategy_") else strat
            entry = PRODUCTION_STRATEGY_REGISTRY.get(key) or {}
            if entry.get("status") == "FORWARD_TEST":
                return str(entry.get("forward_lane") or "FORWARD_TEST")
        except Exception:
            pass
        return None

    def _max_stop_pct_for_strategy(self, strat: str) -> float | None:
        """TASK-STR-FWD-012: the per-strategy max-stop cap override.

        A strategy whose registry entry declares ``max_stop_pct`` (wide
        judged ATR brackets — sleeve_shock_breakout 2.0x weekly ATR,
        dow_effect 3.0x daily ATR) is judged against that value instead
        of the engine-global cap. Under FWD-006, dollar risk is
        quantity-controlled (size = risk budget / stop distance, heat
        cap on top), so a wider stop shrinks the position instead of
        adding risk; the override is a sanity bound against geometry /
        unit errors, not a risk loosening. Strategies without the key
        return None and keep the global cap exactly as before.
        """
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY

            key = strat[len("strategy_"):] if strat.startswith("strategy_") else strat
            entry = PRODUCTION_STRATEGY_REGISTRY.get(key) or {}
            value = entry.get("max_stop_pct")
            if value is None:
                return None
            value = float(value)
            return value if value > 0 else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # TASK-STR-FWD-021: RD-014 vol-target overlay manager.
    #
    # The 21 overlay configurations (config_strategy entries with
    # execution_mode "overlay") have no SL/TP bracket, so the
    # get_signal/_execute_signal path cannot run them. This manager
    # holds each configuration's venue position at the judged target
    # weight m * w (overlay_service.target_weight — signal, vol-target
    # sizing and the shadow-equity drawdown brake, ported line-faithfully
    # from rigorous_backtest/rd14/family14.py). Actions are bar-cadenced
    # and target-based, hence idempotent: no state persists, and a
    # restart simply re-derives the same target from candle history.
    #
    # Governance, mirroring the lane's standing rules:
    # - FORWARD_TEST venue confinement: only venues attested demo in
    #   the strategy registry are touched (fail-closed).
    # - A configuration on the persisted denylist (phase-3 kill
    #   criteria, _maybe_apply_forward_guard) is never opened or
    #   increased; its open position is still reduced/closed here.
    # - Entries/increases additionally require the fail-closed
    #   pause/panic reads of _execute_signal and run only in the
    #   post-daily-loss-gate pass (allow_entries=True); closes and
    #   reductions run in both passes, like the other managers'
    #   exits, so a losing book can always be reduced.
    # - One venue position per symbol account-wide: a symbol held by
    #   another strategy is contention — skipped and counted, never
    #   touched.
    # Order routing: opens go through engine.place_order (position
    # attribution + fill-ledger tag); adjustments to an open position
    # go through the venue adapter directly (engine.place_order is an
    # open-only primitive — it would overwrite the tracked position),
    # following the _manage_trend_positions precedent. A sign flip is
    # a close in this pass and a fresh open once the reconciler shows
    # the symbol flat — never a single double-sided order.
    # Venue bracket (TASK-STR-FWD-031): overlay entries are placed AND
    # held at the venue bracket. Opens carry the SL/TP pair from
    # overlay_service.bracket_levels (a catastrophic backstop at
    # BRACKET_SIGMA_MULTIPLE one-bar sigmas from the entry price,
    # derived from the overlay's own judged sigma — NOT a judged exit;
    # the judged exits remain the target weight and the brake). An
    # open with no computable bracket is refused, never placed
    # unprotected. The entry bracket (closePosition) covers the whole
    # position, so increases place no new protection; a held position
    # that has none (opened before brackets existed) gets one attached
    # by _overlay_ensure_bracket on the next manage pass, unless a
    # protective algo order is already open on the symbol (never stack
    # a second bracket). Closes cancel the protective orders, as
    # before.
    # ------------------------------------------------------------------

    _OVERLAY_MIN_ORDER_NOTIONAL = 10.0    # below this, an open/increase is not worth its fees
    _OVERLAY_REBALANCE_TOLERANCE = 5.0    # |delta| below this is held, not churned
    _OVERLAY_HISTORY_LIMIT = 1500         # candles requested per symbol/timeframe

    def _overlay_entries_blocked(self) -> bool:
        """Fail-closed pause/panic reads, mirroring _execute_signal."""
        try:
            from trading_pause import is_trading_paused

            if is_trading_paused():
                return True
        except Exception as e:
            logger.error(
                f"[STRATEX] Overlay pause-state read failed ({e}); "
                "failing CLOSED, entries blocked"
            )
            return True
        try:
            from panic_state import is_panic_active, is_kill_switch_locked

            if is_panic_active() or is_kill_switch_locked():
                return True
        except Exception as e:
            logger.error(
                f"[STRATEX] Overlay panic-state read failed ({e}); "
                "failing CLOSED, entries blocked"
            )
            return True
        return False

    def _manage_overlay_positions(self, allow_entries: bool) -> None:
        now = time.time()
        throttle_attr = (
            "_last_overlay_entries" if allow_entries else "_last_overlay_exits"
        )
        if now - getattr(self, throttle_attr, 0.0) < 60:
            return
        setattr(self, throttle_attr, now)
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY

            import overlay_service
        except Exception as e:
            logger.warning(f"[STRATEX] Overlay manager unavailable: {e}")
            return
        configs = {
            key: entry
            for key, entry in PRODUCTION_STRATEGY_REGISTRY.items()
            if entry.get("status") == "FORWARD_TEST"
            and entry.get("execution_mode") == "overlay"
            and entry.get("forward_protocol")
            and entry.get("lane_assets")
        }
        if not configs:
            return
        # TASK-STR-FWD-028: the signal path skips any strategy missing
        # from a non-empty STRATEX_STRATEGY_ALLOWLIST, but this manager
        # never consulted it — on 2026-11-19 the daemon opened 30
        # unprotected overlay positions (the overlay path places orders
        # with no venue SL/TP brackets) while the allowlist held only
        # the four signal-path names. Mirror the signal path: with a
        # non-empty allowlist, an overlay config outside it is skipped
        # entirely — no entries and no management. An empty allowlist
        # keeps the previous behaviour (every overlay config managed).
        allowlist = getattr(self, "strategy_allowlist", set())
        if allowlist:
            skipped = sorted(
                "strategy_" + key
                for key in configs
                if "strategy_" + key not in allowlist
            )
            if skipped:
                configs = {
                    key: entry
                    for key, entry in configs.items()
                    if "strategy_" + key in allowlist
                }
                if now - getattr(self, "_last_overlay_allowlist_log", 0.0) >= 60:
                    self._last_overlay_allowlist_log = now
                    logger.warning(
                        "[STRATEX] Overlay WARNING: overlay strategies "
                        "are NOT in STRATEX_STRATEGY_ALLOWLIST and will "
                        f"not be managed: {skipped}"
                    )
                if not configs:
                    return
        try:
            demo_venues = strategy_registry.demo_venues()
        except Exception as e:
            logger.warning(
                f"[STRATEX] Overlay demo-venue attestation read failed: {e}"
            )
            return
        entries_blocked = (not allow_entries) or self._overlay_entries_blocked()
        acted = 0
        contention = 0
        evaluated = 0
        for key in sorted(configs):
            entry = configs[key]
            strat_name = "strategy_" + key
            denylisted = strat_name in self.strategy_denylist
            tf = str(entry.get("timeframe") or "")
            params = entry.get("overlay") or {}
            try:
                signal = str(params["signal"])
                vol_target = float(params["vol_target"])
                brake = str(params["brake"])
                cost = float(params.get("cost_per_turnover", 0.0008))
                alloc = float(entry.get("overlay_capital_pct", 0.005))
            except Exception as e:
                logger.warning(
                    f"[STRATEX] Overlay config {key} malformed ({e}); skipped"
                )
                continue
            bar_seconds = overlay_service.BAR_SECONDS.get(tf)
            if bar_seconds is None:
                continue
            for venue, venue_symbols in self.symbols.items():
                if venue not in demo_venues:
                    continue
                adapter = self.engine.venues.get(venue)
                if adapter is None:
                    continue
                try:
                    equity = float(self.engine.get_venue_equity(venue) or 0.0)
                except Exception:
                    equity = 0.0
                if equity <= 0:
                    continue
                book = alloc * equity
                for symbol in entry["lane_assets"]:
                    if symbol not in venue_symbols:
                        continue
                    try:
                        done = self._overlay_manage_one(
                            overlay_service=overlay_service,
                            key=key,
                            strat_name=strat_name,
                            venue=venue,
                            adapter=adapter,
                            symbol=symbol,
                            tf=tf,
                            bar_seconds=bar_seconds,
                            signal=signal,
                            vol_target=vol_target,
                            brake=brake,
                            cost=cost,
                            book=book,
                            entries_blocked=entries_blocked or denylisted,
                            now=now,
                        )
                        evaluated += 1
                        if done == "acted":
                            acted += 1
                        elif done == "contention":
                            contention += 1
                    except Exception as e:
                        logger.warning(
                            f"[STRATEX] Overlay manage failed for "
                            f"{key} {venue}:{symbol}: {e}"
                        )
        if acted or contention:
            logger.info(
                f"[STRATEX] Overlay manager ({'entries' if allow_entries else 'exits'} pass): "
                f"{acted} orders, {contention} contention skips, "
                f"{evaluated} config-symbols evaluated"
            )

    def _overlay_manage_one(self, *, overlay_service, key, strat_name, venue,
                            adapter, symbol, tf, bar_seconds, signal,
                            vol_target, brake, cost, book,
                            entries_blocked, now) -> str:
        """Drive one (config, venue, symbol) toward its target weight.

        Returns "acted" (an order was placed), "contention" (symbol
        held by another strategy) or "held".
        """
        vs_key = f"{venue}:{symbol}"
        pos = self.engine.positions.get(vs_key)
        if pos is not None and self.engine.position_strategy.get(vs_key) != strat_name:
            return "contention"
        candles = self.engine.get_candles(
            venue, symbol, tf, self._OVERLAY_HISTORY_LIMIT
        )
        if not candles:
            return "held"
        closes = []
        stamps = []
        for c in candles:
            try:
                ts = float(c.get("timestamp", 0))
                px = float(c["close"])
            except Exception:
                continue
            if ts + bar_seconds <= now and px > 0:
                stamps.append(ts)
                closes.append(px)
        if len(closes) < overlay_service.MIN_BARS:
            return "held"
        import pandas as pd

        target = overlay_service.target_weight(
            pd.Series(closes), signal, vol_target, brake, tf, cost
        )
        last_close = closes[-1]
        ticker = self.engine.get_ticker(venue, symbol)
        price = float(ticker.last) if ticker and ticker.last else last_close
        if price <= 0:
            return "held"
        target_notional = target["weight"] * book
        cur_qty = 0.0
        if pos is not None:
            cur_qty = float(pos.quantity or 0.0)
            if str(pos.side).upper() in ("SHORT", "SELL"):
                cur_qty = -cur_qty
        cur_notional = cur_qty * last_close
        delta_notional = target_notional - cur_notional

        def _log(action, qty):
            logger.info(
                f"[STRATEX] Overlay {action}: {key} {venue}:{symbol} {tf} "
                f"qty={qty:.6f} target_w={target['weight']:+.4f} "
                f"(raw {target['raw_weight']:+.4f}, brake_m={target['brake_m']}, "
                f"shadow_dd={target['shadow_dd']:.4f}, bars={target['bars']})"
            )

        # Close: no target, or a sign flip (the open side is taken in a
        # later pass once the reconciler shows the symbol flat).
        if pos is not None and (
            target_notional == 0.0
            or (target_notional > 0) != (cur_notional > 0)
        ):
            close_side = "SELL" if cur_qty > 0 else "BUY"
            result = adapter.place_order(
                symbol, close_side, "MARKET", abs(cur_qty)
            )
            if result is None:
                logger.warning(
                    f"[STRATEX] Overlay close rejected for {key} {venue}:{symbol}"
                )
                return "held"
            if hasattr(adapter, "cancel_protective_orders"):
                adapter.cancel_protective_orders(symbol)
            _log("close", abs(cur_qty))
            return "acted"
        if pos is not None:
            # TASK-STR-FWD-031: a held overlay position must carry the
            # venue bracket. Opens place it with the entry; a position
            # that has none (opened before brackets existed) gets it
            # attached here, before any reduce/increase — the entry
            # bracket then stays armed for the position's whole life.
            is_long = str(pos.side).upper() in ("LONG", "BUY")
            bsl, btp = overlay_service.bracket_levels(
                target["sigma"], tf, price, is_long
            )
            self._overlay_ensure_bracket(
                adapter=adapter, venue=venue, symbol=symbol, key=key,
                stop_loss=bsl, take_profit=btp,
                quantity=float(pos.quantity or 0),
            )
        if abs(delta_notional) < self._OVERLAY_REBALANCE_TOLERANCE:
            return "held"
        if delta_notional * (1 if target_notional >= 0 else -1) < 0:
            # Reduction toward (not past) the target.
            reduce_qty = min(abs(delta_notional) / price, abs(cur_qty))
            if reduce_qty <= 0:
                return "held"
            side = "SELL" if cur_qty > 0 else "BUY"
            result = adapter.place_order(symbol, side, "MARKET", reduce_qty)
            if result is None:
                logger.warning(
                    f"[STRATEX] Overlay reduce rejected for {key} {venue}:{symbol}"
                )
                return "held"
            _log("reduce", reduce_qty)
            return "acted"
        # Open or increase: entries only, under the entry gates.
        if entries_blocked:
            return "held"
        add_notional = abs(delta_notional)
        if pos is None and add_notional < self._OVERLAY_MIN_ORDER_NOTIONAL:
            logger.debug(
                f"[STRATEX] Overlay open skipped for {key} {venue}:{symbol}: "
                f"target notional ${add_notional:.2f} below the "
                f"${self._OVERLAY_MIN_ORDER_NOTIONAL:.0f} floor"
            )
            return "held"
        qty = add_notional / price
        side = "BUY" if delta_notional > 0 else "SELL"
        if pos is not None:
            result = adapter.place_order(symbol, side, "MARKET", qty)
            if result is None:
                logger.warning(
                    f"[STRATEX] Overlay increase rejected for {key} {venue}:{symbol}"
                )
                return "held"
            _log("increase", qty)
            return "acted"
        can_open, reason = self.engine.can_open_position(venue)
        if not can_open:
            logger.debug(
                f"[STRATEX] Overlay open blocked for {key} {venue}:{symbol}: {reason}"
            )
            return "held"
        # TASK-STR-FWD-031: the open carries the venue bracket. No
        # computable bracket means no entry — an unprotected overlay
        # open is never placed.
        stop_loss, take_profit = overlay_service.bracket_levels(
            target["sigma"], tf, price, side == "BUY"
        )
        if stop_loss is None or take_profit is None:
            logger.warning(
                f"[STRATEX] Overlay open refused for {key} {venue}:{symbol}: "
                "no venue bracket computable from sigma "
                f"{target['sigma']:.6g} tf={tf} price={price:.6g}"
            )
            return "held"
        result = self.engine.place_order(
            venue, symbol, side, "MARKET", qty,
            stop_loss=stop_loss, take_profit=take_profit,
            strategy_name=strat_name, timeframe=tf,
        )
        if result is None:
            logger.warning(
                f"[STRATEX] Overlay open rejected for {key} {venue}:{symbol}"
            )
            return "held"
        if self._overlay_bracket_armed(adapter, symbol) is False:
            logger.warning(
                f"[STRATEX] Overlay open for {key} {venue}:{symbol} filled "
                "but no venue bracket is armed — position is UNPROTECTED"
            )
        _log("open", qty)
        return "acted"

    def _overlay_bracket_armed(self, adapter, symbol) -> bool | None:
        """True if a protective algo order is open on the symbol, False
        if the venue reports none, None if the adapter cannot answer.

        TASK-STR-FWD-031: the venue-bracket check for overlay
        positions. Adapters without a get_open_algo_orders seam return
        None — the bracket state is then unverifiable from here.
        """
        get_algos = getattr(adapter, "get_open_algo_orders", None)
        if not callable(get_algos):
            return None
        try:
            return bool(get_algos(symbol))
        except Exception as e:
            logger.warning(
                f"[STRATEX] Overlay bracket check failed for {symbol}: {e}"
            )
            return None

    def _overlay_ensure_bracket(self, *, adapter, venue, symbol, key,
                                stop_loss, take_profit, quantity) -> None:
        """Attach the venue bracket to a held overlay position that has none.

        TASK-STR-FWD-031: every overlay position the daemon holds must
        carry a live venue bracket. A position opened before brackets
        existed (tracked stop_loss/take_profit both zero) gets one
        attached on the next manage pass. Skips when the tracked
        position already records a bracket, or when a protective algo
        order is already open on the symbol (never stack a second
        bracket — the closePosition pair covers the whole position).
        On success the tracked record is updated so the next pass
        skips. Adapters without a place_protective_orders seam are
        logged loudly and the position stays under the judged brake.
        """
        pos = self.engine.positions.get(f"{venue}:{symbol}")
        if pos is None:
            return
        if float(getattr(pos, "stop_loss", 0) or 0) > 0 and float(
                getattr(pos, "take_profit", 0) or 0) > 0:
            return
        if stop_loss is None or take_profit is None:
            logger.warning(
                f"[STRATEX] Overlay {key} {venue}:{symbol} has no venue "
                "bracket and none is computable; held unprotected "
                "under the judged brake"
            )
            return
        place_protective = getattr(adapter, "place_protective_orders", None)
        if not callable(place_protective):
            logger.warning(
                f"[STRATEX] Overlay {key} {venue}:{symbol} has no venue "
                "bracket and this venue adapter cannot attach one; "
                "held unprotected under the judged brake"
            )
            return
        if self._overlay_bracket_armed(adapter, symbol):
            return
        try:
            place_protective(
                symbol=symbol,
                side="BUY" if str(pos.side).upper() in ("LONG", "BUY") else "SELL",
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        except Exception as e:
            logger.warning(
                f"[STRATEX] Overlay bracket attach failed for {key} "
                f"{venue}:{symbol}: {e}"
            )
            return
        if self._overlay_bracket_armed(adapter, symbol) is False:
            logger.warning(
                f"[STRATEX] Overlay bracket attach for {key} {venue}:{symbol} "
                "did not arm — position is UNPROTECTED"
            )
            return
        try:
            pos.stop_loss = float(stop_loss)
            pos.take_profit = float(take_profit)
        except Exception:
            pass

    def _maybe_run_wf_selection(self) -> None:
        """TASK-STR-FWD-022: run due walk-forward selections.

        For each FORWARD_TEST registry entry with execution_mode
        "wf_select", when the persisted pick belongs to an older
        epoch than the current one (or none exists), gather the lane
        panel's candle history from an attested demo venue and run
        the judged selection rule (wf_select_service.run_selection —
        strictly bars closed before the epoch start), persist the
        decision (state + append-only log) and log the pick with its
        in-sample table. Places no orders. Throttled to one check
        per 10 minutes; a failed run leaves the previous pick in
        place and retries on the next check.
        """
        now = time.time()
        if now - getattr(self, "_last_wf_select_check", 0.0) < 600:
            return
        self._last_wf_select_check = now
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY

            import pandas as pd

            import wf_select_service as wfs
        except Exception as e:
            logger.warning(f"[STRATEX] WF selection unavailable: {e}")
            return
        entries = {
            key: entry
            for key, entry in PRODUCTION_STRATEGY_REGISTRY.items()
            if entry.get("status") == "FORWARD_TEST"
            and entry.get("execution_mode") == "wf_select"
            and entry.get("forward_protocol")
            and entry.get("lane_assets")
        }
        if not entries:
            return
        try:
            demo_venues = strategy_registry.demo_venues()
        except Exception as e:
            logger.warning(
                f"[STRATEX] WF selection demo-venue attestation read failed: {e}"
            )
            return
        epoch_start = wfs.epoch_start_for()
        for key in sorted(entries):
            entry = entries[key]
            spec_ref = entry.get("wf_select") or {}
            procedure_id = spec_ref.get("procedure")
            if procedure_id not in wfs.PROCEDURES:
                logger.warning(
                    f"[STRATEX] WF selection: {key} names unregistered "
                    f"procedure {procedure_id!r}; skipped"
                )
                continue
            state = wfs.load_state(procedure_id)
            if state and state.get("epoch_start") == epoch_start.isoformat():
                continue
            tf = str(entry.get("timeframe") or "1d")
            venue = None
            for candidate, symbols in self.symbols.items():
                if candidate in demo_venues and candidate in self.engine.venues:
                    if any(s in symbols for s in entry["lane_assets"]):
                        venue = candidate
                        break
            if venue is None:
                logger.warning(
                    f"[STRATEX] WF selection for {key}: no attested demo "
                    "venue carries the lane panel; pick not refreshed"
                )
                continue
            try:
                frames = {}
                for symbol in entry["lane_assets"]:
                    candles = self.engine.get_candles(venue, symbol, tf, 1500)
                    if not candles:
                        continue
                    frame = pd.DataFrame(candles)
                    frame.index = pd.to_datetime(
                        frame["timestamp"], unit="s", utc=True
                    )
                    frames[symbol] = frame.sort_index()
                if not frames:
                    logger.warning(
                        f"[STRATEX] WF selection for {key}: no candle "
                        f"history on {venue}; pick not refreshed"
                    )
                    continue
                decision = wfs.run_selection(procedure_id, frames, epoch_start)
                if decision["pick"] is None:
                    logger.warning(
                        f"[STRATEX] WF selection for {key}: no variant "
                        f"qualified for epoch {epoch_start.date()} "
                        "(empty in-sample table); previous pick kept"
                    )
                    continue
                wfs.save_selection(decision)
                table = ", ".join(
                    f"{v}: PF {m['profit_factor_net']:.3f} / {m['trades']} tr"
                    if m["profit_factor_net"] is not None
                    else f"{v}: no IS trades"
                    for v, m in sorted(decision["is_table"].items())
                )
                logger.info(
                    f"[STRATEX] WF selection {key}: epoch "
                    f"{epoch_start.date()} pick={decision['pick']} "
                    f"(IS: {table}; history {decision['history']})"
                )
            except Exception as e:
                logger.warning(
                    f"[STRATEX] WF selection run failed for {key}: {e}"
                )

    def _maybe_run_panel_rankings(self) -> None:
        """TASK-STR-FWD-024: refresh cross-sectional panel memberships.

        For each FORWARD_TEST registry entry with execution_mode
        "panel_xs", when the persisted membership predates the
        latest judged rebalance bar (or none exists), gather the
        lane panel's candle history from an attested demo venue and
        run the judged ranking (panel_signal_service.run_membership
        — strictly closed bars, panel grid counted from the judged
        anchor), persist the decision (state + append-only log) and
        log the membership. Places no orders. Throttled to one check
        per 10 minutes; a failed run keeps the PREVIOUS membership
        (fail-closed, wf_select precedent) and retries on the next
        check.
        """
        now = time.time()
        if now - getattr(self, "_last_panel_xs_check", 0.0) < 600:
            return
        self._last_panel_xs_check = now
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY

            import pandas as pd

            import panel_signal_service as pss
        except Exception as e:
            logger.warning(f"[STRATEX] Panel ranking unavailable: {e}")
            return
        entries = {
            key: entry
            for key, entry in PRODUCTION_STRATEGY_REGISTRY.items()
            if entry.get("status") == "FORWARD_TEST"
            and entry.get("execution_mode") == "panel_xs"
            and entry.get("forward_protocol")
            and entry.get("lane_assets")
        }
        if not entries:
            return
        try:
            demo_venues = strategy_registry.demo_venues()
        except Exception as e:
            logger.warning(
                f"[STRATEX] Panel ranking demo-venue attestation read failed: {e}"
            )
            return
        for key in sorted(entries):
            entry = entries[key]
            spec_ref = entry.get("panel_xs") or {}
            stream_id = spec_ref.get("stream")
            stream = pss.STREAMS.get(stream_id)
            if stream is None:
                logger.warning(
                    f"[STRATEX] Panel ranking: {key} names unregistered "
                    f"stream {stream_id!r}; skipped"
                )
                continue
            # Nothing new can be decided until a later rebalance bar
            # than the persisted one has closed.
            state = pss.load_membership(stream_id)
            bar_seconds = pss.BAR_SECONDS[stream["timeframe"]]
            anchor_epoch = int(
                pd.Timestamp(stream["anchor"]).timestamp()
            )
            now_grid = int((now - anchor_epoch) // bar_seconds)
            latest_rebalance = (
                stream["warmup"]
                + ((now_grid - 1 - stream["warmup"]) // stream["rebalance"])
                * stream["rebalance"]
            )
            if (
                state
                and state.get("ok")
                and int(state.get("rebalance_epoch", -1))
                >= anchor_epoch + latest_rebalance * bar_seconds
            ):
                continue
            tf = str(entry.get("timeframe") or "1d")
            venue = None
            for candidate, symbols in self.symbols.items():
                if candidate in demo_venues and candidate in self.engine.venues:
                    if any(s in symbols for s in entry["lane_assets"]):
                        venue = candidate
                        break
            if venue is None:
                logger.warning(
                    f"[STRATEX] Panel ranking for {key}: no attested demo "
                    "venue carries the lane panel; membership not refreshed"
                )
                continue
            try:
                frames = {}
                for symbol in entry["lane_assets"]:
                    candles = self.engine.get_candles(venue, symbol, tf, 1500)
                    if not candles:
                        continue
                    frame = pd.DataFrame(candles)
                    frame.index = pd.to_datetime(
                        frame["timestamp"], unit="s", utc=True
                    )
                    frames[symbol] = frame.sort_index()
                if not frames:
                    logger.warning(
                        f"[STRATEX] Panel ranking for {key}: no candle "
                        f"history on {venue}; membership not refreshed"
                    )
                    continue
                decision = pss.run_membership(stream_id, frames)
                if not decision.get("ok"):
                    logger.warning(
                        f"[STRATEX] Panel ranking for {key} failed closed "
                        f"({decision.get('reason')}); previous membership kept"
                    )
                    continue
                saved = pss.save_membership(decision)
                picks = ", ".join(
                    f"{sym} {e['side']}"
                    for sym, e in sorted(decision["entries"].items())
                )
                logger.info(
                    f"[STRATEX] Panel ranking {key}: rebalance "
                    f"{decision['rebalance_bar']} membership "
                    f"[{picks or 'none'}] (panel as of "
                    f"{decision['panel_asof']}, "
                    f"{decision['panel']['symbols_ranked']} ranked; "
                    f"persisted={saved})"
                )
            except Exception as e:
                logger.warning(
                    f"[STRATEX] Panel ranking run failed for {key}: {e}"
                )

    def _manage_forward_time_exits(self) -> None:
        """Enforce judged bracket_time exits (e.g. dow_effect max_bars=5).

        The judged simulator exits at the close of entry_bar + max_bars - 1
        when neither bracket level was hit; broker protective orders carry
        only SL/TP, so the daemon closes the position at market once that
        bar has fully elapsed (measurement/forward_guard.time_exit_due).
        Only the market order is sent here — the reconciler books the
        close into the fill ledger from userTrades, as for trend exits.
        """
        now = time.time()
        if now - getattr(self, "_last_forward_manage", 0) < 60:
            return
        self._last_forward_manage = now

        entries = self._forward_protocol_entries()
        timed = {name: e for name, e in entries.items() if e.get("max_bars")}
        if not timed:
            return
        try:
            from measurement import forward_guard
        except Exception as e:
            logger.warning(f"[STRATEX] Forward guard import failed: {e}")
            return

        for key, pos in list(self.engine.positions.items()):
            venue, _, symbol = key.partition(":")
            if not venue or not symbol:
                continue
            strat = self.engine.position_strategy.get(key, "")
            gov = timed.get(strat)
            if gov is None:
                continue
            adapter = self.engine.venues.get(venue)
            if adapter is None:
                continue
            try:
                tf = self.engine.position_timeframe.get(key, "") or str(
                    gov.get("timeframe", "1d")
                )
                # TASK-STR-FWD-035: normalize — a position opened
                # before the fix may still carry the legacy "1wk".
                bar_seconds = self._BAR_SECONDS.get(_normalize_timeframe_label(tf), 86400)
                opened_ms = float(self.engine.position_opened_at.get(key, 0) or 0)
                if opened_ms <= 0:
                    continue
                if not forward_guard.time_exit_due(
                    opened_ms / 1000.0, now, int(gov["max_bars"]), bar_seconds
                ):
                    continue
                is_long = str(pos.side).upper() in ("LONG", "BUY")
                close_side = "SELL" if is_long else "BUY"
                result = adapter.place_order(
                    symbol, close_side, "MARKET", pos.quantity
                )
                if result is None:
                    logger.warning(
                        f"[STRATEX] Forward time exit rejected for {venue}:{symbol}"
                    )
                    continue
                if hasattr(adapter, "cancel_protective_orders"):
                    adapter.cancel_protective_orders(symbol)
                logger.info(
                    f"[STRATEX] Forward time exit {venue}:{symbol} ({pos.side}) "
                    f"strategy={strat} max_bars={gov['max_bars']} tf={tf} "
                    f"(TASK-STR-FWD-002 judged bracket_time)"
                )
            except Exception as e:
                logger.warning(f"[STRATEX] Forward time exit check failed for {key}: {e}")

    # ------------------------------------------------------------------
    # TASK-STR-FWD-023: judged trailing-stop exits (donchian/turtle TRAIL)
    # ------------------------------------------------------------------

    def _trailing_spec_for_strategy(self, strat: str) -> dict | None:
        """The judged trailing-exit spec for a strategy, or None.

        A strategy trades the trailing exit ONLY when its registry
        entry explicitly declares ``exit_mode == "trailing"`` with the
        judged multiples (``exit_sl_atr`` / ``exit_trail_atr`` — the
        families2 TRAIL spec: initial stop 2.0 x ATR(14), trailing stop
        2.5 x ATR(14), ATR frozen at the signal bar, no fixed TP).
        Anything else — no entry, no declaration, malformed values —
        returns None and the strategy keeps the fixed-bracket path
        exactly as before (fail-closed: a module returning tp_dist=None
        without this declaration still cannot trade).
        """
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY

            key = strat[len("strategy_"):] if strat.startswith("strategy_") else strat
            entry = PRODUCTION_STRATEGY_REGISTRY.get(key) or {}
            if entry.get("exit_mode") != "trailing":
                return None
            sl_atr = float(entry.get("exit_sl_atr"))
            trail_atr = float(entry.get("exit_trail_atr"))
            if sl_atr <= 0 or trail_atr <= 0:
                return None
            return {"sl_atr": sl_atr, "trail_atr": trail_atr}
        except Exception:
            return None

    def _trailing_state_path(self) -> str:
        """Path of the persisted trailing-position state file."""
        return os.getenv(
            "STRATEX_TRAILING_STATE_FILE",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "state", "trailing_positions.json"),
        )

    def _trailing_state(self) -> dict:
        """{venue:symbol -> trailing record}, loaded lazily; never raises.

        A record is written at entry time by _execute_signal and carries
        the one quantity the judged trailing rule needs that cannot be
        re-derived from the venue position: atr_entry (the signal bar's
        ATR(14) — the executed sl_dist / exit_sl_atr). The stop path
        itself is a pure function of the closed bars since entry and is
        recomputed on every pass, so the record needs no per-scan
        writes beyond the last computed stop/best (kept for the
        journal). A missing or corrupt file degrades to an empty state:
        affected positions then keep their venue-side initial stop and
        are simply never trail-managed (fail-closed, loudly logged at
        the point the record was written or lost).
        """
        state = getattr(self, "_trailing_positions", None)
        if state is None:
            state = {}
            try:
                with open(self._trailing_state_path(), "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    state = {
                        str(k): v for k, v in raw.items() if isinstance(v, dict)
                    }
            except FileNotFoundError:
                state = {}
            except Exception as e:
                logger.warning(f"[STRATEX] Could not load trailing state: {e}")
                state = {}
            self._trailing_positions = state
        return state

    def _persist_trailing_state(self) -> None:
        """Write the trailing records to STRATEX_TRAILING_STATE_FILE."""
        try:
            path = self._trailing_state_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self._trailing_state(), fh, indent=2)
        except Exception as e:
            logger.debug(f"Trailing state persist failed: {e}")

    def _manage_trailing_exits(self) -> None:
        """Enforce judged trailing-stop exits (TASK-STR-FWD-023).

        For every open position whose strategy's registry entry
        declares exit_mode="trailing" AND which carries a trailing
        state record written at entry, replay the judged rule
        (trailing_stop_path) over the CLOSED bars since the entry bar:
        if a closed bar breached the trailed stop, close at market now.
        Only the market order is sent here — the reconciler books the
        close into the ledgers from userTrades, as for trend/time
        exits, so PnL can never be double counted. The venue-side
        protective order placed at entry stays at the judged INITIAL
        stop for the position's whole life: it is the intrabar/gap
        backstop, while the trailed exit is evaluated on closed bars
        on the scan cadence (the judged simulator's own granularity
        is the bar).

        Fail-closed throughout: a position with no state record
        (opened before this support existed, or state lost), a
        strategy whose declaration was removed, an entry bar outside
        the fetched window, or a record that no longer matches the
        live position is skipped — never guessed at.
        """
        now = time.time()
        if now - getattr(self, "_last_trailing_manage", 0) < 60:
            return
        self._last_trailing_manage = now

        state = self._trailing_state()
        # Prune records whose position the engine no longer tracks
        # (closed by the broker-side stop, the forward guard, or
        # manually): a record must not outlive its position, or a later
        # unrelated position on the same symbol could inherit its trail.
        stale = [k for k in state if k not in self.engine.positions]
        if stale:
            for k in stale:
                state.pop(k, None)
            self._persist_trailing_state()

        for key, pos in list(self.engine.positions.items()):
            venue, _, symbol = key.partition(":")
            if not venue or not symbol:
                continue
            strat = self.engine.position_strategy.get(key, "")
            spec = self._trailing_spec_for_strategy(strat)
            if spec is None:
                continue
            record = state.get(key)
            if record is None:
                # Declared trailing but no entry-time record: the
                # position predates this support (or the record was
                # lost). Its venue-side initial stop still protects it;
                # inventing an atr_entry here would fabricate the
                # judged geometry, so it is left unmanaged.
                continue
            adapter = self.engine.venues.get(venue)
            if adapter is None:
                continue
            try:
                # The record must describe THIS position: a strategy or
                # entry-price mismatch means the position changed under
                # the record (closed and reopened) — drop and skip.
                entry_price = float(record.get("entry_price") or 0)
                if (
                    str(record.get("strategy") or "") != strat
                    or entry_price <= 0
                    or abs(entry_price - float(pos.entry_price))
                    > max(1e-9, entry_price * 1e-6)
                ):
                    logger.warning(
                        f"[STRATEX] Trailing record for {key} does not "
                        f"match the live position; dropping it"
                    )
                    state.pop(key, None)
                    self._persist_trailing_state()
                    continue
                atr_entry = float(record.get("atr_entry") or 0)
                opened_ms = float(record.get("opened_at_ms") or 0)
                if atr_entry <= 0 or opened_ms <= 0:
                    logger.warning(
                        f"[STRATEX] Trailing record for {key} is "
                        f"incomplete; leaving the position to its "
                        f"venue-side stop"
                    )
                    continue
                tf = self.engine.position_timeframe.get(key, "") or str(
                    record.get("timeframe") or ""
                )
                # TASK-STR-FWD-035: normalize — a position opened
                # before the fix may still carry the legacy "1wk".
                bar_seconds = self._BAR_SECONDS.get(_normalize_timeframe_label(tf), 86400)
                age_bars = int((now - opened_ms / 1000.0) // bar_seconds) + 3
                limit = max(60, min(1000, age_bars))
                candles = self.engine.get_candles(venue, symbol, tf, limit)
                if not candles:
                    continue
                # Closed bars only: a bar counts once its full span has
                # elapsed (the trend manager's filter).
                closed = [
                    c
                    for c in candles
                    if float(c.get("timestamp", 0)) + bar_seconds <= now
                ]
                # Entry bar: the bar whose span contains the fill time.
                opened_s = opened_ms / 1000.0
                entry_idx = None
                for idx, c in enumerate(closed):
                    ts = float(c.get("timestamp", 0))
                    if ts <= opened_s < ts + bar_seconds:
                        entry_idx = idx
                        break
                if entry_idx is None:
                    logger.warning(
                        f"[STRATEX] Trailing exit check for {key}: entry "
                        f"bar outside the fetched window; skipping "
                        f"(venue-side stop remains armed)"
                    )
                    continue
                path = trailing_stop_path(
                    pos.side,
                    entry_price,
                    atr_entry,
                    spec["sl_atr"],
                    spec["trail_atr"],
                    closed[entry_idx:],
                )
                if float(record.get("stop") or 0) != path["stop"]:
                    record["stop"] = path["stop"]
                    record["best"] = path["best"]
                    self._persist_trailing_state()
                if path["exit_index"] is None:
                    continue
                is_long = str(pos.side).upper() in ("LONG", "BUY")
                close_side = "SELL" if is_long else "BUY"
                result = adapter.place_order(
                    symbol, close_side, "MARKET", pos.quantity
                )
                if result is None:
                    logger.warning(
                        f"[STRATEX] Trailing exit rejected for {venue}:{symbol}"
                    )
                    continue
                if hasattr(adapter, "cancel_protective_orders"):
                    adapter.cancel_protective_orders(symbol)
                state.pop(key, None)
                self._persist_trailing_state()
                logger.info(
                    f"[STRATEX] Trailing exit {venue}:{symbol} ({pos.side}) "
                    f"strategy={strat} reason={path['exit_reason']} "
                    f"stop={path['stop']:.5f} entry={entry_price:.5f} "
                    f"(TASK-STR-FWD-023 judged TRAIL exit)"
                )
            except Exception as e:
                logger.warning(f"[STRATEX] Trailing exit check failed for {key}: {e}")

    def _strategy_open_risk(
        self, strategy_name: str, venue: Optional[str] = None
    ) -> float:
        """Aggregate stop-risk (USD) of a strategy's open positions.

        Risk per position = qty x |entry - stop|. A position with no
        recorded stop is charged at the daemon's max stop distance on
        its notional — a conservative proxy, since such a position's
        true risk is undefined, never zero. Used by the heat cap
        (TASK-STR-FWD-006).
        """
        total = 0.0
        try:
            positions = getattr(self.engine, "positions", {}) or {}
            attribution = getattr(self.engine, "position_strategy", {}) or {}
            for key, pos in positions.items():
                if attribution.get(key) != strategy_name:
                    continue
                if venue is not None and not str(key).startswith(f"{venue}:"):
                    continue
                qty = abs(float(getattr(pos, "quantity", 0) or 0))
                entry = float(getattr(pos, "entry_price", 0) or 0)
                stop = float(getattr(pos, "stop_loss", 0) or 0)
                if qty <= 0 or entry <= 0:
                    continue
                if stop > 0:
                    total += qty * abs(entry - stop)
                else:
                    total += qty * entry * self.max_stop_pct
        except Exception as e:
            logger.warning(
                f"[STRATEX] Open-risk computation failed for {strategy_name}: {e}"
            )
        return total

    def _open_unrealized_by_strategy(self) -> Dict[str, float]:
        """Current unrealized PnL (USD) grouped by strategy attribution."""
        out: Dict[str, float] = {}
        try:
            positions = getattr(self.engine, "positions", {}) or {}
            attribution = getattr(self.engine, "position_strategy", {}) or {}
            for key, pos in positions.items():
                name = attribution.get(key)
                if not name:
                    continue
                pnl = float(getattr(pos, "unrealized_pnl", 0) or 0)
                if pnl == 0.0:
                    entry = float(getattr(pos, "entry_price", 0) or 0)
                    mark = float(getattr(pos, "mark_price", 0) or 0)
                    qty = float(getattr(pos, "quantity", 0) or 0)
                    if entry > 0 and mark > 0 and qty:
                        sign = (
                            -1.0
                            if str(getattr(pos, "side", "LONG")).upper()
                            in ("SHORT", "SELL")
                            else 1.0
                        )
                        pnl = (mark - entry) * qty * sign
                out[name] = out.get(name, 0.0) + pnl
        except Exception as e:
            logger.warning(f"[STRATEX] Unrealized aggregation failed: {e}")
        return out

    def _sleeve_runner_unrealized(self) -> float:
        """The OANDA sleeve leg's last published unrealized PnL (USD).

        The sleeve runner marks its own book to market every scan and
        publishes the figure into its state file (TASK-STR-FWD-006);
        the sleeve guard below consumes it. A missing field (a
        pre-FWD-006 runner) reads as 0.0 — the closed-fills figure
        then governs, exactly as it did before.
        """
        try:
            state_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "sleeve_oanda", "sleeve_state.json",
            )
            with open(state_path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            return float(state.get("unrealized_pnl_usd", 0.0) or 0.0)
        except Exception:
            return 0.0

    def _maybe_apply_forward_guard(self) -> None:
        """Phase-3 kill criteria over the measurement fill ledger.

        TASK-STR-FWD-006: evaluated on the scan cadence (throttled to
        30s inside this continuous loop; previously once per UTC day
        in the auto-prune slot and never on restart days) and marked
        to market — the drawdown test sees closed fills PLUS each
        book's current unrealized PnL, denominated on venue equity.
        A breached strategy is auto-paused through the persisted
        denylist (survives restarts; the scan loop honours it).
        """
        now = time.time()
        if now - getattr(self, "_last_forward_guard_ts", 0.0) < 30:
            return
        self._last_forward_guard_ts = now
        try:
            from measurement import fill_ledger, forward_guard

            entries = self._forward_protocol_entries()
            if not entries:
                return
            risk = self.engine.get_risk_summary()
            equity = float(risk.get("total_equity") or 0.0)
            rows = fill_ledger.read_fills()
            unrealized = self._open_unrealized_by_strategy()
            # Venue basis: every daemon forward book trades on
            # binance_futures; its DD limit is 5% of THAT account.
            binance_equity = 0.0
            try:
                binance_equity = float(
                    self.engine.get_venue_equity("binance_futures") or 0.0
                )
            except Exception:
                binance_equity = 0.0
            equity_by_strategy = {
                name: (binance_equity if binance_equity > 0 else equity)
                for name in entries
            }
            for decision in forward_guard.evaluate(
                rows,
                equity,
                sorted(entries),
                unrealized_by_strategy=unrealized,
                equity_by_strategy=equity_by_strategy,
            ):
                logger.info(
                    "[STRATEX] Forward guard: "
                    f"{decision['strategy']} trades={decision['trades']} "
                    f"net=${decision['net_pnl']:.2f} "
                    f"unrealized=${decision['unrealized_pnl']:.2f} "
                    f"pf={decision['profit_factor']:.3f} "
                    f"expectancy=${decision['expectancy']:.2f} "
                    f"dd=${decision['max_drawdown_usd']:.2f}/"
                    f"${decision['drawdown_limit_usd']:.2f}"
                )
                if decision["breached"] and decision["strategy"] not in self.strategy_denylist:
                    self.strategy_denylist.add(decision["strategy"])
                    self._persist_denylist()
                    logger.warning(
                        "[STRATEX] PHASE-3 KILL CRITERION — auto-paused "
                        f"{decision['strategy']}: " + "; ".join(decision["reasons"])
                    )
            # Sleeve-level rule (TASK-STR-FWD-002 sleeve extension): a
            # portfolio sleeve is judged on compounded equity + max
            # drawdown ONLY — no per-trade kills for its components.
            # A breach pauses EVERY component: daemon-side components
            # via this denylist; the OANDA sleeve runner via its own
            # pause file (data/sleeve_oanda/sleeve_entries_paused).
            try:
                from config_strategy import PRODUCTION_STRATEGY_REGISTRY

                sleeve_map: Dict[str, list] = {}
                for key, entry in PRODUCTION_STRATEGY_REGISTRY.items():
                    if entry.get("sleeve"):
                        sleeve_map.setdefault(entry["sleeve"], []).append(
                            "strategy_" + key
                        )
                # Sleeve basis (TASK-STR-FWD-006): the combined equity
                # of the venue accounts the sleeve actually trades on
                # (Binance daemon leg + OANDA runner leg), marked to
                # market with BOTH legs' unrealized PnL — the daemon
                # leg from live positions, the OANDA leg from the
                # runner's published state.
                oanda_equity = 0.0
                try:
                    oanda_equity = float(
                        self.engine.get_venue_equity("oanda") or 0.0
                    )
                except Exception:
                    oanda_equity = 0.0
                sleeve_equity = (
                    binance_equity + oanda_equity
                    if binance_equity > 0 and oanda_equity > 0
                    else equity
                )
                sleeve_unrealized: Dict[str, float] = {}
                for comps in sleeve_map.values():
                    for comp in comps:
                        if comp == "strategy_sleeve_tsmom2_dual":
                            sleeve_unrealized[comp] = (
                                self._sleeve_runner_unrealized()
                            )
                        else:
                            sleeve_unrealized[comp] = unrealized.get(comp, 0.0)
                for sd in forward_guard.evaluate_sleeves(
                    rows,
                    sleeve_equity,
                    sleeve_map,
                    unrealized_by_component=sleeve_unrealized,
                ):
                    logger.info(
                        "[STRATEX] Sleeve guard: "
                        f"{sd['sleeve']} components={sd['components']} "
                        f"trades={sd['trades']} net=${sd['net_pnl']:.2f} "
                        f"unrealized=${sd['unrealized_pnl']:.2f} "
                        f"dd=${sd['max_drawdown_usd']:.2f}/"
                        f"${sd['drawdown_limit_usd']:.2f} breached={sd['breached']}"
                    )
                    if not sd["breached"]:
                        continue
                    changed = False
                    for comp in sd["components"]:
                        if comp not in self.strategy_denylist:
                            self.strategy_denylist.add(comp)
                            changed = True
                    if changed:
                        self._persist_denylist()
                    try:
                        pause_dir = os.path.join(
                            os.path.dirname(os.path.dirname(__file__)),
                            "data", "sleeve_oanda",
                        )
                        os.makedirs(pause_dir, exist_ok=True)
                        with open(
                            os.path.join(pause_dir, "sleeve_entries_paused"),
                            "w", encoding="utf-8",
                        ) as fh:
                            fh.write(
                                "TASK-STR-FWD-002 sleeve guard: "
                                + "; ".join(sd["reasons"])
                            )
                    except Exception as pe:
                        logger.warning(f"[STRATEX] Sleeve pause-file write failed: {pe}")
                    logger.warning(
                        "[STRATEX] SLEEVE KILL RULE — auto-paused sleeve "
                        f"{sd['sleeve']}: " + "; ".join(sd["reasons"])
                    )
            except Exception as se:
                logger.warning(f"[STRATEX] Sleeve guard evaluation failed: {se}")
        except Exception as e:
            logger.warning(f"[STRATEX] Forward guard evaluation failed: {e}")

    def _prefetch_candles(self):
        """Pre-fetch candles for all symbols/timeframes."""
        try:
            pairs = []
            for venue, symbols in self.symbols.items():
                for symbol in symbols:
                    for tf in self.timeframes:
                        # 1w is derived at scan time from daily bars;
                        # never fetched — native venue weekly klines are
                        # Monday-anchored, not the judged buckets.
                        if tf == SLEEVE_TIMEFRAME:
                            continue
                        pairs.append((venue, symbol, tf))

            # The cloud feed caches automatically, just prime it
            for venue, symbol, tf in pairs[:20]:  # Limit to avoid rate limits
                try:
                    # Same limits as the scan loop (TASK-STR-FWD-002).
                    self.engine.get_candles(venue, symbol, tf, 300 if tf == "1d" else 600 if tf == "4h" else 100)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Prefetch error: {e}")

    def _candles_to_df(self, candles: list) -> "object | None":
        """Convert candle list to a pandas DataFrame (None when pandas is unavailable)."""
        try:
            import pandas as pd
            df = pd.DataFrame(candles)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception:
            return None

    def _calc_adx(self, highs: list, lows: list, closes: list, period: int = 14) -> float | None:
        """Calculate ADX (Average Directional Index) for trend strength."""
        try:
            n = len(closes)
            if n < period + 2:
                return None

            # True Range
            tr = []
            plus_dm = []
            minus_dm = []
            for i in range(1, n):
                high_diff = highs[i] - highs[i-1]
                low_diff = lows[i-1] - lows[i]
                tr_val = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1]),
                )
                tr.append(tr_val)

                # +DM: high up move greater than low down move
                if high_diff > low_diff and high_diff > 0:
                    plus_dm.append(high_diff)
                else:
                    plus_dm.append(0.0)

                # -DM: low down move greater than high up move
                if low_diff > high_diff and low_diff > 0:
                    minus_dm.append(low_diff)
                else:
                    minus_dm.append(0.0)

            # Wilder smoothing
            def wilder_smooth(values, period):
                if len(values) < period:
                    return None
                smoothed = [sum(values[:period])]
                for i in range(period, len(values)):
                    smoothed.append(smoothed[-1] - smoothed[-1] / period + values[i])
                return smoothed

            tr_smooth = wilder_smooth(tr, period)
            plus_smooth = wilder_smooth(plus_dm, period)
            minus_smooth = wilder_smooth(minus_dm, period)

            if tr_smooth is None or plus_smooth is None or minus_smooth is None:
                return None
            if len(tr_smooth) < 2:
                return None

            # +DI and -DI
            plus_di = [100 * p / t if t > 0 else 0 for p, t in zip(plus_smooth, tr_smooth)]
            minus_di = [100 * m / t if t > 0 else 0 for m, t in zip(minus_smooth, tr_smooth)]

            # DX
            dx = []
            for pdi, mdi in zip(plus_di, minus_di):
                denom = pdi + mdi
                dx.append(100 * abs(pdi - mdi) / denom if denom > 0 else 0)

            # ADX = smoothed DX
            adx_values = wilder_smooth(dx, period)
            if adx_values is None or len(adx_values) == 0:
                return None

            return adx_values[-1]
        except Exception:
            return None

    def _execute_signal(self, venue: str, symbol: str, signal: dict, timeframe: str) -> bool:
        """Execute a trading signal on the venue."""
        try:
            # Cross-process safety controls: the Telegram bot and the control API
            # write flags in separate processes, so the daemon must read them
            # from disk or /pause and /halt would be decorative.
            try:
                from trading_pause import is_trading_paused

                if is_trading_paused():
                    logger.info(f"[STRATEX] Entries paused; {symbol} signal ignored")
                    return False
            except Exception as e:
                # TASK-STR-RISK-001: fail CLOSED. trading_pause itself fails
                # closed on a corrupt flag; a read that raises must not
                # silently wave entries through — that made /pause and
                # /halt decorative exactly when state was broken.
                logger.error(f"[STRATEX] Pause-state read failed ({e}); failing CLOSED, entry refused")
                return False

            try:
                from panic_state import is_panic_active, is_kill_switch_locked

                if is_panic_active() or is_kill_switch_locked():
                    logger.info(f"[STRATEX] Panic/kill-switch active; {symbol} signal ignored")
                    return False
            except Exception as e:
                # TASK-STR-RISK-001: fail CLOSED, same reasoning as the
                # pause gate above — panic_state fails closed on corrupt
                # files; an unreadable panic state must block, not pass.
                logger.error(f"[STRATEX] Panic-state read failed ({e}); failing CLOSED, entry refused")
                return False

            # Check position limits + free-margin floor (restored gates; the
            # exchange-side rejection loop this replaces produced ~2,000
            # failed orders/day when fully margined).
            can_open, reason = self.engine.can_open_position(venue)
            if not can_open:
                logger.debug(f"Cannot open position on {venue}: {reason}")
                return False

            # Anti-pyramiding: one position per symbol. Without this gate the
            # same signal re-fired every 15s scan and stacked entries (live:
            # NEARUSDT 991 fills in 2 days, 128k units accumulated).
            if self.engine.has_open_position(venue, symbol):
                logger.debug(f"[STRATEX] {venue}:{symbol} already has a position; no adds")
                return False

            # Re-entry cooldown: a symbol that just stopped out is
            # quarantined (default 900s). The engine recorded exits but
            # nothing read them, so the daemon instantly re-entered.
            if self.engine.symbol_in_cooldown(venue, symbol):
                logger.info(f"[STRATEX] {venue}:{symbol} in re-entry cooldown; skipping")
                return False

            # Get current price for sizing
            ticker = self.engine.get_ticker(venue, symbol)
            if not ticker or ticker.last <= 0:
                return False

            current_price = ticker.last
            side = signal["side"]
            stop_loss = signal.get("stop_loss", signal.get("sl", 0))
            take_profit = signal.get("take_profit", signal.get("tp", 0))

            # TASK-STR-FWD-023: a strategy whose registry entry declares
            # the judged trailing exit (exit_mode="trailing") has NO
            # fixed take-profit by construction — its module returns
            # tp_dist=None and rr_ratio=None. For such entries ONLY, the
            # TP-dependent preconditions below are replaced by the
            # trailing contract: a judged sl_dist must be present, the
            # stop is re-anchored from it alone, the order is placed
            # with the initial stop and no TP, and the daemon manages
            # the trailed exit on closed bars (_manage_trailing_exits).
            # Every other strategy keeps the fixed-bracket path exactly
            # as before — tp_dist=None without the declaration still
            # cannot trade (fail-closed).
            trailing_spec = self._trailing_spec_for_strategy(
                signal.get("strategy") or signal.get("strategy_name") or ""
            )

            # Re-anchor stops to the live entry price when the strategy supplies
            # distances. The backtest entered at the next bar's open, but the
            # daemon can fire hours later; re-anchoring keeps the tested risk
            # geometry (e.g. 2.5xATR) instead of a stale signal-bar level.
            sl_dist = signal.get("sl_dist")
            tp_dist = signal.get("tp_dist")
            if sl_dist and (tp_dist or trailing_spec is not None):
                sign = 1 if str(side).upper() in ("BUY", "LONG") else -1
                try:
                    stop_loss = current_price - sign * float(sl_dist)
                    if tp_dist:
                        take_profit = current_price + sign * float(tp_dist)
                except (TypeError, ValueError):
                    pass

            if trailing_spec is not None:
                # The declaration governs: there is no fixed target to
                # anchor to — the exit is the trailed stop, managed
                # daemon-side after entry. Any tp the module supplied
                # is disregarded so the venue order carries SL only.
                take_profit = None

            if stop_loss <= 0 or (
                trailing_spec is None and (take_profit is None or take_profit <= 0)
            ):
                return False

            # A stop tighter than the min distance means taker fees eat a large
            # share of every R. At 0.8% stop the round-trip is ~0.10R; at the
            # 0.23% stops the backtest saw it was ~0.35R, more than the edge.
            stop_pct = abs(current_price - stop_loss) / current_price
            if stop_pct < self.min_stop_pct:
                logger.info(
                    f"[STRATEX] Skip {symbol}: stop {stop_pct*100:.2f}% "
                    f"< min {self.min_stop_pct*100:.2f}% (fee drag)"
                )
                return False

            # Max stop cap: never risk more than the cap on a single trade.
            # TASK-STR-FWD-012: a strategy whose registry entry declares
            # max_stop_pct is judged against that override (see
            # _max_stop_pct_for_strategy); every other strategy keeps the
            # engine-global cap. The skip line names the strategy so a
            # block is attributable from the journal alone.
            cap_strat = signal.get("strategy") or signal.get("strategy_name") or ""
            max_stop = self._max_stop_pct_for_strategy(cap_strat)
            if max_stop is None:
                max_stop = self.max_stop_pct
            if stop_pct > max_stop:
                logger.info(
                    f"[STRATEX] Skip {symbol}: {cap_strat or 'unknown'} stop "
                    f"{stop_pct*100:.2f}% > max {max_stop*100:.2f}% (risk too large)"
                )
                return False

            # Direction sanity: an inverted SL/TP pair must never reach the venue.
            side_up = str(side).upper() in ("BUY", "LONG")
            if trailing_spec is not None:
                # TASK-STR-FWD-023: only the stop side can be checked —
                # a trailing entry has no fixed target to bracket the
                # price against.
                if side_up and not (stop_loss < current_price):
                    logger.warning(f"[STRATEX] Skip {symbol}: invalid BUY trailing stop geometry")
                    return False
                if not side_up and not (stop_loss > current_price):
                    logger.warning(f"[STRATEX] Skip {symbol}: invalid SELL trailing stop geometry")
                    return False
            else:
                if side_up and not (stop_loss < current_price < take_profit):
                    logger.warning(f"[STRATEX] Skip {symbol}: invalid BUY SL/TP geometry")
                    return False
                if not side_up and not (take_profit < current_price < stop_loss):
                    logger.warning(f"[STRATEX] Skip {symbol}: invalid SELL SL/TP geometry")
                    return False

            # Net expectancy gate. Declared R:R alone is not evidence: the
            # backtest showed 0.78-win-rate strategies losing money after fees.
            strategy_name = signal.get("strategy") or signal.get("strategy_name") or ""
            win_rate = self.strategy_priors.get(strategy_name)
            if win_rate is None:
                win_rate = signal.get("win_rate_prior")
            if win_rate is None:
                win_rate = signal.get("confidence")
            try:
                win_rate = float(win_rate or 0)
            except (TypeError, ValueError):
                win_rate = 0.0

            if win_rate <= 0:
                logger.info(
                    f"[STRATEX] Skip {symbol}: {strategy_name or 'unknown'} has "
                    f"no measured win-rate"
                )
                return False

            # ADX trend filter: only trade trending markets (ADX > threshold).
            # Skip choppy/rangebound markets where breakout strategies fail.
            try:
                candles = self.engine.get_candles(venue, symbol, timeframe, 30)
                if candles and len(candles) >= 30:
                    closes = [float(c["close"]) for c in candles]
                    highs = [float(c["high"]) for c in candles]
                    lows = [float(c["low"]) for c in candles]
                    adx = self._calc_adx(highs, lows, closes, 14)
                    if adx is not None and adx < self.adx_threshold:
                        logger.info(
                            f"[STRATEX] Skip {symbol}: ADX {adx:.1f} < "
                            f"{self.adx_threshold} (choppy market, no trend)"
                        )
                        return False
            except Exception as e:
                logger.debug(f"[STRATEX] ADX calc failed for {symbol}: {e}")

            if trailing_spec is not None:
                # TASK-STR-FWD-023: no fixed target exists, so the R:R
                # expectancy gate and the TP fee floor have nothing to
                # price — any R:R imputed to a trailing exit would be an
                # invented parameter. The judged OOS expectancy is
                # recorded on the registry entry, the win-rate presence
                # check above still applies, and the phase-3 forward
                # guard enforces REALIZED expectancy (kill at
                # expectancy<0 or PF<1.0 after >=50 closes) on the scan
                # cadence — the governor every FORWARD_TEST lane entry
                # answers to.
                logger.info(
                    f"[STRATEX] {symbol}: {strategy_name} trailing exit — "
                    f"R:R expectancy gate not applicable (no fixed target)"
                )
            else:
                target_pct = abs(take_profit - current_price) / current_price
                rr_actual = target_pct / stop_pct if stop_pct > 0 else 0.0
                # Full round-trip friction (fees + spread/slippage), per the
                # RD-002 judged cost model — see __init__ (TASK-STR-RD-010).
                # The getattr fallback keeps manually-constructed engines
                # (tests) on the legacy fees-only rate.
                friction_rate = getattr(
                    self, "friction_rate_roundtrip", None
                ) or self.fee_rate_roundtrip
                fee_r = friction_rate / stop_pct
                expectancy_r = win_rate * rr_actual - (1.0 - win_rate) - fee_r

                # Reward-side fee floor: the stop side already refuses sub-0.5%
                # stops, but a TP narrower than the round-trip fee means even a
                # WINNER nets negative (live: TP hits paying +$0.02 against $0.60
                # fees). The take-profit must clear the fee by the same margin.
                if target_pct < self.min_stop_pct:
                    logger.info(
                        f"[STRATEX] Skip {symbol}: TP {target_pct*100:.2f}% "
                        f"< min {self.min_stop_pct*100:.2f}% (fee floor)"
                    )
                    return False

                if expectancy_r < self.min_expectancy_r:
                    logger.info(
                        f"[STRATEX] Skip {symbol}: {strategy_name} expectancy "
                        f"{expectancy_r:+.3f}R < {self.min_expectancy_r:+.3f}R "
                        f"(p={win_rate:.2f} rr={rr_actual:.2f} fee={fee_r:.2f}R)"
                    )
                    return False

            # Calculate position size based on risk.
            # TASK-STR-FWD-006: sizing is denominated on the equity of
            # the VENUE account this trade will sit on — never the
            # composite cross-venue total (the pre-fix daemon sized a
            # Binance trade off Binance+OANDA equity combined, doubling
            # its true per-trade risk). A venue whose equity cannot be
            # measured does not get entries (fail-closed, consistent
            # with the engine's venue-health accounting).
            equity = 0.0
            try:
                equity = float(self.engine.get_venue_equity(venue) or 0)
            except Exception:
                equity = 0.0
            if equity <= 0:
                logger.warning(
                    f"[STRATEX] Venue equity unavailable for {venue} "
                    f"({equity}); skipping {symbol}"
                )
                return False

            risk_amount = equity * self.risk_per_trade
            # Aggregate heat cap (TASK-STR-FWD-006): this strategy's
            # already-open stop-risk plus the new trade's risk may not
            # exceed max_heat_pct of venue equity. The new trade is
            # resized down to the remaining budget; a strategy already
            # at the cap opens nothing new.
            open_risk = self._strategy_open_risk(strategy_name, venue)
            capped = heat_capped_risk_amount(
                equity, self.risk_per_trade, open_risk, self.max_heat_pct
            )
            if capped <= 0:
                logger.info(
                    f"[STRATEX] Skip {symbol}: {strategy_name} heat cap — "
                    f"open risk ${open_risk:,.2f} already at "
                    f"{self.max_heat_pct * 100:.1f}% of venue equity "
                    f"(${equity * self.max_heat_pct:,.2f})"
                )
                return False
            if capped < risk_amount:
                logger.info(
                    f"[STRATEX] Heat cap resizes {symbol} "
                    f"({strategy_name}): risk ${risk_amount:,.2f} -> "
                    f"${capped:,.2f} (open risk ${open_risk:,.2f} of "
                    f"${equity * self.max_heat_pct:,.2f} cap)"
                )
                risk_amount = capped
            risk_per_unit = abs(current_price - stop_loss)
            if risk_per_unit <= 0:
                logger.warning(f"[STRATEX] Invalid stop distance for {symbol}")
                return False

            position_size = risk_amount / risk_per_unit

            # Hard exposure cap: one position may never exceed max_position_pct of
            # VENUE equity in notional terms (TASK-STR-FWD-006 basis).
            # Without this a tight stop produces an enormous size (risk
            # $10 with a 0.5% stop on BTC = $2,000 notional).
            max_notional = equity * self.max_position_pct
            if current_price > 0:
                position_size = min(position_size, max_notional / current_price)

            if venue == "binance_futures":
                adapter = self.engine.venues.get("binance_futures")
                if adapter:
                    position_size = adapter.round_quantity(symbol, position_size)
                    min_notional = adapter.min_notional(symbol)
                    notional = position_size * current_price
                    if min_notional > 0 and notional < min_notional:
                        bumped = adapter.round_quantity(
                            symbol, (min_notional / current_price) * 1.01
                        )
                        # The bump must respect BOTH caps: the notional
                        # cap and the (possibly heat-capped) risk budget.
                        if (
                            bumped * current_price <= max_notional
                            and bumped * risk_per_unit <= risk_amount + 1e-9
                        ):
                            position_size = bumped
                        else:
                            logger.info(
                                f"[STRATEX] Skip {symbol}: venue min notional "
                                f"{min_notional:.2f} cannot be met within the "
                                f"exposure cap {max_notional:.2f} and risk "
                                f"budget {risk_amount:.2f}"
                            )
                            return False
                if position_size <= 0:
                    return False
            elif venue == "oanda":
                units = max(1, round(position_size))
                notional = units * current_price
                if notional > max_notional:
                    logger.info(
                        f"[STRATEX] Skip {symbol}: minimum OANDA unit notional "
                        f"${notional:,.2f} > exposure cap ${max_notional:,.2f}"
                    )
                    return False
                position_size = units

            # Margin sanity: only send the order if the venue's free margin
            # covers the notional with headroom. This kills the
            # "Margin is insufficient" rejection loop at the source.
            free_margin = self.engine.get_free_margin(venue)
            est_notional = position_size * current_price
            if free_margin > 0 and est_notional > free_margin * 0.8:
                logger.info(
                    f"[STRATEX] Skip {symbol}: notional {est_notional:,.0f} "
                    f"> 80% of free margin {free_margin:,.0f}"
                )
                return False

            # Execute
            result = self.engine.place_order(
                venue=venue,
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_name=strategy_name,
                timeframe=timeframe,
            )

            if result is None:
                return False
            if result.status == "FILLED":
                if trailing_spec is not None:
                    # TASK-STR-FWD-023: record the trailing state the
                    # exit manager needs. atr_entry is the signal bar's
                    # ATR(14), recovered from the executed stop distance
                    # (sl_dist = exit_sl_atr x atr_entry by the judged
                    # geometry). The position is open and protected by
                    # its venue-side initial stop either way; if the
                    # record cannot be written the trailing manager
                    # will (fail-closed) leave it to that stop — loudly,
                    # never silently.
                    try:
                        fill_price = float(result.avg_price or current_price)
                        state = self._trailing_state()
                        state[f"{venue}:{symbol}"] = {
                            "strategy": strategy_name,
                            "timeframe": timeframe,
                            "side": "LONG" if side_up else "SHORT",
                            "entry_price": fill_price,
                            "atr_entry": float(sl_dist) / trailing_spec["sl_atr"],
                            "opened_at_ms": int(time.time() * 1000),
                            "stop": float(stop_loss),
                            "best": fill_price,
                        }
                        self._persist_trailing_state()
                    except Exception as e:
                        logger.warning(
                            f"[STRATEX] Trailing state record failed for "
                            f"{venue}:{symbol}: {e}"
                        )
                return True
            # A PENDING order is not tracked by the engine, so counting it as
            # executed would orphan its SL/TP and lose the PnL attribution.
            logger.warning(
                f"[STRATEX] Order for {symbol} ended {result.status}; not tracked"
            )
            return False

        except Exception as e:
            logger.error(f"Execution error: {e}")
            return False

    def _maybe_prune_strategies(self) -> None:
        """Move strategies with negative expectancy to denylist."""
        try:
            from trading_report import metrics
            stats = metrics()  # reads testnet_trade_ledger.jsonl
            # TASK-STR-FWD-002: forward-protocol strategies are governed by
            # the phase-3 kill criteria (>=50 closed trades), not by this
            # legacy >=10-trade pruner over the retired testnet ledger.
            # Sleeve components are likewise governed ONLY by the
            # sleeve-level drawdown rule, never by per-trade pruning.
            forward_names = set(self._forward_protocol_entries())
            try:
                from config_strategy import PRODUCTION_STRATEGY_REGISTRY

                forward_names |= {
                    "strategy_" + key
                    for key, entry in PRODUCTION_STRATEGY_REGISTRY.items()
                    if entry.get("sleeve")
                }
            except Exception:
                pass
            for strat, bucket in stats.get("by_strategy", {}).items():
                if strat in forward_names:
                    continue
                if bucket.get("trades", 0) >= 10 and bucket.get("net_pnl", 0) < 0:
                    # Negative expectancy after 10+ trades -> denylist
                    if strat not in self.strategy_denylist:
                        self.strategy_denylist.add(strat)
                        logger.warning(
                            f"[STRATEX] Auto-pruned losing strategy: {strat} "
                            f"(trades={bucket['trades']}, net=${bucket['net_pnl']:.2f})"
                        )
                        # Persist denylist
                        self._persist_denylist()
        except Exception as e:
            logger.debug(f"Strategy pruning failed: {e}")

    def _denylist_path(self) -> str:
        """Path of the persisted strategy denylist (single source for the
        writer in _persist_denylist and the reader in _load_denylist)."""
        return os.getenv(
            "STRATEX_STRATEGY_DENYLIST_FILE",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "state", "strategy_denylist.json"),
        )

    def _load_denylist(self) -> set:
        """Read back the persisted denylist so pruned strategies stay pruned.

        Never raises: a missing file means nothing was ever pruned; a
        corrupt file degrades to an empty set with a loud warning (the
        governance gate in the scan loop still applies independently).
        """
        path = self._denylist_path()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            return set()
        except Exception as e:
            logger.warning(f"[STRATEX] Could not load strategy denylist {path}: {e}")
            return set()
        names = {str(x) for x in raw if isinstance(x, str)} if isinstance(raw, list) else set()
        if names:
            logger.warning(
                f"[STRATEX] Strategy denylist loaded from {path}: {sorted(names)}"
            )
        return names

    def _persist_denylist(self) -> None:
        """Write current denylist to STRATEX_STRATEGY_DENYLIST_FILE."""
        try:
            path = self._denylist_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(sorted(self.strategy_denylist), fh, indent=2)
        except Exception as e:
            logger.debug(f"Denylist persist failed: {e}")

    # ------------------------------------------------------------------
    # Daemon heartbeat (consumed by dashboard /health, FRIDAY's
    # stratex_watch snapshot gate and the forward scorecard).
    # TASK-STR-FWD-015: during run() the scan loop only PUBLISHES an
    # in-memory snapshot; a pulse thread is the file's sole writer,
    # republishing that snapshot every heartbeat_pulse_seconds so
    # file freshness means "process alive" even when a scan cycle
    # runs for minutes under host memory pressure.
    # ------------------------------------------------------------------
    def _daemon_heartbeat_path(self) -> str:
        """Path of the daemon heartbeat file (Stratex/state/daemon_heartbeat.json).

        Uses the same state-dir convention as MultiVenueEngine._state_path so
        the writer here and the reader in dashboard.py always agree.
        """
        override = os.getenv("STRATEX_STATE_DIR")
        base = override if override else os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state"
        )
        return os.path.join(base, "daemon_heartbeat.json")

    @staticmethod
    def _heartbeat_pulse_seconds_from_env() -> float:
        """Pulse cadence for the heartbeat thread (TASK-STR-FWD-015).

        Default 15s: worst-case heartbeat age stays far under the
        60s freshness bound consumers enforce (FRIDAY's snapshot
        gate, Stratex's own MAX_TELEMETRY_STALENESS_SECONDS).
        """
        try:
            value = float(os.getenv("STRATEX_HEARTBEAT_PULSE_SECONDS", "15"))
        except (TypeError, ValueError):
            return 15.0
        return value if value > 0 else 15.0

    def _heartbeat_state(self):
        """Return the heartbeat lock, lazily creating the pulse state.

        __init__ creates the same attributes; the lazy path exists
        for engines constructed without __init__ (unit tests build
        the engine with __new__). Only the main thread touches this
        state before the pulse thread starts, so the lazy creation
        cannot race in practice.
        """
        lock = getattr(self, "_heartbeat_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._heartbeat_lock = lock
            self._heartbeat_write_lock = threading.Lock()
            self._heartbeat_snapshot = None
            self._heartbeat_wake = threading.Event()
            self._heartbeat_stop = threading.Event()
            self._heartbeat_thread = None
            if getattr(self, "heartbeat_pulse_seconds", None) is None:
                self.heartbeat_pulse_seconds = self._heartbeat_pulse_seconds_from_env()
        return lock

    def _build_daemon_heartbeat_payload(self, results=None, error=None, status="RUNNING"):
        """Build the heartbeat payload from the daemon's current state.

        Returns None (and publishes nothing) when the state cannot
        be read. A RUNNING build stamps last_strategy_evaluation
        with the build time: builds happen at scan-cycle boundaries
        (or at startup), where an evaluation has just completed.
        The pulse thread never rebuilds — it republishes the stored
        payload — so the evaluation stamp can never be refreshed
        without a real cycle behind it.
        """
        try:
            now_iso = datetime.datetime.utcnow().isoformat() + "Z"
            if status == "RUNNING":
                self._last_evaluation_iso = now_iso
            risk = getattr(self, "_last_risk_summary", None) or {}
            # TASK-STR-PHASE2-001: surface the breaker baseline, venue
            # alerts and active measurement alerts so health checks can
            # prove the breaker is armed and totals are venue-gated.
            measurement_alerts = []
            try:
                from measurement import fill_ledger as _fl

                measurement_alerts = sorted(_fl.active_alerts().keys())
            except Exception:
                measurement_alerts = []
            payload = {
                "status": status,
                "pid": os.getpid(),
                "timestamp": now_iso,
                "updated_at": time.time(),
                "scan_count": self.scan_count,
                "scan_interval_seconds": self.scan_interval,
                "last_strategy_evaluation": getattr(self, "_last_evaluation_iso", None),
                "last_cycle": results,
                "total_balance": risk.get("total_balance"),
                "total_equity": risk.get("total_equity"),
                "unrealized_pnl": risk.get("unrealized_pnl"),
                "realized_pnl": risk.get("realized_pnl"),
                "open_positions": risk.get("positions"),
                "daily_loss_limit_hit": risk.get("daily_loss_limit_hit"),
                "daily_start_equity": risk.get("daily_start_equity"),
                "venue_alerts": risk.get("venue_alerts"),
                "measurement_alerts": measurement_alerts,
                "venues": sorted(self.engine.venues.keys())
                if getattr(self.engine, "venues", None)
                else [],
            }
            if error is not None:
                payload["last_error"] = str(error)[:500]
            return payload
        except Exception as e:
            logger.debug(f"Daemon heartbeat build failed: {e}")
            return None

    def _write_heartbeat_payload(self, payload) -> bool:
        """Atomically write a heartbeat payload; return success.

        The single funnel for every daemon_heartbeat.json write,
        serialised by the write lock so the tmp + os.replace
        sequence can never interleave between writers.
        """
        self._heartbeat_state()
        write_lock = getattr(self, "_heartbeat_write_lock", None)
        if write_lock is None:
            write_lock = self._heartbeat_write_lock = threading.Lock()
        try:
            with write_lock:
                path = self._daemon_heartbeat_path()
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2)
                os.replace(tmp, path)
            return True
        except Exception as e:
            # Warning, not debug: a heartbeat that cannot be written
            # goes stale silently otherwise — staleness consumers
            # cannot distinguish from a dead daemon is the failure
            # mode TASK-STR-FWD-015 exists to remove.
            logger.warning(f"Daemon heartbeat write failed: {e}")
            return False

    def _store_heartbeat_snapshot(self, payload) -> None:
        """Store a payload as the pulse thread's republish source."""
        lock = self._heartbeat_state()
        with lock:
            self._heartbeat_snapshot = copy.deepcopy(payload)

    def _write_daemon_heartbeat(self, results=None, error=None, status="RUNNING"):
        """Atomically rewrite the daemon heartbeat. Never raises.

        The dashboard's /health used to infer this daemon's state from
        state/cloud_portfolio_state.json, a file only the MT5 cTrader engine
        writes (on trade events). This daemon never writes it, so a live,
        evaluating daemon reported ``engine: offline`` for 12 days. The
        heartbeat is written every scan cycle, so its freshness is direct
        evidence that the loop is turning.

        TASK-STR-FWD-015: this synchronous build + store + write is
        retained for direct callers (tests, one-shot uses). The
        running daemon instead publishes snapshots via
        _publish_daemon_heartbeat and lets the pulse thread write.
        """
        payload = self._build_daemon_heartbeat_payload(
            results=results, error=error, status=status
        )
        if payload is None:
            return
        self._store_heartbeat_snapshot(payload)
        self._write_heartbeat_payload(payload)

    def _publish_daemon_heartbeat(self, results=None, error=None, status="RUNNING"):
        """Publish the daemon's latest state for the pulse thread.

        Used by run(): the scan loop never writes the heartbeat file
        itself — it stores the snapshot under the heartbeat lock and
        wakes the pulse thread, which flushes promptly and then
        keeps the file fresh on its own cadence.
        """
        payload = self._build_daemon_heartbeat_payload(
            results=results, error=error, status=status
        )
        if payload is None:
            return
        self._store_heartbeat_snapshot(payload)
        self._heartbeat_state()
        self._heartbeat_wake.set()

    def _flush_heartbeat_snapshot(self) -> bool:
        """Write the latest published snapshot with a fresh pulse.

        Only the pulse fields (timestamp / updated_at) advance;
        every cycle field — scan_count, last_cycle,
        last_strategy_evaluation, the risk figures, the alerts —
        is republished verbatim from the last published snapshot,
        so a fresh file never claims a fresher cycle than the one
        that actually ran. Returns False when nothing has been
        published yet: no payload is invented.
        """
        lock = self._heartbeat_state()
        with lock:
            snapshot = copy.deepcopy(self._heartbeat_snapshot)
        if snapshot is None:
            return False
        now = time.time()
        snapshot["timestamp"] = datetime.datetime.utcfromtimestamp(now).isoformat() + "Z"
        snapshot["updated_at"] = now
        return self._write_heartbeat_payload(snapshot)

    def _heartbeat_pulse_loop(self):
        """Pulse-thread body: keep daemon_heartbeat.json fresh.

        Wakes when a snapshot is published (prompt flush), when a
        stop is requested (final flush of the STOPPED snapshot), or
        every heartbeat_pulse_seconds. If the loop itself dies, the
        error is logged loudly and the thread exits — it is never
        silently restarted, so the file going stale remains
        detectable by consumers exactly as before this task.
        """
        try:
            interval = getattr(self, "heartbeat_pulse_seconds", None)
            if not interval or interval <= 0:
                interval = self._heartbeat_pulse_seconds_from_env()
            while True:
                self._heartbeat_wake.wait(interval)
                self._heartbeat_wake.clear()
                self._flush_heartbeat_snapshot()
                if self._heartbeat_stop.is_set():
                    break
        except Exception:
            logger.error(
                "[STRATEX] Heartbeat pulse thread died; "
                "daemon_heartbeat.json will go stale until the daemon restarts",
                exc_info=True,
            )

    def _start_heartbeat_pulse(self):
        """Start the heartbeat pulse thread (idempotent)."""
        self._heartbeat_state()
        thread = getattr(self, "_heartbeat_thread", None)
        if thread is not None and thread.is_alive():
            return
        self._heartbeat_stop.clear()
        thread = threading.Thread(
            target=self._heartbeat_pulse_loop,
            name="stratex-heartbeat-pulse",
            daemon=True,
        )
        self._heartbeat_thread = thread
        thread.start()

    def _stop_heartbeat_pulse(self):
        """Stop the pulse thread after a final snapshot flush.

        run() publishes the STOPPED snapshot first; the pulse
        thread flushes it before exiting and is joined here. If the
        thread cannot stop in time, the final snapshot is flushed
        from the calling thread instead, so the STOPPED write is
        never lost.
        """
        self._heartbeat_state()
        thread = getattr(self, "_heartbeat_thread", None)
        if thread is None:
            return
        self._heartbeat_stop.set()
        self._heartbeat_wake.set()
        thread.join(timeout=5.0)
        if thread.is_alive():
            logger.warning(
                "[STRATEX] Heartbeat pulse thread did not stop within 5s; "
                "flushing the final heartbeat from the main thread"
            )
            self._flush_heartbeat_snapshot()

    # -- TASK-STR-EXP-004: self-experiment loop wiring -----------------
    #
    # EXP-001 shipped the loop (self_experiments/loop.py) with
    # start_if_enabled() deliberately NOT hooked into the daemon
    # lifespan; its design doc names this activation step: wire the
    # driver with the daemon-activity probe. The hook is inert unless
    # STRATEX_SELF_EXPERIMENTS is exactly "on": the check in
    # _start_self_experiments runs before any self_experiments
    # import, so with the switch unset or any other value nothing is
    # imported, no thread starts and no loop file is written — the
    # daemon's behaviour is the pre-activation behaviour, unchanged.

    def _daemon_idle_probe(self) -> bool:
        """The daemon-activity probe for the self-experiment loop:
        True when the daemon is between scan cycles, False while a
        scan is executing. The loop consults it every cycle (on top
        of its host-load gate) so experiments only run in the
        daemon's idle windows."""
        return not self._scan_in_progress

    def _start_self_experiments(self) -> None:
        """Start the self-experiment loop if the kill switch is on.

        Never raises: a wiring failure (e.g. the production stream
        store not built yet) is logged loudly and the daemon keeps
        trading — the loop is an addition, never a dependency."""
        if os.getenv("STRATEX_SELF_EXPERIMENTS", "off").strip().lower() != "on":
            return
        try:
            from self_experiments import daemon_wiring

            self._selfexp_handle = daemon_wiring.start(
                work_probe=self._daemon_idle_probe
            )
            if self._selfexp_handle is not None:
                logger.info(
                    "[STRATEX] Self-experiment loop wired in "
                    "(STRATEX_SELF_EXPERIMENTS=on)"
                )
        except Exception:
            logger.error(
                "[STRATEX] Self-experiment wiring failed; "
                "daemon continues without it",
                exc_info=True,
            )

    def _stop_self_experiments(self) -> None:
        """Stop the self-experiment loop if it was wired in."""
        handle = getattr(self, "_selfexp_handle", None)
        if handle is None:
            return
        self._selfexp_handle = None
        try:
            handle.stop()
        except Exception:
            logger.error(
                "[STRATEX] Self-experiment loop stop failed",
                exc_info=True,
            )

    def run(self):
        """Main trading loop."""
        logger.info(f"[STRATEX] Trading engine started - scanning every {self.scan_interval}s")

        # TASK-STR-FWD-015: the pulse thread owns heartbeat writes
        # from here on; the loop below only publishes snapshots.
        self._start_heartbeat_pulse()

        # TASK-STR-EXP-004: wire the self-experiment loop into the
        # lifespan (inert unless STRATEX_SELF_EXPERIMENTS is "on").
        self._start_self_experiments()

        # Startup heartbeat: the daemon is alive from here on, even before
        # the first (slowest) scan cycle completes.
        try:
            self._last_risk_summary = self.engine.get_risk_summary()
        except Exception:
            self._last_risk_summary = None
        self._publish_daemon_heartbeat()

        while self.running:
            try:
                cycle_start = time.time()

                # Run scan and execute. The activity flag bracketing
                # the scan is the self-experiment loop's
                # daemon-activity probe input (TASK-STR-EXP-004); it
                # is maintained unconditionally and read only when
                # that loop is wired on.
                self._scan_in_progress = True
                try:
                    results = self.scan_and_execute()
                finally:
                    self._scan_in_progress = False

                if results["executed"] > 0:
                    logger.info(f"[STRATEX] Cycle {self.scan_count}: {results}")

                self._publish_daemon_heartbeat(results=results)

                # Sleep for remainder of interval
                elapsed = time.time() - cycle_start
                sleep_time = max(1, self.scan_interval - elapsed)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("[STRATEX] Shutdown signal received")
                break
            except Exception as e:
                logger.error(f"[STRATEX] Loop error: {e}", exc_info=True)
                self._publish_daemon_heartbeat(error=e, status="ERROR")
                time.sleep(5)

        self._publish_daemon_heartbeat(status="STOPPED")
        self._stop_heartbeat_pulse()
        self._stop_self_experiments()


def main() -> None:
    logger.info("=== STARTING STRATEX 24/7 AUTONOMOUS AI TRADING ENGINE ===")
    
    # Initialize Telegram
    telegram = get_telegram_bot()
    
    # Initialize multi-venue engine with Telegram bot
    engine = create_multi_venue_engine(
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_secret=os.getenv("BINANCE_API_SECRET", ""),
        starting_balance=float(os.getenv("STRATEX_INITIAL_BALANCE", "1000.0")),
        max_positions_per_venue=int(os.getenv("STRATEX_MAX_POSITIONS_PER_VENUE", "5")),
        max_total_positions=int(os.getenv("STRATEX_MAX_TOTAL_POSITIONS", "10")),
        risk_per_trade_pct=float(os.getenv("STRATEX_RISK_PER_TRADE_PCT", "0.001")),
        max_daily_loss_pct=float(os.getenv("STRATEX_MAX_DAILY_LOSS_PCT", "0.03")),
        telegram_bot=telegram,
    )

    # Track positions that were already open before this process started, so a
    # broker-side SL/TP fill is still detected and reported after a restart.
    try:
        engine.adopt_existing_positions()
    except Exception as e:
        logger.warning(f"[STRATEX_DAEMON] Position adoption failed: {e}")

    # Initialize trading engine
    trading_engine = StratexTradingEngine(engine)

    # Setup Telegram
    if not telegram.is_configured:
        logger.warning("[STRATEX_DAEMON] Telegram bot is not configured. Outbound alerts will be suppressed.")
    else:
        logger.info("[STRATEX_DAEMON] Starting Telegram bot background listener daemon...")
        # start_listening honors TELEGRAM_WEBHOOK_URL when set (webhook mode
        # locks out external getUpdates pollers — TASK-STRATEX-TGWEBHOOK),
        # and falls back to the classic polling thread otherwise.
        telegram.start_listening()
        telegram.send_message(
            "🚀 <b>Stratex Online — Multi-Venue</b>\n\n"
            "• Venues: Binance Futures (Crypto) + OANDA (Forex/Indices/Commodities)\n"
            "• Balance: Real-time from venues\n"
            "• SL/TP: Native on orders\n"
            "• Strategies: 6 active (Trend, Mean Reversion, VWAP, Scalping, Pairs, ADX)\n"
            "• Risk: 0.1% of venue equity per trade, 2% heat cap per strategy, 3% daily loss limit\n\n"
            "<i>Send /status, /positions, /balance, /scan for details.</i>"
        )

    # Handle shutdown gracefully
    def signal_handler(signum, frame):
        logger.info("[STRATEX_DAEMON] Shutdown signal received")
        trading_engine.running = False
        telegram.stop_polling()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Send startup heartbeat
    try:
        risk = engine.get_risk_summary()
        telegram.send_message(
            f"📡 <b>Stratex Started</b>\n"
            f"💰 Balance: <code>${risk['total_balance']:,.2f}</code>\n"
            f"📈 Max Positions: <code>{risk['max_positions']}</code>\n"
            f"⚠️ Daily Loss Limit: <code>{risk.get('daily_loss_limit_hit', False)}</code>"
        )
    except Exception:
        pass

    # Run main trading loop
    trading_engine.run()
    
    logger.info("[STRATEX_DAEMON] Shutdown complete")


if __name__ == "__main__":
    main()