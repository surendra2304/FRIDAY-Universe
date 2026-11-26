"""INTELX — Helix lookup watch history (TASK-INT-051).

Helix (thalha-a9/helix) ships a ``--watch`` mode: re-run a username
lookup later and report what changed. This module is IntelX's version
of that mode, built on the existing ``helix_lookup`` (TASK-IG2-INT-03):

  * ``HelixWatchStore`` records each lookup report (in-memory; a
    lookup report is small and the store is a watch aid, not the
    canonical store — persistence to the canonical store is a future
    leg, and the live re-probe itself is owed after Muse clearance);
  * ``diff_helix_reports`` compares two reports for one subject and
    reports added / removed platforms, confidence changes, newly
    discarded false positives, and the overall-confidence movement.

Nothing here performs a lookup or a fetch — the store only records and
diffs reports the caller already ran through the approved-subject gate.
A subject with no recorded history diffs as ``first_seen``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from intelx.osint.helix_lookup import HelixReport

logger = logging.getLogger("intelx.osint.helix_watch")

UTC = UTC


def diff_helix_reports(old: HelixReport | dict, new: HelixReport | dict) -> dict:
    """Diff two lookup reports for the same username.

    Accepts live reports or the plain dicts ``HelixReport.to_dict()``
    returns (the store keeps dicts). Platforms are compared by name;
    a platform that appears in ``new`` but not ``old`` is ``added``
    (and vice versa); a platform in both with a different confidence
    is a ``confidence_change``; a platform the control probe discarded
    this time but not last time is ``newly_discarded``.
    """
    old_dict = old if isinstance(old, dict) else old.to_dict()
    new_dict = new if isinstance(new, dict) else new.to_dict()
    old_hits = {h["platform"]: h for h in old_dict.get("hits", [])}
    new_hits = {h["platform"]: h for h in new_dict.get("hits", [])}
    old_discarded = {d["platform"] for d in old_dict.get("discarded_false_positives", [])}
    new_discarded = {d["platform"] for d in new_dict.get("discarded_false_positives", [])}
    added = sorted(set(new_hits) - set(old_hits))
    removed = sorted(set(old_hits) - set(new_hits))
    confidence_changes = [
        {
            "platform": platform,
            "old_confidence": old_hits[platform]["confidence"],
            "new_confidence": new_hits[platform]["confidence"],
        }
        for platform in sorted(set(old_hits) & set(new_hits))
        if old_hits[platform]["confidence"] != new_hits[platform]["confidence"]
    ]
    return {
        "first_seen": False,
        "added_platforms": added,
        "removed_platforms": removed,
        "confidence_changes": confidence_changes,
        "newly_discarded": sorted(new_discarded - old_discarded),
        "no_longer_discarded": sorted(old_discarded - new_discarded),
        "overall_confidence": {
            "old": old_dict.get("overall_confidence"),
            "new": new_dict.get("overall_confidence"),
        },
        "sites_checked": {
            "old": old_dict.get("sites_checked"),
            "new": new_dict.get("sites_checked"),
        },
    }


@dataclass
class HelixWatchStore:
    """In-memory record of Helix lookup reports, keyed by username."""

    _snapshots: dict[str, list[dict]] = field(default_factory=dict)

    def record(self, report: HelixReport) -> dict:
        """Store a report snapshot; returns the stored snapshot dict."""
        snapshot = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "report": report.to_dict(),
        }
        self._snapshots.setdefault(report.username, []).append(snapshot)
        return snapshot

    def diff(self, username: str, new_report: HelixReport) -> dict:
        """Diff ``new_report`` against the last stored snapshot.

        Returns ``{"first_seen": True, ...}`` with empty change lists
        when nothing is stored for the subject yet.
        """
        history = self._snapshots.get(username, [])
        if not history:
            return {
                "first_seen": True,
                "added_platforms": sorted(h.platform for h in new_report.hits),
                "removed_platforms": [],
                "confidence_changes": [],
                "newly_discarded": sorted(d["platform"] for d in new_report.discarded),
                "no_longer_discarded": [],
                "overall_confidence": {"old": None, "new": new_report.overall_confidence},
                "sites_checked": {"old": None, "new": new_report.sites_checked},
            }
        return diff_helix_reports(history[-1]["report"], new_report)

    def history(self, username: str) -> list[dict]:
        """All stored snapshots for a subject, oldest first."""
        return list(self._snapshots.get(username, []))

    def last(self, username: str) -> dict | None:
        """Most recent snapshot for a subject, or None."""
        history = self._snapshots.get(username, [])
        return history[-1] if history else None


_STORE: HelixWatchStore | None = None


def get_watch_store() -> HelixWatchStore:
    """Process-wide watch store used by the username-lookup route."""
    global _STORE
    if _STORE is None:
        _STORE = HelixWatchStore()
    return _STORE


__all__ = [
    "HelixWatchStore",
    "diff_helix_reports",
    "get_watch_store",
]
