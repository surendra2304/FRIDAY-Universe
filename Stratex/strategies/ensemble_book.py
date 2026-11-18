"""Ensemble-book execution engine — TASK-STR-EXP-002 (slice 2).

Lets the daemon trade an admitted ensemble book: a set of equal-weight
member streams, each a live strategy module + judged config cell, evaluated
on its own timeframe/universe. The book's position is the equal-weight
combination of the member signals.

LIVE-EXECUTION SEMANTICS (read this before judging the book's forward
record against its judged figures — the two are different objects):
  * The judged book (RD-025 / the self-experiment loop) holds the UNION
    of member trades: on one symbol it can hold a LONG leg from one member
    and a SHORT leg from another at the same time, each scaled 1/k.
  * The live book holds ONE net position per (strategy, symbol): per
    symbol, net = (#LONG members) - (#SHORT members); net > 0 -> LONG,
    net < 0 -> SHORT, net == 0 -> no position. The bracket is the
    equal-weight mean of the same-direction signalling members' judged
    brackets, and the position is sized at the lane's 0.1% risk/trade
    (the module must NOT inflate sl_dist to fake 1/k sizing — that would
    distort the stop). The forward demo record, not the judged union,
    is the book's evidence; the kill rules (expectancy < 0 or PF < 1.0
    after >= 50 closed trades) apply to the LIVE book's own fills.
  * Offline measurement of the gap (~/workspace/str-slice2/verify_books.py,
    from the saved trade lists): the share of judged member position-days
    the netting would NOT hold runs 4.3% (3929) to 17.4% (3978) for the
    RD-025 books — and 45.2% for the loop's first-light book (3900), whose
    three crypto-1d members (one of them a reversion stream) oppose each
    other on one in five active days. The live books are therefore
    expected to trade less often and with different P&L than the judged
    unions; 3900's divergence is the largest and is stamped on its entry.

FAIL-CLOSED RULES (the whole book refuses; it never trades a subset):
  * A member whose module cannot be imported, has no get_signal, is not
    governed FORWARD_TEST/VALIDATED, or whose panel has no venue mapping
    -> the book refuses on first evaluation (raises EnsembleBookError,
    logged once) and thereafter returns NO_SIGNAL until the daemon
    restarts. A member that is merely NOT APPLICABLE to the current
    symbol (wrong panel) abstains — that is normal, not a failure: it
    never traded that symbol in the judgement either.
  * A member whose evaluation raises, or which signals without a usable
    bracket, raises (a live defect, not a configuration state) — the
    registry's health rule then applies (5 consecutive exceptions ->
    UNHEALTHY -> blocked until restart).
  * Mixed-panel or mixed-timeframe books refuse without evaluation
    context (symbol/timeframe/venue): a book cannot tell a crypto frame
    from a forex frame without it. Single-panel single-timeframe books
    work without context (their spec symbols already gate the universe).
  * A member whose timeframe differs from the frame being evaluated
    contributes its last cached signal; a member with no cached signal
    yet makes the book NOT READY (NO_SIGNAL, not an error).

MEMBER ENABLEMENT: judged by governance status, not by the daemon's
STRATEX_STRATEGY_ALLOWLIST. The allowlist gates which strategies the
daemon SCANS; members are dependencies of a book, never scanned on their
own through the book. The book module itself must be allowlisted to run
at all — an allowlist omission silently skips the whole book (the proven
FWD-003 lane root cause), which is why the deploy checklist names the
8 book modules explicitly.

REGISTRY INTEGRATION: books register in config_strategy.py as
FORWARD_TEST entries (FWD-003 shape). The loop's admissions
(Stratex/self_experiments/admissions.py, PR #986) live in the loop's own
data-dir registry; merged_registry_view() below is the same view as the
loop's merged_registry() (new dict, base never mutated, key collision
with a governed entry raises) and works with or without the loop merged
— book_from_admission() maps a loop admission entry (members = stream
ids) onto a Book via the known-stream table. When the loop code is
importable, test_exp002 asserts the two views agree.
"""

from __future__ import annotations

import importlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Panel -> demo venue. Only the two demo venues exist; any other panel
# (comm7 / idx7 / idx3) has no venue mapping and its books refuse.
PANEL_VENUE = {
    "crypto30": "binance_futures",
    "forex28": "oanda",
}

# Governance statuses a member may carry. Anything else (DISABLED,
# OBSERVE_ONLY, UNREGISTERED) refuses the whole book.
MEMBER_OK_STATUSES = ("FORWARD_TEST", "VALIDATED")


class EnsembleBookError(Exception):
    """The book refuses to evaluate (fail-closed)."""


class RegistryCollisionError(Exception):
    """A merged-registry key collides with a governed entry."""


@dataclass(frozen=True)
class Member:
    """One member stream of an ensemble book."""

    module: str | None  # production module name; None = no such module exists
    key: str  # registry key, e.g. "vol_adaptive_trend"
    cell: str  # judged config cell, e.g. "ema12_26_nogate"
    panel: str  # "crypto30" | "forex28"
    timeframe: str  # "1d" | "1wk"
    venue: str  # demo venue the panel trades on
    sl_atr: float  # judged stop bracket (x ATR(14))
    tp_atr: float  # judged target bracket (x ATR(14))
    universe: tuple[str, ...] = ()  # symbols the member trades
    unavailable_reason: str = ""  # set when module is None

    @property
    def stream_id(self) -> str:
        return f"{self.key}__{self.cell}__at__{self.panel}__{self.timeframe}"

    @property
    def rr_ratio(self) -> float:
        return self.tp_atr / self.sl_atr


@dataclass(frozen=True)
class Book:
    """An admitted ensemble book (audit figures + member list)."""

    key: str  # registry key, e.g. "ensemble_book_3905"
    trial: int | None  # RD-025 / loop trial number (None if unrecorded)
    verdict: str  # "PROVEN" | "FORWARD_TEST"
    source: str  # "RD-025" | "LOOP"
    members: tuple[Member, ...]
    trades: int = 0  # judged pooled OOS trades (union, scaled 1/k)
    expectancy: float = 0.0  # judged pooled expectancy / trade
    pf: float = 0.0  # judged pooled profit factor
    win_rate: float = 0.0  # judged pooled win rate
    edge_bps: float = 0.0  # expectancy * 10000
    folds: str = ""  # e.g. "4/5"
    max_stop_pct: float = 0.5  # per-book FWD-012 stop-cap override
    execution: str = ""  # machine-visible execution state stamp

    @property
    def panels(self) -> frozenset[str]:
        return frozenset(m.panel for m in self.members)

    @property
    def timeframes(self) -> frozenset[str]:
        return frozenset(m.timeframe for m in self.members)


@dataclass
class BookState:
    """Per-process evaluation state for one book (held by its module).

    _cache: (book_key, symbol, member_key) -> (last_closed_bar_ts, signal)
    where signal is the member's returned dict or None (abstained).
    _resolved: module name -> imported module (None = import failed).
    _refusals: book_key -> reason (configuration refusal, raised once).
    """

    _cache: dict[tuple[str, str, str], tuple[Any, dict | None]] = field(
        default_factory=dict
    )
    _resolved: dict[str, Any] = field(default_factory=dict)
    _refusals: dict[str, str] = field(default_factory=dict)

    def refusal_reason(self, book_key: str) -> str | None:
        return self._refusals.get(book_key)


def _signal_bar_close(df: pd.DataFrame) -> float:
    """Close of the last CLOSED bar (the daemon's bar-latch: index -2)."""
    idx = -2 if len(df) >= 2 else -1
    return float(df["close"].iloc[idx])


def _last_closed_ts(df: pd.DataFrame) -> Any:
    idx = -2 if len(df) >= 2 else -1
    return df.index[idx]


def _governance_status(module_name: str) -> str:
    """Governance status of a member module (lazy import: keeps the
    engine importable without the full registry)."""
    from strategies.strategy_registry import governance_status_for

    return governance_status_for(module_name)


