"""TASK-REL-025 — the singleton agent's shared state machine raced across turns.

Production evidence (Server 1 journal, 2026-11-14): three
``InvalidStateTransitionError`` raises in one day, every one of the shape
``COMPLETED -> <next state>`` — 20:29:53 COMPLETED->UNDERSTANDING,
21:46:20 COMPLETED->PLANNING (a chat probe and a voice greeting turn in
flight at once; the raced turn's ``execution_failed`` fallback was mapped
to HTTP 500 by ``execute_command`` at 21:46:22), 21:52:57
COMPLETED->VERIFYING.

Root cause: ``FridayAgent`` is a process-wide singleton, and
``process_message`` stored each turn's ``ReasoningStateMachine`` in the
shared instance attribute ``self.state_machine``, replacing it at every
turn start. Turns run concurrently on executor threads
(``run_in_executor`` / ``asyncio.to_thread``), so every transition of
every in-flight turn landed on whichever machine the attribute pointed
at *at that moment*. Once any turn drove that machine to the terminal
COMPLETED state, every other in-flight turn's next transition raised.
A turn abandoned by the ``asyncio.wait_for`` chat timeout kept running
as a zombie thread and corrupted the next turn the same way.

Fix: the state machine is bound per execution context (a ContextVar
behind the ``FridayAgent.state_machine`` property), so a turn only ever
sees its own machine; reads outside a turn fall back to the most recent
machine for diagnostics (``current_state``).

These tests fail on clean main and pass with the fix.
"""

import threading
from types import SimpleNamespace

from friday.agent.agent import FridayAgent
from friday.agent.cognitive import CognitivePhase
from friday.agent.state import ReasoningStateMachine, TaskState
from friday.core.types import AgentResponse

COGNITIVE_INPUT = "Describe the trade-offs of tidal power for coastal cities in detail"


def _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry):
    return FridayAgent(
        settings=mock_settings,
        llm_provider=mock_llm_provider,
        memory=memory_buffer,
        tool_registry=tool_registry,
    )


def _stub_cognitive_decision(agent):
    """Force the non-CLARIFY cognitive path deterministically (no LLM)."""
    decision = SimpleNamespace(
        current_phase=CognitivePhase.EXECUTE,
        clarification_prompt=None,
        lacks_information=False,
        confidence=SimpleNamespace(
            understanding_confidence=0.95,
            reasons=[],
            to_dict=lambda: {"understanding_confidence": 0.95},
        ),
    )
    agent.cognitive_engine.evaluate_request = lambda _inp: decision


class _BlockingExecution:
    """execute_complex_task stub: parks the turn mid-flight until released."""

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.machine_seen = None

    def __call__(self, agent, goal, context=None):
        self.machine_seen = agent.state_machine
        self.entered.set()
        if not self.release.wait(timeout=60):
            raise RuntimeError("test harness: release was never signalled")
        return AgentResponse(
            content="blocking execution finished",
            is_done=True,
            metadata={"is_successful": True},
        )


def _run_turn(agent, outcome, key="response"):
    try:
        outcome[key] = agent.process_message(COGNITIVE_INPUT)
    except Exception as exc:  # captured for assertion — the race surfaces here
        outcome["error"] = exc


def _cognitive_history_pairs(response):
    return [
        (r["from_state"], r["to_state"])
        for r in response.metadata["state_history"]
    ]


