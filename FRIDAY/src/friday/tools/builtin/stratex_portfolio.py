"""TASK-STR-002: Stratex portfolio questions through FRIDAY chat.

"Friday, how's my portfolio?" / "any open positions?" must return Stratex's
REAL engine snapshot — balance, positions, strategies, trading mode — from
the Binance demo account. Live trading stays blocked by the merged fail-closed
guard (owner decision D-015): this tool is READ-ONLY by construction (status
and analyze actions only; order/panic actions are not sendable from here and
Stratex rejects them server-side anyway).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = logging.getLogger(__name__)

#: The only actions this tool may ever send — read-only surface.
_ALLOWED_ACTIONS = ("status", "analyze")


def _format_portfolio(data: dict[str, Any]) -> str:
    """Render Stratex's engine snapshot as the owner's portfolio answer."""
    balance = data.get("balance")
    cash = data.get("cash_balance")
    positions = data.get("current_positions") or []
    strategies = data.get("active_strategies") or []
    mode = data.get("trading_mode") or data.get("mode") or "demo"
    engine = data.get("engine", "Stratex")

    lines = [f"Portfolio snapshot ({engine}, {mode} mode):"]
    if balance is not None:
        lines.append(f"- Balance: {balance:,.2f}" if isinstance(balance, (int, float)) else f"- Balance: {balance}")
    if cash is not None and cash != balance:
        lines.append(f"- Cash: {cash:,.2f}" if isinstance(cash, (int, float)) else f"- Cash: {cash}")
    if positions:
        lines.append(f"- Open positions: {len(positions)}")
        for p in positions[:8]:
            sym = p.get("symbol", "?")
            side = p.get("side", "")
            entry = p.get("entry_price", p.get("entry", ""))
            pnl = p.get("unrealized_pnl", p.get("pnl", ""))
            pnl_s = f", PnL {pnl:+,.2f}" if isinstance(pnl, (int, float)) else (f", PnL {pnl}" if pnl else "")
            lines.append(f"    {side.upper()} {sym} @ {entry}{pnl_s}")
    else:
        lines.append("- Open positions: none")
    if strategies:
        lines.append(f"- Active strategies ({len(strategies)}): {', '.join(str(s) for s in strategies[:8])}")
    lines.append("")
    lines.append("Live trading remains blocked by your fail-closed guard (D-015) — this is the demo account only.")
    return "\n".join(lines)


def _format_analysis(data: dict[str, Any]) -> str:
    """Render Stratex's market analysis result."""
    signals = data.get("signal_count", len(data.get("signals") or []))
    symbols = data.get("symbols_analyzed") or []
    lines = ["Stratex market analysis:"]
    for sig in (data.get("signals") or [])[:8]:
        sym = sig.get("symbol", "?")
        direction = sig.get("signal", sig.get("direction", "?"))
        lines.append(f"- {sym}: {direction}")
    if signals:
        lines.append(f"\n{signals} signal(s) across {len(symbols)} symbol(s).")
    status = data.get("status")
    if status and str(status).upper() not in {"SUCCESS", "OK"}:
        lines.append(f"Analysis status: {status}.")
    if not (data.get("signals") or signals):
        lines.append("No actionable signals right now — that is the real analysis result.")
    lines.append("")
    lines.append("Signals are analysis only; no orders can be placed (fail-closed, D-015).")
    return "\n".join(lines)


def _stratex_state_dir() -> Path | None:
    """Locate the local Stratex state directory (read-only, never invents).

    Order: FRIDAY_STRATEX_STATE_DIR env override, then the sibling
    ``Stratex/`` directory of this checkout (this file lives at
    FRIDAY/src/friday/tools/builtin/ → parents[5] is the repo root).
    """
    override = (os.getenv("FRIDAY_STRATEX_STATE_DIR") or "").strip()
    if override:
        p = Path(override)
        return p if p.is_dir() else None
    try:
        candidate = Path(__file__).resolve().parents[5] / "Stratex"
        return candidate if candidate.is_dir() else None
    except IndexError:  # pragma: no cover - path layout changed
        return None


