"""IntelX standing research watches (TASK-INT-007).

See ``intelx.watches.engine`` for the implementation and
``IntelX/docs/STANDING_WATCHES.md`` for the design.
"""

from intelx.watches.engine import (
    WATCHES,
    PollResult,
    WatchDefinition,
    WatchRunner,
    WatchService,
    with_overrides,
)

__all__ = [
    "WATCHES",
    "PollResult",
    "WatchDefinition",
    "WatchRunner",
    "WatchService",
    "with_overrides",
]
