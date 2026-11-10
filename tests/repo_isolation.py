"""Shared module-cache hygiene for the root monorepo test suite.

Several agents ship identically named top-level packages (``app``, ``apps``,
``core``, ``dashboard``, ``routers``, ``storage``). When more than one agent
app is imported inside a single pytest process, bare imports such as
``from core.config import settings`` resolve against whichever agent's path
currently precedes in ``sys.path``, and stale ``sys.modules`` entries shadow
the intended module for the rest of the session.

The fix has two cooperating parts:

1. Every agent-scoped test setup purges the AMBIGUOUS top-level names (and
   their dotted descendants) from ``sys.modules`` before inserting its own
   agent path at ``sys.path[0]``, so its own packages win resolution.
2. Agents must ship the contested packages as REGULAR packages (with
   ``__init__.py``). Python lets a regular package found anywhere on
   ``sys.path`` beat a namespace package found earlier, so namespace
   semantics make resolution depend on unrelated path entries.

The purge is deliberately surgical. Purging EVERY repository module would
re-import modules that earlier tests imported (or patched with ``@patch``)
at collection time, splitting a test's captured references from the freshly
re-imported module and silently breaking those tests. Only the ambiguous
names plus per-class extras are purged; unique names (``scripts``,
``friday_core``, ``Stratex``, ...) stay cached.

One caveat for maintainers: this module must never be moved into a directory
whose name collides with an agent package, because ``import repo_isolation``
resolves through the same ``sys.path`` that the suite manipulates.
"""
from __future__ import annotations

import sys

# Top-level package names that more than one agent ships. Everything whose
# first dotted segment is in this set is dropped from sys.modules.
AMBIGUOUS_TOP_LEVEL_NAMES = (
    "app",
    "apps",
    "core",
    "dashboard",
    "routers",
    "storage",
    "api",  # Stratex ships a top-level `api` package; so do some agents' apps
)


def purge_ambiguous_modules(extra: tuple[str, ...] = ()) -> None:
    """Drop cached modules for the ambiguous top-level names plus ``extra``.

    ``extra`` lets a caller additionally drop its agent-unique package (for
    example ``cortex_api``) when the agent app must be re-imported to pick up
    test-time environment changes made after an earlier import.
    """
    targets = frozenset(AMBIGUOUS_TOP_LEVEL_NAMES) | frozenset(extra)
    for name in list(sys.modules):
        top_level = name.split(".", 1)[0]
        if top_level in targets:
            sys.modules.pop(name, None)
