"""Memora core package.

The explicit ``__init__.py`` is required, not cosmetic: several agents in the
monorepo ship a top-level ``core`` package (Forge's is ``Forge/app/core``),
and Python lets a REGULAR package found anywhere on ``sys.path`` beat a
namespace package found earlier. Without this file, Memora's ``core`` is a
namespace package, and importing Memora inside the monorepo test process
resolves bare ``from core.config import settings`` to Forge's ``core`` --
whose ``__init__`` then imports ``app.core.config``, cascading into the
Memora ``app`` shim and a circular-import crash (see tests/repo_isolation.py).
With regular packages on both sides, the agent whose path precedes wins
deterministically.
"""
