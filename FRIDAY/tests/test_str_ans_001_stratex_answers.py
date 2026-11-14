"""TASK-STR-ANS-001: FRIDAY's Stratex answers must carry real substance.

Live evidence (Server 1, 2026-11-15 ~02:37 IST): Stratex's supervision
payload held balance 10,792.80, flat positions and 7 active strategies,
while FRIDAY's /api/chat answer to "Ask Stratex how my portfolio is
doing" was "STRATEX finished that. Stratex supervision status retrieved
for friday." — the mesh outcome carried the figures in ``result`` the
whole time; the autonomous controller composed the reply from the peer's
boilerplate ``summary`` and dropped them (the VOI-004 acceptance failure,
2026-11-14 23:09 IST). Two sibling defects on the same path:

- "What is my Stratex balance?" was captured by the server memory-recall
  gate (REL-022's "what is my" trigger) and answered from the memory
  store — "I don't have anything stored on that yet" — Stratex was
  never asked.
- Every mesh outcome store to Memora 404'd: the fabric posted to
  /api/v1/memora/context[/store|/search], routes Memora has never
  mounted (FRIDAY journal 2026-11-14 23:09:14). Memora's real surface is
  the viking context DB: POST /v1/context/remember, GET
  /v1/context/search, POST /v1/context (self-targeted; verified live).

These tests pin the seams. Every figure asserted below comes from the
fixture payload — the same discipline the fix follows in production.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_CORE_SRC = _REPO / "FRIDAY" / "apps" / "core" / "src"
if str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

pytestmark = [pytest.mark.unit]

# The live Stratex supervision shape (Server 1, 2026-11-15), extended
# with the ledger scorecard block the same task adds on the Stratex side
# (phase-2 ledger: LEGACY 3 closes +195.71, bb_reversion 1 close +0.5437).
_SNAPSHOT: dict[str, Any] = {
    "engine": "Stratex",
    "trading_mode": "FUTURES",
    "balance": 10792.8,
    "cash_balance": 10792.8,
    "portfolio": {"equity": 10792.8, "cash": 10792.8, "open_positions_count": 0},
    "current_positions": [],
    "position_count": 0,
    "unrealized_pnl": 0.0,
    "panic_active": False,
    "kill_switch_active": False,
    "active_strategies": [
        "supertrend", "bb_reversion", "factory_winner_1", "factory_winner_2",
        "factory_winner_3", "factory_winner_4", "factory_winner_5",
    ],
    "ledger_scorecard": {
        "generated_at": "2026-11-15T00:00:00Z",
        "source": "fill_ledger",
        "total_fills": 9,
        "totals": {
            "trades": 4, "net_pnl": 196.25, "win_rate": 0.75,
            "profit_factor": 6.77, "expectancy_net_per_trade": 49.06,
            "max_drawdown": 33.64, "fees": 0.0,
        },
        "strategies": {
            "LEGACY-UNATTRIBUTED": {"trades": 3, "net_pnl": 195.71, "profit_factor": 6.77, "win_rate": 0.67},
            "bb_reversion": {"trades": 1, "net_pnl": 0.54, "profit_factor": None, "win_rate": 1.0},
            "supertrend": {"trades": 0, "net_pnl": 0.0, "profit_factor": None, "win_rate": 0.0},
        },
        "reset_boundaries": 2,
    },
}


# ── 1. The controller composition seam ──────────────────────────────────


def _mesh(monkeypatch, controller, behaviour):
    from friday.cognition.mesh import Mesh, build_contracts
    from friday.autonomous import controller as controller_module

    contracts = build_contracts(controller_module.fleet_client)
    mesh, transport = Mesh.in_process(contracts, attempts=1, backoff_seconds=0.0)
    transport.behave("stratex", behaviour)
    monkeypatch.setattr(controller, "_peer_mesh", mesh, raising=False)
    return transport


@pytest.mark.asyncio
async def test_verified_stratex_delegation_reply_carries_the_payload_figures(monkeypatch):
    """The defect itself: a verified Stratex status outcome must answer
    with the snapshot's figures, not the peer's boilerplate summary."""
    from friday.autonomous import controller as controller_module
    from friday.cognition.mesh import HarnessBehaviour

    controller = controller_module.AutonomousController()
    _mesh(monkeypatch, controller, HarnessBehaviour(result=dict(_SNAPSHOT)))

    result = await controller.execute_agent_control("stratex", "status of my portfolio")

    assert result["metadata"]["task_completion_verified"] is True
    reply = result["reply"]
    assert "10,792.80" in reply, reply
    assert "Open positions: none" in reply, reply
    assert "supertrend" in reply and "factory_winner_5" in reply, reply
    assert "Ledger P&L" in reply and "+196.25" in reply, reply
    # The old content-thin answer was exactly this shape; it must be gone.
    assert reply.strip() != "STRATEX finished that. stratex completed the task"


@pytest.mark.asyncio
async def test_verified_stratex_delegation_without_a_snapshot_invents_nothing(monkeypatch):
    """A verified outcome whose result carries no snapshot falls back to
    the summary line — no figures appear out of thin air."""
    from friday.autonomous import controller as controller_module
    from friday.cognition.mesh import HarnessBehaviour

    controller = controller_module.AutonomousController()
    _mesh(monkeypatch, controller, HarnessBehaviour(result={"note": "nothing structured"}))

    result = await controller.execute_agent_control("stratex", "status of my portfolio")

    assert result["metadata"]["task_completion_verified"] is True
    assert "10,792" not in result["reply"]
    assert "Ledger P&L" not in result["reply"]


# ── 2. The shared snapshot renderer ─────────────────────────────────────


class TestFormatPortfolioSubstance:
    def test_ledger_pnl_block_renders_from_the_payload(self):
        from friday.tools.builtin.stratex_portfolio import _format_portfolio

        text = _format_portfolio(dict(_SNAPSHOT))
        assert "Ledger P&L (recorded fills): 4 closed trade(s), net P&L +196.25" in text
        assert "win rate 75%" in text
        assert "profit factor 6.77" in text
        assert "LEGACY-UNATTRIBUTED: 3 trade(s), net +195.71" in text
        assert "bb_reversion: 1 trade(s), net +0.54" in text
        # A strategy with no recorded trades is not listed as if it traded.
        assert "supertrend: 0 trade(s)" not in text

    def test_halt_and_unrealized_render_when_present(self):
        from friday.tools.builtin.stratex_portfolio import _format_portfolio

        snap = dict(
            _SNAPSHOT,
            panic_active=True,
            unrealized_pnl=-42.5,
            current_positions=[{"symbol": "BTCUSDT", "side": "long", "entry_price": 67000, "unrealized_pnl": -42.5}],
        )
        text = _format_portfolio(snap)
        assert "Trading HALTED" in text
        assert "Unrealized P&L: -42.50" in text

    def test_no_ledger_block_and_no_halt_line_when_absent(self):
        from friday.tools.builtin.stratex_portfolio import _format_portfolio

        snap = {k: v for k, v in _SNAPSHOT.items() if k != "ledger_scorecard"}
        text = _format_portfolio(snap)
        assert "Ledger P&L" not in text
        assert "HALTED" not in text
        assert "Unrealized P&L" not in text  # flat + zero: nothing to report

    def test_empty_ledger_says_so_honestly(self):
        from friday.tools.builtin.stratex_portfolio import _format_portfolio

        snap = dict(_SNAPSHOT, ledger_scorecard={"totals": {"trades": 0, "net_pnl": 0.0}, "strategies": {}})
        text = _format_portfolio(snap)
        assert "no closed trades recorded yet" in text


# ── 3. "Which strategies" reaches the portfolio fast path ───────────────


class _FakeResult:
    def __init__(self, status: str, result: dict[str, Any] | None = None, error: str | None = None):
        self.status = status
        self.result = result or {}
        self.error = error
        self.task_id = "task_str_ans"
        self.execution_time_ms = 10


class _FakeFleetClient:
    def __init__(self, result):
        self._result = result

    async def dispatch_task(self, envelope):
        return self._result


def test_which_strategies_running_gets_the_snapshot():
    from unittest.mock import patch

    from friday.agent.agent import FridayAgent
    from friday.core.config import Settings
    from friday.memory.in_memory import InMemoryConversationMemory
    from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool

    with patch.object(
        StratexPortfolioTool, "_client",
        return_value=_FakeFleetClient(_FakeResult("SUCCESS", dict(_SNAPSHOT))),
    ):
        agent = FridayAgent(
            settings=Settings(env="testing"),
            memory=InMemoryConversationMemory(),
        )
        response = agent.process_message("which strategies are running?")

    assert response.metadata.get("fast_path") is True, response.metadata
    assert response.metadata.get("portfolio_query") is True, response.metadata
    assert "supertrend" in response.content
    assert "10,792.80" in response.content


# ── 4. The recall gate must not capture trading-account questions ───────


def test_stratex_balance_question_is_not_answered_from_memory(tmp_path, monkeypatch):
    from unittest.mock import patch

    import friday.memory.memora_client as memora_module
    from friday.api.server import _dispatch_command
    from friday.memory.memora_client import MemoraClient
    from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool

    client = MemoraClient(local_db_path=str(tmp_path / "str_ans.db"), remote_enabled=False)
    monkeypatch.setattr(memora_module, "memora_client", client)
    try:
        with patch.object(
            StratexPortfolioTool, "_client",
            return_value=_FakeFleetClient(_FakeResult("SUCCESS", dict(_SNAPSHOT))),
        ):
            result = asyncio.run(_dispatch_command("What is my Stratex balance?"))
        assert result["metadata"].get("memory_recall") is not True, result["metadata"]
        assert "don't have anything stored" not in result["reply"]
        assert "10,792.80" in result["reply"], result["reply"]
    finally:
        client._executor.shutdown(wait=True)


def test_genuine_memory_question_still_uses_the_recall_gate(tmp_path, monkeypatch):
    """Control: the carve-out is narrow — REL-022's 'what is my' recall
    keeps working for actual memory questions."""
    import friday.memory.memora_client as memora_module
    from friday.api.server import _dispatch_command
    from friday.memory.memora_client import MemoraClient

    client = MemoraClient(local_db_path=str(tmp_path / "str_ans_ctl.db"), remote_enabled=False)
    monkeypatch.setattr(memora_module, "memora_client", client)
    try:
        saved = asyncio.run(_dispatch_command('remember that my safe word is "crimson tiger 8"'))
        assert saved["metadata"]["memory_store"] is True

        recalled = asyncio.run(_dispatch_command("What is my safe word?"))
        assert recalled["metadata"].get("memory_recall") is True
        assert "crimson tiger 8" in recalled["reply"]
    finally:
        client._executor.shutdown(wait=True)


# ── 5. The Memora fabric speaks Memora's real API ───────────────────────


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    calls: list = []
    payload: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None, params=None):
        type(self).calls.append(("POST", url, json, params))
        return _FakeResponse(type(self).payload)

    async def get(self, url, params=None, headers=None):
        type(self).calls.append(("GET", url, None, params))
        return _FakeResponse(type(self).payload)


@pytest.fixture()
def fake_httpx(monkeypatch):
    import httpx

    _FakeAsyncClient.calls = []
    _FakeAsyncClient.payload = {}
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


@pytest.mark.asyncio
async def test_fabric_store_posts_to_the_viking_remember_endpoint(fake_httpx):
    from friday.cognition.mesh import MemoraFabric

    fake_httpx.payload = {"stored": True, "uri": "viking://user/memora/memories/episodic/task_123.md"}
    fabric = MemoraFabric("http://memora.test", "key", agent_name="friday")
    out = await fabric.store(
        "stratex outcome: verified\nSTRATEX finished that.",
        memory_type="episodic",
        importance=0.9,
        provenance={"task_id": "task_123", "source_agent": "friday", "target_agent": "stratex"},
    )
    assert out.get("stored") is True
    method, url, body, _ = fake_httpx.calls[0]
    assert method == "POST"
    assert url == "http://memora.test/v1/context/remember", url
    assert body["kind"] == "episodic"
    assert body["key"] == "task_123"
    assert body["body"].startswith("stratex outcome: verified")
    assert body["confidence"] == 0.9


@pytest.mark.asyncio
async def test_fabric_search_reads_the_viking_search_hits(fake_httpx):
    from friday.cognition.mesh import MemoraFabric

    fake_httpx.payload = {"query": "stratex outcome", "count": 1, "hits": [{"uri": "u1", "score": 3.6}]}
    fabric = MemoraFabric("http://memora.test", "key", agent_name="friday")
    hits = await fabric.search("stratex outcome", limit=3)
    assert hits == [{"uri": "u1", "score": 3.6}]
    method, url, _, params = fake_httpx.calls[0]
    assert method == "GET"
    assert url == "http://memora.test/v1/context/search", url
    assert params == {"query": "stratex outcome", "limit": 3}


@pytest.mark.asyncio
async def test_fabric_build_context_targets_the_authenticated_agent(fake_httpx):
    """Memora refuses (403, verified live) a bundle built for another
    agent's identity; the fabric must target itself even when the caller
    names the peer whose dispatch the context supports."""
    from friday.cognition.mesh import MemoraFabric

    fake_httpx.payload = {"bundle": "ctx"}
    fabric = MemoraFabric("http://memora.test", "key", agent_name="friday")
    await fabric.build_context("portfolio status", agent_id="stratex")
    method, url, body, _ = fake_httpx.calls[0]
    assert method == "POST"
    assert url == "http://memora.test/v1/context", url
    assert body["agent_id"] == "friday"
    assert body["task_query"] == "portfolio status"
