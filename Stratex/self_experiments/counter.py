"""The persistent global trial counter (TASK-STR-EXP-001).

Every experiment the loop judges increments this counter BEFORE
judgement, and the post-increment value is the Bonferroni denominator
for that trial — the same global accounting the research programme
keeps by hand (RD-001..RD-020), now owned by Stratex itself.

Seed: 3,899 — the programme counter at RD-020. Sources:
~/workspace/rd020-record/STATE.md ("Programme trial counter now
3,899"; the RD-020 run was invoked with N_global 3899) and
~/workspace/str-nearmiss/REPORT.md headline ("programme counter at
RD-020, N_global 3,899"). The seed and its source are recorded in the
counter file itself. Concurrent crew rounds (RD-021, RD-025) advance
the programme counter outside the loop; at activation the coordinator
reconciles this counter upward to the recorded programme value if it
has moved — the loop never silently resets: a counter file below the
seed is treated as tampering and raises.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

SEED_VALUE = 3899
SEED_SOURCE = (
    "rd020-record/STATE.md: 'Programme trial counter now 3,899' "
    "(RD-020 invoked with N_global 3899); str-nearmiss/REPORT.md "
    "headline: 'programme counter at RD-020, N_global 3,899'"
)


class CounterError(Exception):
    """The trial counter file is corrupt or below its seed."""


class TrialCounter:
    """A monotonic, atomically persisted trial counter."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                value = int(data["value"])
            except Exception as exc:
                raise CounterError(
                    f"trial counter at {self.path} is unreadable: {exc}"
                ) from exc
            if value < SEED_VALUE:
                raise CounterError(
                    f"trial counter at {self.path} reads {value}, below "
                    f"the recorded seed {SEED_VALUE} — refusing to run "
                    f"on a reset counter"
                )
            self._value = value
        else:
            self._value = SEED_VALUE
            self._persist()

    @property
    def value(self) -> int:
        return self._value

    def next(self) -> int:
        """Increment, persist, and return the new global trial number."""
        self._value += 1
        self._persist()
        return self._value

    def _persist(self) -> None:
        payload = {
            "value": self._value,
            "seed": SEED_VALUE,
            "seed_source": SEED_SOURCE,
            "updated_at": datetime.now(UTC).isoformat(),
            "owner": "stratex_self_experiments",
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
