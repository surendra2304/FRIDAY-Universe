"""
Oracle Autonomous Database 23ai native vector store adapter for Memora.

A SQLAlchemy session supplied by the memory pipeline remains caller-owned.
Vector writes/deletes use a savepoint and are never independently committed.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from storage.relational.session import SessionLocal, storage_receipt
from storage.vector.qdrant_adapter import VectorSearchResult

logger = logging.getLogger(__name__)

_ORACLE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,29}$")


class _VectorTenantConflict(Exception):
    """A vector ID is already owned by a different tenant."""


class OracleVectorAdapter:
    """
    Native vector adapter for Oracle Autonomous Database 23ai.

    The relational memory ID is the vector primary key. Tenant ownership is
    immutable: an ID already present for another tenant cannot be reassigned.
    SQLite is supported only as a local/test emulation backend.
    """

    def __init__(self, table_name: str = "memora_vector_store", dimension: int = 384):
        if not isinstance(table_name, str) or not _ORACLE_IDENTIFIER.fullmatch(table_name):
            raise ValueError("table_name must be a simple Oracle identifier of at most 30 characters.")
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension <= 0:
            raise ValueError("dimension must be a positive integer.")
        if len(f"{table_name}_idx") > 30:
            raise ValueError("table_name is too long for the derived Oracle vector index name.")

        self.table_name = table_name
        self.dimension = dimension
        self._schema_initialized = False
        self._schema_lock = threading.Lock()

    def is_oracle_backend(self) -> bool:
        return storage_receipt().get("backend") == "oracle"

    def ensure_schema(self, db: Optional[Session] = None) -> bool:
        """
        Bootstrap the vector table with a separately managed session.

        The db argument is retained for call compatibility but is deliberately
        not used. Schema bootstrap must not commit or roll back the caller's
        unit-of-work. init_db invokes this before request transactions begin.
        """
        if self._schema_initialized:
            return True

        with self._schema_lock:
            if self._schema_initialized:
                return True

            session = SessionLocal()
            try:
                if self.is_oracle_backend():
                    table_ddl = f"""
                    BEGIN
                        EXECUTE IMMEDIATE '
                            CREATE TABLE {self.table_name} (
                                id VARCHAR2(64) PRIMARY KEY,
                                tenant_id VARCHAR2(64) DEFAULT ''default'' NOT NULL,
                                embedding VECTOR({self.dimension}, FLOAT32),
                                payload CLOB,
                                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                            )
                        ';
                    EXCEPTION
                        WHEN OTHERS THEN
                            IF SQLCODE != -955 THEN RAISE; END IF;
                    END;
                    """
                    session.execute(text(table_ddl))

                    index_ddl = f"""
                    BEGIN
                        EXECUTE IMMEDIATE '
                            CREATE VECTOR INDEX {self.table_name}_idx ON {self.table_name} (embedding)
                            ORGANIZATION INMEMORY NEIGHBOR GRAPH
                            DISTANCE COSINE
                        ';
                    EXCEPTION
                        WHEN OTHERS THEN
                            IF SQLCODE NOT IN (-955, -1408) THEN RAISE; END IF;
                    END;
                    """
                    session.execute(text(index_ddl))
                else:
                    session.execute(text(f"""
                        CREATE TABLE IF NOT EXISTS {self.table_name} (
                            id VARCHAR(64) PRIMARY KEY,
                            tenant_id VARCHAR(64) DEFAULT 'default' NOT NULL,
                            embedding TEXT NOT NULL,
                            payload TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))

                session.commit()
                self._schema_initialized = True
                logger.info(
                    "Vector table schema initialized: table=%s backend=%s dimension=%d",
                    self.table_name,
                    storage_receipt().get("backend"),
                    self.dimension,
                )
                return True
            except Exception as exc:
                session.rollback()
                logger.warning(
                    "Could not initialize vector table %s (%s)",
                    self.table_name,
                    type(exc).__name__,
                )
                return False
            finally:
                session.close()

    def _validate_vector(self, vector: List[float]) -> bool:
        if not isinstance(vector, (list, tuple)) or len(vector) != self.dimension:
            return False
        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError, OverflowError):
            return False
        return all(math.isfinite(value) for value in values)

    @staticmethod
    def _valid_identity(memory_id: str, tenant_id: str) -> bool:
        return (
            isinstance(memory_id, str)
            and 1 <= len(memory_id) <= 64
            and isinstance(tenant_id, str)
            and 1 <= len(tenant_id) <= 64
        )

    def upsert_embedding(
        self,
        memory_id: str,
        vector: List[float],
        payload: Optional[Dict[str, Any]] = None,
        tenant_id: str = "default",
        db: Optional[Session] = None,
    ) -> bool:
        """Upsert a vector without committing a caller-owned transaction."""
        if not self._valid_identity(memory_id, tenant_id) or not self._validate_vector(vector):
            return False
        if not self.ensure_schema(db):
            return False

        session = db or SessionLocal()
        caller_owned = db is not None
        savepoint = None

        try:
            if caller_owned:
                savepoint = session.begin_nested()

            payload_str = json.dumps(payload or {}, allow_nan=False)
            vector_values = [round(float(value), 6) for value in vector]

            if self.is_oracle_backend():
                vector_str = f"[{','.join(str(value) for value in vector_values)}]"
                sql = f"""
                MERGE INTO {self.table_name} dest
                USING (
                    SELECT :id AS id, :tenant_id AS tenant_id,
                           TO_VECTOR(:vector) AS embedding, :payload AS payload
                    FROM DUAL
                ) src
                ON (dest.id = src.id AND dest.tenant_id = src.tenant_id)
                WHEN MATCHED THEN
                    UPDATE SET
                        dest.embedding = src.embedding,
                        dest.payload = src.payload,
                        dest.updated_at = CURRENT_TIMESTAMP
                WHEN NOT MATCHED THEN
                    INSERT (id, tenant_id, embedding, payload, updated_at)
                    VALUES (src.id, src.tenant_id, src.embedding, src.payload, CURRENT_TIMESTAMP)
                """
                # The ID is the primary key. A different tenant cannot match;
                # its attempted insert hits the primary key instead of changing
                # the existing owner's vector or metadata.
                session.execute(
                    text(sql),
                    {
                        "id": memory_id,
                        "tenant_id": tenant_id,
                        "vector": vector_str,
                        "payload": payload_str,
                    },
                )
            else:
                vector_str = json.dumps(vector_values, allow_nan=False)
                existing_tenant = session.execute(
                    text(f"SELECT tenant_id FROM {self.table_name} WHERE id = :id"),
                    {"id": memory_id},
                ).scalar()

                if existing_tenant is not None and str(existing_tenant) != tenant_id:
                    raise _VectorTenantConflict(
                        "Vector ID is already owned by another tenant."
                    )

                if existing_tenant is not None:
                    session.execute(
                        text(
                            f"UPDATE {self.table_name} "
                            "SET embedding = :emb, payload = :p "
                            "WHERE id = :id AND tenant_id = :tenant_id"
                        ),
                        {
                            "id": memory_id,
                            "tenant_id": tenant_id,
                            "emb": vector_str,
                            "p": payload_str,
                        },
                    )
                else:
                    session.execute(
                        text(
                            f"INSERT INTO {self.table_name} "
                            "(id, tenant_id, embedding, payload) "
                            "VALUES (:id, :tenant_id, :emb, :p)"
                        ),
                        {
                            "id": memory_id,
                            "tenant_id": tenant_id,
                            "emb": vector_str,
                            "p": payload_str,
                        },
                    )

            if savepoint is not None:
                savepoint.commit()
            elif not caller_owned:
                session.commit()
            return True
        except _VectorTenantConflict:
            if savepoint is not None:
                savepoint.rollback()
            logger.warning("Refusing vector upsert for an ID owned by another tenant.")
            return False
        except Exception as exc:
            if savepoint is not None:
                savepoint.rollback()
            elif not caller_owned:
                session.rollback()
            logger.warning(
                "Vector upsert failed for %s (%s)",
                memory_id,
                type(exc).__name__,
            )
            return False
        finally:
            if not caller_owned:
                session.close()

    def delete_embedding(
        self,
        memory_id: str,
        tenant_id: str = "default",
        db: Optional[Session] = None,
    ) -> bool:
        """Delete a vector within the caller's transaction when a session is supplied."""
        if not self._valid_identity(memory_id, tenant_id):
            return False
        if not self.ensure_schema(db):
            return False

        session = db or SessionLocal()
        caller_owned = db is not None
        savepoint = None
        try:
            if caller_owned:
                savepoint = session.begin_nested()

            session.execute(
                text(
                    f"DELETE FROM {self.table_name} "
                    "WHERE id = :id AND tenant_id = :tenant_id"
                ),
                {"id": memory_id, "tenant_id": tenant_id},
            )

            if savepoint is not None:
                savepoint.commit()
            elif not caller_owned:
                session.commit()
            return True
        except Exception as exc:
            if savepoint is not None:
                savepoint.rollback()
            elif not caller_owned:
                session.rollback()
            logger.warning(
                "Vector deletion failed for %s (%s)",
                memory_id,
                type(exc).__name__,
            )
            return False
        finally:
            if not caller_owned:
                session.close()

    def search_similarity(
        self,
        query_vector: List[float],
        limit: int = 10,
        tenant_id: str = "default",
        score_threshold: float = 0.3,
        db: Optional[Session] = None,
    ) -> List[VectorSearchResult]:
        """Search vectors within a tenant boundary; failures remain fail-soft."""
        if (
            not self._valid_identity("query", tenant_id)
            or not self._validate_vector(query_vector)
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or not math.isfinite(float(score_threshold))
            or not 0.0 <= score_threshold <= 1.0
        ):
            return []
        if not any(float(value) != 0.0 for value in query_vector):
            return []
        if not self.ensure_schema(db):
            return []

        session = db or SessionLocal()
        caller_owned = db is not None
        try:
            if self.is_oracle_backend():
                vector_str = f"[{','.join(str(round(float(v), 6)) for v in query_vector)}]"
                sql = f"""
                SELECT id, payload,
                       (1 - VECTOR_DISTANCE(embedding, TO_VECTOR(:query_vec), COSINE)) AS score
                FROM {self.table_name}
                WHERE tenant_id = :tenant_id
                ORDER BY score DESC
                FETCH FIRST :limit ROWS ONLY
                """
                rows = session.execute(
                    text(sql),
                    {
                        "query_vec": vector_str,
                        "tenant_id": tenant_id,
                        "limit": limit,
                    },
                ).fetchall()

                results: List[VectorSearchResult] = []
                for row in rows:
                    memory_id, raw_payload, score = row[0], row[1], float(row[2])
                    if score >= score_threshold:
                        if isinstance(raw_payload, (str, bytes, bytearray)):
                            parsed_payload = json.loads(raw_payload)
                        else:
                            parsed_payload = raw_payload or {}
                        results.append(
                            VectorSearchResult(
                                memory_id=str(memory_id),
                                score=score,
                                payload=parsed_payload,
                            )
                        )
                return results

            rows = session.execute(
                text(
                    f"SELECT id, embedding, payload FROM {self.table_name} "
                    "WHERE tenant_id = :tenant_id"
                ),
                {"tenant_id": tenant_id},
            ).fetchall()

            scored: List[VectorSearchResult] = []
            q_values = [float(value) for value in query_vector]
            q_norm = math.sqrt(sum(value * value for value in q_values))
            if q_norm == 0:
                return []

            for row in rows:
                memory_id = row[0]
                stored_vector = (
                    json.loads(row[1]) if isinstance(row[1], str) else row[1]
                )
                stored_payload = (
                    json.loads(row[2])
                    if isinstance(row[2], str)
                    else (row[2] or {})
                )
                if len(stored_vector) != self.dimension:
                    logger.warning(
                        "Skipping vector with an incompatible stored dimension (id=%s).",
                        memory_id,
                    )
                    continue

                values = [float(value) for value in stored_vector]
                v_norm = math.sqrt(sum(value * value for value in values))
                if v_norm > 0:
                    dot = sum(a * b for a, b in zip(q_values, values, strict=True))
                    cosine_sim = dot / (q_norm * v_norm)
                    if cosine_sim >= score_threshold:
                        scored.append(
                            VectorSearchResult(
                                memory_id=str(memory_id),
                                score=round(cosine_sim, 4),
                                payload=stored_payload,
                            )
                        )

            scored.sort(key=lambda result: result.score, reverse=True)
            return scored[:limit]
        except Exception as exc:
            logger.warning("Vector similarity search failed (%s)", type(exc).__name__)
            return []
        finally:
            if not caller_owned:
                session.close()

    def readiness(self) -> Dict[str, Any]:
        """Report only a bootstrapped vector schema as ready."""
        receipt = storage_receipt()
        backend = receipt.get("backend")
        if backend == "oracle":
            backend_name = "oracle_23ai_native_vector"
        elif backend == "sqlite":
            backend_name = "sqlite_vector_emulation"
        else:
            backend_name = str(backend or "unknown")

        available = self._schema_initialized and backend in {"oracle", "sqlite"}
        if available:
            status = "available"
        elif backend in {"oracle", "sqlite"}:
            status = "not_initialized"
        else:
            status = "unavailable"

        return {
            "status": status,
            "available": available,
            "backend": backend_name,
            "dimension": self.dimension,
            "table": self.table_name,
        }


oracle_vector_adapter = OracleVectorAdapter()
