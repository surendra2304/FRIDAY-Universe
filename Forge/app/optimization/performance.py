"""
Performance Optimization and Storage Tuning Utilities for Project FORGE.
"""

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from app.core.logging import get_logger
from app.memory.db import DatabaseManager, db_manager

logger = get_logger("optimization.performance")


class PerformanceOptimizer:
    """Configures high-performance runtime middleware and database PRAGMAs."""

    @classmethod
    def apply_fastapi_optimizations(cls, app: FastAPI):
        """Enable response compression (GZip) for payload size reduction."""
        app.add_middleware(GZipMiddleware, minimum_size=1000)
        logger.info("Applied GZip compression middleware.")

    @classmethod
    async def optimize_sqlite_pragmas(cls, db: DatabaseManager = db_manager):
        """Apply high-performance production SQLite PRAGMA settings.

        PRAGMAs are SQLite-only. On Oracle/PostgreSQL the call is skipped (the
        connection wrapper already ignores PRAGMA statements, but skipping avoids
        five pointless round-trips per startup).
        """
        try:
            async with db.connection() as conn:
                if not db.is_sqlite:
                    logger.debug(
                        f"Skipping SQLite PRAGMAs: active backend is {db.dialect_name}."
                    )
                    return
                await conn.execute("PRAGMA journal_mode = WAL;")
                await conn.execute("PRAGMA synchronous = NORMAL;")
                await conn.execute("PRAGMA busy_timeout = 5000;")
                await conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
                await conn.execute("PRAGMA temp_store = MEMORY;")
            logger.info("SQLite production PRAGMAs applied (WAL mode, NORMAL sync, busy_timeout 5s, 64MB cache).")
        except Exception as e:
            logger.warning(f"Could not apply SQLite optimizations: {e}")


performance_optimizer = PerformanceOptimizer()
