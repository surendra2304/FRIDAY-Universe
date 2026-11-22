"""The Stratex self-experiment loop (TASK-STR-EXP-001).

One cycle: gates -> propose from the closed catalogue -> DECLARE in
the ledger -> run on the verified stream store -> judge under the
frozen bars -> admit or record closed -> bank the Memora lesson.

Bounds (bounds.py, Self-Upgrade DESIGN section 5):
- kill switch: STRATEX_SELF_EXPERIMENTS must be exactly "on",
  re-read every cycle. Default is OFF — stricter than FRG-017,
  because this loop can admit entries to a trading lane.
- host-load gate from the start (the FRG-017 C2 lesson): a cycle
  starts only when the 1-minute load average is calm.
- idle gate: an injectable work probe; the production wiring supplies
  the daemon-activity probe at activation. Slice 1's default probe is
  the load gate alone, and the loop is NOT wired into the daemon.
- one experiment at a time, a daily cap, a per-experiment time box.
- risk parameters are read-only to this loop: it writes only inside
  its own data directory (ledger, counter, admissions, lessons).

run_forever() is the driver a follow-up wires after review; nothing
in this slice starts it.

TASK-STR-EXP-006 (starvation breaker, scheduling only): the
whole-box load gate above never opens on the production host, so
run_one_cycle() also offers ONE niced trial per starvation window
when no trial has run for STARVATION_BREAKER_AFTER_S, the daemon
is idle, and the load stays below the breaker ceiling. The breaker
changes WHEN a trial runs, never how it is judged: the frozen
admission gate (judge.py) and the daily cap, time box and
declaration discipline are untouched, and a breaker trial is
recorded as such (scheduling + load evidence on its result row).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import bounds, catalogue
from .admissions import AdmissionsRegistry
from .counter import TrialCounter
from .judge import Verdict, judge
from .ledger import ExperimentLedger, canonical_hash
from .lessons import FabricLessonWriter
from .runner import pooled_metrics
from .store import StreamRecord, StreamStore

UTC = timezone.utc

logger = logging.getLogger(__name__)


@dataclass
class CycleReport:
    """The outcome of one attempted cycle (ran or skipped, and why)."""

    status: str  # "ran" | "skipped"
    reason: str = ""
    declaration_id: str = ""
    verdict: str = ""  # "PROVEN" | "FORWARD_TEST" | "FAIL" when ran
    n_global: int | None = None
    admission_key: str = ""
    # TASK-STR-EXP-006: which gate let the trial run — "load_gate"
    # (the normal whole-box gate) or "starvation_breaker" — plus the
    # load averages observed at the gate check, so a breaker trial
    # always carries its load evidence (load1 is the normal gate's
    # signal; load5 is the breaker ceiling's signal).
    via: str = "load_gate"
    load1: float | None = None
    load5: float | None = None


class SelfExperimentLoop:
    """Stratex's autonomous research cycle (see module docstring)."""

    def __init__(
        self,
        store: StreamStore,
        data_dir: Path,
        lesson_writer: FabricLessonWriter | None = None,
        work_probe: Callable[[], bool] | None = None,
        daily_cap: int = bounds.DEFAULT_DAILY_CAP,
        time_box_s: float = bounds.DEFAULT_TIME_BOX_S,
        load_gate_fraction: float = bounds.LOAD_GATE_FRACTION,
        starvation_breaker_after_s: float = bounds.STARVATION_BREAKER_AFTER_S,
        breaker_load_ceiling_fraction: float = bounds.BREAKER_LOAD_CEILING_FRACTION,
    ):
        self.store = store
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ExperimentLedger(self.data_dir)
        self.counter = TrialCounter(self.data_dir / "trial_counter.json")
        self.admissions = AdmissionsRegistry(self.data_dir / "admissions.json")
        self.lesson_writer = lesson_writer or FabricLessonWriter()
        self.work_probe = work_probe
        self.daily_cap = daily_cap
        self.time_box_s = time_box_s
        self.load_gate_fraction = load_gate_fraction
        self.starvation_breaker_after_s = starvation_breaker_after_s
        self.breaker_load_ceiling_fraction = breaker_load_ceiling_fraction

    # -- gates ------------------------------------------------------------

    @staticmethod
    def experiments_enabled() -> bool:
        """The kill switch, re-read on every call: only the exact
        value "on" enables the loop. Unset, "off", or anything else
        means disabled."""
        return os.getenv("STRATEX_SELF_EXPERIMENTS", "off").strip().lower() == "on"

    @staticmethod
    def _load1() -> float | None:
        """The 1-minute load average, or None when it cannot be read.

        None fails every gate closed: a trial never runs on an
        unreadable load.
        """
        try:
            return os.getloadavg()[0]
        except (OSError, AttributeError):
            return None

    @staticmethod
    def _load5() -> float | None:
        """The 5-minute load average, or None when it cannot be read.

        The starvation breaker's signal (see breaker_load_ok): the
        sustained load, not the instantaneous spike.
        """
        try:
            return os.getloadavg()[1]
        except (OSError, AttributeError, IndexError):
            return None

    def host_load_ok(self, load1: float | None = None) -> bool:
        """The normal whole-box gate, on the 1-minute average. The
        caller may pass an already-read load so the gate decision
        and the recorded evidence are the same sample."""
        if load1 is None:
            load1 = self._load1()
        return (
            load1 is not None
            and load1 < self.load_gate_fraction * (os.cpu_count() or 1)
        )

    def breaker_load_ok(self, load5: float | None = None) -> bool:
        """The starvation breaker's hard ceiling: the 5-minute load
        average must stay below the ceiling multiple of the CPU
        count, so the box is busy but not SUSTAINED-saturated. The
        1-minute average is deliberately NOT the signal here: the
        daemon's own 15-second scans spike it at whatever instant a
        poll lands. A breaker trial runs niced, so it only ever
        takes CPU nothing else wants; the ceiling guards the
        sustained case where it would make no progress."""
        if load5 is None:
            load5 = self._load5()
        return (
            load5 is not None
            and load5
            < self.breaker_load_ceiling_fraction * (os.cpu_count() or 1)
        )

    def starved(self, now: datetime | None = None) -> bool:
        """True when no trial has completed within the breaker window.

        No result row ever means starved: the loop has never run a
        trial in this data directory. An unreadable last-result
        timestamp fails closed (not starved) — the gate is never
        bypassed on state the loop cannot read.
        """
        last_ts = self.ledger.last_result_ts()
        if last_ts is None:
            return True
        try:
            last = datetime.fromisoformat(last_ts)
        except ValueError:
            logger.warning(
                "self-experiment last-result timestamp unreadable "
                "(%r); treating the loop as not starved",
                last_ts,
            )
            return False
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        moment = now or datetime.now(UTC)
        return (moment - last).total_seconds() > self.starvation_breaker_after_s

    def _breaker_allows(self, load5: float | None) -> bool:
        """The starvation breaker: one niced trial when the loop has
        not run one in a whole window, the box is busy but not
        sustained-saturated, and the load is readable. The
        daemon-activity probe and the daily cap are NOT decided here
        — run_one_cycle still applies them authoritatively below, so
        a breaker trial can never run while the daemon is working or
        over its cap.
        """
        if not self.breaker_load_ok(load5):
            return False
        return self.starved()

    def is_idle(self) -> bool:
        if not self.host_load_ok():
            return False
        if self.work_probe is not None:
            return bool(self.work_probe())
        return True

    # -- durable lesson mirror ----------------------------------------------

    @property
    def _lessons_path(self) -> Path:
        return self.data_dir / "lessons.jsonl"

    def _read_lessons(self) -> list[dict[str, Any]]:
        if not self._lessons_path.exists():
            return []
        rows = []
        for line in self._lessons_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _append_lesson(self, row: dict[str, Any]) -> None:
        with self._lessons_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def flush_pending_lessons(self) -> int:
        """Retry Memora delivery for lessons still marked pending.

        Returns how many lessons became fully delivered. Mirrors
        FRG-017: delivery flags only ever move False -> True, and a
        FAIL lesson is fully delivered only when BOTH its private and
        its universal copy have landed (rule R).
        """
        rows = self._read_lessons()
        if not rows:
            return 0
        delivered_now = 0
        changed = False
        for row in rows:
            deliveries = row.get("deliveries") or {}
            needs_universal = row.get("verdict") == "FAIL"
            pending = deliveries.get("private") is not True or (
                needs_universal and deliveries.get("universal") is not True
            )
            if not pending:
                continue
            if deliveries.get("private") is not True:
                deliveries["private"] = self.lesson_writer.deliver(
                    row["content"], row.get("metadata") or {}, universal=False
                )
                changed = True
            if needs_universal and deliveries.get("universal") is not True:
                deliveries["universal"] = self.lesson_writer.deliver(
                    row["content"], row.get("metadata") or {}, universal=True
                )
                changed = True
            row["deliveries"] = deliveries
            if deliveries.get("private") is True and (
                not needs_universal or deliveries.get("universal") is True
            ):
                delivered_now += 1
        if changed:
            tmp = self._lessons_path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, default=str) + "\n")
            os.replace(tmp, self._lessons_path)
        return delivered_now

    # -- one cycle ------------------------------------------------------------

    def run_one_cycle(self) -> CycleReport:
        if not self.experiments_enabled():
            return CycleReport(status="skipped", reason="kill_switch_off")
        load1 = self._load1()
        load5 = self._load5()
        via = "load_gate"
        if not self.host_load_ok(load1):
            # TASK-STR-EXP-006 starvation breaker: when the whole-box
            # gate has not opened for a full window, one niced trial
            # may run while the daemon is idle and the box is busy
            # but not sustained-saturated. Anything else still skips
            # here.
            if not self._breaker_allows(load5):
                return CycleReport(
                    status="skipped",
                    reason="host_load_gate",
                    load1=load1,
                    load5=load5,
                )
            via = "starvation_breaker"
            logger.info(
                "self-experiment starvation breaker firing: no trial "
                "in %.0fh, load1=%.2f load5=%.2f (gate %.2f, "
                "ceiling %.2f)",
                self.starvation_breaker_after_s / 3600,
                load1 if load1 is not None else -1,
                load5 if load5 is not None else -1,
                self.load_gate_fraction * (os.cpu_count() or 1),
                self.breaker_load_ceiling_fraction * (os.cpu_count() or 1),
            )
        if self.work_probe is not None and not self.work_probe():
            return CycleReport(
                status="skipped",
                reason="work_in_progress",
                via=via,
                load1=load1,
                load5=load5,
            )
        if self.ledger.results_today() >= self.daily_cap:
            return CycleReport(
                status="skipped",
                reason="daily_cap_reached",
                via=via,
                load1=load1,
                load5=load5,
            )
        self.flush_pending_lessons()

        declared = self.ledger.declared_hashes()
        proposal = None
        for candidate in catalogue.all_proposals(self.store):
            if canonical_hash(candidate.to_dict()) not in declared:
                proposal = candidate
                break
        if proposal is None:
            return CycleReport(
                status="skipped",
                reason="catalogue_exhausted",
                via=via,
                load1=load1,
                load5=load5,
            )

        declaration_id = self.ledger.declare(proposal.to_dict())
        return self.run_declared(
            declaration_id, proposal, via=via, load1=load1, load5=load5
        )

    def run_declared(
        self,
        declaration_id: str,
        proposal: catalogue.Proposal,
        via: str = "load_gate",
        load1: float | None = None,
        load5: float | None = None,
    ) -> CycleReport:
        """Run one declared experiment end-to-end.

        The declaration is re-verified here (ledger.require_declaration):
        work that was never declared, or whose content differs from
        its declaration, is refused with DeclarationRequired before
        anything runs or is counted.
        """
        self.ledger.require_declaration(declaration_id, proposal.to_dict())
        deadline = time.monotonic() + self.time_box_s
        if proposal.experiment_type == "combination_greedy_forward":
            outcome = self._run_greedy(declaration_id, proposal, deadline)
            if outcome is None:
                self.ledger.record_result(
                    {
                        "declaration_id": declaration_id,
                        "status": "aborted_timebox",
                        "experiment_type": proposal.experiment_type,
                        "scheduling": via,
                        "load1": load1,
                        "load5": load5,
                    }
                )
                return CycleReport(
                    status="skipped",
                    reason="timebox_aborted",
                    declaration_id=declaration_id,
                    via=via,
                    load1=load1,
                    load5=load5,
                )
            metrics, n_global, verdict = outcome
        else:
            members = [self.store.stream(s) for s in proposal.members]
            metrics = pooled_metrics(members)
            n_global = self.counter.next()
            self.ledger.record_evaluation(
                {
                    "declaration_id": declaration_id,
                    "trial": n_global,
                    "members": list(metrics.members),
                    "metrics": metrics.to_dict(),
                }
            )
            verdict = judge(metrics, n_global)

        admission_key = ""
        if verdict.verdict in ("FORWARD_TEST", "PROVEN"):
            members = [self.store.stream(s) for s in metrics.members]
            admission_key = self.admissions.admit(
                members=members,
                metrics=metrics,
                verdict=verdict,
                declaration_id=declaration_id,
                n_global=n_global,
                panel=proposal.panel,
                timeframe=proposal.timeframe,
            )
            self.ledger.record_admission(
                {
                    "declaration_id": declaration_id,
                    "admission_key": admission_key,
                    "verdict": verdict.verdict,
                    "trial": n_global,
                }
            )

        self.ledger.record_result(
            {
                "declaration_id": declaration_id,
                "status": "ran",
                "experiment_type": proposal.experiment_type,
                "hypothesis": proposal.hypothesis,
                "metrics": metrics.to_dict(),
                "verdict": verdict.to_dict(),
                "trial": n_global,
                "admission_key": admission_key or None,
                "scheduling": via,
                "load1": load1,
                "load5": load5,
            }
        )
        self._bank_lesson(proposal, metrics, verdict, declaration_id, n_global)
        return CycleReport(
            status="ran",
            reason=verdict.reasons[0] if verdict.reasons else "",
            declaration_id=declaration_id,
            verdict=verdict.verdict,
            n_global=n_global,
            admission_key=admission_key,
            via=via,
            load1=load1,
            load5=load5,
        )

    # -- greedy forward selection --------------------------------------------

    def _run_greedy(
        self,
        declaration_id: str,
        proposal: catalogue.Proposal,
        deadline: float,
    ) -> tuple[Any, int, Verdict] | None:
        """Greedy forward selection. Returns (metrics, n, verdict) for
        the final set, or None on time-box abort.

        Every candidate evaluation increments the global counter and
        leaves a compact evaluation record — the selection search is
        itself trials, and the counter says so. An addition is
        accepted only when it improves the pooled (PF, expectancy)
        over the current set.
        """
        pool = {r.stream_id: r for r in self.store.streams()}
        current: list[StreamRecord] = [self.store.stream(proposal.members[0])]
        current_metrics = pooled_metrics(current)
        final_n = self.counter.value
        while len(current) < catalogue.GREEDY_MAX_MEMBERS:
            best: tuple[Any, Any, int] | None = None
            for candidate_id in proposal.candidate_pool:
                if candidate_id in {r.stream_id for r in current}:
                    continue
                if time.monotonic() > deadline:
                    return None
                trial_metrics = pooled_metrics(
                    current + [pool[candidate_id]]
                )
                n = self.counter.next()
                final_n = n
                self.ledger.record_evaluation(
                    {
                        "declaration_id": declaration_id,
                        "trial": n,
                        "greedy_step": len(current),
                        "candidate_set": list(trial_metrics.members),
                        "metrics": {
                            "trades": trial_metrics.trades,
                            "expectancy": trial_metrics.expectancy,
                            "pf": trial_metrics.pf,
                        },
                    }
                )
                if best is None or (trial_metrics.pf, trial_metrics.expectancy) > (
                    best[1].pf,
                    best[1].expectancy,
                ):
                    best = (pool[candidate_id], trial_metrics, n)
            if best is None:
                break
            candidate, trial_metrics, n = best
            if (trial_metrics.pf, trial_metrics.expectancy) <= (
                current_metrics.pf,
                current_metrics.expectancy,
            ):
                break  # nothing improves the set — selection stops
            current = current + [candidate]
            current_metrics = trial_metrics
            final_n = n
        if len(current) < 2:
            verdict = Verdict(
                verdict="FAIL",
                checks={},
                reasons=[
                    "greedy forward selection found no addition that "
                    "improves the seed stream's pooled record — no "
                    "combination admitted"
                ],
            )
            return current_metrics, final_n, verdict
        return current_metrics, final_n, judge(current_metrics, final_n)

    # -- lessons ---------------------------------------------------------------

    def _bank_lesson(
        self,
        proposal: catalogue.Proposal,
        metrics,
        verdict: Verdict,
        declaration_id: str,
        n_global: int,
    ) -> None:
        members = ", ".join(metrics.members)
        if verdict.verdict == "PROVEN":
            action = (
                "the combination cleared the FULL frozen bar and is "
                "proven-eligible; promotion to VALIDATED travels the "
                "Universe change path (Forge builds, Sentinel gates, "
                "Cortex schedules), never the loop's own call"
            )
        elif verdict.verdict == "FORWARD_TEST":
            action = (
                "the combination is admitted to the FORWARD_TEST lane; "
                "demo forward evidence will decide it under the lane's "
                "kill criteria; do not re-propose this member set"
            )
        else:
            action = (
                "the combination is recorded closed; do not re-propose "
                "this member set — its pooled record is the reason"
            )
        holdout = (
            f"{metrics.holdout_expectancy:+.4%} over {metrics.holdout_trades} "
            f"untouched trades"
            if metrics.holdout_expectancy is not None
            else "not available for every member"
        )
        content = (
            f"Self-experiment {declaration_id} ({proposal.experiment_type}, "
            f"global trial N={n_global}) on {bounds.DATA_WINDOW}: "
            f"{proposal.hypothesis} Pooled over {members}: expectancy "
            f"{metrics.expectancy:+.4%}/trade, PF {metrics.pf:.4f}, "
            f"{metrics.trades} trades, {metrics.positive_folds}/"
            f"{metrics.folds_with_trades} positive folds, one-sided p "
            f"{metrics.p_one_sided:.3g}, holdout expectancy {holdout}. "
            f"Verdict: {verdict.verdict} — "
            f"{'; '.join(verdict.reasons)}. Lesson: {action}."
        )
        metadata = {
            "declaration_id": declaration_id,
            "experiment_type": proposal.experiment_type,
            "members": list(metrics.members),
            "verdict": verdict.verdict,
            "trial": n_global,
            "pf": metrics.pf,
            "expectancy": metrics.expectancy,
            "trades": metrics.trades,
        }
        deliveries = {
            "private": self.lesson_writer.deliver(
                content, metadata, universal=False
            ),
            "universal": None,
        }
        if verdict.verdict == "FAIL":
            # Standing rule R: a failed experiment's lesson also goes
            # to the universal section, so every agent learns from it.
            deliveries["universal"] = self.lesson_writer.deliver(
                content, metadata, universal=True
            )
        self._append_lesson(
            {
                "ts": datetime.now(UTC).isoformat(),
                "declaration_id": declaration_id,
                "verdict": verdict.verdict,
                "content": content,
                "metadata": metadata,
                "deliveries": deliveries,
            }
        )

    # -- driver ------------------------------------------------------------------

    async def run_forever(
        self,
        poll_seconds: float = bounds.DEFAULT_POLL_SECONDS,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Poll for calm windows and run one cycle per window.

        Not wired into the daemon in this slice (see module
        docstring). A failing cycle is logged in the ledger as a skip
        and never kills the loop.
        """
        stop = stop_event or asyncio.Event()
        while not stop.is_set():
            try:
                # TASK-STR-EXP-006: a skipped cycle is logged with its
                # reason — before this the starvation was invisible
                # except to outside load checks; the daemon log now
                # shows every host_load_gate skip and every trial.
                report = await asyncio.to_thread(self.run_one_cycle)
                if report.status == "skipped":
                    logger.info(
                        "self-experiment cycle skipped: %s "
                        "(load1=%s load5=%s)",
                        report.reason,
                        report.load1,
                        report.load5,
                    )
                else:
                    logger.info(
                        "self-experiment trial %s ran via %s: %s",
                        report.n_global,
                        report.via,
                        report.verdict,
                    )
            except Exception:
                # A failing cycle never kills the loop; the gates make
                # cycles return reports rather than raise, so reaching
                # this means an environment fault — wait for the next
                # window and try again.
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                continue


def start_if_enabled(
    store_dir: Path, data_dir: Path, **kwargs: Any
) -> SelfExperimentLoop | None:
    """The activation wiring point: a loop instance when the kill
    switch is on, else None. The coordinator's activation step calls
    this (after building the production stream store); slice 1 wires
    it nowhere."""
    if not SelfExperimentLoop.experiments_enabled():
        return None
    return SelfExperimentLoop(
        store=StreamStore(store_dir), data_dir=data_dir, **kwargs
    )
