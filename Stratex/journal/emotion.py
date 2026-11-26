"""Emotion-aware trade journal for Stratex (TASK-STR-081).

Source pattern: stratex package S-06 ("OurMind AI" — import your trades for
AI analysis, pattern detection, and risk analysis). Stratex's journal had no
emotion/pattern layer; this module adds it end to end on Stratex's own demo
trades: trades imported -> emotion analysis attached -> pattern detection ->
a per-period risk summary the desk and the risk gate can read.

Honesty rule, stated once: the ledger carries no self-reported feelings and
no separate entry time (entry and exit timestamps are identical), so no
hold-duration signal exists. Every "emotion" here is a RULE-BASED BEHAVIOURAL
PROXY computed from observable trade records — sequence, timing between
closes, size moves, symbol repetition, and fee bleed — labelled as such, each
with its rule. Nothing here claims to know how anyone felt.

Thresholds are grounded in the journal data itself (the checked-in Binance
Futures testnet/demo ledger, 64 fills, 2026-09-09..2026-09-26, net +22.71):
  * 36 of 63 close-to-close gaps are <= 10 min; 55 are <= 60 min.
  * 13 fills close inside one 60-min window (2026-09-10 14:00 UTC); 8 inside
    one 10-min window; 11 inside ~1 second (2026-09-09 15:52 UTC batch).
  * 18 of 47 losses are fee-dominated (|gross| < fees); 10 of them land on
    2026-09-10 alone.
  * Median notional is 99.54; 6 fills exceed 3x the median (max 1111.91).
  * ATOMUSDT is 18/64 fills (28%) with net -7.72.
  * Longest raw consecutive-loss run is 28 fills (win rate 26.6%).

Stdlib only. No import from any other Stratex module, so the journal runs
hermetically (offline tests, CI) and never touches a live path.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- Thresholds (grounded in the journal data; see module docstring) ---
REVENGE_GAP_MIN = 10.0          # close-to-close gap that counts as "quick re-entry after a loss"
CHASE_GAP_MIN = 30.0            # max gap between consecutive same-symbol loss trades in a chase run
CHASE_MIN_RUN = 3               # same-symbol consecutive losses that form a chase pattern
BURST_WINDOW_MIN = 60.0         # window for the overtrading burst
BURST_MIN_TRADES = 8            # fills in BURST_WINDOW_MIN that form a burst
BURST10_WINDOW_MIN = 10.0       # tight window for the burst
BURST10_MIN_TRADES = 5          # fills in BURST10_WINDOW_MIN that form a tight burst
SIMULTANEOUS_WINDOW_SEC = 60.0  # window for a simultaneous book exit
SIMULTANEOUS_MIN_TRADES = 5     # fills in SIMULTANEOUS_WINDOW_SEC that form a simultaneous exit
CHURN_MIN_RUN = 3               # fee-dominated losses in one day that form a churn run
STREAK_MIN = 5                  # consecutive-loss episode that forms a streak pattern
STREAK_GAP_MAX_H = 24.0         # max gap (hours) between consecutive losses in one episode
SIZE_OUTLIER_MULT = 3.0         # notional >= this x period median notional counts as a size outlier
SIZE_PATTERN_MIN = 3            # size outliers in a period that form a concentration pattern
FIXATION_MIN_SHARE = 0.25       # one symbol's share of period fills that counts as fixation
# Risk-level rules: HIGH when the desk must act now (very long loss episode or
# heavy one-day fee churn); ELEVATED when any major pattern is present.
HIGH_STREAK = 10
HIGH_CHURN_DAY = 8


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing timestamp")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not a number: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} is not finite: {value!r}")
    return number


@dataclass(frozen=True)
class Trade:
    """One closed trade, as the journal sees it."""

    symbol: str
    timestamp: datetime
    net_pnl: float
    gross_pnl: float = 0.0
    fees: float = 0.0
    quantity: float = 0.0
    entry_price: float = 0.0
    exit_price: float = 0.0
    side: str = ""
    order_id: str = ""
    exit_reason: str = ""
    strategy: str = ""
    source: str = ""

    @property
    def notional(self) -> float:
        return self.quantity * self.entry_price

    @property
    def is_win(self) -> bool:
        if self.exit_reason:
            return self.exit_reason.upper() == "WIN"
        return self.net_pnl > 0

    @property
    def is_fee_dominated_loss(self) -> bool:
        """True when the loss IS the fee: the market move was smaller than the fee paid."""
        return self.net_pnl < 0 and abs(self.gross_pnl) < self.fees


def trade_from_dict(raw: dict[str, Any]) -> Trade:
    """Parse one trade record. Accepts the testnet-ledger shape
    (quantity / action / direction / timestamp) and the measurement
    fill-ledger shape (qty / side / engine / venue). Raises ValueError on
    missing symbol, timestamp, or net PnL, or on non-finite numbers."""
    if not isinstance(raw, dict):
        raise ValueError("trade record is not an object")
    symbol = raw.get("symbol") or raw.get("pair")
    if not symbol or not isinstance(symbol, str):
        raise ValueError("missing symbol")
    timestamp = _parse_ts(raw.get("timestamp") or raw.get("exit_timestamp") or raw.get("close_time"))
    if raw.get("net_pnl") is None and raw.get("pnl") is None:
        raise ValueError("missing net_pnl")
    net_pnl = _finite(raw.get("net_pnl", raw.get("pnl")), "net_pnl")
    fees = _finite(raw.get("fees", 0.0), "fees")
    gross = raw.get("gross_pnl")
    gross_pnl = _finite(gross, "gross_pnl") if gross is not None else net_pnl + fees
    quantity = _finite(raw.get("quantity", raw.get("qty", 0.0)), "quantity")
    entry_price = _finite(raw.get("entry_price", 0.0), "entry_price")
    exit_price = _finite(raw.get("exit_price", entry_price), "exit_price")
    side = str(raw.get("direction") or raw.get("side") or raw.get("action") or "")
    order_id = str(raw.get("order_id") or raw.get("trade_id") or "")
    exit_reason = str(raw.get("exit_reason") or "")
    if not exit_reason:
        exit_reason = "WIN" if net_pnl > 0 else "LOSS"
    return Trade(
        symbol=symbol,
        timestamp=timestamp,
        net_pnl=net_pnl,
        gross_pnl=gross_pnl,
        fees=fees,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        side=side,
        order_id=order_id,
        exit_reason=exit_reason,
        strategy=str(raw.get("strategy") or ""),
        source=str(raw.get("source") or ""),
    )


def load_jsonl(path: str | Path) -> tuple[list[Trade], int]:
    """Load trades from a JSONL ledger. Returns (trades, skipped_rows).
    Blank lines and malformed rows are skipped and counted, never fatal."""
    trades: list[Trade] = []
    skipped = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                trades.append(trade_from_dict(json.loads(line)))
            except (ValueError, TypeError, json.JSONDecodeError):
                skipped += 1
    trades.sort(key=lambda t: (t.timestamp, t.order_id))
    return trades, skipped


def sort_trades(trades: list[Trade]) -> list[Trade]:
    return sorted(trades, key=lambda t: (t.timestamp, t.order_id))


@dataclass
class EmotionTag:
    """One behavioural-proxied emotion tag attached to a trade."""

    tag: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "reason": self.reason}


def analyse_trade(
    trade: Trade,
    prev_trade: Trade | None,
    period_median_notional: float,
) -> list[EmotionTag]:
    """Attach emotion-proxy tags to one trade, given the previous trade in
    time order and the period median notional. Tags are behavioural proxies
    (see module docstring), never claims about feelings."""
    tags: list[EmotionTag] = []
    if trade.is_fee_dominated_loss:
        tags.append(EmotionTag(
            "fee_churn",
            f"fee-dominated loss: |gross {trade.gross_pnl:.4f}| < fees {trade.fees:.4f}; the loss is the fee",
        ))
    if period_median_notional > 0 and trade.notional >= SIZE_OUTLIER_MULT * period_median_notional:
        tags.append(EmotionTag(
            "size_outlier",
            f"notional {trade.notional:.2f} is >= {SIZE_OUTLIER_MULT}x period median {period_median_notional:.2f}",
        ))
    if prev_trade is not None:
        gap_min = (trade.timestamp - prev_trade.timestamp).total_seconds() / 60.0
        if gap_min <= SIMULTANEOUS_WINDOW_SEC / 60.0:
            # Same decision event (e.g. a batch book-close): the previous fill
            # is not a separate decision, so no re-entry / scale-up tag applies.
            return tags
        if not prev_trade.is_win and gap_min <= REVENGE_GAP_MIN:
            tags.append(EmotionTag(
                "quick_reentry_after_loss",
                f"closed {gap_min:.1f} min after a loss (prev {prev_trade.symbol} "
                f"{prev_trade.net_pnl:.2f}); fast re-entry after a loss",
            ))
        if (
            not prev_trade.is_win
            and prev_trade.symbol == trade.symbol
            and gap_min <= CHASE_GAP_MIN
        ):
            tags.append(EmotionTag(
                "same_symbol_after_loss",
                f"same-symbol re-entry {gap_min:.1f} min after a {trade.symbol} loss "
                f"({prev_trade.net_pnl:.2f}); chasing the same symbol",
            ))
        if prev_trade.is_win and prev_trade.notional > 0 and trade.notional >= 1.5 * prev_trade.notional:
            tags.append(EmotionTag(
                "scale_up_after_win",
                f"notional {trade.notional:.2f} is >= 1.5x the previous win's "
                f"{prev_trade.notional:.2f}; sizing up right after a win",
            ))
    return tags

@dataclass
class DecisionEvent:
    """One decision moment: fills closing within the same second are one
    decision (e.g. a batch book-close), not N independent emotional trades.
    The event outcome is the sign of the aggregate net PnL."""

    timestamp: datetime
    trades: list[Trade] = field(default_factory=list)

    @property
    def net_pnl(self) -> float:
        return sum(t.net_pnl for t in self.trades)

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0


def collapse_events(trades: list[Trade], window_seconds: float = 5.0) -> list[DecisionEvent]:
    """Group fills closing within `window_seconds` of the group's first fill
    into one decision event. Default 5s: the observed batch closes span at
    most 3.9s (2026-09-09 15:52 batch: 1.1s; 2026-09-10 13:05 batch: 3.9s),
    while the smallest gap between separate decisions in the journal is
    minutes — so the window merges batch closes and nothing else. Used for
    streak counting, so a simultaneous multi-symbol book-close does not read
    as a streak of independent trades."""
    ordered = sort_trades(trades)
    events: list[DecisionEvent] = []
    for trade in ordered:
        if events and (trade.timestamp - events[-1].timestamp).total_seconds() <= window_seconds:
            events[-1].trades.append(trade)
        else:
            events.append(DecisionEvent(timestamp=trade.timestamp, trades=[trade]))
    return events


def _sliding_windows(
    trades: list[Trade], window_min: float, min_trades: int
) -> list[tuple[datetime, datetime, list[Trade]]]:
    """Maximal non-overlapping windows holding >= min_trades fills.
    Greedy from the earliest uncovered trade; each reported window starts at
    a trade and extends window_min forward, taking every fill inside."""
    ordered = sort_trades(trades)
    windows: list[tuple[datetime, datetime, list[Trade]]] = []
    i = 0
    while i < len(ordered):
        start = ordered[i].timestamp
        group = [t for t in ordered[i:] if (t.timestamp - start).total_seconds() <= window_min * 60.0]
        if len(group) >= min_trades:
            windows.append((start, group[-1].timestamp, group))
            i += len(group)
        else:
            i += 1
    return windows


def detect_patterns(trades: list[Trade]) -> list[dict[str, Any]]:
    """Detect tilt patterns over a period of trades. Each pattern carries its
    rule in `detail` so the desk can audit it; severities are major (act on
    it) or minor (informational). Returns patterns in time order."""
    ordered = sort_trades(trades)
    patterns: list[dict[str, Any]] = []
    if not ordered:
        return patterns

    # Simultaneous book exit: many fills closing inside one minute.
    for start, end, group in _sliding_windows(ordered, SIMULTANEOUS_WINDOW_SEC / 60.0, SIMULTANEOUS_MIN_TRADES):
        patterns.append({
            "pattern": "SIMULTANEOUS_EXIT",
            "severity": "minor",
            "count": len(group),
            "first": start.isoformat(),
            "last": end.isoformat(),
            "trade_ids": [t.order_id for t in group],
            "detail": (
                f"{len(group)} fills closed within "
                f"{(end - start).total_seconds():.1f}s ({start.isoformat()}..{end.isoformat()}): "
                "one batch book-close, read as one decision, not N independent trades"
            ),
        })

    # Overtrading bursts: many fills inside 60 min, and inside 10 min.
    for window_min, min_trades, label in (
        (BURST_WINDOW_MIN, BURST_MIN_TRADES, "OVERTRADING_BURST"),
        (BURST10_WINDOW_MIN, BURST10_MIN_TRADES, "OVERTRADING_BURST_10MIN"),
    ):
        for start, end, group in _sliding_windows(ordered, window_min, min_trades):
            patterns.append({
                "pattern": label,
                "severity": "major",
                "count": len(group),
                "first": start.isoformat(),
                "last": end.isoformat(),
                "trade_ids": [t.order_id for t in group],
                "detail": f"{len(group)} fills closed in {(end - start).total_seconds() / 60.0:.0f} min "
                          f"({start.isoformat()}..{end.isoformat()}); burst pace, not spaced decisions",
            })

    # Fee-churn runs: one day with many fee-dominated losses.
    by_day: dict[str, list[Trade]] = {}
    for trade in ordered:
        by_day.setdefault(trade.timestamp.date().isoformat(), []).append(trade)
    for day in sorted(by_day):
        churn = [t for t in by_day[day] if t.is_fee_dominated_loss]
        if len(churn) >= CHURN_MIN_RUN:
            bleed = sum(t.net_pnl for t in churn)
            patterns.append({
                "pattern": "FEE_CHURN_RUN",
                "severity": "major",
                "count": len(churn),
                "first": day,
                "last": day,
                "trade_ids": [t.order_id for t in churn],
                "detail": f"{len(churn)} fee-dominated losses on {day} (net bleed {bleed:.2f}); "
                          "the desk paid fees to lose, repeatedly",
            })

    # Loss-streak episodes on collapsed decision events (gaps <= 24h stay in
    # one episode; a multi-day gap breaks it).
    events = collapse_events(ordered)
    run: list[DecisionEvent] = []
    for event in events:
        if not event.is_win:
            if run and (event.timestamp - run[-1].timestamp).total_seconds() > STREAK_GAP_MAX_H * 3600.0:
                if len(run) >= STREAK_MIN:
                    patterns.append(_streak_pattern(run))
                run = []
            run.append(event)
        else:
            if len(run) >= STREAK_MIN:
                patterns.append(_streak_pattern(run))
            run = []
    if len(run) >= STREAK_MIN:
        patterns.append(_streak_pattern(run))

    # Same-symbol chase: per symbol, consecutive losses on that symbol, each
    # gap <= 30 min. (Per-symbol subsequences, not global order: other
    # symbols' fills interleave, but returning to the same losing symbol is
    # the chase.)
    by_symbol: dict[str, list[Trade]] = {}
    for trade in ordered:
        by_symbol.setdefault(trade.symbol, []).append(trade)
    for symbol in sorted(by_symbol):
        seq = by_symbol[symbol]
        run_trades: list[Trade] = []
        for trade in seq:
            if (
                run_trades
                and not trade.is_win
                and (trade.timestamp - run_trades[-1].timestamp).total_seconds() <= CHASE_GAP_MIN * 60.0
            ):
                run_trades.append(trade)
            else:
                if len(run_trades) >= CHASE_MIN_RUN:
                    patterns.append(_chase_pattern(run_trades))
                run_trades = [trade] if not trade.is_win else []
        if len(run_trades) >= CHASE_MIN_RUN:
            patterns.append(_chase_pattern(run_trades))

    # Symbol fixation: one symbol is >= 25% of fills and net negative.
    counts: dict[str, int] = {}
    net_by_symbol: dict[str, float] = {}
    for trade in ordered:
        counts[trade.symbol] = counts.get(trade.symbol, 0) + 1
        net_by_symbol[trade.symbol] = net_by_symbol.get(trade.symbol, 0.0) + trade.net_pnl
    for symbol in sorted(counts, key=lambda s: -counts[s]):
        share = counts[symbol] / len(ordered)
        if share >= FIXATION_MIN_SHARE and net_by_symbol[symbol] < 0:
            patterns.append({
                "pattern": "SYMBOL_FIXATION",
                "severity": "major",
                "count": counts[symbol],
                "symbol": symbol,
                "first": ordered[0].timestamp.isoformat(),
                "last": ordered[-1].timestamp.isoformat(),
                "trade_ids": [t.order_id for t in ordered if t.symbol == symbol],
                "detail": f"{symbol} is {counts[symbol]}/{len(ordered)} fills ({share:.0%}) "
                          f"with net {net_by_symbol[symbol]:.2f}; fixation on a losing symbol",
            })

    # Size concentration: several fills at >= 3x the period median notional.
    notionals = sorted(t.notional for t in ordered)
    median = notionals[len(notionals) // 2] if notionals else 0.0
    outliers = [t for t in ordered if median > 0 and t.notional >= SIZE_OUTLIER_MULT * median]
    if len(outliers) >= SIZE_PATTERN_MIN:
        patterns.append({
            "pattern": "SIZE_OUTLIERS",
            "severity": "minor",
            "count": len(outliers),
            "first": outliers[0].timestamp.isoformat(),
            "last": outliers[-1].timestamp.isoformat(),
            "trade_ids": [t.order_id for t in outliers],
            "detail": f"{len(outliers)} fills at >= {SIZE_OUTLIER_MULT}x median notional "
                      f"({median:.2f}); largest {max(t.notional for t in outliers):.2f}",
        })

    patterns.sort(key=lambda p: (p["first"], p["pattern"]))
    return patterns


def _streak_pattern(run: list[DecisionEvent]) -> dict[str, Any]:
    net = sum(e.net_pnl for e in run)
    return {
        "pattern": "LOSS_STREAK",
        "severity": "major",
        "count": len(run),
        "first": run[0].timestamp.isoformat(),
        "last": run[-1].timestamp.isoformat(),
        "trade_ids": [t.order_id for e in run for t in e.trades],
        "detail": f"{len(run)} consecutive losing decision events "
                  f"({run[0].timestamp.date().isoformat()}..{run[-1].timestamp.date().isoformat()}), "
                  f"net {net:.2f}; tilt episode, not spaced losses",
    }


def _chase_pattern(run: list[Trade]) -> dict[str, Any]:
    net = sum(t.net_pnl for t in run)
    return {
        "pattern": "SYMBOL_CHASE",
        "severity": "major",
        "count": len(run),
        "symbol": run[0].symbol,
        "first": run[0].timestamp.isoformat(),
        "last": run[-1].timestamp.isoformat(),
        "trade_ids": [t.order_id for t in run],
        "detail": f"{len(run)} consecutive {run[0].symbol} losses, each <= {CHASE_GAP_MIN:.0f} min "
                  f"apart ({run[0].timestamp.isoformat()}..{run[-1].timestamp.isoformat()}), "
                  f"net {net:.2f}; re-entering the same losing symbol",
    }


def summarise_period(trades: list[Trade], period_label: str) -> dict[str, Any]:
    """Analyse one journal period end to end: import -> emotion tags ->
    patterns -> risk summary. Returns a JSON-serializable dict the desk and
    the risk gate can read (see `risk` for the machine-readable surface)."""
    ordered = sort_trades(trades)
    wins = [t for t in ordered if t.is_win]
    losses = [t for t in ordered if not t.is_win]
    net = sum(t.net_pnl for t in ordered)
    gross = sum(t.gross_pnl for t in ordered)
    fees = sum(t.fees for t in ordered)
    notionals = sorted(t.notional for t in ordered)
    median = notionals[len(notionals) // 2] if notionals else 0.0
    tag_counts: dict[str, int] = {}
    tagged: list[dict[str, Any]] = []
    prev: Trade | None = None
    for trade in ordered:
        tags = analyse_trade(trade, prev, median)
        for tag in tags:
            tag_counts[tag.tag] = tag_counts.get(tag.tag, 0) + 1
        if tags:
            tagged.append({
                "order_id": trade.order_id,
                "symbol": trade.symbol,
                "timestamp": trade.timestamp.isoformat(),
                "net_pnl": round(trade.net_pnl, 4),
                "tags": [tag.to_dict() for tag in tags],
            })
        prev = trade
    patterns = detect_patterns(ordered)
    by_day: dict[str, int] = {}
    for trade in ordered:
        by_day[trade.timestamp.date().isoformat()] = by_day.get(trade.timestamp.date().isoformat(), 0) + 1
    per_symbol_net: dict[str, float] = {}
    for trade in ordered:
        per_symbol_net[trade.symbol] = round(per_symbol_net.get(trade.symbol, 0.0) + trade.net_pnl, 4)
    summary: dict[str, Any] = {
        "period": period_label,
        "trades": len(ordered),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(ordered), 4) if ordered else 0.0,
        "net_pnl": round(net, 4),
        "gross_pnl": round(gross, 4),
        "fees": round(fees, 4),
        "avg_win": round(sum(t.net_pnl for t in wins) / len(wins), 4) if wins else 0.0,
        "avg_loss": round(sum(t.net_pnl for t in losses) / len(losses), 4) if losses else 0.0,
        "profit_factor": round(
            sum(t.net_pnl for t in wins) / -sum(t.net_pnl for t in losses), 4
        ) if wins and losses else None,
        "median_notional": round(median, 2),
        "max_win": round(max((t.net_pnl for t in ordered), default=0.0), 4),
        "max_loss": round(min((t.net_pnl for t in ordered), default=0.0), 4),
        "first_trade": ordered[0].timestamp.isoformat() if ordered else None,
        "last_trade": ordered[-1].timestamp.isoformat() if ordered else None,
        "trades_per_day": by_day,
        "net_by_symbol": per_symbol_net,
        "emotion_tag_counts": tag_counts,
        "tagged_trades": tagged,
        "patterns": patterns,
    }
    summary["risk"] = risk_assessment(summary, patterns)
    return summary


def risk_assessment(summary: dict[str, Any], patterns: list[dict[str, Any]]) -> dict[str, Any]:
    """Machine-readable risk surface for the desk and the risk gate.
    Levels: HIGH (act now), ELEVATED (a major pattern is present),
    WATCH (only minor patterns), OK (clean)."""
    flags: list[str] = []
    streaks = [p for p in patterns if p["pattern"] == "LOSS_STREAK"]
    churns = [p for p in patterns if p["pattern"] == "FEE_CHURN_RUN"]
    for pattern in patterns:
        first = str(pattern["first"])
        stamp = first[:16].replace("T", "_")  # YYYY-MM-DD_HH:MM; keeps same-day repeats distinct
        if pattern["pattern"] == "LOSS_STREAK":
            flags.append(f"LOSS_STREAK_{stamp}_{pattern['count']}")
        elif pattern["pattern"] == "FEE_CHURN_RUN":
            flags.append(f"FEE_CHURN_{pattern['first']}_{pattern['count']}")
        elif pattern["pattern"] == "OVERTRADING_BURST":
            flags.append(f"OVERTRADING_BURST_{stamp}_{pattern['count']}")
        elif pattern["pattern"] == "OVERTRADING_BURST_10MIN":
            flags.append(f"OVERTRADING_BURST_10MIN_{stamp}_{pattern['count']}")
        elif pattern["pattern"] == "SIMULTANEOUS_EXIT":
            flags.append(f"SIMULTANEOUS_EXIT_{stamp}_{pattern['count']}")
        elif pattern["pattern"] == "SYMBOL_CHASE":
            flags.append(f"SYMBOL_CHASE_{pattern.get('symbol', '?')}_{stamp}_{pattern['count']}")
        elif pattern["pattern"] == "SYMBOL_FIXATION":
            flags.append(f"SYMBOL_FIXATION_{pattern.get('symbol', '?')}")
        elif pattern["pattern"] == "SIZE_OUTLIERS":
            flags.append(f"SIZE_OUTLIERS_{pattern['count']}")
    flags = list(dict.fromkeys(flags))
    max_streak = max((p["count"] for p in streaks), default=0)
    max_churn = max((p["count"] for p in churns), default=0)
    has_major = any(p["severity"] == "major" for p in patterns)
    if max_streak >= HIGH_STREAK or max_churn >= HIGH_CHURN_DAY:
        level = "HIGH"
        reason = (
            f"loss episode of {max_streak} events" if max_streak >= HIGH_STREAK
            else f"one-day fee churn of {max_churn} losses"
        )
    elif has_major:
        level = "ELEVATED"
        reason = "a major tilt pattern is present"
    elif patterns:
        level = "WATCH"
        reason = "only minor patterns present"
    else:
        level = "OK"
        reason = "no tilt pattern detected"
    return {"level": level, "reason": reason, "flags": flags}


def render_markdown(summary: dict[str, Any]) -> str:
    """Render the period summary as a desk-readable Markdown report."""
    risk = summary["risk"]
    lines = [
        f"# Emotion-aware journal — {summary['period']}",
        "",
        f"Trades: {summary['trades']} (wins {summary['wins']}, losses {summary['losses']}, "
        f"win rate {summary['win_rate']:.1%}) | Net {summary['net_pnl']:.2f} | "
        f"Gross {summary['gross_pnl']:.2f} | Fees {summary['fees']:.2f}",
        f"Avg win {summary['avg_win']:.2f} | Avg loss {summary['avg_loss']:.2f} | "
        f"Profit factor {summary['profit_factor']} | Median notional {summary['median_notional']:.2f}",
        "",
        f"## Risk: {risk['level']} — {risk['reason']}",
        "",
    ]
    if risk["flags"]:
        lines.append("Flags: " + ", ".join(f"`{flag}`" for flag in risk["flags"]))
        lines.append("")
    lines.append("## Patterns")
    lines.append("")
    if summary["patterns"]:
        for pattern in summary["patterns"]:
            lines.append(
                f"- **{pattern['pattern']}** ({pattern['severity']}, n={pattern['count']}): {pattern['detail']}"
            )
    else:
        lines.append("None detected.")
    lines.append("")
    lines.append("## Emotion tags (behavioural proxies, rule-based)")
    lines.append("")
    if summary["emotion_tag_counts"]:
        for tag, count in sorted(summary["emotion_tag_counts"].items()):
            lines.append(f"- `{tag}`: {count} trades")
    else:
        lines.append("None attached.")
    lines.append("")
    lines.append("## Net by symbol")
    lines.append("")
    for symbol, net in sorted(summary["net_by_symbol"].items(), key=lambda item: item[1]):
        lines.append(f"- {symbol}: {net:.2f}")
    return "\n".join(lines) + "\n"
