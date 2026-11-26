"""TASK-IG-FRD-001 — Goal-loop autonomy (IG corpus idea, reel DdckMRAjAsD).

The "loop method": the owner states a GOAL plus explicit SUCCESS CRITERIA
once, gives FRIDAY the access it needs, and FRIDAY works the goal
autonomously over a long horizon — in cycles, through the same chat brain
the mission queue uses — and reports on completion instead of waiting to be
prompted step by step.

What already existed and is NOT replaced here:
- A11 goal persistence (``proactive/goals.py``) remembers a goal statement
  as a pinned Memora memory. It never *works* the goal.
- The G6/G12 mission queue (``proactive/mission_queue.py``) runs queued
  one-shot commands overnight. It has no criteria and no completion test.

What this module adds:
- A restart-safe, file-backed registry of goal loops (atomic JSON writes,
  same pattern as the mission queue).
- A deterministic default planner: one work step per success criterion,
  plus an opening "work the goal" step — no LLM needed to structure a loop.
- A cycle runner: each cycle executes the pending steps through an
  injected executor (production default: ``friday.tools.execute_command``,
  the same brain entry the mission queue executes through), accumulates
  the step outputs as evidence, and evaluates EVERY criterion against
  that evidence.
- Criteria checks: ``contains`` / ``not_contains`` (evidence text),
  ``judge`` (an injected judge callable — an LLM judge in production
  wiring, a fake in tests), ``manual`` (never auto-met; the loop ends
  BLOCKED naming the owner confirmation it still needs).
- Honest terminal states: ``completed`` only when every criterion
  evaluates met; ``failed`` when the cycle budget is exhausted with
  criteria unmet; ``blocked`` when a step errors/refuses or a manual
  criterion is the only thing left. A completion report is produced for
  every terminal loop: criteria with met/unmet + the evidence each
  judgement rests on, every step with its outcome, cycle count, times.

Nothing here invents progress: a step that the brain refuses is recorded
as refused, a criterion with no evidence is unmet, and an unreachable
store raises instead of pretending.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable, Optional

from friday.autonomous.woop import (
    format_woop_summary,
    normalise_woop,
    woop_plan,
    woop_to_criteria,
)

logger = logging.getLogger(__name__)

#: Hard bound on cycles per loop unless the owner sets otherwise — a loop
#: must never run unbounded against the fleet's free-tier quotas.
DEFAULT_MAX_CYCLES = 5
MAX_CYCLES_CEILING = 50
#: Per-step attempt bound inside one cycle.
MAX_STEP_ATTEMPTS = 2

STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"
STATUS_PAUSED = "paused"
TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_BLOCKED}

CHECK_CONTAINS = "contains"
CHECK_NOT_CONTAINS = "not_contains"
CHECK_JUDGE = "judge"
CHECK_MANUAL = "manual"
_KNOWN_CHECKS = {CHECK_CONTAINS, CHECK_NOT_CONTAINS, CHECK_JUDGE, CHECK_MANUAL}

# Executor: takes a step instruction, returns (ok: bool, output: str).
ExecutorFn = Callable[[str], "tuple[bool, str]"]
# Judge: takes (criterion dict, evidence text), returns (met: bool, why: str).
JudgeFn = Callable[[dict, str], "tuple[bool, str]"]


def _default_store_path() -> str:
    """The loop registry lives with the service's runtime data.

    Same resolution as the mission queue: the process working directory
    first (the systemd unit sets WorkingDirectory=.../FRIDAY), then the
    package-tree fallback for tests and manual runs.
    """
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "goal_loops", "loops.json"))
    here = os.path.dirname(__file__)  # .../friday/autonomous
    return os.path.abspath(
        os.path.join(here, "..", "..", ".data", "goal_loops", "loops.json")
    )


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def normalise_criterion(raw: Any, index: int) -> dict[str, Any]:
    """Validate + normalise one success criterion.

    Accepts a plain string (becomes a ``judge`` criterion — only an
    injected judge or the owner can call it met) or a dict with
    ``description`` plus ``check`` in {contains, not_contains, judge,
    manual} and ``needle`` for the text checks.
    """
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise ValueError("criterion text must not be empty")
        return {
            "id": f"c{index + 1}",
            "description": text,
            "check": CHECK_JUDGE,
            "needle": "",
        }
    if not isinstance(raw, dict):
        raise ValueError(f"criterion #{index + 1} must be a string or an object")
    description = str(raw.get("description") or "").strip()
    if not description:
        raise ValueError(f"criterion #{index + 1} needs a description")
    check = str(raw.get("check") or CHECK_JUDGE).strip().lower()
    if check not in _KNOWN_CHECKS:
        raise ValueError(
            f"criterion #{index + 1}: unknown check {check!r} "
            f"(known: {sorted(_KNOWN_CHECKS)})"
        )
    needle = str(raw.get("needle") or "").strip()
    if check in (CHECK_CONTAINS, CHECK_NOT_CONTAINS) and not needle:
        raise ValueError(
            f"criterion #{index + 1}: check {check!r} needs a 'needle' to look for"
        )
    return {
        "id": str(raw.get("id") or f"c{index + 1}"),
        "description": description,
        "check": check,
        "needle": needle,
    }


def default_plan(goal: str, criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic plan: work the goal, then one step per criterion.

    The per-criterion steps make the executor produce evidence each
    criterion can be judged against (a status check, a draft, a lookup —
    the brain decides the mechanics; the loop only asks the question).
    """
    steps = [
        {
            "id": "s1",
            "instruction": f"Work on this goal and report concrete progress: {goal}",
            "status": "pending",
            "attempts": 0,
            "result": "",
        }
    ]
    for i, crit in enumerate(criteria):
        steps.append(
            {
                "id": f"s{i + 2}",
                "instruction": (
                    "For the goal "
                    f"'{goal}', produce evidence for this success criterion: "
                    f"{crit['description']}. Report exactly what exists now, "
                    "with specifics — do not claim anything you cannot show."
                ),
                "status": "pending",
                "attempts": 0,
                "result": "",
            }
        )
    return steps


