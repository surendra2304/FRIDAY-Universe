"""Memora application packages.

The explicit ``__init__.py`` is required, not cosmetic: ``Sentinel`` also
ships an ``apps`` directory reachable as a top-level ``apps`` namespace
portion when the monorepo test process puts ``Sentinel/`` on ``sys.path``.
Python lets a regular package found anywhere on ``sys.path`` beat a
namespace package found earlier, so without this file Memora's ``apps``
could lose bare ``from apps.api...`` imports to any regular ``apps``
package elsewhere in the fleet. With this file, resolution follows
``sys.path`` order deterministically (see tests/repo_isolation.py).
"""
