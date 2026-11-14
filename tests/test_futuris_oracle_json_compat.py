"""Futuris Oracle JSON dialect compatibility contract (TASK-REL-006).

Production failure (2026-11-14): every ``POST /v1/friday/forecast`` returned
HTTP 500. The service traceback ended with::

    AttributeError: 'OracleDialectAsync_oracledb' object has no attribute
    '_json_deserializer'

raised while ``ForecastRepository.get_by_idempotency_key`` read a generic
``JSON()`` column. Futuris was the only Oracle-backed agent missing the JSON
dialect compatibility shim that IntelX/Memora/Cortex install before engine
creation. These tests pin the contract locally (no Oracle instance needed):
after importing Futuris' storage layer, the Oracle dialect must provide
working JSON bind/result processors for generic ``JSON()`` columns — the
exact operations the idempotency lookup performs.
"""

import importlib.util
from pathlib import Path

from sqlalchemy import JSON
from sqlalchemy.dialects.oracle.base import OracleDialect

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPAT_PATH = REPO_ROOT / "Futuris" / "futuris" / "oracle_dialect_compat.py"
DB_PATH = REPO_ROOT / "Futuris" / "futuris" / "storage" / "db.py"


def _load_compat_module():
    spec = importlib.util.spec_from_file_location(
        "futuris_oracle_dialect_compat_under_test", COMPAT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_futuris_storage_layer_wires_the_compat_shim():
    """db.py must import the shim before any engine is created."""
    source = DB_PATH.read_text(encoding="utf-8")
    assert "oracle_dialect_compat" in source
    import_pos = source.index("oracle_dialect_compat")
    engine_pos = source.index("create_async_engine(")
    assert import_pos < engine_pos


def test_futuris_oracle_dialect_supports_generic_json_processors():
    _load_compat_module()

    dialect = OracleDialect()
    column_type = JSON()

    bind_processor = column_type.bind_processor(dialect)
    result_processor = column_type.result_processor(dialect, None)

    payload = {"idempotency_key": "rel006", "items": [1, 2, 3], "ok": True}
    bound = bind_processor(payload) if bind_processor is not None else payload
    assert isinstance(bound, str)
    assert result_processor is not None
    assert result_processor(bound) == payload


def test_futuris_oracle_async_dialect_json_lookup_does_not_raise():
    """The production crash was on OracleDialectAsync_oracledb: instantiating
    the async dialect and processing a JSON value must not raise
    AttributeError for a missing _json_deserializer."""
    _load_compat_module()

    try:
        from sqlalchemy.dialects.oracle import oracledb as _oracledb_module
    except Exception:
        return  # driver dialect unavailable in this environment

    dialect_cls = getattr(_oracledb_module, "OracleDialectAsync_oracledb", None) or getattr(
        _oracledb_module, "OracleDialect_oracledb", None
    )
    if dialect_cls is None:
        return
    dialect = dialect_cls()
    column_type = JSON()
    result_processor = column_type.result_processor(dialect, None)
    bind_processor = column_type.bind_processor(dialect)
    payload = {"forecast": {"horizon": 7}}
    bound = bind_processor(payload) if bind_processor is not None else payload
    if result_processor is not None:
        assert result_processor(bound) == payload