def evaluate_criterion(
    criterion: dict[str, Any],
    evidence: str,
    judge: Optional[JudgeFn] = None,
) -> dict[str, Any]:
    """Evaluate one criterion against the accumulated evidence text.

    Returns {met, why}. Never guesses: a judge criterion with no judge
    wired is unmet with that reason stated; a manual criterion is unmet
    until the owner confirms it (see ``confirm_criterion``).
    """
    check = criterion.get("check") or CHECK_JUDGE
    if check == CHECK_CONTAINS:
        hit = criterion["needle"].lower() in evidence.lower()
        return {
            "met": hit,
            "why": (
                f"evidence contains {criterion['needle']!r}"
                if hit
                else f"evidence does not contain {criterion['needle']!r}"
            ),
        }
    if check == CHECK_NOT_CONTAINS:
        hit = criterion["needle"].lower() in evidence.lower()
        return {
            "met": not hit,
            "why": (
                f"evidence still contains {criterion['needle']!r}"
                if hit
                else f"evidence is free of {criterion['needle']!r}"
            ),
        }
    if check == CHECK_MANUAL:
        return {
            "met": False,
            "why": "manual criterion — only the owner can confirm this one",
        }
    # judge
    if judge is None:
        return {
            "met": False,
            "why": "no judge wired for this criterion — unmet until judged",
        }
    try:
        met, why = judge(criterion, evidence)
    except Exception as exc:  # a broken judge must not fake a pass
        return {"met": False, "why": f"judge errored: {type(exc).__name__}: {exc}"}
    return {"met": bool(met), "why": str(why or "")}


