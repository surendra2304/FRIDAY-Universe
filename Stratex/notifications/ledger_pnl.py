"""
notifications/ledger_pnl.py — Settled-trade PnL from the testnet trade ledger.

Batch 2 task 7 (owner directive 2026-11-11): the /pnl Telegram command must
report daily + rolling 7-day PnL measured from the AUTHORITATIVE settled-trade
ledger (testnet_trade_ledger.jsonl), not only live venue snapshots (which
reset when the demo account is reset and miss closed-trade history).

IST-first: the owner's day boundary is IST (project standard), so "today" and
"last 7 days" are computed in Asia/Kolkata.

Every read is fail-soft: a missing/corrupt ledger line is skipped, never fatal.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")


def _ledger_path() -> Path:
    return Path(os.getenv("TESTNET_LEDGER_FILE", "testnet_trade_ledger.jsonl"))


def _parse_ts(raw: object) -> datetime.datetime | None:
    if not raw:
        return None
    try:
        ts = datetime.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(IST)


def load_settled_trades(ledger_file: Path | None = None) -> list[dict]:
    """Load closed trades (net_pnl present) newest-last. Bad lines are skipped."""
    path = ledger_file or _ledger_path()
    trades: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pnl = rec.get("net_pnl", rec.get("pnl"))
                ts = _parse_ts(rec.get("exit_timestamp") or rec.get("timestamp"))
                try:
                    pnl = float(pnl)
                except (TypeError, ValueError):
                    continue
                if ts is None:
                    continue
                trades.append({
                    "ts": ts,
                    "net_pnl": pnl,
                    "symbol": str(rec.get("symbol", "?")),
                    "strategy": str(rec.get("strategy", "?")),
                    "direction": str(rec.get("direction", rec.get("action", "?"))),
                    "exit_reason": str(rec.get("exit_reason", "")),
                })
    except OSError:
        return []
    trades.sort(key=lambda t: t["ts"])
    return trades


def ledger_pnl_summary(ledger_file: Path | None = None, now: datetime.datetime | None = None) -> dict:
    """Daily + rolling 7-day + all-time settled PnL (IST day boundaries)."""
    now = now or datetime.datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    now = now.astimezone(IST)
    trades = load_settled_trades(ledger_file)
    today = now.date()
    week_start = today - datetime.timedelta(days=6)  # 7 calendar days incl. today

    def _agg(sub: list[dict]) -> dict:
        wins = [t for t in sub if t["net_pnl"] > 0]
        return {
            "trades": len(sub),
            "net_pnl": round(sum(t["net_pnl"] for t in sub), 2),
            "wins": len(wins),
            "win_rate": round(len(wins) / len(sub), 4) if sub else None,
            "best": round(max((t["net_pnl"] for t in sub), default=0.0), 2),
            "worst": round(min((t["net_pnl"] for t in sub), default=0.0), 2),
        }

    return {
        "asof_ist": now.strftime("%Y-%m-%d %H:%M IST"),
        "today": _agg([t for t in trades if t["ts"].date() == today]),
        "week": _agg([t for t in trades if week_start <= t["ts"].date() <= today]),
        "all_time": _agg(trades),
    }


def format_ledger_pnl(ledger_file: Path | None = None, now: datetime.datetime | None = None) -> str:
    """HTML-formatted daily + 7-day settled PnL for Telegram."""
    s = ledger_pnl_summary(ledger_file, now)
    if s["all_time"]["trades"] == 0:
        return ("📭 <b>Settled-trade ledger is empty</b>\n\n"
                "No closed trades recorded yet — the daily and 7-day PnL will "
                "appear here after the first round-trip closes.")

    def _line(label: str, agg: dict) -> str:
        emoji = "🟢" if agg["net_pnl"] >= 0 else "🔴"
        wr = f"{agg['win_rate'] * 100:.0f}%" if agg["win_rate"] is not None else "—"
        return (f"{emoji} <b>{label}</b>: <code>${agg['net_pnl']:+,.2f}</code> "
                f"over <code>{agg['trades']}</code> trades · win rate <code>{wr}</code> · "
                f"best <code>${agg['best']:+,.2f}</code> / worst <code>${agg['worst']:+,.2f}</code>")

    return "\n".join([
        "📜 <b>Settled PnL — trade ledger (IST)</b>",
        "",
        _line("Today", s["today"]),
        _line("Rolling 7 days", s["week"]),
        _line("All time", s["all_time"]),
        "",
        f"<i>As of {s['asof_ist']} · source: settled ledger, survives demo resets</i>",
    ])
