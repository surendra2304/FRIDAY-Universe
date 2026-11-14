"""TASK-REL-031 — the REL-025 follow-up: per-turn state beyond the state machine.

TASK-REL-025 scoped the turn's ReasoningStateMachine per execution
context, and its own report flagged the remaining shared attributes that
follow the identical per-turn-replaced pattern on the FridayAgent
singleton: ``_processed_tool_ids``, ``_processed_tool_signatures`` and
``task_context``. They race the same way whenever a chat turn
(``run_in_executor``) and a voice turn (``asyncio.to_thread``) — or a
zombie turn abandoned by the chat timeout — overlap:

- ``process_message`` CLEARS the two replay-guard sets at every turn
  start, so a turn that starts while another is mid-flight wipes the
  in-flight turn's guards: a tool the first turn already executed can
  execute a second time (duplicate side effects).
- The same clearing is the only thing masking the opposite hazard: two
  turns in flight at once share one signature set, so turn B's first
  legitimate call is refused as a "Repeated tool operation" merely
  because turn A ran the same tool with the same arguments.
- ``task_context`` is overwritten by whichever turn planned last, so a
  turn's observations and its finalize step (which extracts the
  long-term summary into memory) can land on the OTHER turn's context.

Fix: the same REL-025 pattern — the three attributes live behind
properties bound to the execution context (ContextVar), with the most
recent binding kept as a fallback for out-of-turn diagnostic reads, and
the parallel-safe tool batch propagates the turn's context into its
worker threads (``copy_context``) so within-turn dedup still sees one
shared guard set per turn.

These tests fail on clean main and pass with the fix.
"""

import threading
from types import SimpleNamespace

from friday.agent.agent import FridayAgent
from friday.agent.cognitive import CognitivePhase
from friday.agent.state import TaskState
from friday.core.types import AgentResponse, ToolCall
from friday.memory.task_context import ActiveTaskContext

COGNITIVE_INPUT = "Describe the trade-offs of tidal power for coastal cities in detail"
TOOL_ARGS = {"category": "os"}


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


def _fresh_turn_guards(agent):
    """Exactly what process_message does at turn start (fresh guard sets)."""
    agent._processed_tool_ids = set()
    agent._processed_tool_signatures = set()


def test_replay_guards_are_scoped_per_context(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry
):
    """Two threads binding guard sets at the same time each keep their own."""
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    barrier = threading.Barrier(2)
    seen = {}

    def worker():
        _fresh_turn_guards(agent)
        agent._processed_tool_ids.add("worker-call")
        agent._processed_tool_signatures.add("worker-sig")
        barrier.wait(timeout=30)  # both threads have now bound + mutated
        seen["ids"] = set(agent._processed_tool_ids)
        seen["sigs"] = set(agent._processed_tool_signatures)

    agent._processed_tool_ids = {"main-call"}
    agent._processed_tool_signatures = {"main-sig"}
    thread = threading.Thread(target=worker, name="rel030-guards")
    thread.start()
    barrier.wait(timeout=30)
    main_ids = set(agent._processed_tool_ids)
    main_sigs = set(agent._processed_tool_signatures)
    thread.join(timeout=30)

    assert seen["ids"] == {"worker-call"}, f"worker saw {seen['ids']}"
    assert seen["sigs"] == {"worker-sig"}, f"worker saw {seen['sigs']}"
    assert main_ids == {"main-call"}, f"main saw {main_ids}"
    assert main_sigs == {"main-sig"}, f"main saw {main_sigs}"


def test_task_context_is_scoped_per_context(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry
):
    """Concurrent turns plan into their own ActiveTaskContext, never each other's."""
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    barrier = threading.Barrier(2)
    seen = {}

    def worker():
        ctx = ActiveTaskContext(goal="worker goal")
        agent.task_context = ctx
        barrier.wait(timeout=30)  # both bindings are now in place
        seen["goal"] = agent.task_context.goal
        seen["own"] = agent.task_context is ctx

    main_ctx = ActiveTaskContext(goal="main goal")
    agent.task_context = main_ctx
    thread = threading.Thread(target=worker, name="rel030-taskctx")
    thread.start()
    barrier.wait(timeout=30)
    main_goal = agent.task_context.goal
    main_own = agent.task_context is main_ctx
    thread.join(timeout=30)

    assert seen["goal"] == "worker goal" and seen["own"], f"worker saw {seen}"
    assert main_goal == "main goal" and main_own, "main thread lost its own task_context"


