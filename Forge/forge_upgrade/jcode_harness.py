"""Lean build-session layer adapted from JCode (TASK-FRG-027).

JCode (1jehuang/jcode, MIT) is a high-performance coding-agent
harness built for heavy multi-agent/multi-session work on small
machines: tiny per-session footprint, parallel sessions coordinated
by a server, and swarm file-conflict resolution. Forge does not
adopt the Rust harness; it adapts the two patterns that fit its
~1GB fleet shape into the build runtime:

* **Lean context** — a build run declares a character budget for
  the context it carries. Required parts (task, assumptions,
  success criteria, sketch brief) are never dropped; optional
  parts are admitted in order while they fit and dropped
  honestly when they do not. If the required parts alone exceed
  the budget the run is refused before any code is written —
  a lean session must not silently truncate its own brief.
* **Parallel-session scope ledger** — sessions reserve their
  declared scope prefixes before implementing. A second session
  whose scope overlaps a live reservation is refused at plan
  time, so parallel build sessions cannot write the same files
  and discover the conflict at review.

The module is stdlib-only and deterministic: same inputs, same
compaction, same conflict verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _norm_prefix(prefix: str) -> str:
    """Normalise a scope prefix for overlap checks."""
    text = str(prefix).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def scopes_overlap(a: str, b: str) -> bool:
    """True when two scope prefixes can name the same file."""
    na, nb = _norm_prefix(a), _norm_prefix(b)
    if not na or not nb:
        return True  # an empty prefix claims everything
    return na == nb or na.startswith(nb + "/") or nb.startswith(na + "/")


@dataclass(slots=True)
class ContextCompaction:
    """Outcome of fitting a run context into its lean budget."""

    ok: bool
    total_chars: int
    budget_chars: int
    kept_optional: int
    dropped_optional: int
    detail: str


def compact_context(
    required: list[str],
    optional: list[str],
    budget_chars: int,
) -> ContextCompaction:
    """Fit required + optional context parts into ``budget_chars``.

    Required parts are kept whole or the compaction fails;
    optional parts are admitted in order while they fit.
    A non-positive budget means "no lean budget declared" and
    everything is kept.
    """
    required_text = "\n".join(part for part in required if part)
    required_chars = len(required_text)
    if budget_chars <= 0:
        total = required_chars + sum(len(p) for p in optional if p)
        return ContextCompaction(
            ok=True,
            total_chars=total,
            budget_chars=budget_chars,
            kept_optional=len([p for p in optional if p]),
            dropped_optional=0,
            detail=f"lean context {total} chars (no budget declared)",
        )
    if required_chars > budget_chars:
        return ContextCompaction(
            ok=False,
            total_chars=required_chars,
            budget_chars=budget_chars,
            kept_optional=0,
            dropped_optional=len([p for p in optional if p]),
            detail=(
                f"required context {required_chars} chars exceeds "
                f"lean budget {budget_chars}"
            ),
        )
    total = required_chars
    kept = 0
    dropped = 0
    for part in optional:
        if not part:
            continue
        if total + 1 + len(part) <= budget_chars:
            total += 1 + len(part)
            kept += 1
        else:
            dropped += 1
    return ContextCompaction(
        ok=True,
        total_chars=total,
        budget_chars=budget_chars,
        kept_optional=kept,
        dropped_optional=dropped,
        detail=(
            f"lean context {total}/{budget_chars} chars, "
            f"dropped {dropped} optional parts"
        ),
    )


@dataclass(slots=True)
class LeanSessionLedger:
    """Scope reservations for parallel build sessions.

    A session reserves its declared scope prefixes at plan time.
    Reservations are released when the run finishes; a live
    reservation from another session blocks an overlapping
    reservation instead of letting both sessions write.
    """

    reservations: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def reserve(self, session_id: str, prefixes: list[str]) -> list[str]:
        """Reserve ``prefixes`` for ``session_id``.

        Returns conflict descriptions; empty means reserved.
        Re-reserving the same prefixes for the same session is
        idempotent.
        """
        wanted = tuple(_norm_prefix(p) for p in prefixes)
        conflicts: list[str] = []
        for other_id, held in self.reservations.items():
            if other_id == session_id:
                continue
            for mine in wanted:
                for theirs in held:
                    if scopes_overlap(mine, theirs):
                        conflicts.append(
                            f"scope '{mine}' overlaps session "
                            f"{other_id} reservation '{theirs}'"
                        )
        if conflicts:
            return conflicts
        self.reservations[session_id] = wanted
        return []

    def check_files(self, session_id: str, files: list[str]) -> list[str]:
        """Files that fall under another session's reservation."""
        conflicts: list[str] = []
        for path in files:
            for other_id, held in self.reservations.items():
                if other_id == session_id:
                    continue
                if any(scopes_overlap(path, prefix) for prefix in held):
                    conflicts.append(
                        f"file '{path}' is under session "
                        f"{other_id} reservation"
                    )
        return conflicts

    def release(self, session_id: str) -> None:
        self.reservations.pop(session_id, None)
