"""TASK-FUT-003 regression tests: Futuris storage reads must tolerate
Oracle native-JSON values.

Production failure (2026-11-15, Futuris journal, Server 1): ``GET /trends``
and ``POST /simulate`` returned HTTP 500 with::

    TypeError: the JSON object must be str, bytes or bytearray, not list

raised inside ``ForecastRepository.list_filtered`` at ``session.execute``
(app.py ``quick_trends`` / ``quick_simulate`` call sites). The same defect
poisoned the scheduler's shared session: ``forecast_refresh_job`` raised at
``list_by_target`` and the follow-on ``PendingRollbackError`` failed
``calibration_sweep_job`` in the same cycle.

Root cause: every JSON column in ``futuris/storage/models.py`` is declared
as generic ``JSON()`` but compiles to Oracle's native ``JSON`` type (the
module-level ``@compiles(JSON, "oracle")``), so python-oracledb hands
SQLAlchemy values that are ALREADY deserialized (list/dict). The stock
``JSON`` result processor unconditionally applies ``json.loads`` and raises
``TypeError`` on them. Same bug class TASK-REL-038 fixed for IntelX with a
``TolerantJSON`` type (PR #238); FUT-002's repaired handlers merely removed
the AttributeError that had been masking it.

These tests feed the storage columns' result processors exactly the values
the Oracle driver returns (native list/dict), plus the JSON text other
backends return, and pin both behaviours. The processor sweep fails on
clean main with the production TypeError; the stock-JSON mechanism test
passes on both trees and documents why.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.dialects import oracle
from sqlalchemy.types import JSON

import futuris.oracle_dialect_compat  # noqa: F401  (production applies this shim before any engine exists)
from futuris.storage.models import Base

# The JSON columns the sweep must cover: (table, column). Every one of them
# compiles to Oracle native JSON, so every one is subject to the defect.
EXPECTED_JSON_COLUMNS = {
    ("forecasts", "assumptions"),
    ("forecasts", "drivers"),
    ("forecasts", "predictive_distribution"),
    ("forecasts", "intervals"),
    ("forecasts", "calibration_metrics"),
    ("forecasts", "model_metadata"),
    ("scenarios", "assumptions_override"),
    ("forecast_events", "payload"),
    ("intelx_notices", "payload"),
    ("observations", "tags"),
    ("model_registry", "benchmark_scores"),
    ("evaluation_runs", "metrics"),
}


def _json_columns():
    found = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSON):
                found.append((table.name, column.name, column.type))
    return found


def test_storage_models_declare_the_expected_json_columns():
    """Guard: the processor sweep below covers every storage JSON column."""
    found = {(table, column) for table, column, _ in _json_columns()}
    assert found >= EXPECTED_JSON_COLUMNS


def test_stock_json_processor_raises_on_oracle_native_values():
    """Pin the production defect mechanism on the pre-fix column type.

    This passes before and after the fix: it documents that a plain
    ``JSON()`` column cannot survive an Oracle native-JSON read, which is
    why the storage models must not use it.
    """
    processor = JSON().result_processor(oracle.dialect(), None)
    with pytest.raises(TypeError):
        processor([{"name": "driver"}])
    with pytest.raises(TypeError):
        processor({"key": "value"})
    # Text backends decode normally.
    assert processor('[{"name": "driver"}]') == [{"name": "driver"}]
    assert processor(None) is None


def test_every_storage_json_column_accepts_oracle_native_values():
    """Each storage JSON column's result processor must accept the native
    list/dict values python-oracledb returns for Oracle JSON columns.

    On clean main every column here is stock ``JSON()`` and the first
    native value raises the production TypeError.
    """
    dialect = oracle.dialect()
    for table_name, column_name, column_type in _json_columns():
        processor = column_type.result_processor(dialect, None)
        assert processor is not None, f"{table_name}.{column_name}"
        native_list = [{"name": "driver", "strength": 0.5}]
        native_dict = {"p50": 1.0}
        assert processor(native_list) == native_list, f"{table_name}.{column_name}"
        assert processor(native_dict) == native_dict, f"{table_name}.{column_name}"
        # Values that arrive as text (SQLite and other backends) still decode.
        assert processor('[{"name": "driver", "strength": 0.5}]') == native_list, (
            f"{table_name}.{column_name}"
        )
        assert processor('{"p50": 1.0}') == native_dict, f"{table_name}.{column_name}"
        assert processor(None) is None, f"{table_name}.{column_name}"


def test_forecast_repository_to_domain_consumes_native_json_values():
    """Repository-level guard: a ForecastModel whose JSON attributes hold
    native list/dict values (what the fixed read path yields on Oracle)
    converts to the domain Forecast with drivers and distributions intact.
    """
    from futuris.storage.models import ForecastModel
    from futuris.storage.repositories import ForecastRepository

    now = datetime.now(UTC)
    model = ForecastModel(
        forecast_id=uuid4(),
        target="BTCUSDT",
        as_of=now,
        horizon=timedelta(hours=24),
        expires_at=now + timedelta(hours=24),
        prediction=100.0,
        range_lower=90.0,
        range_upper=110.0,
        probability=0.5,
        confidence="medium",
        model_version="fut003-test",
        assumptions=["native assumption"],
        review_at=now,
        status="active",
        drivers=[
            {
                "name": "native_driver",
                "direction": "positive",
                "strength": 0.5,
                "leading_or_lagging": "leading",
                "evidence_refs": [],
            }
        ],
        predictive_distribution={"p50": 100.0},
        intervals=[{"level": 0.9, "lower": 90.0, "upper": 110.0}],
        calibration_metrics={"ece": 0.1},
        model_metadata={"origin": "oracle-native"},
        evidence_refs=[],
    )

    domain = ForecastRepository(None)._to_domain(model)

    assert domain.target == "BTCUSDT"
    assert [d.name for d in domain.drivers] == ["native_driver"]
    assert domain.assumptions == ["native assumption"]
    assert domain.predictive_distribution == {"p50": 100.0}
    assert domain.intervals == [{"level": 0.9, "lower": 90.0, "upper": 110.0}]
    assert domain.calibration_metrics == {"ece": 0.1}
    assert domain.model_metadata == {"origin": "oracle-native"}
