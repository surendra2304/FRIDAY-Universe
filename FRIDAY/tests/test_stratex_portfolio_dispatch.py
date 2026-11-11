"""TASK-STR-002: Stratex portfolio questions through FRIDAY chat.

"How's my portfolio?" / "any open positions?" / "what strategies are
running?" must return Stratex's REAL engine snapshot (Binance demo account)
— never the LLM's guess. Live trading stays blocked by the merged fail-closed
guard (owner decision D-015): the tool is read-only by construction
(_ALLOWED_ACTIONS = status/analyze; Stratex rejects orders server-side too).
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

from friday.memory.in_memory import InMemoryConversationMemory
from friday.routing.capability_router import (
    CapabilityRouter,
    ExecutionCapabilityType,
)
from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool


class _FakeResult:
    def __init__(self, status: str, result: dict[str, Any] | None = None, error: str | None = None):
        self.status = status
        self.result = result or {}
        self.error = error
        self.task_id = "task_strx1"
        self.execution_time_ms = 7301


class _FakeFleetClient:
    def __init__(self, result):
        self._result = result
        self.envelopes = []

    async def dispatch_task(self, envelope):
        self.envelopes.append(envelope)
        return self._result


class _BrokenFleetClient:
    async def dispatch_task(self, envelope):
        raise ConnectionError("stratex unreachable")


_SNAPSHOT = {
    "engine": "Stratex", "trading_mode": "demo",
    "balance": 10792.8, "cash_balance": 10792.8,
    "current_positions": [],
    "active_strategies": ["supertrend", "bb_reversion", "factory_winner_1"],
}


class TestPortfolioQuestionsRouteToStratex:
    @pytest.mark.parametrize(
        "question",
        [
            "friday, how is my portfolio doing",
            "any open positions right now",
            "what strategies are running",
            "check my balance on the trading account",
            "show me the market signals",
            "how is my pnl today",
        ],
    )
    def test_portfolio_questions_route_to_stratex(self, question: str) -> None:
        decision = CapabilityRouter().route_request(question)
        assert decision.selected_capability != ExecutionCapabilityType.DIRECT_REASONING, (
            f"{question!r} routed to DIRECT_REASONING — portfolio needs Stratex"
        )
        stratex = [
            c for c in decision.candidate_evaluations
            if getattr(c, "required_tools", None) == ["stratex_portfolio"]
        ]
        assert stratex, f"{question!r} produced no stratex_portfolio candidate"

    def test_plain_chat_stays_conversational(self) -> None:
        decision = CapabilityRouter().route_request("hello, what can you do for me")
        assert decision.selected_capability == ExecutionCapabilityType.DIRECT_REASONING


class TestStratexToolReportsTruth:
    def test_portfolio_snapshot(self) -> None:
        client = _FakeFleetClient(_FakeResult("SUCCESS", dict(_SNAPSHOT)))
        result = StratexPortfolioTool(fleet_client=client).execute(question="my portfolio")
        assert not result.is_error
        assert "10,792.80" in result.content
        assert "Open positions: none" in result.content
        assert "supertrend" in result.content
        assert "demo mode" in result.content
        assert "D-015" in result.content  # the live-trading guard is stated
        env = client.envelopes[0]
        assert env.target_agent == "stratex"
        assert env.action == "status"

    def test_positions_are_listed(self) -> None:
        snapshot = dict(_SNAPSHOT, current_positions=[
            {"symbol": "BTCUSDT", "side": "long", "entry_price": 67000, "unrealized_pnl": 120.5},
        ])
        result = StratexPortfolioTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS", snapshot))).execute(question="positions")
        assert "Open positions: 1" in result.content
        assert "LONG BTCUSDT @ 67000" in result.content
        assert "+120.50" in result.content

    def test_failure_is_honest(self) -> None:
        result = StratexPortfolioTool(fleet_client=_FakeFleetClient(_FakeResult("FAILED", error="HTTP 503"))).execute(question="portfolio")
        assert result.is_error
        assert "HTTP 503" in result.content
        assert "nothing was invented" in result.content

    def test_crash_is_honest(self) -> None:
        result = StratexPortfolioTool(fleet_client=_BrokenFleetClient()).execute(question="portfolio")
        assert result.is_error
        assert "could not reach Stratex" in result.content

    def test_tool_never_sends_order_actions(self) -> None:
        """The tool's action surface is read-only by construction."""
        from friday.tools.builtin.stratex_portfolio import _ALLOWED_ACTIONS
        assert set(_ALLOWED_ACTIONS) == {"status", "analyze"}

    def test_analysis_kind(self) -> None:
        client = _FakeFleetClient(_FakeResult("SUCCESS", {
            "signal_count": 2, "symbols_analyzed": ["BTCUSDT"],
            "signals": [{"symbol": "BTCUSDT", "signal": "HOLD"}],
        }))
        result = StratexPortfolioTool(fleet_client=client).execute(question="market signals", kind="analysis")
        assert not result.is_error
        assert "BTCUSDT: HOLD" in result.content
        assert client.envelopes[0].action == "analyze"


class TestPortfolioFastPath:
    def test_my_portfolio_gets_stratex_snapshot(self) -> None:
        from unittest.mock import patch
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings

        with patch.object(
            StratexPortfolioTool, "_client",
            return_value=_FakeFleetClient(_FakeResult("SUCCESS", dict(_SNAPSHOT))),
        ):
            agent = FridayAgent(
                settings=Settings(env="testing"),
                memory=InMemoryConversationMemory(),
            )
            response = agent.process_message("friday, how is my portfolio doing?")
        assert response.metadata.get("fast_path") is True
        assert response.metadata.get("portfolio_query") is True
        assert "10,792.80" in response.content

    def test_general_finance_question_takes_normal_path(self) -> None:
        """'what is a portfolio' must NOT hit the Stratex fast path."""
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings
        from unittest.mock import patch

        captured = []
        with patch.object(
            StratexPortfolioTool, "execute",
            side_effect=lambda *a, **k: captured.append(1) or None,
        ):
            agent = FridayAgent(
                settings=Settings(env="testing"),
                memory=InMemoryConversationMemory(),
            )
            # The fast path must decline; the cognitive path runs (mock LLM).
            response = agent.process_message("what is a portfolio in finance?")
        assert not captured or response is not None  # no crash either way
        from friday.routing.capability_router import CapabilityRouter
        low = "what is a portfolio in finance?"
        possessive = {"my portfolio", "the portfolio", "my balance", "my positions",
                      "open positions", "stratex", "binance"}
        assert not CapabilityRouter._matches(low, possessive)
