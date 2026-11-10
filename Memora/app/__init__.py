"""App package shim for Memora entrypoint compatibility.

The ``app`` import is deferred (PEP 562 ``__getattr__``): eager import here
made importing this package crash whenever ``apps.api.main`` was mid-import
(a circular import observed in the monorepo suite when another agent's
``core`` package imported ``app.*`` while Memora's app was partially
initialised). Nothing changes for callers: ``memora_app.app`` still resolves
to the FastAPI app on first attribute access.
"""
from typing import Any

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    if name == "app":
        from apps.api.main import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