def _read_local_snapshot() -> tuple[dict[str, Any], str] | None:
    """Last-known Stratex engine state from local files (READ-ONLY, newest-wins).

    Sources: Stratex/testnet_heartbeat.json / heartbeat.json (the engine's own
    heartbeat, newest timestamp wins) and, as a secondary equity source, the
    last line of Stratex/ledger/live_equity_curve.jsonl. Only fields actually
    present in the files are returned — nothing is fabricated. Never raises.
    """
    base = _stratex_state_dir()
    if base is None:
        return None
    best: tuple[dict[str, Any], str] | None = None
    best_ts = ""
    for rel in ("testnet_heartbeat.json", "heartbeat.json"):
        f = base / rel
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        ts = str(data.get("timestamp") or "")
        if best is not None and (not ts or ts <= best_ts):
            continue
        strategies = data.get("strategies") or []
        if not strategies and data.get("strategy") and str(data["strategy"]).lower() != "none":
            strategies = [data["strategy"]]
        fields: dict[str, Any] = {
            "engine": "Stratex",
            "source_file": f.name,
            "snapshot_timestamp": ts or "unknown",
            "engine_status": str(data.get("status") or "UNREPORTED").upper(),
            "trading_mode": str(data.get("mode") or data.get("trading_mode") or "UNREPORTED").upper(),
            "balance": data.get("current_equity"),
            "open_position_count": data.get("open_positions"),
            "binance_connected": bool(data.get("binance_connected")),
            "websocket_connected": bool(data.get("websocket_connected")),
            "active_strategies": list(strategies),
            "last_market_update": data.get("last_market_update"),
            "service_start_time": data.get("service_start_time"),
        }
        best = (fields, f"{f.name} (recorded {ts or 'at an unknown time'})")
        best_ts = ts
    # Secondary source: the equity ledger's most recent recorded point.
    ledger = base / "ledger" / "live_equity_curve.jsonl"
    if best is not None:
        try:
            last_line = ""
            with ledger.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        last_line = line
            if last_line:
                point = json.loads(last_line)
                if isinstance(point, dict):
                    best[0]["ledger_equity"] = point
                    best[0]["ledger_note"] = (
                        f"ledger last equity point: {json.dumps(point, default=str)[:200]}"
                    )
        except (OSError, ValueError):
            pass
    return best


def _format_last_known(fields: dict[str, Any], source: str) -> str:
    """Render the local last-known state clearly labelled as NOT live."""
    balance = fields.get("balance")
    lines = [f"Last known engine state from Stratex/{source}:"]
    if isinstance(balance, (int, float)):
        lines.append(f"- Balance: {balance:,.2f}")
    else:
        lines.append("- Balance: not recorded in the state file")
    count = fields.get("open_position_count")
    lines.append(f"- Open positions: {count if isinstance(count, int) else 'not recorded'}")
    lines.append(f"- Engine status: {fields.get('engine_status', 'UNREPORTED')}")
    lines.append(f"- Mode: {fields.get('trading_mode', 'UNREPORTED')}")
    lines.append(f"- Binance connected: {'yes' if fields.get('binance_connected') else 'no'}")
    strategies = fields.get("active_strategies") or []
    if strategies:
        lines.append(f"- Active strategies ({len(strategies)}): {', '.join(str(s) for s in strategies[:8])}")
    return "\n".join(lines)


def _unavailable_content(reason: str, question_kind: str) -> tuple[str, dict[str, Any] | None]:
    """Honest 'cannot answer' content: live reason + last-known local state.

    Returns (content, fallback_fields). Never invents numbers: when no local
    state exists the answer says so plainly.
    """
    snapshot = _read_local_snapshot()
    parts = [reason]
    if snapshot:
        fields, source = snapshot
        parts.append(_format_last_known(fields, source))
        parts.append(
            "That is recorded state, not a live reading — nothing was invented. "
            "The Stratex engine was not answering the live query when you asked."
        )
    else:
        parts.append(
            "No local engine state file exists either, so there is genuinely no "
            f"{question_kind} data to report — nothing was invented."
        )
    return "\n".join(parts), (snapshot[0] if snapshot else None)


