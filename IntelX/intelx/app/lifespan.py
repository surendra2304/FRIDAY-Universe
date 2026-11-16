"""Application lifespan management for startup, demonstration seeding, and background worker loop."""

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text

from intelx.core.logging import setup_logging
from intelx.core.settings import get_settings
from intelx.db.base import Base
from intelx.db.engine import dispose_engine, get_async_engine

logger = logging.getLogger("intelx.lifespan")


class EmbeddedWorkerHook:
    """Active background worker hook running OrchestrationWorker in an asyncio task."""

    def __init__(self) -> None:
        self.worker: Any = None
        self.task: asyncio.Task | None = None
        self.is_running = False

    async def start(self) -> None:
        """Start the background worker."""
        if self.is_running:
            return
        from intelx.orchestration.worker import OrchestrationWorker

        self.worker = OrchestrationWorker(poll_interval_s=1.0)
        self.task = asyncio.create_task(self.worker.start())
        self.is_running = True
        logger.info("Embedded background OrchestrationWorker started.")

    async def stop(self) -> None:
        """Stop the background worker."""
        if not self.is_running:
            return
        self.is_running = False
        if self.worker:
            self.worker.stop()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        logger.info("Embedded background OrchestrationWorker stopped cleanly.")


worker_hook = EmbeddedWorkerHook()


class NewsIngesterHook:
    """Hook managing the continuous news ingestion background loop."""

    def __init__(self) -> None:
        from intelx.ingestion.news_ingester import NewsIngester

        self._ingester = NewsIngester(interval_seconds=300)

    async def start(self) -> None:
        await self._ingester.start()

    async def stop(self) -> None:
        await self._ingester.stop()


class AutonomousResearchHook:
    """Hook managing the continuous autonomous research generation loop."""

    def __init__(self) -> None:
        from intelx.orchestration.autonomous_researcher import AutonomousResearcher

        self._researcher = AutonomousResearcher(interval_seconds=900)

    async def start(self) -> None:
        await self._researcher.start()

    async def stop(self) -> None:
        await self._researcher.stop()


class StandingWatchHook:
    """Hook managing the IntelX standing research watches (TASK-INT-007)."""

    def __init__(self) -> None:
        from intelx.watches.engine import WatchRunner

        self._runner = WatchRunner()

    async def start(self) -> None:
        await self._runner.start()

    async def stop(self) -> None:
        await self._runner.stop()


class HeadlineWatchHook:
    """Hook managing the standing financial-headline watch (TASK-IG-INT-01).

    Drives the shared HeadlineWatch from intelx.ingestion.feed_service —
    the same instance the /api/v1/feeds routes read — so the standing
    operation and the API surface never diverge.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        from intelx.ingestion.feed_service import get_headline_watch

        watch = get_headline_watch()
        interval = float(get_settings().HEADLINE_WATCH_INTERVAL_S)

        async def _loop() -> None:
            while True:
                try:
                    await watch.poll_once()
                except Exception:  # one bad sweep must not kill the watch
                    logger.exception("headline watch sweep failed")
                await asyncio.sleep(interval)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None


class AiRadarHook:
    """Hook managing the AI-trending radar polling loop (TASK-IG2-INT-05)."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        from intelx.ingestion.feed_service import get_ai_radar

        radar = get_ai_radar()
        interval = float(get_settings().AI_RADAR_INTERVAL_S)

        async def _loop() -> None:
            while True:
                try:
                    await radar.poll_once()
                except Exception:  # one bad sweep must not kill the radar
                    logger.exception("ai radar sweep failed")
                await asyncio.sleep(interval)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None


news_hook = NewsIngesterHook()
auto_research_hook = AutonomousResearchHook()
watch_hook = StandingWatchHook()
headline_hook = HeadlineWatchHook()
ai_radar_hook = AiRadarHook()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup, database initialization, and shutdown lifecycle."""
    settings = get_settings()

    # 1. Setup structured logging
    setup_logging(level="INFO")
    logger.info(f"Booting INTELX in [{settings.ENV}] mode (MOCK_MODE={settings.MOCK_MODE})")

    # 2. Ensure data directories exist
    data_dir = Path("./data").resolve()
    (data_dir / "raw").mkdir(parents=True, exist_ok=True)
    (data_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    # 3. Initialize database connection, schemas, and search indexes. The FTS5
    # block only runs for the test suite's SQLite engine; Oracle uses the
    # repository's case-insensitive substring search instead.
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "sqlite" and "pytest" in sys.modules:
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(id UNINDEXED, text);"
                )
            )
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(id UNINDEXED, text, quote);"
                )
            )
            await conn.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS chunks_after_insert AFTER INSERT ON chunks BEGIN "
                    "INSERT INTO chunks_fts(id, text) VALUES (new.id, new.text); "
                    "END;"
                )
            )
            await conn.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS chunks_after_delete AFTER DELETE ON chunks BEGIN "
                    "DELETE FROM chunks_fts WHERE id = old.id; "
                    "END;"
                )
            )
            await conn.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS claims_after_insert AFTER INSERT ON claims BEGIN "
                    "INSERT INTO claims_fts(id, text, quote) VALUES (new.id, new.text, new.quote); "
                    "END;"
                )
            )
            await conn.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS claims_after_delete AFTER DELETE ON claims BEGIN "
                    "DELETE FROM claims_fts WHERE id = old.id; "
                    "END;"
                )
            )
    logger.info("Database schemas and search indexes initialized.")

    # 3.5 Seed API keys from settings
    from intelx.core.auth import seed_api_keys_from_settings
    from intelx.db.session import get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await seed_api_keys_from_settings(session, settings)
    logger.info("API keys seeded from settings.")

    # 3.6 Seed demonstration research runs if explicitly enabled (default false)
    if getattr(settings, "ENABLE_DEMO_SEEDER", False):
        from intelx.db.demo_seeder import auto_seed_demonstrations_if_empty

        async with sessionmaker() as session:
            await auto_seed_demonstrations_if_empty(session)

    # 4. Start background services only when explicitly enabled (or when a
    # non-production development instance uses the embedded-worker default).
    run_embedded_worker = settings.RUN_EMBEDDED_WORKER
    if run_embedded_worker is None:
        run_embedded_worker = not settings.is_production()
    if run_embedded_worker:
        await worker_hook.start()

    if settings.ENABLE_NEWS_INGESTER:
        await news_hook.start()
        logger.info("Continuous news ingestion started.")

    if settings.ENABLE_AUTONOMOUS_RESEARCH:
        await auto_research_hook.start()
        logger.info("Autonomous research engine started.")

    if settings.ENABLE_STANDING_WATCHES:
        await watch_hook.start()
        logger.info("IntelX standing watches started.")

    if settings.ENABLE_HEADLINE_WATCH:
        await headline_hook.start()
        logger.info("IntelX headline watch started.")

    if settings.ENABLE_AI_RADAR:
        await ai_radar_hook.start()
        logger.info("IntelX AI radar started.")

    yield

    # Shutdown sequence: abort active tasks gracefully and flush SQLite handles within 5s
    logger.info("Initiating INTELX shutdown sequence...")
    try:
        async with asyncio.timeout(5.0):
            await auto_research_hook.stop()
            await watch_hook.stop()
            await headline_hook.stop()
            await ai_radar_hook.stop()
            await news_hook.stop()
            await worker_hook.stop()
            await dispose_engine()
    except (TimeoutError, Exception) as e:
        logger.warning(f"Graceful shutdown exceeded 5s or encountered error: {e}")
        try:
            await dispose_engine()
        except Exception:
            pass
    logger.info("INTELX shutdown complete.")
