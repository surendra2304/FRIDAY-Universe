"""
Real Deep Layer 9 Tests — Awesome Harness Engineering → FRIDAY core.

Real functional tests for
FRIDAY/apps/core/src/friday_core/real_harness_engineering.py:
token accounting, context compaction, planning graphs, typed tools,
permission gates and approvals, verification loops, tracing, checkpoints,
human interrupts, evals, harness audits and the bounded agent loop.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from friday_core.real_harness_engineering import (  # noqa: E402
    HARNESS_PRIMITIVES,
    PRIMITIVE_WEIGHTS,
    AgentLoop,
    ApprovalRequest,
    Check,
    Checkpoint,
    ContextBudget,
    ContextCompactor,
    EvalCase,
    EvalSuite,
    HarnessBlueprint,
    HarnessEngine,
    HumanApprovalQueue,
    HumanInterface,
    Interrupt,
    LoopAction,
    LoopResult,
    Message,
    ParamSpec,
    PermissionGate,
    PermissionRule,
    Plan,
    Span,
    StateStore,
    Subtask,
    TaskDecomposer,
    ToolRegistry,
    ToolSpec,
    Trace,
    Tracer,
    VerificationLoop,
    default_registry,
    diff_states,
    estimate_tokens,
    pass_at_k,
    percentile,
    token_overlap,
    truncate_to_tokens,
    validate_arguments,
    engine,
)


def _chat(turns=8, words="lorem ipsum dolor sit amet "):
    return [Message("user", f"Message {index}: " + words * 6) for index in range(turns)]


# ── Token accounting ──────────────────────────────────────────────────────

class TestTokenAccounting:
    def test_estimate_tokens(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens("a b c") == 3
        assert estimate_tokens("hello world") == 4          # two 5-char words
        assert estimate_tokens("x" * 12) == 3               # ceil(12 / 4)
        assert estimate_tokens("a" * 40) > estimate_tokens("a" * 8)

    def test_truncate_to_tokens(self):
        assert truncate_to_tokens("", 10) == ""
        assert truncate_to_tokens("hello world foo bar", 4) == "hello world"
        assert truncate_to_tokens("hello", 0) == ""
        assert estimate_tokens(truncate_to_tokens("word " * 50, 10)) <= 10

    def test_message_tokens_include_role(self):
        message = Message("user", "hello world")
        assert message.tokens == estimate_tokens("hello world") + estimate_tokens("user") + 2
        assert message.as_dict()["tokens"] == message.tokens
        assert Message("system", "x").tokens > Message("u", "x").tokens

    def test_budget_maths(self):
        budget = ContextBudget(window=1000, reserve_output=200, system_tokens=100)
        assert budget.available() == 700
        messages = [Message("user", "x" * 400)]
        assert budget.used(messages) > 0
        assert budget.fits(messages) is True
        assert 0 < budget.usage(messages) < 1
        assert budget.headroom(messages) == 700 - budget.used(messages)
        assert ContextBudget(window=10, reserve_output=20).available() == 0
        assert ContextBudget(window=10, reserve_output=20).usage(messages) == 1.0

    def test_budget_validation(self):
        with pytest.raises(ValueError):
            ContextBudget(window=0)
        with pytest.raises(ValueError):
            ContextBudget(window=100, reserve_output=-1)


# ── Compaction ────────────────────────────────────────────────────────────

class TestContextCompactor:
    def _compactor(self, strategy="summarise"):
        return ContextCompactor(
            ContextBudget(window=120, reserve_output=20),
            strategy=strategy, keep_recent=3, summary_tokens=40,
        )

    def test_no_compaction_when_it_fits(self):
        messages = [Message("user", "short")]
        result = self._compactor().compact(messages)
        assert result.fits is True
        assert result.dropped == 0
        assert result.tokens_before == result.tokens_after
        assert result.saved == 0

    @pytest.mark.parametrize("strategy", ContextCompactor.STRATEGIES)
    def test_every_strategy_fits(self, strategy):
        messages = _chat()
        result = self._compactor(strategy).compact_until_fits(messages, "lorem")
        assert result.fits is True
        assert result.strategy == strategy
        assert result.tokens_after < result.tokens_before
        assert result.saved == result.tokens_before - result.tokens_after
        assert result.ratio < 1.0
        assert result.dropped > 0

    def test_summarise_keeps_a_summary(self):
        result = self._compactor("summarise").compact(_chat(), "lorem")
        assert result.summarised == 1
        assert result.summary
        assert "lorem" in result.summary.lower()
        assert result.messages[0].role == "summary"
        assert result.as_dict()["summarised"] == 1

    def test_truncate_drops_without_summary(self):
        result = self._compactor("truncate").compact(_chat(), "lorem")
        assert result.summarised == 0
        assert result.summary == ""
        assert all(message.role == "user" for message in result.messages)

    def test_sliding_window_keeps_recent(self):
        messages = _chat(10)
        result = self._compactor("sliding").compact(messages, "lorem")
        kept = [message.content for message in result.messages]
        assert messages[-1].content in kept
        assert messages[0].content not in kept

    def test_pinned_messages_survive(self):
        messages = _chat()
        messages.insert(0, Message("system", "You are FRIDAY, be exact.", pinned=True))
        result = self._compactor("summarise").compact(messages, "lorem")
        assert result.messages[0].content == "You are FRIDAY, be exact."
        assert result.messages[0].role == "system"
        assert result.fits is True

    def test_hierarchical_tiers(self):
        compactor = self._compactor("hierarchical")
        text = compactor._hierarchical_summary(_chat(12), "lorem")
        assert text
        assert estimate_tokens(text) <= compactor.summary_tokens

    def test_summarise_respects_max_tokens(self):
        compactor = self._compactor()
        text = compactor.summarise(_chat(6), "lorem", max_tokens=30)
        assert estimate_tokens(text) <= 30
        assert compactor.summarise([], "x") == ""

    def test_summary_relevance(self):
        compactor = self._compactor()
        messages = [Message("user", "The deployment failed. Unrelated chatter follows.")]
        summary = compactor.summarise(messages, "deployment failed", 40)
        assert "deployment" in summary.lower()

    def test_unknown_strategy(self):
        with pytest.raises(ValueError):
            ContextCompactor(ContextBudget(), strategy="magic")


# ── Planning ──────────────────────────────────────────────────────────────

class TestPlan:
    def _plan(self):
        return TaskDecomposer().decompose("Ship feature", [
            {"task_id": "a", "title": "Design", "est_tokens": 100},
            {"task_id": "b", "title": "Implement", "depends_on": ["a"], "est_tokens": 500},
            {"task_id": "c", "title": "Docs", "est_tokens": 300, "risk": "medium"},
            {"task_id": "d", "title": "Release", "depends_on": ["b", "c"], "est_tokens": 50},
        ])

    def test_sequential_decomposition(self):
        plan = TaskDecomposer().decompose("Do it", ["first", "second", "third"])
        assert [task.task_id for task in plan.subtasks] == ["s1", "s2", "s3"]
        assert plan.index["s2"].depends_on == ["s1"]
        assert plan.topological_order() == ["s1", "s2", "s3"]
        assert plan.batches() == [["s1"], ["s2"], ["s3"]]

    def test_dependency_graph(self):
        plan = self._plan()
        assert plan.topological_order() == ["a", "b", "c", "d"]
        assert plan.batches() == [["a", "c"], ["b"], ["d"]]
        assert plan.total_tokens() == 950

    def test_critical_path(self):
        plan = self._plan()
        assert plan.critical_path() == ["a", "b", "d"]
        assert plan.path_weight() == 650
        assert plan.path_weight(["c", "d"]) == 350

    def test_risk_ranking(self):
        plan = self._plan()
        assert plan.risk_ranking()[0] == "c"       # only medium-risk task
        assert plan.risk_ranking()[-1] in ("a", "b", "d")

    def test_split_by_budget(self):
        plan = self._plan()
        groups = TaskDecomposer().split_by_budget(plan, 400)
        assert groups == [["a"], ["b"], ["c", "d"]]
        assert sum(plan.index[t].est_tokens for t in groups[2]) <= 400
        with pytest.raises(ValueError):
            TaskDecomposer().split_by_budget(plan, 0)

    def test_cycles_and_bad_graphs(self):
        with pytest.raises(ValueError):
            Plan("x", [Subtask("a", "A", ["b"]), Subtask("b", "B", ["a"])])
        with pytest.raises(ValueError):
            Plan("x", [Subtask("a", "A", ["ghost"])])
        with pytest.raises(ValueError):
            Plan("x", [Subtask("a", "A"), Subtask("a", "A again")])
        with pytest.raises(ValueError):
            TaskDecomposer().decompose("nothing", [])

    def test_subtask_validation(self):
        with pytest.raises(ValueError):
            Subtask("a", "A", est_tokens=0)
        with pytest.raises(ValueError):
            Subtask("a", "A", risk="extreme")
        task = Subtask("a", "A", ["b"], 100, "high")
        assert task.as_dict()["risk"] == "high"

    def test_as_dict(self):
        payload = self._plan().as_dict()
        assert payload["goal"] == "Ship feature"
        assert payload["critical_path"] == ["a", "b", "d"]
        assert len(payload["subtasks"]) == 4


# ── Tools ─────────────────────────────────────────────────────────────────

class TestToolRegistry:
    def _registry(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            "greet", "Say hello.",
            [ParamSpec("name"), ParamSpec("times", type="integer", required=False,
                                          default=1),
             ParamSpec("shout", type="boolean", required=False, default=False),
             ParamSpec("mode", required=False, default="plain",
                       enum=("plain", "loud"))],
            risk="low", cost=4),
            lambda name, times=1, shout=False, mode="plain": (
                (name.upper() if shout or mode == "loud" else name) * int(times)),
        )
        return registry

    def test_registration_and_lookup(self):
        registry = self._registry()
        assert registry.names() == ["greet"]
        assert len(registry) == 1
        assert "greet" in registry
        assert registry.get("greet").risk == "low"
        assert registry.get("nope") is None
        assert registry.risk_of("nope") == "high"
        with pytest.raises(ValueError):
            registry.register(ToolSpec("greet", "dupe"), lambda: None)

    def test_schema(self):
        spec = self._registry().get("greet")
        schema = spec.schema()
        assert schema["parameters"]["times"]["default"] == 1
        assert schema["parameters"]["mode"]["enum"] == ["plain", "loud"]
        assert spec.required() == ["name"]
        assert "greet(name)" in self._registry().describe()

    def test_validation_coerces_types(self):
        result = self._registry().validate(
            "greet", {"name": 7, "times": "3", "shout": "true"})
        assert result.ok is True
        assert result.cleaned == {"name": "7", "times": 3, "shout": True, "mode": "plain"}

    def test_validation_errors(self):
        registry = self._registry()
        assert registry.validate("greet", {}).ok is False
        assert registry.validate("greet", {"name": "a", "extra": 1}).errors[0].field == "extra"
        assert registry.validate("greet", {"name": "a", "mode": "quiet"}).ok is False
        assert registry.validate("greet", {"name": "a", "times": "many"}).ok is False
        assert registry.validate("greet", {"name": "a", "shout": "maybe"}).ok is False
        assert registry.validate("ghost", {}).ok is False
        errors = registry.validate("greet", {"name": "a", "times": True})
        assert errors.ok is False

    def test_validate_arguments_standalone(self):
        spec = ToolSpec("f", "f", [ParamSpec("x", type="number")])
        result = validate_arguments(spec, {"x": "2.5"})
        assert result.cleaned == {"x": 2.5}
        assert validate_arguments(spec, {"x": "abc"}).ok is False

    def test_call_success(self):
        result = self._registry().call("greet", {"name": "friday", "times": 2})
        assert result.ok is True
        assert result.value == "fridayfriday"
        assert result.cost == 4
        assert result.observation() == "fridayfriday"
        assert self._registry().call("greet", {"name": "f", "shout": True}).value == "F"

    def test_call_failures_are_observations(self):
        registry = self._registry()
        unknown = registry.call("ghost", {})
        assert unknown.ok is False and "unknown tool" in unknown.error
        invalid = registry.call("greet", {"name": "a", "times": "x"})
        assert invalid.ok is False and "times" in invalid.error
        assert invalid.observation().startswith("error:")

    def test_handler_exception(self):
        registry = ToolRegistry()
        registry.register(ToolSpec("boom", "Fails."), lambda: 1 / 0)
        result = registry.call("boom", {})
        assert result.ok is False
        assert "ZeroDivisionError" in result.error

    def test_describe(self):
        text = self._registry().describe()
        assert "greet(name)" in text
        assert "[low]" in text

    def test_default_registry_is_functional(self):
        registry = default_registry({"a.py": "import os\nprint(os.getcwd())\n"})
        assert registry.call("read_file", {"path": "a.py"}).value.startswith("import os")
        written = registry.call("write_file", {"path": "b.py", "content": "x = 1\n"})
        assert written.value.startswith("created b.py")
        assert registry.call("read_file", {"path": "b.py"}).value == "x = 1\n"
        assert registry.call("grep", {"pattern": "getcwd"}).value.startswith("a.py:2")
        assert registry.call("grep", {"pattern": "getcwd", "path": "b.py"}).value == "no matches"
        assert registry.call("count_tokens", {"text": "hello world"}).value == 4
        assert registry.call("check_syntax", {"source": "x = 1\n"}).value == "ok"
        assert "syntax error" in registry.call("check_syntax", {"source": "def f(:"}).value
        assert registry.call("read_file", {"path": "missing"}).ok is False
        updated = registry.call("write_file", {"path": "b.py", "content": "y = 2\n"})
        assert updated.value.startswith("updated b.py")


# ── Permissions ───────────────────────────────────────────────────────────

class TestPermissionGate:
    def _gate(self, rules=None, registry=None):
        return PermissionGate(rules if rules is not None else None,
                              registry=registry or default_registry())

    def test_default_rules(self):
        gate = self._gate()
        assert gate.decide("read_file", {"path": "a"}).allowed is True
        ask = gate.decide("write_file", {"path": "a", "content": "b"})
        assert ask.requires_approval is True and ask.allowed is False
        assert ask.risk == "medium"
        deny = gate.decide("delete_everything", {})
        assert deny.allowed is False and deny.requires_approval is False
        assert "delete_*" in deny.reason

    def test_argument_patterns(self):
        gate = self._gate()
        assert gate.decide("run_command", {"command": "pytest -q"}).requires_approval is True
        denied = gate.decide("run_command", {"command": "rm -rf /"})
        assert denied.allowed is False and denied.requires_approval is False

    def test_default_deny(self):
        gate = self._gate()
        decision = gate.decide("exfiltrate", {})
        assert decision.allowed is False
        assert decision.reason == "no rule permits 'exfiltrate'"

    def test_custom_rules_and_specificity(self):
        rules = [
            PermissionRule("shell_*", "deny", priority=1),
            PermissionRule("shell_read", "allow", priority=10),
            PermissionRule("db_*", "ask", argument="query", pattern="select*", priority=5),
        ]
        registry = default_registry()
        gate = PermissionGate(rules, registry=registry)
        assert gate.decide("shell_read", {}).allowed is True
        assert gate.decide("shell_write", {}).allowed is False
        assert gate.decide("db_query", {"query": "select 1"}).requires_approval is True
        assert gate.decide("db_query", {"query": "drop table"}).allowed is False

    def test_risk_tier_filtering(self):
        registry = default_registry()
        gate = PermissionGate([PermissionRule("write_file", "allow", risk_tier="high")],
                              registry=registry)
        assert gate.decide("write_file", {}).allowed is False   # medium-risk tool
        gate_high = PermissionGate([PermissionRule("write_file", "allow", risk_tier="medium")],
                                   registry=registry)
        assert gate_high.decide("write_file", {}).allowed is True

    def test_allowed_tools_and_report(self):
        gate = self._gate()
        allowed = gate.allowed_tools()
        assert "read_file" in allowed
        assert "write_file" not in allowed
        report = gate.report()
        assert report["checks"] == 5
        assert report["allowed"] == len(allowed)
        assert report["approval"] == 1
        assert report["rules"] == len(gate.rules)
        assert gate.decide("read_file", {}).as_dict()["risk"] == "low"

    def test_rule_validation(self):
        with pytest.raises(ValueError):
            PermissionRule("x", decision="maybe")
        with pytest.raises(ValueError):
            PermissionRule("x", risk_tier="extreme")
        assert PermissionRule("a*b").specificity()[2] == 2
        assert PermissionRule("write_file", argument="p", pattern="*.py").specificity()[0] == 1


class TestApprovals:
    def test_queue_lifecycle(self):
        queue = HumanApprovalQueue()
        first = queue.submit("write_file", {"path": "a"}, "medium", "needs approval")
        second = queue.submit("deploy", {"env": "prod"}, "high", "needs approval")
        assert isinstance(first, ApprovalRequest)
        assert first.resolved is False
        assert len(queue.pending()) == 2
        assert [r.request_id for r in queue.pending(risk="high")] == [second.request_id]
        queue.resolve(first.request_id, True, "ciso")
        assert first.approved is True and first.approver == "ciso"
        assert len(queue.pending()) == 1
        assert second.as_dict()["resolved"] is False
        stats = queue.stats()
        assert stats["total"] == 2 and stats["pending"] == 1 and stats["approved"] == 1
        assert stats["by_risk"]["high"] == 1

    def test_resolve_errors(self):
        queue = HumanApprovalQueue()
        with pytest.raises(KeyError):
            queue.resolve("appr-999", True)
        request = queue.submit("x", {}, "low", "r")
        queue.resolve(request.request_id, False)
        assert queue.stats()["denied"] == 1


# ── Verification ──────────────────────────────────────────────────────────

class TestVerificationLoop:
    def _checks(self):
        return [
            Check("length", lambda artifact: (len(artifact) > 5, f"len={len(artifact)}")),
            Check("clean", lambda artifact: ("TODO" not in artifact, "no todos"), weight=2.0),
        ]

    def test_weighted_scoring(self):
        attempt = VerificationLoop(self._checks()).evaluate("hello TODO")
        assert attempt.score == pytest.approx(1 / 3, abs=1e-4)
        assert len(attempt.failures()) == 1
        passing = VerificationLoop(self._checks()).evaluate("hello there")
        assert passing.score == 1.0 and passing.passed is True
        assert passing.as_dict()["checks"][1]["weight"] == 2.0

    def test_partial_credit_threshold(self):
        loop = VerificationLoop(self._checks(), threshold=0.3)
        attempt = loop.evaluate("hello TODO")
        assert attempt.score == pytest.approx(1 / 3, abs=1e-4)
        assert attempt.passed is True
        assert VerificationLoop(self._checks(), threshold=0.9).evaluate("hello TODO").passed is False

    def test_revision_until_pass(self):
        loop = VerificationLoop(self._checks(), max_attempts=3)
        report = loop.run("hi", lambda artifact, feedback: artifact + " and more")
        assert report.passed is True
        assert report.attempts_used == 2
        assert report.attempts[0].score < report.attempts[-1].score
        assert report.final_artifact == "hi and more"
        assert report.feedback == []
        assert report.as_dict()["attempts_used"] == 2

    def test_exhausts_attempts_with_feedback(self):
        loop = VerificationLoop(self._checks(), max_attempts=2)
        report = loop.run("hi", lambda artifact, feedback: artifact)
        assert report.passed is False
        assert report.attempts_used == 2
        assert report.feedback
        assert any("length" in item for item in report.feedback)

    def test_no_revise_stops_early(self):
        report = VerificationLoop(self._checks(), max_attempts=5).run("hi")
        assert report.passed is False
        assert report.attempts_used == 1

    def test_check_exception_is_failure(self):
        loop = VerificationLoop([Check("boom", lambda artifact: 1 / 0)])
        attempt = loop.evaluate("x")
        assert attempt.passed is False
        assert "ZeroDivisionError" in attempt.checks[0].detail

    def test_validation(self):
        with pytest.raises(ValueError):
            VerificationLoop([])
        with pytest.raises(ValueError):
            VerificationLoop(self._checks(), max_attempts=0)
        with pytest.raises(ValueError):
            Check("bad", lambda artifact: (True, ""), weight=0)


# ── Observability ─────────────────────────────────────────────────────────

class TestTracing:
    def _trace(self):
        trace = Trace("trace-test")
        root = trace.add("root", start=0.0)
        root.close(10.0)
        first = trace.add("child-a", parent_id=root.span_id, start=0.0)
        first.close(2.0)
        second = trace.add("child-b", parent_id=root.span_id, start=2.0)
        second.close(10.0, status="error")
        grand = trace.add("grand", parent_id=second.span_id, start=3.0)
        grand.close(8.0)
        return trace, root, first, second, grand

    def test_span_maths(self):
        trace, root, first, second, grand = self._trace()
        assert root.duration == 10.0
        assert first.duration == 2.0
        assert second.duration == 8.0
        assert second.status == "error"
        assert trace.depth(grand.span_id) == 2
        assert trace.depth(root.span_id) == 0
        assert trace.get("missing") is None
        assert trace.children(root.span_id) == [first, second]
        assert grand.as_dict()["duration"] == 5.0

    def test_dominant_path(self):
        trace, root, _, second, grand = self._trace()
        assert trace.dominant_path() == [root.span_id, second.span_id, grand.span_id]
        assert trace.roots() == [root]

    def test_summary(self):
        trace, _, _, _, _ = self._trace()
        summary = trace.summary()
        assert summary["spans"] == 4
        assert summary["duration"] == 10.0
        assert summary["errors"] == 1
        assert summary["error_rate"] == 0.25
        assert summary["max_depth"] == 2
        assert summary["by_name"]["root"]["count"] == 1
        assert summary["slowest"] == "root"
        assert summary["p50"] > 0 and summary["p95"] >= summary["p50"]
        assert summary["dominant_path"]

    def test_empty_trace(self):
        trace = Trace("empty")
        assert trace.total_duration() == 0.0
        assert trace.dominant_path() == []
        assert trace.summary()["spans"] == 0
        assert trace.summary()["error_rate"] == 0.0

    def test_percentile(self):
        assert percentile([], 0.5) == 0.0
        assert percentile([5], 0.9) == 5.0
        assert percentile([1, 2, 3, 4], 0.5) == 2.5
        assert percentile([1, 2, 3, 4], 0.0) == 1.0
        assert percentile([1, 2, 3, 4], 1.0) == 4.0
        assert percentile([1, 2, 3, 4], 2.0) == 4.0

    def test_tracer_nests_and_records_errors(self):
        tracer = Tracer()
        with tracer.span("outer"):
            with tracer.span("inner", kind="tool"):
                pass
        assert tracer.trace.summary()["spans"] == 2
        assert tracer.trace.depth(tracer.trace.spans[1].span_id) == 1
        assert tracer.current is None

        with pytest.raises(RuntimeError):
            with tracer.span("failing"):
                raise RuntimeError("boom")
        failing = tracer.trace.spans[-1]
        assert failing.status == "error"
        assert "boom" in failing.attributes["error"]
        assert tracer.current is None


# ── State ─────────────────────────────────────────────────────────────────

class TestStateStore:
    def test_save_and_restore(self):
        store = StateStore()
        first = store.save(1, {"step": 1, "files": ["a"]})
        second = store.save(2, {"step": 2, "files": ["a", "b"]})
        assert first.verify() is True
        assert first.checkpoint_id.startswith("ckpt-001-")
        assert store.latest() is second
        assert store.restore() == {"step": 2, "files": ["a", "b"]}
        assert store.restore(first.checkpoint_id) == {"step": 1, "files": ["a"]}
        assert len(store) == 2
        assert store.get(second.checkpoint_id) is second
        with pytest.raises(KeyError):
            store.get("ckpt-999")

    def test_rollback(self):
        store = StateStore()
        store.save(1, {"step": 1})
        store.save(2, {"step": 2})
        store.save(3, {"step": 3})
        assert store.rollback() == {"step": 2}
        assert store.rollback(2) == {"step": 1}
        with pytest.raises(LookupError):
            store.rollback(5)
        with pytest.raises(ValueError):
            store.rollback(0)
        with pytest.raises(LookupError):
            StateStore().restore()

    def test_tamper_detection(self):
        store = StateStore()
        checkpoint = store.save(1, {"step": 1})
        assert checkpoint.verify() is True
        checkpoint.payload["step"] = 99
        assert checkpoint.verify() is False
        with pytest.raises(ValueError):
            store.restore(checkpoint.checkpoint_id)

    def test_diff_and_history(self):
        store = StateStore()
        first = store.save(1, {"a": 1, "b": 2})
        second = store.save(2, {"a": 1, "b": 3, "c": 4})
        diff = store.diff(first.checkpoint_id, second.checkpoint_id)
        assert diff == {"added": ["c"], "removed": [], "changed": ["b"]}
        assert diff_states({"x": 1}, {"y": 2}) == {
            "added": ["y"], "removed": ["x"], "changed": []}
        history = store.history()
        assert [entry["step"] for entry in history] == [1, 2]
        assert all(entry["verified"] for entry in history)

    def test_checkpoint_dataclass(self):
        checkpoint = Checkpoint("ckpt-x", 1, {"a": 1}, "digest")
        assert checkpoint.verify() is False
        assert checkpoint.as_dict()["step"] == 1


# ── Human in the loop ─────────────────────────────────────────────────────

class TestHumanInterface:
    def test_asks_and_answers(self):
        human = HumanInterface(auto_approve_risk="low")
        high = human.ask("Deploy to prod?", ["yes", "no"], risk="high")
        low = human.ask("Rename file?", ["yes", "no"], risk="low")
        assert high.resolved is False
        assert low.answer == "auto-approved"
        assert len(human.pending()) == 1
        assert human.stats() == {"asks": 2, "pending": 1, "answered": 1}
        human.answer(high.interrupt_id, "yes")
        assert human.pending() == []
        assert high.answer == "yes"
        assert human.stats()["answered"] == 2

    def test_errors(self):
        human = HumanInterface()
        with pytest.raises(ValueError):
            human.ask("x", [], risk="extreme")
        interrupt = human.ask("Proceed?", ["yes", "no"], risk="high")
        with pytest.raises(ValueError):
            human.answer(interrupt.interrupt_id, "maybe")
        with pytest.raises(KeyError):
            human.answer("int-999", "yes")

    def test_escalation(self):
        human = HumanInterface(auto_approve_risk="low")
        assert human.escalate("high") is True
        assert human.escalate("low") is False
        interrupt = human.ask("Risky?", risk="critical")
        assert isinstance(interrupt, Interrupt)
        assert interrupt.as_dict()["resolved"] is False


# ── Evaluation ────────────────────────────────────────────────────────────

class TestEvaluations:
    def _cases(self):
        return [
            EvalCase("c1", "2+2", "4 = four", tags=("math",)),
            EvalCase("c2", "capital of France", "Paris", tags=("geo",)),
            EvalCase("c3", "reverse a list", "use slicing", tags=("code", "math"), weight=2.0),
        ]

    def test_pass_at_k(self):
        assert pass_at_k(10, 3, 2) == pytest.approx(0.533333, abs=1e-5)
        assert pass_at_k(10, 3, 1) == pytest.approx(0.3)
        assert pass_at_k(3, 3, 2) == 1.0
        assert pass_at_k(5, 0, 1) == 0.0
        assert pass_at_k(0, 0, 1) == 0.0
        assert pass_at_k(2, 1, 5) == 1.0

    def test_token_overlap(self):
        assert token_overlap("a b", "a b c") == 1.0
        assert token_overlap("a b c", "a") == pytest.approx(1 / 3, abs=1e-4)
        assert token_overlap("", "") == 1.0
        assert token_overlap("", "text") == 0.0
        assert token_overlap("Paris", "the answer is Lyon") == 0.0

    def test_suite_scoring(self):
        report = EvalSuite(self._cases()).run(
            lambda case: "4 = four" if case.case_id == "c1" else "Lyon")
        assert len(report.results) == 3
        assert report.pass_rate() == pytest.approx(1 / 3, abs=1e-3)
        assert report.failures()[0].case_id in ("c2", "c3")
        payload = report.as_dict()
        assert payload["cases"] == 3
        assert payload["threshold"] == 0.8
        assert "c2" in payload["failures"]

    def test_weighted_score(self):
        report = EvalSuite(self._cases()).run(
            lambda case: case.expected if case.case_id != "c3" else "no")
        assert report.weighted_score() == pytest.approx(0.5)
        assert report.by_tag()["geo"]["pass_rate"] == 1.0
        assert report.by_tag()["math"]["cases"] == 2

    def test_tuple_solver_and_threshold(self):
        suite = EvalSuite(self._cases(), threshold=0.5)
        report = suite.run(lambda case: (0.6, "partial"))
        assert all(result.passed for result in report.results)
        assert report.results[0].detail == "partial"
        assert report.pass_rate() == 1.0

    def test_validation(self):
        with pytest.raises(ValueError):
            EvalSuite([])
        with pytest.raises(ValueError):
            EvalCase("c", "p", "e", weight=0)


# ── Harness audit ─────────────────────────────────────────────────────────

class TestHarnessBlueprint:
    def test_all_primitives(self):
        blueprint = HarnessBlueprint()
        review = blueprint.audit([key for key, _, _ in HARNESS_PRIMITIVES])
        assert review.score == 1.0
        assert review.grade == "A"
        assert review.missing == []
        assert review.recommendations == []

    def test_partial_build_is_graded(self):
        blueprint = HarnessBlueprint()
        review = blueprint.audit(["agent-loop", "planning", "verification"])
        assert review.present == ["agent-loop", "planning", "verification"]
        assert "permissions" in review.missing
        assert review.grade in ("C", "D")
        assert review.score < 0.5
        assert review.recommendations[0].startswith("Add permissions")
        assert len(review.missing) == len(HARNESS_PRIMITIVES) - 3
        assert review.as_dict()["grade"] == review.grade

    def test_recommendations_follow_weights(self):
        review = HarnessBlueprint().audit([])
        keys = [line.split(":")[0].split()[-1] for line in review.recommendations]
        assert keys[0] in ("agent-loop", "permissions", "verification")
        assert PRIMITIVE_WEIGHTS["agent-loop"] == 2.0
        assert len(review.recommendations) == len(HARNESS_PRIMITIVES)

    def test_unknown_primitive_and_checklist(self):
        with pytest.raises(ValueError):
            HarnessBlueprint().audit(["telepathy"])
        checklist = HarnessBlueprint().checklist().splitlines()
        assert len(checklist) == len(HARNESS_PRIMITIVES)
        assert checklist[0].startswith("[ ] agent-loop")


# ── Agent loop ────────────────────────────────────────────────────────────

class TestAgentLoop:
    def _registry(self):
        return default_registry({"a.py": "print(1)\n", "b.py": "print(2)\n"})

    def test_successful_run(self):
        registry = self._registry()
        gate = PermissionGate(registry=registry)

        def policy(task, steps):
            if not steps:
                return LoopAction(kind="tool", tool="read_file",
                                  arguments={"path": "a.py"})
            return LoopAction(kind="respond", text=f"read: {steps[-1].observation}")

        result = AgentLoop(registry=registry, gate=gate).run("read a.py", policy)
        assert isinstance(result, LoopResult)
        assert result.stop_reason == "final_answer"
        assert result.succeeded is True
        assert result.final_text == "read: print(1)\n"
        assert result.tool_sequence() == ["read_file"]
        assert result.tokens_used > 0
        assert result.steps[0].allowed is True
        assert result.as_dict()["stop_reason"] == "final_answer"

    def test_loop_detection(self):
        registry = self._registry()

        def policy(task, steps):
            return LoopAction(kind="tool", tool="read_file", arguments={"path": "a.py"})

        result = AgentLoop(registry=registry, max_steps=6).run("loop", policy)
        assert result.stop_reason == "loop_detected"
        assert len(result.steps) <= 2
        assert result.succeeded is False

    def test_denials_are_observations(self):
        registry = self._registry()
        gate = PermissionGate(registry=registry)

        def policy(task, steps):
            if len(steps) < 2:
                return LoopAction(kind="tool", tool=f"delete_{len(steps)}", arguments={})
            return LoopAction(kind="respond", text="stopped after denials")

        result = AgentLoop(registry=registry, gate=gate, max_steps=5).run("deny", policy)
        assert result.denials == 2
        assert result.stop_reason == "final_answer"
        assert all("denied" in step.observation for step in result.steps[:2])
        assert result.steps[0].allowed is False

    def test_approval_escalation(self):
        registry = self._registry()
        gate = PermissionGate(registry=registry)
        queue = HumanApprovalQueue()

        def policy(task, steps):
            return LoopAction(kind="tool", tool="write_file",
                              arguments={"path": "c.py", "content": "x = 1\n"})

        result = AgentLoop(registry=registry, gate=gate, approvals=queue,
                           max_steps=3).run("write", policy)
        assert result.stop_reason == "approval_required"
        assert result.succeeded is False
        assert len(result.approvals) == 1
        assert result.approvals[0].tool == "write_file"
        assert len(queue.pending()) == 1
        assert "approval required" in result.steps[-1].observation

    def test_invalid_tool_arguments(self):
        registry = self._registry()

        def policy(task, steps):
            if not steps:
                return LoopAction(kind="tool", tool="write_file", arguments={"path": "x"})
            return LoopAction(kind="respond", text="recovered")

        result = AgentLoop(registry=registry).run("bad args", policy)
        assert result.steps[0].allowed is False
        assert "content" in result.steps[0].observation
        assert result.stop_reason == "final_answer"

    def test_no_action_and_exceptions(self):
        registry = self._registry()
        assert AgentLoop(registry=registry).run("x", lambda task, steps: None).stop_reason == "no_action"

        def exploding(task, steps):
            raise RuntimeError("policy down")

        result = AgentLoop(registry=registry).run("x", exploding)
        assert result.stop_reason == "no_action"
        assert "policy error" in result.steps[0].observation

    def test_budget_exhaustion(self):
        registry = self._registry()
        result = AgentLoop(registry=registry, budget=1).run(
            "a long task description that already costs tokens", lambda task, steps: None)
        assert result.stop_reason == "budget_exhausted"
        assert result.steps == []

    def test_max_steps(self):
        registry = self._registry()
        names = ["a.py", "b.py", "a.py", "b.py", "a.py", "b.py"]

        def policy(task, steps):
            index = min(len(steps), len(names) - 1)
            return LoopAction(kind="tool", tool="read_file",
                              arguments={"path": names[index]})

        result = AgentLoop(registry=registry, max_steps=2).run("keep going", policy)
        assert result.stop_reason == "max_steps"
        assert len(result.steps) == 2

    def test_escalate_and_stop(self):
        registry = self._registry()
        escalated = AgentLoop(registry=registry).run(
            "x", lambda task, steps: LoopAction(kind="escalate", text="need a human"))
        assert escalated.stop_reason == "approval_required"
        assert escalated.steps[-1].observation == "need a human"
        stopped = AgentLoop(registry=registry).run(
            "x", lambda task, steps: LoopAction(kind="stop"))
        assert stopped.stop_reason == "policy_stop"

    def test_action_validation_and_signature(self):
        first = LoopAction(kind="tool", tool="t", arguments={"b": 2, "a": 1})
        second = LoopAction(kind="tool", tool="t", arguments={"a": 1, "b": 2})
        assert first.signature() == second.signature()
        assert first.as_dict()["arguments"] == {"b": 2, "a": 1}
        with pytest.raises(ValueError):
            LoopAction(kind="teleport")
        with pytest.raises(ValueError):
            AgentLoop(max_steps=0)
        with pytest.raises(ValueError):
            AgentLoop(budget=0)


# ── Facade ────────────────────────────────────────────────────────────────

class TestHarnessEngine:
    def _engine(self):
        return HarnessEngine(budget=ContextBudget(window=160, reserve_output=20))

    def test_describe(self):
        payload = engine.describe()
        assert "read_file" in payload["tools"]
        assert payload["rules"] == len(engine.gate.rules)
        assert payload["window"] == 8192
        assert payload["available_tokens"] == 7168
        assert len(payload["primitives"]) == 14
        assert "loop_detected" in payload["stop_reasons"]

    def test_plan_and_schedule(self):
        harness = self._engine()
        payload = harness.plan("audit repo", ["read", "check", "fix"])
        assert payload["goal"] == "audit repo"
        assert payload["critical_path"] == ["s1", "s2", "s3"]
        plan = TaskDecomposer().decompose("x", ["a", "b"])
        assert harness.schedule(plan, 450) == [["s1", "s2"]]

    def test_compact(self):
        harness = self._engine()
        result = harness.compact(_chat(8))
        assert result.fits is True
        assert result.tokens_after < result.tokens_before
        assert result.strategy in ContextCompactor.STRATEGIES

    def test_loop(self):
        harness = self._engine()
        registry = default_registry({"a.py": "x = 1\n"})
        harness.registry = registry
        harness.gate = PermissionGate(registry=registry)

        def policy(task, steps):
            if not steps:
                return LoopAction(kind="tool", tool="read_file", arguments={"path": "a.py"})
            return LoopAction(kind="respond", text="done")

        result = harness.loop("read", policy)
        assert result.stop_reason == "final_answer"
        assert result.final_text == "done"
        assert harness.approvals.stats()["total"] == 0

    def test_verify(self):
        harness = self._engine()
        checks = [Check("nonempty", lambda artifact: (bool(artifact), "must not be empty"))]
        assert harness.verify("text", checks).passed is True
        assert harness.verify("", checks).passed is False

    def test_evaluate(self):
        harness = self._engine()
        cases = [EvalCase("c1", "p", "answer", tags=("t",))]
        payload = harness.evaluate(cases, lambda case: "answer")
        assert payload["pass_rate"] == 1.0
        assert payload["by_tag"]["t"]["passed"] == 1

    def test_audit(self):
        payload = self._engine().audit(["agent-loop", "planning"])
        assert payload["score"] > 0
        assert "compaction" in payload["missing"]
        assert payload["recommendations"]

    def test_state_and_human(self):
        harness = self._engine()
        harness.state.save(1, {"done": ["a"]})
        harness.state.save(2, {"done": ["a", "b"]})
        assert harness.state.restore()["done"] == ["a", "b"]
        assert harness.state.rollback()["done"] == ["a"]
        interrupt = harness.human.ask("Proceed?", ["yes", "no"], risk="high")
        assert len(harness.human.pending()) == 1
        harness.human.answer(interrupt.interrupt_id, "no")
        assert harness.human.pending() == []