class StratexPortfolioTool(BaseTool):
    """Answer portfolio/position/market questions with Stratex's real Binance-demo data."""

    name = "stratex_portfolio"
    description = (
        "Get the live portfolio snapshot from Stratex, the fleet's Algorithmic "
        "Trading Platform: balance, open positions, active strategies and "
        "trading mode on the Binance demo account. Also answers market-analysis "
        "questions (current signals per symbol). Read-only: live trading is "
        "blocked by the owner's fail-closed guard (D-015). Use for questions "
        "like 'how is my portfolio', 'any open positions', 'what strategies "
        "are running', 'analyze the current market signals'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 45.0
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The portfolio or market question (e.g. 'how is my portfolio doing').",
            },
            "kind": {
                "type": "string",
                "enum": ["portfolio", "analysis"],
                "description": "'portfolio' (default) for the account snapshot; 'analysis' for market signals.",
                "default": "portfolio",
            },
        },
        "required": [],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def _dispatch(self, action: str, question: str) -> Any:
        from friday.core.task_envelope import TaskEnvelope

        assert action in _ALLOWED_ACTIONS  # read-only surface, by construction
        envelope = TaskEnvelope(
            capability=f"stratex.{action}",
            objective=f"Portfolio question: {question}",
            action=action,
            target_agent="stratex",
            payload={"question": question},
        )
        return asyncio.run(self._client().dispatch_task(envelope))

    def execute(self, question: str = "", kind: str = "portfolio", **kwargs: Any) -> ToolResult:
        question = (question or "").strip()
        action = "analyze" if kind == "analysis" else "status"
        try:
            result = self._dispatch(action, question or ("market analysis" if action == "analyze" else "portfolio snapshot"))
        except Exception as exc:
            # Live Stratex unreachable: report WHY, then the last-known local
            # state file. The owner gets the best real data available — never a
            # refusal, never an invented number (TASK-STR-002 discipline).
            reason = (
                f"I could not reach Stratex for that ({type(exc).__name__}: {exc}). "
            )
            try:
                url = str(getattr(self._client(), "stratex_url", "") or "")
            except Exception:
                url = ""
            if not url:
                reason += (
                    "The Stratex service URL is not configured here "
                    "(FRIDAY_STRATEX_URL / STRATEX_URL). "
                )
            reason += "I won't guess at your portfolio — here is everything real I have."
            content, fallback = _unavailable_content(reason, "portfolio")
            return ToolResult(
                name=self.name,
                content=content,
                is_error=True,
                safety_level=self.safety_level,
                metadata={
                    "error": f"{type(exc).__name__}: {exc}",
                    "live_url": url,
                    "fallback": fallback,
                },
            )

        status = str(getattr(result, "status", "")).lower()
        if status not in {"success", "completed"}:
            error = getattr(result, "error", None) or f"status {status or 'unknown'}"
            reason = (
                f"Stratex could not answer that: {error}. "
                "That is the real live outcome — nothing was invented. "
                "Here is the last-known recorded state I do have."
            )
            content, fallback = _unavailable_content(reason, "portfolio")
            return ToolResult(
                name=self.name,
                content=content,
                is_error=True,
                safety_level=self.safety_level,
                metadata={"status": status, "error": error, "fallback": fallback},
            )

        data = getattr(result, "result", None) or {}
        if not isinstance(data, dict):
            data = {"summary": str(data)}
        content = _format_analysis(data) if action == "analyze" else _format_portfolio(data)
        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "stratex": {
                    "task_id": getattr(result, "task_id", ""),
                    "action": action,
                    "execution_time_ms": getattr(result, "execution_time_ms", 0),
                    "balance": data.get("balance"),
                    "position_count": len(data.get("current_positions") or []),
                },
                "raw": json.dumps(data, default=str)[:4000],
            },
        )
