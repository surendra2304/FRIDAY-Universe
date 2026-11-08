"""Regression coverage for INTELX Oracle generic JSON processor compatibility.

The monorepo's conftest adds multiple agent roots to sys.path. Load the INTELX
helper by its exact file path to avoid another agent's same-named package.
"""

import importlib.util
import json
from pathlib import Path

from sqlalchemy.dialects.oracle.base import OracleDialect
from sqlalchemy.types import JSON


def test_oracle_json_bind_and_result_processors_use_stdlib_defaults():
    """Oracle generic JSON processors must bind/read after IntelX hook loads."""
    helper_path = (
        Path(__file__).resolve().parents[1]
        / "IntelX"
        / "intelx"
        / "oracle_dialect_compat.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_intelx_oracle_dialect_compat", helper_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dialect = OracleDialect()
    payload = {
        "status": "verified",
        "claims": [{"id": "claim-1", "confidence": 0.97}],
        "metadata": {"source": "intelx"},
    }

    bind_processor = JSON().bind_processor(dialect)
    result_processor = JSON().result_processor(dialect, None)

    assert bind_processor is not None
    assert result_processor is not None

    encoded = bind_processor(payload)
    assert json.loads(encoded) == payload
    assert result_processor(encoded) == payload
