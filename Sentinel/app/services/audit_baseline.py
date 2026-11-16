"""
Sentinel/app/services/audit_baseline.py — Audit-finding baseline memorist.

TASK-IG2-SEN-03: the PentAGI 'memorist' pattern in defensive, fleet-sized
form. PentAGI stores findings in PostgreSQL/pgvector; the fleet cannot
carry that stack, and does not need it — baselines are small JSON records
and the diff is deterministic code with zero LLM cost per comparison.

Behaviour
---------
- ``record_run(findings)`` diffs a new audit run against the stored
  baseline and returns only what changed: new exposures, fixed items,
  regressions (same finding, higher severity) and the unchanged count.
  A raw full report every week trains the owner to ignore it; a delta is
  the part that matters.
- Alerts are produced for new CRITICAL/HIGH exposures and for any
  regression, so a caller (Sentinel's watchdog / daily briefing) can
  surface exactly those.
- ``accept_baseline(findings)`` promotes a run to be the new baseline —
  an explicit act, never a side effect of recording a run, so a bad week
  cannot silently redefine 'normal'.

Findings are plain dicts with at least ``finding_id`` and ``severity``
(the shape produced by fleet_audit_pipeline.Finding.as_dict()); objects
with an ``as_dict()`` method are accepted too.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

SEVERITY_RANK: dict[str, int] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
ALERT_SEVERITIES: frozenset[str] = frozenset({"HIGH", "CRITICAL"})


def _normalise(finding: Any) -> dict[str, Any]:
    if hasattr(finding, "as_dict"):
        finding = finding.as_dict()
    record = dict(finding)
    if "finding_id" not in record:
        raise ValueError(f"finding has no finding_id: {record!r}")
    record.setdefault("severity", "LOW")
    record.setdefault("title", record["finding_id"])
    record.setdefault("detail", "")
    return record


def _index(findings: Iterable[Any]) -> dict[str, dict[str, Any]]:
    return {record["finding_id"]: record for record in map(_normalise, findings)}


@dataclass
class BaselineDiff:
    """The delta between a baseline and a new run."""

    has_baseline: bool
    new: list[dict[str, Any]] = field(default_factory=list)
    fixed: list[dict[str, Any]] = field(default_factory=list)
    regressions: list[dict[str, Any]] = field(default_factory=list)
    unchanged_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "has_baseline": self.has_baseline,
            "new": self.new,
            "fixed": self.fixed,
            "regressions": self.regressions,
            "unchanged_count": self.unchanged_count,
            "counts": {
                "new": len(self.new), "fixed": len(self.fixed),
                "regressions": len(self.regressions),
                "unchanged": self.unchanged_count,
            },
        }

    def to_markdown(self) -> str:
        lines = ["# Sentinel audit delta vs baseline"]
        if not self.has_baseline:
            lines.append("No baseline stored yet — every finding counts as new.")
        if not (self.new or self.fixed or self.regressions):
            lines.append("No changes against the baseline.")
        for record in self.new:
            lines.append(f"- NEW [{record['severity']}] {record['title']}")
        for record in self.regressions:
            lines.append(
                f"- REGRESSION {record['finding_id']}: "
                f"{record['from_severity']} → {record['severity']} — {record['title']}"
            )
        for record in self.fixed:
            lines.append(f"- FIXED [{record['severity']}] {record['title']}")
        lines.append(f"Unchanged: {self.unchanged_count}")
        return "\n".join(lines) + "\n"


def diff_findings(
    baseline: Iterable[Any] | None, current: Iterable[Any],
) -> BaselineDiff:
    """Pure diff: new / fixed / regressions / unchanged."""
    current_index = _index(current)
    if baseline is None:
        return BaselineDiff(
            has_baseline=False,
            new=sorted(current_index.values(), key=lambda r: r["finding_id"]),
        )
    baseline_index = _index(baseline)
    new = [r for fid, r in current_index.items() if fid not in baseline_index]
    fixed = [r for fid, r in baseline_index.items() if fid not in current_index]
    regressions: list[dict[str, Any]] = []
    unchanged = 0
    for fid, record in current_index.items():
        base = baseline_index.get(fid)
        if base is None:
            continue
        if SEVERITY_RANK.get(record["severity"], 0) > SEVERITY_RANK.get(
            base["severity"], 0
        ):
            regressions.append({
                **record, "from_severity": base["severity"],
            })
        else:
            unchanged += 1
    by_id = lambda r: r["finding_id"]  # noqa: E731
    return BaselineDiff(
        has_baseline=True,
        new=sorted(new, key=by_id), fixed=sorted(fixed, key=by_id),
        regressions=sorted(regressions, key=by_id),
        unchanged_count=unchanged,
    )


def alerts_for(diff: BaselineDiff) -> list[dict[str, Any]]:
    """Alert-worthy deltas: new HIGH/CRITICAL exposures and regressions."""
    alerts: list[dict[str, Any]] = []
    for record in diff.new:
        if record["severity"] in ALERT_SEVERITIES:
            alerts.append({
                "kind": "new_exposure",
                "finding_id": record["finding_id"],
                "severity": record["severity"],
                "message": f"New {record['severity']} exposure: {record['title']}",
            })
    for record in diff.regressions:
        alerts.append({
            "kind": "regression",
            "finding_id": record["finding_id"],
            "severity": record["severity"],
            "message": (
                f"Regression: {record['title']} worsened "
                f"{record['from_severity']} → {record['severity']}"
            ),
        })
    return alerts


class BaselineStore(Protocol):
    def load(self) -> dict[str, Any] | None: ...
    def save(self, baseline: dict[str, Any]) -> None: ...


class InMemoryBaselineStore:
    """Baseline store for tests and single-process use."""

    def __init__(self) -> None:
        self._baseline: dict[str, Any] | None = None

    def load(self) -> dict[str, Any] | None:
        return self._baseline

    def save(self, baseline: dict[str, Any]) -> None:
        self._baseline = baseline


class JsonBaselineStore:
    """File-backed baseline store (small JSON, atomic replace)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, baseline: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(baseline, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, self.path)


class BaselineMemorist:
    """The memorist role: remember the baseline, report only the delta."""

    def __init__(self, store: BaselineStore) -> None:
        self.store = store

    def current_baseline(self) -> list[dict[str, Any]] | None:
        stored = self.store.load()
        if stored is None:
            return None
        return list(stored.get("findings", []))

    def record_run(
        self, findings: Iterable[Any],
    ) -> tuple[BaselineDiff, list[dict[str, Any]]]:
        """Diff a run against the baseline; returns (diff, alerts)."""
        diff = diff_findings(self.current_baseline(), findings)
        return diff, alerts_for(diff)

    def accept_baseline(self, findings: Iterable[Any]) -> dict[str, Any]:
        """Promote a run's findings to be the stored baseline."""
        baseline = {
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "findings": sorted(
                _index(findings).values(), key=lambda r: r["finding_id"]
            ),
        }
        self.store.save(baseline)
        return baseline
