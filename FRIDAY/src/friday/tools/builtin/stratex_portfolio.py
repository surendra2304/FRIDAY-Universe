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
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach Stratex for that ({type(exc).__name__}: {exc}). "
                    "I won't guess at your portfolio — try again shortly."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        status = str(getattr(result, "status", "")).lower()
        if status not in {"success", "completed"}:
            error = getattr(result, "error", None) or f"status {status or 'unknown'}"
            return ToolResult(
                name=self.name,
                content=(
                    f"Stratex could not answer that: {error}. "
                    "That is the real outcome — nothing was invented."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"status": status, "error": error},
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