def _resolve_member(member: Member, state: BookState) -> Any:
    """Import and governance-check one member module (cached per process).

    Raises EnsembleBookError on any configuration failure.
    """
    if member.module is None:
        raise EnsembleBookError(
            f"member {member.key} ({member.cell} @ {member.panel} "
            f"{member.timeframe}) has no production module: "
            f"{member.unavailable_reason or 'unavailable'}"
        )
    if member.module in state._resolved:
        module = state._resolved[member.module]
        if module is None:
            raise EnsembleBookError(
                f"member module {member.module} failed to import "
                f"(cached refusal)"
            )
        return module
    try:
        module = importlib.import_module(member.module)
    except Exception as exc:  # noqa: BLE001 - any import failure refuses
        state._resolved[member.module] = None
        raise EnsembleBookError(
            f"member module {member.module} cannot be imported: {exc}"
        ) from exc
    get_signal = getattr(module, "get_signal", None)
    if get_signal is None or not callable(get_signal):
        state._resolved[member.module] = None
        raise EnsembleBookError(
            f"member module {member.module} has no callable get_signal"
        )
    expected_venue = PANEL_VENUE.get(member.panel)
    if expected_venue is None:
        raise EnsembleBookError(
            f"member {member.key} panel {member.panel!r} has no demo "
            f"venue mapping — the book cannot trade it"
        )
    if member.venue != expected_venue:
        raise EnsembleBookError(
            f"member {member.key} venue {member.venue!r} does not match "
            f"its panel {member.panel!r} (expected {expected_venue!r})"
        )
    status = _governance_status(member.module)
    if status not in MEMBER_OK_STATUSES:
        raise EnsembleBookError(
            f"member module {member.module} is governed {status} "
            f"(needs FORWARD_TEST or VALIDATED) — book refused"
        )
    state._resolved[member.module] = module
    return module


def _member_bracket(signal: dict, df: pd.DataFrame) -> tuple[float, float]:
    """(sl_dist, tp_dist) for a member signal, preferring the module's
    own dists, then deriving them from absolute sl/tp prices at the
    signal bar's close. Raises if no usable bracket exists."""
    sl_dist = signal.get("sl_dist")
    tp_dist = signal.get("tp_dist")
    if sl_dist is not None and tp_dist is not None:
        return float(sl_dist), float(tp_dist)
    sl = signal.get("sl")
    tp = signal.get("tp")
    if sl is not None and tp is not None and sl and tp:
        close = _signal_bar_close(df)
        side = signal.get("side")
        if side == "BUY":
            return abs(close - float(sl)), abs(float(tp) - close)
        if side == "SELL":
            return abs(float(sl) - close), abs(close - float(tp))
    raise EnsembleBookError(
        f"member signal {signal.get('side')} carries no usable bracket "
        f"(neither sl_dist/tp_dist nor sl/tp prices)"
    )


def _frame_panel(symbol: str | None, venue: str | None, book: Book) -> str:
    """The panel the current frame belongs to, from context.

    A symbol names its panel unambiguously (the universes are disjoint);
    a venue names its panel. With neither, a single-panel book's panel
    applies; a mixed-panel book refuses (it cannot tell a crypto frame
    from a forex frame without context).
    """
    if symbol is not None:
        for member in book.members:
            if symbol in member.universe:
                return member.panel
        raise EnsembleBookError(
            f"symbol {symbol!r} is in no member universe of book "
            f"{book.key} — the frame cannot belong to this book"
        )
    if venue is not None:
        for panel, mapped in PANEL_VENUE.items():
            if mapped == venue:
                return panel
        raise EnsembleBookError(
            f"venue {venue!r} maps to no known panel"
        )
    if len(book.panels) == 1:
        return next(iter(book.panels))
    raise EnsembleBookError(
        f"book {book.key} is mixed-panel {sorted(book.panels)} and was "
        f"evaluated without symbol or venue context — refusing"
    )


