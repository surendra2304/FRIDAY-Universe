"""Delegated-errand framework (TASK-IG-FRD-004) — FRAMEWORK ONLY.

Pattern source: IG corpus item ``DejxPCWjUro`` (Manus Cue — an agent
with its own phone number, email and wallet that runs errands like a
human PA). Manus Cue is closed-source commercial software; this module
implements the *pattern* — a delegated errand with steps, approvals and
a budget — under hard safety gates:

* **No real-world action is possible from this module.** The only
  channel implementation is :class:`DryRunChannel`, which records what
  *would* happen and returns ``executed: False``. Registering any other
  channel raises — wiring a live phone/email/payment channel is a
  separate, future, owner-gated task, not a config change.
* **Every external step starts ``awaiting_approval``** and can only be
  approved through :meth:`ErrandEngine.approve_step`. The engine
  enforces this; :meth:`ErrandEngine.run` refuses unapproved steps.
* **Budget ledger, default cap zero.** Approving a step whose cost
  would exceed the errand's remaining budget is refused. With the
  default cap of 0, no costed step can ever be approved — money
  movement is impossible unless the owner deliberately raises a cap on
  a specific errand (and even then, only dry-run executes).

Errands persist to a JSON file (atomic replace) so an errand and its
approval state survive restarts.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# The framework-only lock. There is deliberately no code path in this
# module that flips it; a live-channel build is a different task.
FRAMEWORK_ONLY = True

EXTERNAL_CHANNELS = ("phone", "email", "message", "purchase")
STEP_KINDS = ("external", "internal")

STATE_AWAITING = "awaiting_approval"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_DONE = "executed_dry_run"


class ErrandError(Exception):
    """Raised for gate violations and unknown ids."""


class DryRunChannel:
    """The only channel: records intent, performs nothing."""

    name = "dry_run"

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def execute(self, step: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "channel": step.get("channel"),
            "description": step.get("description"),
            "estimated_cost": step.get("estimated_cost", 0.0),
            "at": time.time(),
        }
        self.calls.append(record)
        return {
            "executed": False,
            "dry_run": True,
            "note": (
                "FRAMEWORK ONLY: no real channel is connected, so nothing "
                "was sent, called, or paid. This records what WOULD happen "
                "if a live channel were wired in a future owner-gated task."
            ),
            "would_have_done": record,
        }


class ChannelRegistry:
    """Holds channels; refuses anything that is not a DryRunChannel."""

    def __init__(self) -> None:
        self._channels: Dict[str, DryRunChannel] = {"dry_run": DryRunChannel()}

    def register(self, name: str, channel: Any) -> None:
        if not isinstance(channel, DryRunChannel):
            raise ErrandError(
                "Refused: only DryRunChannel implementations may be "
                "registered in the framework-only build. Connecting a live "
                "channel requires a separate owner-gated task."
            )
        self._channels[name] = channel

    def get(self, name: str = "dry_run") -> DryRunChannel:
        channel = self._channels.get(name)
        if channel is None:
            raise ErrandError(f"Unknown channel {name!r} (only 'dry_run' exists).")
        return channel


def _default_store_path() -> str:
    base = os.environ.get("FRIDAY_DATA_DIR", "").strip()
    root = base if base else os.path.join("FRIDAY", ".data")
    return os.path.join(root, "errands", "errands.json")


@dataclass
class ErrandStore:
    path: str = field(default_factory=_default_store_path)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._cache = data
        except (OSError, ValueError):
            self._cache = {}

    def _save(self) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".errands-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def put(self, errand: Dict[str, Any]) -> None:
        with self._lock:
            self._cache[errand["id"]] = json.loads(json.dumps(errand))
            self._save()

    def get(self, errand_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            errand = self._cache.get(errand_id)
            return json.loads(json.dumps(errand)) if errand else None

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [json.loads(json.dumps(e)) for e in self._cache.values()]


class ErrandEngine:
    """Creates errands, enforces approvals + budget, runs dry-run only."""

    def __init__(
        self,
        store: Optional[ErrandStore] = None,
        channels: Optional[ChannelRegistry] = None,
        internal_runner: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self.store = store or ErrandStore()
        self.channels = channels or ChannelRegistry()
        # Internal steps (summarise, look up) may run through an injected
        # runner; the default records intent only, like the dry-run channel.
        self._internal_runner = internal_runner

    # -- creation ------------------------------------------------------
    def create_errand(
        self,
        instruction: str,
        steps: List[Dict[str, Any]],
        budget_cap: float = 0.0,
    ) -> Dict[str, Any]:
        if budget_cap < 0:
            raise ErrandError("budget_cap cannot be negative.")
        built_steps = []
        for i, raw in enumerate(steps):
            kind = str(raw.get("kind", "external"))
            if kind not in STEP_KINDS:
                raise ErrandError(f"step {i}: kind must be one of {STEP_KINDS}.")
            channel = raw.get("channel")
            if kind == "external":
                if channel not in EXTERNAL_CHANNELS:
                    raise ErrandError(
                        f"step {i}: external steps need a channel in {EXTERNAL_CHANNELS}."
                    )
            cost = float(raw.get("estimated_cost", 0.0) or 0.0)
            if cost < 0:
                raise ErrandError(f"step {i}: estimated_cost cannot be negative.")
            built_steps.append(
                {
                    "id": f"s{i + 1}",
                    "kind": kind,
                    "channel": channel,
                    "description": str(raw.get("description", "")).strip(),
                    # External steps are gated; internal steps carry no
                    # outside-world effect and start approved.
                    "state": STATE_AWAITING if kind == "external" else STATE_APPROVED,
                    "estimated_cost": cost,
                    "result": None,
                }
            )
        errand = {
            "id": "errand-" + uuid.uuid4().hex[:10],
            "instruction": instruction,
            "budget_cap": float(budget_cap),
            "status": "open",
            "framework_only": FRAMEWORK_ONLY,
            "steps": built_steps,
            "created_at": time.time(),
            "history": [{"event": "created", "at": time.time()}],
        }
        self.store.put(errand)
        return errand

    # -- gates -----------------------------------------------------------
    def _get(self, errand_id: str) -> Dict[str, Any]:
        errand = self.store.get(errand_id)
        if errand is None:
            raise ErrandError(f"Unknown errand {errand_id!r}.")
        return errand

    @staticmethod
    def _step(errand: Dict[str, Any], step_id: str) -> Dict[str, Any]:
        for step in errand["steps"]:
            if step["id"] == step_id:
                return step
        raise ErrandError(f"Errand {errand['id']} has no step {step_id!r}.")

    @staticmethod
    def committed_spend(errand: Dict[str, Any]) -> float:
        """Cost locked in by approved or executed steps."""
        return sum(
            float(s.get("estimated_cost", 0.0))
            for s in errand["steps"]
            if s["state"] in (STATE_APPROVED, STATE_DONE)
        )

    def approve_step(self, errand_id: str, step_id: str, by: str = "owner") -> Dict[str, Any]:
        errand = self._get(errand_id)
        step = self._step(errand, step_id)
        if step["state"] != STATE_AWAITING:
            raise ErrandError(
                f"Step {step_id} is {step['state']}, not awaiting_approval."
            )
        cost = float(step.get("estimated_cost", 0.0))
        remaining = float(errand["budget_cap"]) - self.committed_spend(errand)
        if cost > remaining:
            raise ErrandError(
                f"Budget gate: step costs {cost} but only {remaining} of the "
                f"errand's cap {errand['budget_cap']} remains uncommitted. "
                "Approval refused."
            )
        step["state"] = STATE_APPROVED
        errand["history"].append(
            {"event": "step_approved", "step": step_id, "by": by, "at": time.time()}
        )
        self.store.put(errand)
        return errand

    def reject_step(self, errand_id: str, step_id: str, by: str = "owner") -> Dict[str, Any]:
        errand = self._get(errand_id)
        step = self._step(errand, step_id)
        if step["state"] not in (STATE_AWAITING, STATE_APPROVED):
            raise ErrandError(f"Step {step_id} is {step['state']}; cannot reject.")
        step["state"] = STATE_REJECTED
        errand["history"].append(
            {"event": "step_rejected", "step": step_id, "by": by, "at": time.time()}
        )
        self.store.put(errand)
        return errand

    # -- execution (dry-run only) ---------------------------------------
    def run(self, errand_id: str) -> Dict[str, Any]:
        errand = self._get(errand_id)
        for step in errand["steps"]:
            if step["state"] == STATE_DONE or step["state"] == STATE_REJECTED:
                continue
            if step["state"] != STATE_APPROVED:
                # The gate: an unapproved external step is never executed,
                # and the run stops rather than skipping ahead silently.
                errand["history"].append(
                    {"event": "run_blocked_unapproved", "step": step["id"], "at": time.time()}
                )
                self.store.put(errand)
                raise ErrandError(
                    f"Gate: step {step['id']} ({step['description']!r}) is "
                    "awaiting approval. Nothing was executed for it."
                )
            if step["kind"] == "external":
                step["result"] = self.channels.get("dry_run").execute(step)
            else:
                if self._internal_runner is not None:
                    step["result"] = self._internal_runner(step)
                else:
                    step["result"] = {
                        "executed": False,
                        "dry_run": True,
                        "note": "No internal runner wired; intent recorded only.",
                    }
            step["state"] = STATE_DONE
            errand["history"].append(
                {"event": "step_executed_dry_run", "step": step["id"], "at": time.time()}
            )
        if all(s["state"] in (STATE_DONE, STATE_REJECTED) for s in errand["steps"]):
            errand["status"] = "complete"
        self.store.put(errand)
        return errand

    # -- reporting --------------------------------------------------------
    def summarise(self, errand_id: str) -> str:
        errand = self._get(errand_id)
        counts: Dict[str, int] = {}
        for s in errand["steps"]:
            counts[s["state"]] = counts.get(s["state"], 0) + 1
        lines = [
            f"Errand {errand['id']}: {errand['instruction']}",
            f"Status: {errand['status']} · budget cap {errand['budget_cap']} · "
            f"committed {self.committed_spend(errand)}",
            "Steps: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
        ]
        if errand.get("framework_only"):
            lines.append(
                "FRAMEWORK ONLY: no real-world action was taken — external "
                "steps run through a dry-run channel that records intent."
            )
        return "\n".join(lines)


def default_engine() -> ErrandEngine:
    return ErrandEngine()


__all__ = [
    "FRAMEWORK_ONLY",
    "EXTERNAL_CHANNELS",
    "STATE_AWAITING",
    "STATE_APPROVED",
    "STATE_REJECTED",
    "STATE_DONE",
    "ErrandError",
    "DryRunChannel",
    "ChannelRegistry",
    "ErrandStore",
    "ErrandEngine",
    "default_engine",
]
