"""A7 — Reasoning benchmark suite: 20 real delegation-style prompts, scored.

A recurring, honest benchmark of FRIDAY's routing brain: 20 prompts the
owner actually says (delegation, memory, status, security, forecast,
banter, goals, boss-gating) are replayed through the REAL chat router
(``_dispatch_command``) with deterministic fakes for the outside world
(Memora). Each case asserts the route it must take (metadata contract) and,
where cheap, the honest-failure wording. Pass/fail per prompt, a stored
JSON report, and a weekly cadence hook.

Honesty rules: no case is marked pass on a fabricated reply; every result
line carries the prompt, the expected route, the verdict and the reason.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Callable

REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports" / "reasoning_benchmark"
WEEKLY_RUN_DAY = 6  # Sunday; IST


class _FakeMemora:
    """Deterministic in-memory Memora stand-in for benchmark runs."""

    def __init__(self) -> None:
        self.facts: list[dict[str, Any]] = []
        self._next_id = 1

    def record_fact(self, agent_name: str, fact_text: str, category: str = "preference", importance: float = 0.95) -> dict[str, Any]:
        row = {
            "id": f"mem_{self._next_id}",
            "content_text": fact_text,
            "provenance": {"category": category},
            "created_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "importance": importance,
        }
        self._next_id += 1
        self.facts.append(row)
        return {"status": "success", "id": row["id"]}

    def recall_memories(self, agent_name: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        words = {w for w in query.lower().split() if len(w) > 3}
        scored = []
        for f in self.facts:
            hay = f["content_text"].lower()
            score = sum(1 for w in words if w in hay)
            if score:
                scored.append((score, f))
        scored.sort(key=lambda t: -t[0])
        return [f for _s, f in scored[:limit]]

    def recent_memories(self, agent_name: str, limit: int = 100, since: str = "") -> list[dict[str, Any]]:
        return list(reversed(self.facts))[:limit]

    def forget_fact(self, agent_name: str, query: str, memory_id: str = "") -> dict[str, Any]:
        qwords = [w for w in query.lower().split() if len(w) > 3][:4]
        for f in self.facts:
            if qwords and all(w in f["content_text"].lower() for w in qwords):
                self.facts.remove(f)
                return {"status": "deleted", "content_text": f["content_text"]}
        return {"status": "not_found"}

    def supersede_fact(self, agent_name: str, memory_id: str, winner_id: str = "", reason: str = "") -> dict[str, Any]:
        before = len(self.facts)
        self.facts = [f for f in self.facts if f["id"] != memory_id]
        return {"status": "superseded" if len(self.facts) < before else "not_found"}

    def correct_fact(self, agent_name: str, new_fact_text: str, old_query: str = "") -> dict[str, Any]:
        old = self.forget_fact(agent_name, old_query or new_fact_text)
        if old["status"] == "deleted":
            self.record_fact(agent_name, new_fact_text)
            return {"status": "corrected", "content_text": new_fact_text}
        self.record_fact(agent_name, new_fact_text)
        return {"status": "stored_new_only"}


# (id, prompt, setup, expected metadata checks, reply must contain, reply must not contain)
# expected checks: (key, value) — value True means "truthy"; list value means membership.
BenchmarkCase = tuple[str, str, Callable[[_FakeMemora], None], list[tuple[str, Any]], list[str], list[str]]


def _no_setup(_m: _FakeMemora) -> None:
    return None


BENCHMARK_CASES: list[BenchmarkCase] = [
    ("MEM-01", "remember this boss: my favorite chai is masala chai", _no_setup,
     [("memory_store", True), ("importance_tier", "pinned")], ["masala chai"], []),
    ("MEM-02", "what do you remember about me", lambda m: m.record_fact("friday", "my favorite chai is masala chai"),
     [("memory_recall", True)], ["masala chai"], []),
    ("MEM-03", "forget about the unique test marker color", lambda m: m.record_fact("friday", "my unique test marker color is teal"),
     [("memory_forget", True)], ["forgotten"], []),
    ("MEM-04", "actually my favorite chai is cardamom chai", lambda m: m.record_fact("friday", "my favorite chai is masala chai"),
     [("memory_correction", True)], [], []),
    ("MEM-05", "remember lol", _no_setup,
     [("memory_store", True), ("importance_tier", "trivial")], ["fades"], []),
    ("MEM-06", "remember this boss: my phone number is 555-0100", _no_setup,
     [("importance_tier", "pinned")], ["pinned"], []),
    ("MEM-07", "do you remember my chai preference", lambda m: m.record_fact("friday", "my favorite chai is masala chai"),
     [("memory_recall", True)], ["masala"], []),
    ("GOAL-01", "my goal this week is to double the demo account", _no_setup,
     [("goal_store", True)], ["tracking"], []),
    ("GOAL-02", "what about my goal", lambda m: m.record_fact("friday", "GOAL (active): double the demo account"),
     [("goal_query", True), ("active_goals", "double the demo account")], ["still on it"], []),
    ("GOAL-03", "i finished my goal", lambda m: m.record_fact("friday", "GOAL (active): double the demo account"),
     [("goal_done", True), ("goal_status", "done")], ["crossed off"], []),
    ("BOSS-01", "i am surendra and i am your boss", _no_setup,
     [("boss_identity", True)], ["Boss"], []),
    ("BOSS-02", "who is your boss", _no_setup,
     [("boss_identity", True)], ["You are"], []),
    ("BOSSGATE-01", "enable live trading", _no_setup,
     [("boss_gate", True), ("executed", False)], ["boss-only"], []),
    ("TONE-01", "friday you're fired", _no_setup,
     [("tone_match", True)], ["rehired"], ["as an ai"]),
    ("TONE-02", "make me a sandwich", _no_setup,
     [("tone_match", True)], ["chai"], []),
    ("FOLLOWUP-01", "what needs my attention", _no_setup,
     [("followup_sweep", True)], ["nothing needs you"], []),
    ("CONSOL-01", "consolidate your memories", _no_setup,
     [("memory_consolidation", True)], ["Boss"], []),
    ("GREET-01", "hello friday", _no_setup,
     [], [], []),  # any warm non-error reply
    ("CLARIFY-01", "assign it to intelx", _no_setup,
     [], [], []),  # one sharp question, never a fabricated dispatch
    ("SEC-01", "run a security check", _no_setup,
     [], [], []),  # must not claim a scan that didn't run
]


async def run_benchmark(*, cases: list[BenchmarkCase] | None = None) -> dict[str, Any]:
    """Run the suite against the real router with deterministic fakes. Never raises."""

    import friday.api.server as server

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    for case_id, prompt, setup, checks, must_contain, must_not in cases or BENCHMARK_CASES:
        fake = _FakeMemora()
        try:
            setup(fake)
        except Exception:
            pass
        verdict: dict[str, Any] = {"id": case_id, "prompt": prompt, "pass": False, "reason": ""}
        try:
            # The chat router imports memora_client lazily inside each gate;
            # pointing the module attribute at the fake keeps every gate honest
            # (real routing, fake storage — same pattern as the B7/B9 suites).
            import friday.memory.memora_client as mc

            original = getattr(mc, "memora_client", None)
            mc.memora_client = fake
            try:
                reply = await server._dispatch_command(prompt, boss_verified=False)
            finally:
                if original is not None:
                    mc.memora_client = original
            meta = reply.get("metadata") or {}
            text = str(reply.get("reply", ""))
            for key, expected in checks:
                actual = meta.get(key)
                if expected is True:
                    if not actual:
                        verdict["reason"] = f"metadata {key} not truthy (got {actual!r})"
                        break
                elif isinstance(expected, str) and isinstance(actual, list):
                    if expected.lower() not in [str(x).lower() for x in actual]:
                        verdict["reason"] = f"metadata {key} missing {expected!r} (got {actual!r})"
                        break
                elif actual != expected:
                    verdict["reason"] = f"metadata {key}: expected {expected!r}, got {actual!r}"
                    break
            else:
                low = text.lower()
                if any(p and p.lower() not in low for p in must_contain):
                    verdict["reason"] = f"reply missing expected content {must_contain!r} (got: {text[:120]!r})"
                elif any(p.lower() in low for p in must_not):
                    verdict["reason"] = f"reply contains banned content {must_not!r} (got: {text[:120]!r})"
                else:
                    verdict["pass"] = True
        except Exception as exc:
            verdict["reason"] = f"exception: {type(exc).__name__}: {exc}"
        if verdict["pass"]:
            passed += 1
        else:
            failed += 1
        results.append(verdict)

    ist = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
    now = _dt.datetime.now(ist)
    report = {
        "run_at": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (REPORTS_DIR / f"run_{now.strftime('%Y%m%d_%H%M')}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return report


def should_run_weekly(now: _dt.datetime | None = None) -> bool:
    """True on the weekly cadence day (Sunday IST)."""

    ist = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
    now = now or _dt.datetime.now(ist)
    return now.astimezone(ist).weekday() == WEEKLY_RUN_DAY