def evaluate_book(
    book: Book,
    df: pd.DataFrame,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    venue: str | None = None,
    state: BookState | None = None,
) -> dict[str, Any] | None:
    """Evaluate a book on one frame; return the daemon's signal dict or
    None (no signal / not ready / already refused).

    Raises EnsembleBookError ONCE per process for a configuration refusal
    (missing/disabled member, bad venue mapping, no context for a mixed
    book); later calls return None. Member evaluation errors and
    bracket failures raise every time (live defects, not configuration).
    """
    if state is None:
        state = BookState()
    if book.key in state._refusals:
        return None
    if df is None or len(df) == 0:
        return None
    try:
        resolved = {m.key: _resolve_member(m, state) for m in book.members}
    except EnsembleBookError as exc:
        state._refusals[book.key] = str(exc)
        logger.error("Ensemble book %s REFUSED: %s", book.key, exc)
        raise
    try:
        panel = _frame_panel(symbol, venue, book)
    except EnsembleBookError as exc:
        state._refusals[book.key] = str(exc)
        logger.error("Ensemble book %s REFUSED: %s", book.key, exc)
        raise

    # A member applies to this frame iff its panel matches the frame's
    # panel AND (no symbol context, or the symbol is in its universe).
    applicable = [
        m
        for m in book.members
        if m.panel == panel and (symbol is None or symbol in m.universe)
    ]
    if not applicable:
        return None

    if timeframe is None:
        if len({m.timeframe for m in applicable}) != 1:
            raise EnsembleBookError(
                f"book {book.key} evaluated without a timeframe and its "
                f"applicable members span timeframes "
                f"{sorted({m.timeframe for m in applicable})} — refusing"
            )
        timeframe = applicable[0].timeframe

    last_closed = _last_closed_ts(df)
    signals: dict[str, dict] = {}
    for member in applicable:
        cache_key = (book.key, symbol or panel, member.key)
        if member.timeframe == timeframe:
            # Evaluate now on this frame; cache the stance at the last
            # closed bar (the daemon's bar-latch).
            result = resolved[member.key].get_signal(df)
            signal = None
            if isinstance(result, dict) and result.get("side") in ("BUY", "SELL"):
                signal = dict(result)
            state._cache[cache_key] = (last_closed, signal)
        else:
            cached = state._cache.get(cache_key)
            if cached is None:
                # A member whose timeframe has never been scanned yet:
                # the book is not ready — NO_SIGNAL, not an error.
                return None
            _cached_ts, signal = cached
        if signal is not None:
            signals[member.key] = signal

    if not signals:
        return None
    net = sum(1 if s["side"] == "BUY" else -1 for s in signals.values())
    if net == 0:
        return None
    direction = "BUY" if net > 0 else "SELL"
    in_direction = [
        (m, signals[m.key])
        for m in applicable
        if m.key in signals and signals[m.key]["side"] == direction
    ]
    brackets = [_member_bracket(s, df) for _m, s in in_direction]
    sl_dist = sum(b[0] for b in brackets) / len(brackets)
    tp_dist = sum(b[1] for b in brackets) / len(brackets)
    close = _signal_bar_close(df)
    if direction == "BUY":
        sl_price = close - sl_dist
        tp_price = close + tp_dist
    else:
        sl_price = close + sl_dist
        tp_price = close - tp_dist
    return {
        "side": direction,
        "sl_dist": sl_dist,
        "tp_dist": tp_dist,
        "sl": sl_price,
        "tp": tp_price,
        "win_rate_prior": book.win_rate,
        "rr_ratio": tp_dist / sl_dist if sl_dist else 0.0,
        "strategy_type": "ENSEMBLE_BOOK",
        "book": book.key,
        "members_signalled": [
            (m.key, signals[m.key]["side"]) for m in applicable if m.key in signals
        ],
        "net": net,
    }


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

