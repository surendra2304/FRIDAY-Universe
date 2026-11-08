"""SQLAlchemy Oracle dialect compatibility for INTELX generic JSON columns.

SQLAlchemy generic JSON bind/result processors expect _json_serializer and
_json_deserializer attributes on the dialect. Some supported python-oracledb
sync/async dialect classes inherit OracleDialect releases where those attributes
are not defined. A value of None intentionally selects SQLAlchemy standard-library
json.dumps/json.loads defaults. This preserves Oracle 23ai native JSON DDL and
does not alter existing data.
"""

from sqlalchemy.dialects.oracle.base import OracleDialect


if not hasattr(OracleDialect, "_json_serializer"):
    OracleDialect._json_serializer = None

if not hasattr(OracleDialect, "_json_deserializer"):
    OracleDialect._json_deserializer = None
