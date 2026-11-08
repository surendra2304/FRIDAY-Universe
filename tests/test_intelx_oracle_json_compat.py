"""Regression coverage for INTELX Oracle generic JSON processor compatibility.

The production async Oracle dialect subclasses OracleDialect. Importing the
async driver module itself requires SQLAlchemy's optional greenlet extra, so
this regression exercises the generic processors on the shared base class
that the async dialect inherits, without requiring a DB connection.
"""

import json

from sqlalchemy.dialects.oracle.base import OracleDialect
from sqlalchemy.types import JSON

# The engine imports this module before constructing the concrete Oracle
# dialect. Import it directly here to avoid importing SQLAlchemy's async extra.
import intelx.oracle_dialect_compat  # noqa: F401


def test_oracle_json_bind_and_result_processors_use_stdlib_defaults():
    """Oracle's generic JSON processors must bind and read nested JSON values."""
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