def merged_registry_view(
    base_registry: dict[str, Any], admissions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """The daemon-side registry view: base entries plus loop admissions.

    Same shape as the loop's merged_registry() (TASK-STR-EXP-001):
    returns a NEW dict, the base is never mutated, and a key collision
    with a governed base entry raises instead of shadowing it.
    """
    merged = dict(base_registry)
    for key, entry in admissions.items():
        if key in merged:
            raise RegistryCollisionError(
                f"admission key {key} collides with a governed registry "
                f"entry — refusing to shadow it"
            )
        merged[key] = entry
    return merged


# (family, variant, panel, timeframe) -> (module, sl_atr, tp_atr).
# The known judged streams a loop admission may name. A stream outside
# this table cannot be mapped to a production module and refuses the
# book — never silently substituted.
KNOWN_STREAMS: dict[tuple[str, str, str, str], tuple[str, float, float]] = {
    ("vol_adaptive_trend", "ema12_26_nogate", "crypto30", "1d"): (
        "strategy_vol_adaptive_trend", 2.5, 5.0),
    ("donchian_turtle", "n55_b26", "crypto30", "1d"): (
        "strategy_donchian_turtle", 2.0, 6.0),
    ("ts_momentum", "roc72", "crypto30", "1d"): (
        "strategy_ts_momentum", 2.0, 4.0),
    ("macd_trend", "hist_raw", "crypto30", "1d"): (
        "strategy_macd_trend", 2.5, 5.0),
    ("tsmom2_dual", "roc90_ema200", "crypto30", "1d"): (
        "strategy_tsmom2_dual_crypto_1d", 2.5, 5.0),
    ("shock_breakout", "k1.5", "crypto30", "1d"): (
        "strategy_shock_breakout_k15", 2.0, 4.0),
    ("shock_breakout", "k1.0", "crypto30", "1d"): (
        "strategy_shock_breakout", 2.0, 4.0),
    ("shock_breakout", "k1.0", "crypto30", "1wk"): (
        "strategy_shock_breakout_1wk", 2.0, 4.0),
    ("ichimoku_trend", "tk_cloud", "crypto30", "1d"): (
        "strategy_ichimoku_trend_1d", 2.0, 4.0),
    ("ha_trend", "two_candle", "crypto30", "1d"): (
        "strategy_ha_trend", 2.0, 4.0),
    ("bollinger_trend", "p20_sd2.0", "crypto30", "1d"): (
        "strategy_bollinger_trend_p20", 2.0, 4.0),
    ("stoch_reversion", "k14_raw", "forex28", "1d"): (
        "strategy_stoch_reversion", 2.0, 4.0),
    ("stoch_reversion", "k14_raw", "crypto30", "1d"): (
        "strategy_stoch_reversion_crypto", 2.0, 4.0),
    ("zscore_reversion", "w50_t2.5_filt", "forex28", "1d"): (
        "strategy_zscore_reversion", 2.0, 2.0),
}


def _parse_stream_id(stream_id: str) -> tuple[str, str, str, str]:
    """'family__variant__at__panel__tf' -> (family, variant, panel, tf)."""
    try:
        left, right = stream_id.split("__at__")
        family, variant = left.split("__", 1)
        panel, tf = right.split("__", 1)
    except ValueError as exc:
        raise EnsembleBookError(
            f"unparsable stream id {stream_id!r}"
        ) from exc
    return family, variant, panel, tf


def book_from_admission(
    entry: dict[str, Any],
    key: str,
    *,
    metrics: dict[str, Any] | None = None,
    universes: dict[str, tuple[str, ...]] | None = None,
) -> Book:
    """Build a Book from a loop admission entry (TASK-STR-EXP-001 shape).

    members = stream ids; figures come from `metrics` when given
    (trades/expectancy/pf/win_rate/folds) and otherwise from the entry's
    own priors (win rate, edge bps). A stream outside KNOWN_STREAMS
    refuses — including xs_lowvol, which is a cross-sectional rotation,
    not a per-symbol stream. `universes` maps panel -> symbol tuple
    (defaults to the config universes, resolved lazily).
    """
    if universes is None:
        from config_strategy import CRYPTO30_SYMBOLS, FOREX28_SYMBOLS

        universes = {
            "crypto30": tuple(CRYPTO30_SYMBOLS),
            "forex28": tuple(FOREX28_SYMBOLS),
        }
    members: list[Member] = []
    for stream_id in entry.get("members", []):
        parsed = _parse_stream_id(stream_id)
        known = KNOWN_STREAMS.get(parsed)
        if known is None:
            raise EnsembleBookError(
                f"stream {stream_id!r} has no production module mapping — "
                f"admission {key} refused, not substituted"
            )
        module, sl_atr, tp_atr = known
        _family, _variant, panel, tf = parsed
        members.append(Member(
            module=module,
            key=parsed[0],
            cell=parsed[1],
            panel=panel,
            timeframe=tf,
            venue=PANEL_VENUE[panel],
            sl_atr=sl_atr,
            tp_atr=tp_atr,
            universe=universes.get(panel, ()),
        ))
    if metrics is not None:
        trades = int(metrics.get("trades", 0))
        expectancy = float(metrics.get("expectancy", 0.0))
        pf = float(metrics.get("pf", 0.0))
        win_rate = float(metrics.get("win_rate", entry.get("oos_win_rate_prior") or 0.0))
        folds = str(metrics.get("folds", ""))
    else:
        trades = 0
        expectancy = float(entry.get("expected_net_edge_bps") or 0.0) / 10000.0
        pf = 0.0
        win_rate = float(entry.get("oos_win_rate_prior") or 0.0)
        folds = ""
    trial = None
    reason = str(entry.get("reason", ""))
    match = re.search(r"global trial N=(\d+)", reason)
    if match:
        trial = int(match.group(1))
    return Book(
        key=key,
        trial=trial,
        verdict=str(entry.get("self_experiment_verdict", "FORWARD_TEST")),
        source="LOOP",
        members=tuple(members),
        trades=trades,
        expectancy=expectancy,
        pf=pf,
        win_rate=win_rate,
        edge_bps=round(expectancy * 10000.0, 1),
        folds=folds,
        execution=str(entry.get("execution", "")),
    )


def book_from_registry_entry(key: str, entry: dict[str, Any]) -> Book:
    """Build a Book from a config_strategy.py FORWARD_TEST entry.

    The entry's "members" list is the machine-readable member table
    (module, cell, panel, timeframe, venue, sl_atr, tp_atr); the entry's
    reason carries the trial number. Used by the consistency test that
    pins config entries against the canonical BOOKS dict.
    """
    from config_strategy import CRYPTO30_SYMBOLS, FOREX28_SYMBOLS

    universes = {
        "crypto30": tuple(CRYPTO30_SYMBOLS),
        "forex28": tuple(FOREX28_SYMBOLS),
    }
    members: list[Member] = []
    for spec in entry.get("members", []):
        panel = spec["panel"]
        members.append(Member(
            module=spec.get("module"),
            key=spec["key"],
            cell=spec["cell"],
            panel=panel,
            timeframe=spec["timeframe"],
            venue=spec["venue"],
            sl_atr=float(spec["sl_atr"]),
            tp_atr=float(spec["tp_atr"]),
            universe=universes.get(panel, ()),
            unavailable_reason=spec.get("unavailable_reason", ""),
        ))
    reason = str(entry.get("reason", ""))
    trial = None
    for pattern in (r"RD-025 trial (\d+)", r"loop trial (\d+)"):
        match = re.search(pattern, reason)
        if match:
            trial = int(match.group(1))
            break
    return Book(
        key=key,
        trial=trial,
        verdict=str(entry.get("self_experiment_verdict", "PROVEN")),
        source="LOOP" if entry.get("self_experiment") else "RD-025",
        members=tuple(members),
        trades=int(entry.get("oos_trades", 0)),
        expectancy=float(entry.get("expected_net_edge_bps") or 0.0) / 10000.0,
        pf=float(entry.get("oos_profit_factor", 0.0)),
        win_rate=float(entry.get("oos_win_rate_prior") or 0.0),
        edge_bps=float(entry.get("expected_net_edge_bps") or 0.0),
        folds=str(entry.get("oos_folds", "")),
        max_stop_pct=float(entry.get("max_stop_pct") or 0.5),
        execution=str(entry.get("execution", "")),
    )
