"""TASK-IG2-FRG-05: ECC agent/skill harness patterns, adopted FRIDAY-native.

Source: affaan-m/ECC ("Everything Claude Code"), MIT licence — the OSS core
only. ECC Pro (the paid hosted GitHub App) is out of scope under the owner's
FREE-only rule and nothing here depends on it.

ECC is a Node/Claude-Code plugin; per the protocol this is *pattern
adoption*, not a port. The four patterns that fit Forge, re-implemented in
stdlib-only Python following Forge's own conventions:

1. **Fixed pipeline** — ECC drives every task through
   plan -> test -> implement -> review -> verify -> remember -> improve.
   :class:`HarnessRun` is that sequence as an explicit state machine: a run
   can only advance one stage at a time, in order.
2. **Verification hooks** — ECC's hooks *enforce* the process instead of
   trusting the agent to follow it. Here, hooks are callables consulted on
   every stage transition; any hook may veto with a reason. One built-in
   gate is non-negotiable: a run cannot pass ``verify`` (or enter
   ``remember``) without recorded test evidence — "tests were run" is data,
   not a claim.
3. **AgentShield-style config scanning** — ECC ships a scanner for prompts,
   hooks, MCP configs, permissions and secrets. :func:`scan_agent_config`
   is Forge's version: it scans an agent/skill/hook/MCP configuration (a
   nested dict, e.g. parsed JSON/YAML) and reports hardcoded secrets,
   allow-all permissions, permission-bypassing flags and dangerous hook
   commands, each with severity and location.
4. **Instincts (continuous learning)** — ECC's memory layer keeps small
   learned behaviours whose confidence rises when they are confirmed and
   falls when contradicted. :class:`InstinctStore` is that ledger: an
   instinct is only *trusted* (surfaced for prompt assembly) once its
   confidence crosses a threshold, and contradictions decay it back out.

Nothing here changes existing Forge behaviour: the harness is a library
the orchestrator can adopt incrementally, exactly like the skill registry
(TASK-IG-FRG-02).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. Fixed pipeline
# ---------------------------------------------------------------------------

PIPELINE_STAGES: Tuple[str, ...] = (
    "plan",
    "test",
    "implement",
    "review",
    "verify",
    "remember",
    "improve",
)

# A hook receives (run, from_stage, to_stage) and returns None to allow the
# transition or a human-readable reason string to veto it.
Hook = Callable[["HarnessRun", str, str], Optional[str]]


def stage_gate(run: "HarnessRun", from_stage: str, to_stage: str) -> Optional[str]:
    """Built-in verification gate (ECC hook pattern).

    Leaving ``verify`` requires recorded test evidence with a passing
    verdict. Evidence is attached via :meth:`HarnessRun.record_test_evidence`.
    """
    if from_stage == "verify" and not run.test_evidence:
        return "verify gate: no test evidence recorded — run the tests and record the result before advancing"
    if from_stage == "verify" and not all(e.get("passed") for e in run.test_evidence):
        return "verify gate: recorded test evidence contains failures — fix or re-run before advancing"
    return None


@dataclass
class HarnessRun:
    """One task moving through the fixed ECC pipeline."""

    task_id: str
    stage_index: int = 0
    test_evidence: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Tuple[str, str]] = field(default_factory=list)
    hooks: List[Hook] = field(default_factory=list)

    @property
    def stage(self) -> str:
        return PIPELINE_STAGES[self.stage_index]

    @property
    def done(self) -> bool:
        return self.stage_index >= len(PIPELINE_STAGES) - 1 and bool(self.history) and self.history[-1][1] == PIPELINE_STAGES[-1]

    def record_test_evidence(self, suite: str, passed: bool, detail: str = "") -> None:
        self.test_evidence.append({"suite": suite, "passed": bool(passed), "detail": detail})

    def advance(self) -> Tuple[bool, str]:
        """Advance exactly one stage, consulting the built-in gate + hooks.

        Returns ``(ok, reason)``; on a veto the run does not move.
        """
        if self.stage_index >= len(PIPELINE_STAGES) - 1:
            return False, "already at final stage 'improve'"
        frm, to = self.stage, PIPELINE_STAGES[self.stage_index + 1]
        for hook in (stage_gate, *self.hooks):
            veto = hook(self, frm, to)
            if veto:
                return False, veto
        self.stage_index += 1
        self.history.append((frm, to))
        return True, f"{frm} -> {to}"


# ---------------------------------------------------------------------------
# 2. AgentShield-style configuration scanning
# ---------------------------------------------------------------------------

SEVERITIES = ("critical", "high", "medium", "low")


@dataclass(frozen=True)
class ShieldFinding:
    rule: str
    severity: str  # one of SEVERITIES
    location: str  # dotted path inside the scanned config
    detail: str

    def to_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "severity": self.severity, "location": self.location, "detail": self.detail}


_SECRET_PATTERNS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("generic_secret_assignment", re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}")),
)

_DANGEROUS_COMMAND_PATTERNS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("pipe_to_shell", re.compile(r"(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b")),
    ("recursive_root_delete", re.compile(r"rm\s+-[rf]{2}\s+/(\s|$)")),
    ("permission_bypass_flag", re.compile(r"--dangerously-skip-permissions|--yes-always|--force\b.*\bpush\b")),
)

_ALLOW_ALL_VALUES = {"*", "all", "any", "Bash(*)", "Write(*)", "Edit(*)"}
_PERMISSION_KEYS = {"permissions", "allowed_tools", "allow", "tools", "scopes"}


def _walk(node: Any, path: str) -> Iterable[Tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            yield child, value
            yield from _walk(value, child)
    elif isinstance(node, (list, tuple)):
        for i, value in enumerate(node):
            child = f"{path}[{i}]"
            yield child, value
            yield from _walk(value, child)


def scan_agent_config(config: Any) -> List[ShieldFinding]:
    """Scan an agent/skill/hook/MCP config for ECC-AgentShield-class issues.

    ``config`` is any nested dict/list/str structure (parsed JSON/YAML).
    Findings are sorted most-severe first. An empty result means no known
    pattern matched — it is not a proof the config is safe.
    """
    findings: List[ShieldFinding] = []
    for location, value in _walk(config, ""):
        key = location.rsplit(".", 1)[-1].split("[")[0].lower()
        if isinstance(value, str):
            for rule, pattern in _SECRET_PATTERNS:
                if pattern.search(value):
                    findings.append(ShieldFinding("hardcoded_secret", "critical", location,
                                                  f"matches {rule} pattern — secrets belong in env/credential store, never in config"))
            for rule, pattern in _DANGEROUS_COMMAND_PATTERNS:
                if pattern.search(value):
                    severity = "critical" if rule != "permission_bypass_flag" else "high"
                    findings.append(ShieldFinding(rule, severity, location,
                                                  "dangerous command pattern in config/hook text"))
            if key in _PERMISSION_KEYS and value.strip() in _ALLOW_ALL_VALUES:
                findings.append(ShieldFinding("allow_all_permission", "high", location,
                                              f"permission value {value!r} grants unrestricted access"))
        if isinstance(value, (list, tuple)) and key in _PERMISSION_KEYS:
            if any(isinstance(v, str) and v.strip() in _ALLOW_ALL_VALUES for v in value):
                findings.append(ShieldFinding("allow_all_permission", "high", location,
                                              "permission list contains an allow-all entry"))
    order = {name: i for i, name in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: order[f.severity])
    return findings


# ---------------------------------------------------------------------------
# 3. Instincts — confidence-weighted continuous learning
# ---------------------------------------------------------------------------

TRUST_THRESHOLD = 0.7
_INITIAL_CONFIDENCE = 0.5
_CONFIRM_STEP = 0.15
_CONTRADICT_STEP = 0.25


@dataclass
class Instinct:
    """One learned behaviour: when ``trigger`` applies, prefer ``action``."""

    trigger: str
    action: str
    confidence: float = _INITIAL_CONFIDENCE
    confirmations: int = 0
    contradictions: int = 0

    @property
    def trusted(self) -> bool:
        return self.confidence >= TRUST_THRESHOLD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger": self.trigger,
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "confirmations": self.confirmations,
            "contradictions": self.contradictions,
            "trusted": self.trusted,
        }


class InstinctStore:
    """Ledger of instincts whose confidence moves with observed outcomes."""

    def __init__(self) -> None:
        self._instincts: Dict[Tuple[str, str], Instinct] = {}

    def observe(self, trigger: str, action: str, *, confirmed: bool) -> Instinct:
        key = (trigger.strip().lower(), action.strip().lower())
        instinct = self._instincts.get(key)
        if instinct is None:
            instinct = Instinct(trigger=trigger, action=action)
            self._instincts[key] = instinct
        if confirmed:
            instinct.confirmations += 1
            instinct.confidence = min(1.0, instinct.confidence + _CONFIRM_STEP)
        else:
            instinct.contradictions += 1
            instinct.confidence = max(0.0, instinct.confidence - _CONTRADICT_STEP)
        return instinct

    def trusted_for(self, trigger: str) -> List[Instinct]:
        """Trusted instincts for a trigger, strongest first."""
        wanted = trigger.strip().lower()
        matches = [i for i in self._instincts.values() if i.trigger.strip().lower() == wanted and i.trusted]
        return sorted(matches, key=lambda i: i.confidence, reverse=True)

    def all(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in sorted(self._instincts.values(), key=lambda i: i.confidence, reverse=True)]
