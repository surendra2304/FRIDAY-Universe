"""Oracle dialect JSON processing compatibility shim (TASK-REL-006).

Production failure (2026-11-14): ``POST /v1/friday/forecast`` returned
HTTP 500 for every request. The Futuris.service traceback ended in
``sqlalchemy/sql/sqltypes.py`` with::

    AttributeError: 'OracleDialectAsync_oracledb' object has no attribute
    '_json_deserializer'

raised from ``ForecastRepository.get_by_idempotency_key`` while reading a
generic ``JSON()`` column (``futuris/storage/models.py`` uses generic JSON
columns throughout).

SQLAlchemy only defines ``_json_serializer`` / ``_json_deserializer`` on
some dialect classes depending on the installed version. Futuris was the
only Oracle-backed agent without this shim: IntelX
(``intelx/oracle_dialect_compat.py``), Memora and Cortex all install it
before creating their engines. Mirrored from IntelX so the fleet carries
one consistent guard.
"""

from __future__ import annotations


def patch_oracle_dialect_json_support() -> None:
    """Restore dialect-level JSON hooks when SQLAlchemy omits them."""
    try:
        from sqlalchemy.dialects.oracle.base import OracleDialect
    except Exception:  # pragma: no cover - import environment guard
        return

    if not hasattr(OracleDialect, "_json_serializer"):
        OracleDialect._json_serializer = None  # type: ignore[attr-defined]
    if not hasattr(OracleDialect, "_json_deserializer"):
        OracleDialect._json_deserializer = None  # type: ignore[attr-defined]


patch_oracle_dialect_json_support()
