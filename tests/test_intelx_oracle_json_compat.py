"""Regression coverage for INTELX's Oracle async JSON processor contract.

This file runs in the root monorepo validation suite. tests/conftest.py adds
IntelX/ to sys.path before importing the package.
"""

import json

from sqlalchemy.dialects.oracle.oracledb import OracleDialectAsync_oracledb
from sqlalchemy.types import JSON

# Importing the compatibility module installs the same defaults imported by
# intelx.db.engine before the Oracle async engine is constructed.
import intelx.db.oracle_dialect_compat  # noqa: F401


def test_oracle_async_json_bind_and_result_processors_use_stdlib_defaults():
    """Oracle native JSON fields must bind and read through generic SQLAlchemy JSON."""
    dialect = OracleDialectAsync_oracledb()
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