def _default_executor(instruction: str) -> "tuple[bool, str]":
    """Production executor: the same brain entry the mission queue uses.

    Lazy import — constructing the brain is heavy and tests always inject
    their own executor.
    """
    try:
        from friday.tools.execute_command import execute_command

        result = execute_command(instruction)
    except Exception as exc:
        return False, f"executor unavailable: {type(exc).__name__}: {exc}"
    if isinstance(result, dict):
        output = str(result.get("output") or result.get("response") or result)
        ok = not bool(result.get("is_error") or result.get("error"))
        return ok, output
    return True, str(result)


class GoalLoopStore:
    """File-backed registry of goal loops (atomic writes, thread-safe)."""

    def __init__(self, store_path: Optional[str] = None) -> None:
        self._path = store_path or _default_store_path()
        self._lock = threading.RLock()
        self._cache: Optional[list[dict[str, Any]]] = None
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    # -- persistence ----------------------------------------------------
    def _load(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = list(data.get("loops") or [])
        except FileNotFoundError:
            self._cache = []
        except Exception as exc:
            logger.warning(
                "[GOAL-LOOP] registry unreadable (%s) — starting empty, file untouched",
                exc,
            )
            self._cache = []
        return self._cache

    def _save(self, loops: list[dict[str, Any]]) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"loops": loops, "saved_at": _now()}, f, indent=2)
        os.replace(tmp, self._path)

    # -- CRUD -------------------------------------------------------------
    def create(
        self,
        goal: str,
        criteria: list[Any],
        *,
        max_cycles: int = DEFAULT_MAX_CYCLES,
        source: str = "chat",
        woop: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Create a goal loop.

        TASK-FRD-045: when ``woop`` is given (a Wish/Outcome/Obstacle/
        Plan record — see ``friday.autonomous.woop``), the goal is
        structured as a WOOP record that the loop works against: the
        Outcome becomes the success criterion when the caller passes no
        explicit criteria, the Plan's if-then entries become work steps,
        and the record itself is stored on the loop. The ``goal`` text
        should be the Wish when a WOOP record is supplied.
        """
        goal_text = (goal or "").strip()
        if not goal_text:
            raise ValueError("goal must not be empty")
        woop_norm = normalise_woop(woop) if woop is not None else None
        if woop_norm is not None and not criteria:
            criteria = woop_to_criteria(woop_norm)
        if not criteria:
            raise ValueError("a goal loop needs at least one success criterion")
        norm = [normalise_criterion(c, i) for i, c in enumerate(criteria)]
        cycles = max(1, min(int(max_cycles or DEFAULT_MAX_CYCLES), MAX_CYCLES_CEILING))
        steps = woop_plan(woop_norm, norm) if woop_norm is not None else default_plan(goal_text, norm)
        loop = {
            "id": _new_id("goal"),
            "goal": goal_text,
            "criteria": norm,
            "steps": steps,
            "status": STATUS_ACTIVE,
            "cycles_run": 0,
            "max_cycles": cycles,
            "source": source,
            "created_at": _now(),
            "updated_at": _now(),
            "evaluations": [],
            "report": "",
            "history": [{"at": _now(), "event": "created", "detail": source}],
        }
        if woop_norm is not None:
            loop["woop"] = woop_norm
        with self._lock:
            loops = self._load()
            loops.append(loop)
            self._save(loops)
        return json.loads(json.dumps(loop))

    def get(self, loop_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            for loop in self._load():
                if loop.get("id") == loop_id:
                    # Deep copy: callers mutate the returned dict freely;
                    # persistence goes through _mutate, never aliasing.
                    return json.loads(json.dumps(loop))
        return None

    def list(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        with self._lock:
            loops = json.loads(json.dumps(self._load()))
        if status:
            loops = [l for l in loops if l.get("status") == status]
        return loops

    def _mutate(self, loop_id: str, fn: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        with self._lock:
            loops = self._load()
            for loop in loops:
                if loop.get("id") == loop_id:
                    fn(loop)
                    loop["updated_at"] = _now()
                    self._save(loops)
                    return loop
        raise KeyError(f"no goal loop with id {loop_id!r}")

    def confirm_criterion(self, loop_id: str, criterion_id: str) -> dict[str, Any]:
        """Owner confirmation for a ``manual`` criterion — the ONLY way one
        is ever marked met, recorded as an evaluation with the owner as
        the judge."""

        def _apply(loop: dict[str, Any]) -> None:
            known = {c["id"] for c in loop.get("criteria") or []}
            if criterion_id not in known:
                raise KeyError(f"loop {loop_id} has no criterion {criterion_id!r}")
            loop.setdefault("evaluations", []).append(
                {
                    "criterion_id": criterion_id,
                    "met": True,
                    "why": "confirmed by the owner",
                    "cycle": loop.get("cycles_run", 0),
                    "at": _now(),
                }
            )
            loop.setdefault("history", []).append(
                {"at": _now(), "event": "criterion_confirmed", "detail": criterion_id}
            )

        return self._mutate(loop_id, _apply)

    # -- the loop ---------------------------------------------------------
    def run_cycle(
        self,
        loop_id: str,
        *,
        executor: Optional[ExecutorFn] = None,
        judge: Optional[JudgeFn] = None,
    ) -> dict[str, Any]:
        """Run one cycle: execute pending steps, then evaluate criteria.

        Terminal transitions happen here: all criteria met → completed;
        cycle budget spent with unmet criteria → failed; a step error
        with no other way forward, or only manual criteria left → blocked.
        """
        executor = executor or _default_executor
        loop = self.get(loop_id)
        if loop is None:
            raise KeyError(f"no goal loop with id {loop_id!r}")
        if loop.get("status") in TERMINAL_STATUSES:
            return loop
        if loop.get("status") == STATUS_PAUSED:
            return loop

        cycle_no = int(loop.get("cycles_run") or 0) + 1
        step_error = False
        for step in loop.get("steps") or []:
            if step.get("status") == "done":
                continue
            step["attempts"] = int(step.get("attempts") or 0) + 1
            ok, output = executor(step["instruction"])
            step["result"] = (output or "")[:4000]
            if ok:
                step["status"] = "done"
            else:
                step_error = True
                if step["attempts"] >= MAX_STEP_ATTEMPTS:
                    step["status"] = "failed"
                loop.setdefault("history", []).append(
                    {
                        "at": _now(),
                        "event": "step_failed",
                        "detail": f"{step['id']} cycle {cycle_no}: {step['result'][:200]}",
                    }
                )

        evidence = "\n\n".join(
            f"[{s['id']}] {s.get('result') or ''}"
            for s in loop.get("steps") or []
            if s.get("status") == "done"
        )
        # Latest evaluation per criterion wins (owner confirmations included).
        latest: dict[str, dict[str, Any]] = {}
        for ev in loop.get("evaluations") or []:
            latest[ev["criterion_id"]] = ev
        cycle_evals: list[dict[str, Any]] = []
        for crit in loop.get("criteria") or []:
            prior = latest.get(crit["id"])
            if prior and prior.get("met") and crit.get("check") == CHECK_MANUAL:
                cycle_evals.append(prior)  # an owner confirmation stands
                continue
            ev = evaluate_criterion(crit, evidence, judge)
            ev = {"criterion_id": crit["id"], "cycle": cycle_no, "at": _now(), **ev}
            cycle_evals.append(ev)
            latest[crit["id"]] = ev
        loop.setdefault("evaluations", []).extend(
            [e for e in cycle_evals if e not in (loop.get("evaluations") or [])]
        )
        loop["cycles_run"] = cycle_no

        unmet = [e for e in cycle_evals if not e.get("met")]
        manual_only_left = bool(unmet) and all(
            (next((c for c in loop["criteria"] if c["id"] == e["criterion_id"]), {}) or {}).get(
                "check"
            )
            == CHECK_MANUAL
            for e in unmet
        )
        if not unmet:
            loop["status"] = STATUS_COMPLETED
        elif manual_only_left:
            loop["status"] = STATUS_BLOCKED
        elif step_error and all(
            s.get("status") == "failed" for s in loop["steps"] if s.get("status") != "done"
        ) and any(s.get("status") == "failed" for s in loop["steps"]):
            loop["status"] = STATUS_BLOCKED
        elif cycle_no >= int(loop.get("max_cycles") or DEFAULT_MAX_CYCLES):
            loop["status"] = STATUS_FAILED
        if loop["status"] in TERMINAL_STATUSES:
            loop["report"] = build_report(loop, cycle_evals)
            loop.setdefault("history", []).append(
                {"at": _now(), "event": f"terminal:{loop['status']}", "detail": f"cycle {cycle_no}"}
            )

        def _persist(l: dict[str, Any]) -> None:
            l.clear()
            l.update(loop)

        return self._mutate(loop_id, _persist)

    def run_until_terminal(
        self,
        loop_id: str,
        *,
        executor: Optional[ExecutorFn] = None,
        judge: Optional[JudgeFn] = None,
    ) -> dict[str, Any]:
        """Cycle until the loop reaches a terminal state (bounded by the
        loop's own max_cycles, so this always terminates)."""
        loop = self.get(loop_id)
        if loop is None:
            raise KeyError(f"no goal loop with id {loop_id!r}")
        guard = int(loop.get("max_cycles") or DEFAULT_MAX_CYCLES) + 1
        while loop.get("status") == STATUS_ACTIVE and guard > 0:
            loop = self.run_cycle(loop_id, executor=executor, judge=judge)
            guard -= 1
        return loop


def build_report(loop: dict[str, Any], evaluations: list[dict[str, Any]]) -> str:
    """The completion report — what was asked, what the evidence shows,
    what is still unmet and why. Produced for every terminal loop."""
    lines = [
        f"Goal loop {loop.get('id')} — {str(loop.get('status') or '').upper()}",
        f"Goal: {loop.get('goal')}",
    ]
    if loop.get("woop"):
        lines.append(format_woop_summary(loop["woop"]))
    lines.extend(
        [
            f"Cycles run: {loop.get('cycles_run')} of {loop.get('max_cycles')}",
            "",
            "Success criteria:",
        ]
    )
    by_id = {e["criterion_id"]: e for e in evaluations}
    for crit in loop.get("criteria") or []:
        ev = by_id.get(crit["id"]) or {}
        mark = "MET" if ev.get("met") else "UNMET"
        lines.append(f"- [{mark}] {crit['description']} — {ev.get('why', 'not evaluated')}")
    lines.append("")
    lines.append("Steps:")
    for step in loop.get("steps") or []:
        lines.append(
            f"- [{step.get('status')}] {step['id']}: {step['instruction'][:120]}"
        )
        if step.get("result"):
            lines.append(f"    result: {step['result'][:300]}")
    return "\n".join(lines)


def format_loop_summary(loop: dict[str, Any]) -> str:
    """One-paragraph human summary for chat/voice status answers."""
    criteria = loop.get("criteria") or []
    latest: dict[str, dict[str, Any]] = {}
    for ev in loop.get("evaluations") or []:
        latest[ev["criterion_id"]] = ev
    met = sum(1 for c in criteria if (latest.get(c["id"]) or {}).get("met"))
    summary = (
        f"Goal loop {loop.get('id')}: '{loop.get('goal')}' — "
        f"status {loop.get('status')}, {met}/{len(criteria)} criteria met, "
        f"cycle {loop.get('cycles_run')}/{loop.get('max_cycles')}."
    )
    if loop.get("woop"):
        summary += f" {format_woop_summary(loop['woop'])}"
    return summary
