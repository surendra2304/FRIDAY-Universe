"""IntelX standing research watches (TASK-INT-007).

See ``intelx.watches.engine`` for the implementation and
``IntelX/docs/STANDING_WATCHES.md`` for the design. Topic domains
(TASK-INT-013) live in ``intelx.watches.domains``.
"""

from intelx.watches.domains import (
    DOMAINS,
    DomainSpec,
    domains_in_use,
    validate_watch_domains,
    watches_in_domain,
)
from intelx.watches.engine import (
    WATCHES,
    PollResult,
    WatchDefinition,
    WatchRunner,
    WatchService,
    with_overrides,
)

__all__ = [
    "DOMAINS",
    "DomainSpec",
    "WATCHES",
    "PollResult",
    "WatchDefinition",
    "WatchRunner",
    "WatchService",
    "domains_in_use",
    "validate_watch_domains",
    "watches_in_domain",
    "with_overrides",
]