def test_concurrent_turns_do_not_block_each_others_identical_tool_call(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry
):
    """Cross-turn false-positive dedup: B's first call is not A's repeat.

    Both turns are in flight (both past turn start). A executes
    get_system_info; B then issues the same tool with the same arguments
    under a different call id. On clean main the shared signature set
    makes B's legitimate call a 'Repeated tool operation' refusal.
    """
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    barrier = threading.Barrier(2)
    results = {}

    def turn_a():
        _fresh_turn_guards(agent)
        barrier.wait(timeout=30)  # both turns have started
        results["a"] = agent._execute_single_tool_call_internal(
            ToolCall(id="a-call-1", name="get_system_info", arguments=dict(TOOL_ARGS))
        )
        barrier.wait(timeout=30)  # A's execution is complete before B calls

    def turn_b():
        _fresh_turn_guards(agent)
        barrier.wait(timeout=30)
        barrier.wait(timeout=30)
        results["b"] = agent._execute_single_tool_call_internal(
            ToolCall(id="b-call-1", name="get_system_info", arguments=dict(TOOL_ARGS))
        )

    ta = threading.Thread(target=turn_a, name="rel030-turn-a")
    tb = threading.Thread(target=turn_b, name="rel030-turn-b")
    ta.start()
    tb.start()
    ta.join(timeout=60)
    tb.join(timeout=60)
    assert not ta.is_alive() and not tb.is_alive()

    assert not results["a"].is_error, f"A's own call failed: {results['a'].content}"
    assert not results["b"].is_error, (
        "B's first legitimate call was refused as a repeat of A's: "
        f"{results['b'].content}"
    )


class _BlockingExecutionWithToolUse:
    """execute_complex_task stub: uses a tool, parks mid-turn, repeats the call."""

    def __init__(self, agent):
        self.agent = agent
        self.entered = threading.Event()
        self.release = threading.Event()
        self.first_result = None
        self.repeat_result = None

    def __call__(self, goal, context=None):
        call = ToolCall(id="a-call-1", name="get_system_info", arguments=dict(TOOL_ARGS))
        self.first_result = self.agent._execute_single_tool_call_internal(call)
        self.entered.set()
        if not self.release.wait(timeout=60):
            raise RuntimeError("test harness: release was never signalled")
        # After the other turn has run its turn start (which on clean main
        # CLEARS the shared guard sets), repeat the exact same call: the
        # turn's own replay guard must still refuse it.
        self.repeat_result = self.agent._execute_single_tool_call_internal(call)
        return AgentResponse(
            content="blocking execution finished",
            is_done=True,
            metadata={"is_successful": True},
        )


def test_turn_start_does_not_wipe_inflight_turns_replay_guards(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry
):
    """The production shape: B starts (and finishes) while A is mid-turn.

    On clean main, B's turn start clears the shared guard sets, so A's
    repeated call executes a second time — the duplicate-side-effect
    hazard REL-025's report predicted for these attributes.
    """
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    _stub_cognitive_decision(agent)
    blocking = _BlockingExecutionWithToolUse(agent)
    agent.execute_complex_task = blocking

    outcome = {}

    def run_turn_a():
        try:
            outcome["response"] = agent.process_message(COGNITIVE_INPUT)
        except Exception as exc:  # captured for assertion
            outcome["error"] = exc

    thread_a = threading.Thread(target=run_turn_a, name="rel030-turn-a")
    thread_a.start()
    assert blocking.entered.wait(timeout=30), "turn A never reached execution"
    assert blocking.first_result is not None and not blocking.first_result.is_error, (
        f"A's first call failed: {blocking.first_result and blocking.first_result.content}"
    )

    # Turn B runs a full turn on the same singleton while A is parked.
    response_b = agent.process_message("hello")
    assert response_b.metadata["task_state"] == TaskState.COMPLETED.value

    blocking.release.set()
    thread_a.join(timeout=30)
    assert not thread_a.is_alive()
    assert "error" not in outcome, f"turn A raised {outcome.get('error')!r}"

    repeat = blocking.repeat_result
    assert repeat is not None and repeat.is_error, (
        "A's repeated tool call executed again — its replay guards were "
        "wiped by turn B's turn start"
    )
    assert (
        "Duplicate tool call ID" in repeat.content
        or "Repeated tool operation" in repeat.content
    ), f"unexpected refusal shape: {repeat.content}"


def test_sequential_dedup_still_applies_within_one_turn(
    mock_settings, mock_llm_provider, memory_buffer, tool_registry
):
    """No-regression guard: within one turn, a repeat is still refused."""
    agent = _make_agent(mock_settings, mock_llm_provider, memory_buffer, tool_registry)
    _fresh_turn_guards(agent)
    call = ToolCall(id="solo-1", name="get_system_info", arguments=dict(TOOL_ARGS))
    first = agent._execute_single_tool_call_internal(call)
    second = agent._execute_single_tool_call_internal(call)
    assert not first.is_error
    assert second.is_error and "Duplicate tool call ID" in second.content