def test_concurrent_turns_do_not_share_state_machine(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry, caplog
):
    """A greeting turn completing mid-flight must not crash a cognitive turn."""
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    _stub_cognitive_decision(agent)
    blocking = _BlockingExecution()
    agent.execute_complex_task = lambda goal, context=None: blocking(agent, goal, context)

    outcome = {}
    thread_a = threading.Thread(target=_run_turn, args=(agent, outcome), name="rel025-turn-a")
    thread_a.start()
    assert blocking.entered.wait(timeout=30), "turn A never reached execution"

    # Turn B runs to COMPLETED on the same singleton while A is mid-turn —
    # the exact interleave behind the 21:46:20 production raise.
    response_b = agent.process_message("hello")
    assert response_b.metadata["task_state"] == TaskState.COMPLETED.value

    blocking.release.set()
    thread_a.join(timeout=30)
    assert not thread_a.is_alive()

    assert "error" not in outcome, f"turn A raised {outcome.get('error')!r}"
    response_a = outcome["response"]
    assert response_a.metadata["task_state"] == TaskState.COMPLETED.value
    # A's audit trail is A's own cognitive sequence — nothing of B's leaked in.
    assert _cognitive_history_pairs(response_a) == [
        ("NOT_STARTED", "UNDERSTANDING"),
        ("UNDERSTANDING", "PLANNING"),
        ("PLANNING", "VERIFYING"),
        ("VERIFYING", "COMPLETED"),
    ]
    reasons_a = [r["reason"] or "" for r in response_a.metadata["state_history"]]
    assert any("Interpreting user turn" in r for r in reasons_a)
    assert not any("Greeting" in r or "Conversational" in r for r in reasons_a)
    # The machine A was driving is A's own, and it completed cleanly.
    assert blocking.machine_seen is not None
    assert blocking.machine_seen.current_state == TaskState.COMPLETED
    assert len(blocking.machine_seen.history) == 4
    assert not [
        r for r in caplog.records if "Invalid state transition" in r.getMessage()
    ]


def test_abandoned_turn_cannot_corrupt_next_turn(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry, caplog
):
    """A turn abandoned by the chat timeout (zombie thread) harms no one."""
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    _stub_cognitive_decision(agent)
    blocking = _BlockingExecution()
    agent.execute_complex_task = lambda goal, context=None: blocking(agent, goal, context)

    outcome = {}
    zombie = threading.Thread(target=_run_turn, args=(agent, outcome), name="rel025-zombie")
    zombie.start()
    assert blocking.entered.wait(timeout=30), "zombie turn never reached execution"

    # The waiter has already given up (asyncio.wait_for timeout in
    # production); a full new turn runs and completes meanwhile.
    response_b = agent.process_message("hello")
    assert response_b.metadata["task_state"] == TaskState.COMPLETED.value

    # The zombie eventually finishes its work and drives its last
    # transitions — on clean main they land on B's COMPLETED machine.
    blocking.release.set()
    zombie.join(timeout=30)
    assert not zombie.is_alive()
    assert "error" not in outcome, f"abandoned turn raised {outcome.get('error')!r}"
    assert outcome["response"].metadata["task_state"] == TaskState.COMPLETED.value
    assert not [
        r for r in caplog.records if "Invalid state transition" in r.getMessage()
    ]


def test_state_machine_binding_is_scoped_per_thread(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry
):
    """Two threads binding a machine at the same time each keep their own."""
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    machine_main = ReasoningStateMachine()
    agent.state_machine = machine_main

    barrier = threading.Barrier(2)
    seen = {}

    def worker():
        mine = ReasoningStateMachine()
        agent.state_machine = mine
        barrier.wait(timeout=30)  # both bindings are now in place
        seen["worker_read"] = agent.state_machine
        seen["worker_own"] = mine

    thread = threading.Thread(target=worker, name="rel025-binding")
    thread.start()
    barrier.wait(timeout=30)
    seen["main_read"] = agent.state_machine
    thread.join(timeout=30)

    assert seen["worker_read"] is seen["worker_own"]
    assert seen["main_read"] is machine_main


def test_sequential_turns_keep_independent_histories(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry
):
    """No-regression guard: back-to-back turns each complete on their own machine."""
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    first = agent.process_message("hello")
    second = agent.process_message("hello")
    assert first.metadata["task_state"] == TaskState.COMPLETED.value
    assert second.metadata["task_state"] == TaskState.COMPLETED.value
    assert agent.current_state == TaskState.COMPLETED
