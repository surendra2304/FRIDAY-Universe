"""The persistent global trial counter (TASK-STR-EXP-001).

Every experiment the loop judges increments this counter BEFORE
judgement, and the post-increment value is the Bonferroni denominator
for that trial — the same global accounting the research programme
keeps by hand (RD-001..RD-020), now owned by Stratex itself.

Seed: 3,979 — the programme counter after RD-025, reconciled upward
at activation (TASK-STR-EXP-004) from the original EXP-001 seed of
3,899 (the programme counter at RD-020; sources:
~/workspace/rd020-record/STATE.md, "Programme trial counter now
3,899", and ~/workspace/str-nearmiss/REPORT.md headline). The
reconciliation chain (~/workspace/986-activation/RECONCILIATION.md,
verified 2026-11-20): 3,899 at RD-020, +4 = 3,903 (RD-021's floor
reservation), +76 = 3,979 (RD-025 executed trials 3,904-3,979 — the
range is independently proven by the MySQL store's RD-025 rows).

RESERVATION, recorded so no future reader mistakes the counter for a
strictly-executed total: trials 3,900-3,903 are RD-021's floor
reservation — allocated in the programme counter but UNEXECUTED
(RD-021's run never ran). The strictly-executed total is therefore
3,975, not 3,979. The counter stays at 3,979: it is the conservative
direction for Bonferroni (larger N, tighter alpha), it preserves
RD-025's judged trial numbering, and if RD-021 ever runs it consumes
3,900-3,903 as already allocated.

The seed and its source are recorded in the counter file itself. The
loop never silently resets: a counter file below the seed is treated
as tampering and raises.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

# The programme trial counter after RD-025 (TASK-STR-EXP-004
# reconciliation, 2026-11-20). Includes RD-021's floor reservation:
# trials 3,900-3,903 are allocated but UNEXECUTED — the strictly
# executed total is 3,975. Never lower this seed: a counter file
# below it is refused as a reset (see TrialCounter).
SEED_VALUE = 3979
SEED_SOURCE = (
    "Reconciled 2026-11-20 (TASK-STR-EXP-004; "
    "~/workspace/986-activation/RECONCILIATION.md): EXP-001 seed "
    "3,899 = programme counter at RD-020 (rd020-record/STATE.md: "
    "'Programme trial counter now 3,899'; str-nearmiss/REPORT.md "
    "headline); +4 = 3,903 RD-021 floor reservation — trials "
    "3,900-3,903 allocated but UNEXECUTED (strictly executed total "
    "is 3,975, not 3,979); +76 = 3,979 RD-025 executed trials "
    "3,904-3,979 (verified against the MySQL store's RD-025 rows). "
    "RD-025's judging N of 3,987 (counter + 8 reserved E2 headroom, "
    "never consumed) is a spent judging parameter, not the counter."
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
