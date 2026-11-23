"""Continuous autonomous forecasting scheduler with APScheduler and noise suppression."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from typing import Any
from uuid import uuid4

import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from futuris.agents.runner import AgentRunner
from futuris.connectors.factory import build_scheduler_connector
from futuris.core.enums import ForecastEventType, ForecastStatus
from futuris.core.lifecycle import LifecycleManager
from futuris.core.pipeline import ForecastingPipeline, IngestionStage
from futuris.core.schemas import Forecast, ForecastEvent
from futuris.evaluation.backtest import BacktestEngine
from futuris.evaluation.drift import DriftMonitor
from futuris.infra.events import EventEmitter, event_emitter
from futuris.infra.logging import get_logger
from futuris.models.adapters import StatsForecastUnavailableError
from futuris.storage.repositories import (
    EvaluationRepository,
    EventRepository,
    ForecastRepository,
    ObservationRepository,
    OutcomeRepository,
)
from futuris.upgrade.scheduler import DistributedLeaseTable, SafeScheduler

logger = get_logger("futuris.scheduler")


async def _recover_scheduler_session(session: Any) -> None:
    """Roll back a session a failed universe refresh left unusable.

    Mirrors ``universe_forecasting._recover_session``: a write cancelled
    or failed mid-flush leaves the session in pending-rollback state, in
    which every later target's write would fail too. Only the failed
    target's write is lost -- completed targets commit inside
    ``generate_universe_forecast`` itself.
    """
    if getattr(session, "is_active", True):
        return
    try:
        await session.rollback()
        logger.info("universe_provider_refresh_session_recovered")
    except Exception as exc:
        logger.warning("universe_provider_refresh_session_recovery_failed", error=str(exc))


@dataclass
class ForecastSubscription:
    """Subscription configuration defining scheduled forecast refresh requirements."""

    target: str
    horizon: timedelta = timedelta(hours=24)
    refresh_interval_minutes: int = 60
    delta_prob_threshold: float = 0.05
    delta_pred_threshold: float = 50.0
    enabled: bool = True


@dataclass
class _JobScope:
    """One scheduler job run's isolated store access (TASK-FUT-025).

    Before this task every job shared the process's single scheduler
    session (``app.py`` built one ``async_session_factory()`` session and
    handed it to every repo). APScheduler runs jobs concurrently, so a
    flush in one job collided with a flush or commit in another
    (``Session is already flushing``), and a rollback after any job's
    failure discarded other jobs' uncommitted writes -- the 17:45
    scoring pass logged scored 8 / n=374 while the store still held 366,
    and the 17:15 telemetry cycle emitted a forecast_updated event for a
    forecast that was never persisted (FUT-023 section 6).

    A scope owns the session when the scheduler was given a
    ``session_factory``: the job's repos are built on a fresh session,
    its writes commit when the job succeeds, and a failure rolls back
    only that job's writes. When no factory was given (tests that inject
    repos directly) the scope reuses the injected repos and commits,
    rolls back and closes nothing -- the legacy behaviour, so existing
    tests keep passing unchanged.
    """

    session: Any | None
    forecast_repo: ForecastRepository | None
    outcome_repo: OutcomeRepository | None
    event_repo: EventRepository | None
    observation_repo: ObservationRepository | None
    evaluation_repo: EvaluationRepository | None
    lifecycle_manager: LifecycleManager | None
    drift_monitor: DriftMonitor
    owns_session: bool

    async def commit(self) -> None:
        """Commit the job's writes; a no-op on a scope that owns no session."""
        if self.session is not None:
            await self.session.commit()

    async def rollback(self) -> None:
        """Roll the job's writes back; a no-op on a scope that owns no session."""
        if self.session is not None:
            from futuris.storage.db import safe_rollback

            await safe_rollback(self.session)


class ForecastScheduler:
    """Orchestrates unattended ingestion, forecast refreshes, lifecycle sweeps, and agent runs."""

    def __init__(
        self,
        forecast_repo: ForecastRepository | None = None,
        outcome_repo: OutcomeRepository | None = None,
        event_repo: EventRepository | None = None,
        observation_repo: ObservationRepository | None = None,
        evaluation_repo: EvaluationRepository | None = None,
        emitter: EventEmitter | None = None,
        pipeline: ForecastingPipeline | None = None,
        agent_runner: AgentRunner | None = None,
        lifecycle_manager: LifecycleManager | None = None,
        lease_table: DistributedLeaseTable | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self.scheduler = AsyncIOScheduler()
        self.forecast_repo = forecast_repo
        self.outcome_repo = outcome_repo
        self.event_repo = event_repo
        self.observation_repo = observation_repo
        self.evaluation_repo = evaluation_repo
        self.emitter = emitter or event_emitter
        # TASK-FUT-025: a callable returning a fresh AsyncSession (the
        # process-wide ``async_session_factory``, resolved at call time
        # by the caller -- see B23 in deps.py). When set, every job runs
        # on its own session (see _job_scope); when unset, jobs reuse
        # the injected repos exactly as before.
        self.session_factory = session_factory
        # The unattended pipeline reads from the configured telemetry source
        # (FUTURIS_TELEMETRY_SOURCE), not a hardcoded synthetic generator.
        self.pipeline = pipeline or ForecastingPipeline(
            ingestion=IngestionStage(connector=build_scheduler_connector())
        )
        self.agent_runner = agent_runner or AgentRunner()
        self.lifecycle_manager = lifecycle_manager
        self.drift_monitor = DriftMonitor(event_repo=event_repo)
        self.safe_scheduler = SafeScheduler(lease_table)
        self.subscriptions: list[ForecastSubscription] = [
            ForecastSubscription(target="service:checkout:capacity_exceedance_24h"),
            ForecastSubscription(target="trading:BTCUSDT:price_variance_24h"),
            ForecastSubscription(target="trading:ETHUSDT:price_variance_24h"),
            ForecastSubscription(target="trading:SOLUSDT:price_variance_24h"),
            ForecastSubscription(target="macro:SPY:return_exceedance_24h"),
            ForecastSubscription(target="macro:DGS10:yield_shift_30d"),
            ForecastSubscription(target="macro:T10Y2Y:curve_inversion_30d"),
            ForecastSubscription(target="macro:UNRATE:unemployment_drift_90d"),
        ]
        self._in_flight_tasks: set[asyncio.Task] = set()
        # TASK-FUT-025: the standalone 30-minute scoring job and a sweep's
        # tail-call scoring pass are two APScheduler job ids calling the
        # same function in one process. Serialise the scoring body so the
        # second run lists unscored forecasts only after the first has
        # committed (the unique forecast_id would otherwise make the
        # loser fail its commit; the tracker also guards each insert
        # with a savepoint, so a loser that does slip through still
        # cannot report the winner's rows as its own).
        self._scoring_lock = asyncio.Lock()
        self._mae_history: dict[str, list[float]] = {}
        # TASK-FUT-017: the standing per-cycle scoring record. Every cycle
        # that resolves matured forecasts scores them in the same pass
        # (see _score_matured_forecasts); the last pass is kept here so
        # the status surface can show it, and the scheduler never claims
        # a cycle scored anything it did not.
        self.last_scoring_summary: dict[str, Any] = {}
        self.last_cycle_scoring: dict[str, Any] = {}

    @asynccontextmanager
    async def _job_scope(self):
        """Yield the isolated store access for one job run (TASK-FUT-025).

        With a ``session_factory`` the scope owns a fresh session: the
        job's repos are built on it, the scope commits it when the job
        body returns, and a failure rolls back only this job's writes
        before the session is closed. Without a factory the scope
        reuses the injected repos and owns nothing (legacy path).
        """
        if self.session_factory is None:
            yield _JobScope(
                session=None,
                forecast_repo=self.forecast_repo,
                outcome_repo=self.outcome_repo,
                event_repo=self.event_repo,
                observation_repo=self.observation_repo,
                evaluation_repo=self.evaluation_repo,
                lifecycle_manager=self.lifecycle_manager,
                drift_monitor=self.drift_monitor,
                owns_session=False,
            )
            return
        from futuris.storage.db import safe_rollback

        session = self.session_factory()
        try:
            forecast_repo = ForecastRepository(session)
            outcome_repo = OutcomeRepository(session)
            event_repo = EventRepository(session)
            observation_repo = ObservationRepository(session)
            evaluation_repo = EvaluationRepository(session)
            lifecycle_manager = None
            if self.lifecycle_manager is not None:
                lifecycle_manager = LifecycleManager(
                    forecast_repo=forecast_repo,
                    outcome_repo=outcome_repo,
                    event_repo=event_repo,
                    resolver=getattr(self.lifecycle_manager, "resolver", None),
                    emitter=self.emitter,
                )
            yield _JobScope(
                session=session,
                forecast_repo=forecast_repo,
                outcome_repo=outcome_repo,
                event_repo=event_repo,
                observation_repo=observation_repo,
                evaluation_repo=evaluation_repo,
                lifecycle_manager=lifecycle_manager,
                drift_monitor=DriftMonitor(event_repo=event_repo),
                owns_session=True,
            )
            await session.commit()
        except Exception:
            await safe_rollback(session)
            raise
        finally:
            await session.close()

    def should_suppress_refresh_event(
        self,
        previous_forecast: Forecast,
        new_forecast: Forecast,
        delta_prob_threshold: float = 0.05,
        delta_pred_threshold: float = 50.0,
    ) -> bool:
        """Return True if change is below significance delta to suppress notification noise."""
        prev_p = previous_forecast.probability or 0.0
        new_p = new_forecast.probability or 0.0
        prob_diff = abs(new_p - prev_p)
        pred_diff = abs(new_forecast.prediction - previous_forecast.prediction)

        return prob_diff < delta_prob_threshold and pred_diff < delta_pred_threshold

    async def sync_dynamic_trading_subscriptions(self) -> list[str]:
        """Query Stratex to discover active trading pairs and register subscriptions."""
        from futuris.connectors.trading_bot import TradingBotConnector

        discovered_targets: list[str] = []
        try:
            connector = TradingBotConnector()
            pairs = await connector.discover_active_trade_pairs()
            existing_targets = {sub.target for sub in self.subscriptions}

            for pair in pairs:
                target = f"trading:{pair}:price_variance_24h"
                discovered_targets.append(target)
                if target not in existing_targets:
                    self.subscriptions.append(
                        ForecastSubscription(
                            target=target,
                            horizon=timedelta(hours=24),
                            refresh_interval_minutes=60,
                            delta_prob_threshold=0.05,
                            delta_pred_threshold=25.0,
                            enabled=True,
                        )
                    )
                    logger.info("dynamic_trading_subscription_registered", target=target, pair=pair)
        except Exception as exc:
            logger.debug("dynamic_trading_subscription_sync_failed", error=str(exc))

        return discovered_targets

    async def ingest_job(self) -> int:
        """Scheduled ingestion job pulling fresh telemetry and persisting observations."""
        logger.info("ingest_job_started")
        await self.sync_dynamic_trading_subscriptions()
        connector = build_scheduler_connector()
        now = datetime.now(UTC)
        obs = await connector.fetch(now - timedelta(days=1), now)
        # TASK-FUT-025: observations persist on this job's own session;
        # the scope commits them when the job returns.
        async with self._job_scope() as scope:
            if scope.observation_repo and obs:
                await scope.observation_repo.record_batch(obs)
        logger.info("ingest_job_completed", points=len(obs))
        return len(obs)

    async def forecast_refresh_job(self) -> list[Forecast]:
        """Scheduled job orchestrating forecasts and emitting updates for meaningful movements."""
        logger.info("forecast_refresh_job_started")
        await self.sync_dynamic_trading_subscriptions()
        refreshed: list[Forecast] = []
        now = datetime.now(UTC)

        # TASK-FUT-025: the refresh runs on its own session and commits
        # after every subscription, so a 12-minute cycle keeps the
        # forecasts it already fitted even if a later subscription
        # fails -- and a forecast_updated event is only emitted after
        # the forecast it names is committed (FUT-023 section 6.1: the
        # 17:15 cycle emitted an event for forecast 823e8307..., which
        # was never persisted).
        async with self._job_scope() as scope:
            for sub in self.subscriptions:
                if not sub.enabled:
                    continue

                prev_forecast: Forecast | None = None
                if scope.forecast_repo:
                    existing = await scope.forecast_repo.list_by_target(sub.target)
                    active_list = [f for f in existing if f.status == ForecastStatus.ACTIVE]
                    if active_list:
                        prev_forecast = active_list[-1]

                try:
                    res = await self.pipeline.run(target=sub.target, as_of=now, horizon=sub.horizon)
                except StatsForecastUnavailableError as exc:
                    # TASK-REL-018: explicit degradation per subscription -- log
                    # and skip; never let a missing model backend abort the
                    # whole refresh cycle or, worse, substitute a mock forecast.
                    logger.warning(
                        "forecast_refresh_skipped_statsforecast_unavailable",
                        target=sub.target,
                        error=str(exc),
                    )
                    continue
                new_f = res.forecast

                if scope.forecast_repo:
                    await scope.forecast_repo.create(new_f)

                refreshed.append(new_f)

                event: ForecastEvent | None = None
                if prev_forecast:
                    suppress = self.should_suppress_refresh_event(
                        previous_forecast=prev_forecast,
                        new_forecast=new_f,
                        delta_prob_threshold=sub.delta_prob_threshold,
                        delta_pred_threshold=sub.delta_pred_threshold,
                    )
                    if not suppress:
                        event = ForecastEvent(
                            event_id=uuid4(),
                            forecast_id=new_f.forecast_id,
                            event_type=ForecastEventType.FORECAST_UPDATED,
                            payload={
                                "target": new_f.target,
                                "previous_probability": prev_forecast.probability,
                                "new_probability": new_f.probability,
                                "previous_prediction": prev_forecast.prediction,
                                "new_prediction": new_f.prediction,
                            },
                            emitted_at=now,
                        )
                        if scope.event_repo:
                            await scope.event_repo.append(event)

                # Commit before emitting: the event must never name a
                # forecast the store does not hold.
                await scope.commit()
                if event is not None:
                    await self.emitter.emit(event)

                # High-conviction or significant forecast broadcast to FRIDAY mesh
                if new_f.probability and new_f.probability >= 0.70:
                    try:
                        from futuris.ecosystem.signals import signal_dispatcher

                        t = asyncio.create_task(
                            signal_dispatcher.notify_friday_forecast(
                                {
                                    "forecast_id": str(new_f.forecast_id),
                                    "target": new_f.target,
                                    "prediction": round(float(new_f.prediction), 4),
                                    "probability": round(float(new_f.probability), 4),
                                    "range_lower": round(float(new_f.range_lower), 4),
                                    "range_upper": round(float(new_f.range_upper), 4),
                                    "model_version": new_f.model_version,
                                    "status": new_f.status.value,
                                }
                            )
                        )
                        self._in_flight_tasks.add(t)
                        t.add_done_callback(self._in_flight_tasks.discard)
                    except Exception as exc:
                        logger.debug("friday_forecast_dispatch_skipped", error=str(exc))

        return refreshed

    async def universe_provider_refresh_job(self) -> list[Forecast]:
        """Refresh the TASK-FUT-012 series-provider universe targets.

        TASK-FUT-013: until this job existed, no scheduled path ever called
        :func:`generate_universe_forecast` -- the scheduler's only forecast
        job runs the telemetry pipeline over its eight subscriptions, so
        the provider targets (the only LIVE-evidence universe targets)
        could forecast only when a human or the matrix backfill happened
        to ask, and the matrix backfill in turn treated their pre-flip
        ``insufficient_data`` rows as present forever. This job closes the
        unattended path: hourly, one attempt per provider target, each
        refusal logged with its reason and never aborting the others.
        Persistence is ``generate_universe_forecast``'s own (it commits
        per target through the supplied session).
        """
        logger.info("universe_provider_refresh_job_started")
        from futuris.core.universe_domains import UNIVERSE_TARGETS
        from futuris.core.universe_forecasting import generate_universe_forecast

        targets = [t for t, spec in UNIVERSE_TARGETS.items() if spec.series_provider]
        if not targets:
            return []
        # TASK-FUT-025: the provider refresh runs on its own session.
        # generate_universe_forecast commits per target; on the old
        # shared session that commit collided with other jobs' flushes
        # ("Session is already flushing" for vyralx/intelx at 17:15 and
        # 18:15) and a failed target's rollback discarded other jobs'
        # pending writes. On a per-job session a target failure rolls
        # back only this job, and its commit touches only this job.
        async with self._job_scope() as scope:
            session = scope.session
            if session is None and scope.forecast_repo is not None:
                session = scope.forecast_repo.session
            if session is None:
                logger.warning(
                    "universe_provider_refresh_skipped_no_session",
                    targets=targets,
                )
                return []

            refreshed: list[Forecast] = []
            for target in targets:
                try:
                    forecast = await generate_universe_forecast(target, session=session)
                except Exception as exc:
                    logger.warning(
                        "universe_provider_refresh_target_failed",
                        target=target,
                        error=str(exc),
                    )
                    await _recover_scheduler_session(session)
                    continue
                refreshed.append(forecast)
                if forecast.status == ForecastStatus.INSUFFICIENT_DATA:
                    logger.warning(
                        "universe_provider_refresh_insufficient_data",
                        target=target,
                        error=(forecast.model_metadata or {}).get("error"),
                    )
                else:
                    logger.info(
                        "universe_provider_refresh_forecast",
                        target=target,
                        prediction=forecast.prediction,
                        model_version=forecast.model_version,
                    )
            logger.info(
                "universe_provider_refresh_job_completed",
                generated=len(refreshed),
                active=sum(1 for f in refreshed if f.status == ForecastStatus.ACTIVE),
            )
            return refreshed

    async def lifecycle_sweep_job(self) -> Any:
        """Scheduled lifecycle resolution and invalidation sweep."""
        logger.info("lifecycle_sweep_job_started")
        if not self.lifecycle_manager:
            return None
        # TASK-FUT-025: the sweep runs on its own session. Its outcomes
        # are committed before the tail-call scoring pass, so scoring
        # reads committed resolutions, not this session's uncommitted
        # flushes -- and a scoring failure can no longer roll the
        # sweep's resolutions back with it.
        async with self._job_scope() as scope:
            now = datetime.now(UTC)
            connector = build_scheduler_connector()
            obs = await connector.fetch(now - timedelta(days=2), now)
            df = pd.DataFrame([{"timestamp": o.observed_at, "value": o.value} for o in obs])
            report = await scope.lifecycle_manager.run_lifecycle_sweep(
                observations_df=df, as_of=now
            )
            await scope.commit()
            # TASK-FUT-017: the sweep just matured forecasts (their
            # horizons passed and outcomes were recorded); score them in
            # this same cycle instead of leaving them for a later job.
            await self._score_matured_forecasts(source="lifecycle_sweep_job", _scope=scope)
            return report

    async def backtest_nightly_job(self) -> None:
        """Nightly backtesting and drift check job."""
        logger.info("backtest_nightly_job_started")
        # TASK-FUT-025: reads and drift-event writes run on this job's
        # own session, like every other job.
        async with self._job_scope() as scope:
            backtester = BacktestEngine(
                forecast_repo=scope.forecast_repo,
                outcome_repo=scope.outcome_repo,
            )
            await self._run_backtest_nightly(scope, backtester)

    async def _run_backtest_nightly(self, scope: _JobScope, backtester: BacktestEngine) -> None:
        """Backtest body, split out so the job wrapper owns the session scope."""
        now = datetime.now(UTC)
        for sub in self.subscriptions:
            report = await backtester.run_backtest(
                target=sub.target,
                start_date=now - timedelta(days=7),
                end_date=now,
                stride_hours=24,
                horizon=sub.horizon,
            )
            if report.scored_forecasts == 0:
                # No origin had a genuinely observed actual, so the report's
                # metrics are NaN: appending one to the drift history would
                # poison every later comparison for this target.
                logger.info(
                    "drift_check_skipped_no_scored_forecasts",
                    target=sub.target,
                    unscored=report.unscored_forecasts,
                )
                continue
            h_metrics = list(report.metrics_by_horizon.values())
            if h_metrics:
                recent_mae = h_metrics[0].mae
                # Drift is only detectable against real history: keep the MAEs
                # this process has actually measured and wait for enough of
                # them instead of comparing against invented baselines.
                history = self._mae_history.setdefault(sub.target, [])
                history.append(recent_mae)
                window = history[-30:]
                if len(window) >= 5:
                    await scope.drift_monitor.check_and_emit(
                        model_version=getattr(sub, "model_version", None) or "unknown",
                        historical_scores=window[:-1],
                        recent_scores=[recent_mae],
                    )
                else:
                    logger.info(
                        "drift_check_skipped_insufficient_history",
                        target=sub.target,
                        samples=len(window),
                    )

    async def calibration_sweep_job(self) -> dict[str, Any]:
        """Scheduled calibration sweep comparing realized outcomes with historical forecasts.

        Enforces Safety Invariant 3 (Brier Score Penalization):
        Computes Brier calibration scores on resolved forecasts and penalizes overconfidence
        by conformally widening uncertainty intervals.
        """
        logger.info("calibration_sweep_job_started")
        from futuris.core.resolution import outcome_resolver
        from futuris.evaluation.calibration import CalibrationAnalyzer

        now = datetime.now(UTC)
        resolved_count = 0

        # TASK-FUT-025: the sweep runs on its own session. Before this
        # task it shared the scheduler's single session with the scoring
        # and provider jobs: a concurrent flush raised "Session is
        # already flushing" inside list_resolved_with_forecasts (17:15)
        # and inside the resolve loop (b5c0a661 + f8921fe7 at 18:15).
        async with self._job_scope() as scope:
            # 1. Resolve expired forecasts against observations
            if scope.outcome_repo:
                unresolved = await scope.outcome_repo.list_unresolved(past_horizon=True)
                if unresolved:
                    connector = build_scheduler_connector()
                    earliest = min(f.as_of for f in unresolved)
                    obs = await connector.fetch(earliest, now)
                    df = pd.DataFrame([{"timestamp": o.observed_at, "value": o.value} for o in obs])

                    for f in unresolved:
                        try:
                            outcome = outcome_resolver.resolve_forecast(f, df)
                            await scope.outcome_repo.record_outcome(outcome)
                            # Commit each resolution as it lands: a later
                            # failure in this loop must not roll back the
                            # outcomes already recorded, and the next
                            # record_outcome must start from a clean
                            # session (a failed flush leaves it in
                            # pending-rollback state).
                            await scope.commit()
                            resolved_count += 1
                        except Exception as exc:
                            await scope.rollback()
                            logger.warning(
                                "calibration_resolve_failed",
                                forecast_id=str(f.forecast_id),
                                error=str(exc),
                            )

            # TASK-FUT-025: the recorded outcomes are committed before
            # the sweep reads them back (step 2) and before scoring
            # them, so neither step can see uncommitted flushes.
            await scope.commit()

            # TASK-FUT-017: the sweep just recorded outcomes for matured
            # forecasts; score them in this same cycle, so a forecast whose
            # horizon passed is scored by the cycle that resolved it.
            if resolved_count:
                await self._score_matured_forecasts(source="calibration_sweep_job", _scope=scope)

            # 2. Compute Brier calibration metrics across resolved pairs
            analyzer = CalibrationAnalyzer()
            metrics: dict[str, Any] = {
                "brier_score": 0.0,
                "ece": 0.0,
                "resolved_count": resolved_count,
                "overconfidence_penalized": False,
                "interval_expansion_factor": 1.0,
                "target_breakdown": {},
            }

            if scope.outcome_repo:
                pairs = await scope.outcome_repo.list_resolved_with_forecasts(limit=1000)
                probs: list[float] = []
                actuals: list[bool] = []
                target_groups: dict[str, list[tuple[Any, Any]]] = {}

                for f, o in pairs:
                    if f.probability is not None and o.event_occurred is not None:
                        probs.append(float(f.probability))
                        actuals.append(bool(o.event_occurred))
                        tgt = str(f.target or "global")
                        target_groups.setdefault(tgt, []).append((f, o))

                # Target-level Brier calibration breakdown
                target_breakdown: dict[str, dict[str, Any]] = {}
                for tgt, group in target_groups.items():
                    t_probs = [float(f.probability) for f, o in group]
                    t_acts = [bool(o.event_occurred) for f, o in group]
                    if t_probs and t_acts:
                        t_metrics = analyzer.update_calibration_metrics(t_probs, t_acts)
                        target_breakdown[tgt] = {
                            "brier_score": round(float(t_metrics.get("brier_score", 0.0)), 4),
                            "ece": round(float(t_metrics.get("ece", 0.0)), 4),
                            "resolved_count": len(t_probs),
                        }
                metrics["target_breakdown"] = target_breakdown

                if probs and actuals:
                    cal_metrics = analyzer.update_calibration_metrics(probs, actuals)
                    brier = cal_metrics.get("brier_score", 0.0)
                    ece = cal_metrics.get("ece", 0.0)
                    metrics.update(cal_metrics)

                    # Overconfidence penalty: if Brier score > 0.20 or ECE > 0.10,
                    # mark penalty and compute interval expansion factor
                    if brier > 0.20 or ece > 0.10:
                        metrics["overconfidence_penalized"] = True
                        expansion = round(1.0 + max(0.0, (brier - 0.20) * 2.0), 3)
                        metrics["interval_expansion_factor"] = expansion
                        logger.warning(
                            "calibration_overconfidence_detected",
                            brier_score=brier,
                            ece=ece,
                            expansion_factor=metrics["interval_expansion_factor"],
                        )
                        try:
                            from futuris.ecosystem.signals import signal_dispatcher

                            t_risk = asyncio.create_task(
                                signal_dispatcher.notify_stratex_risk_regime(
                                    target="calibration:brier_overconfidence",
                                    risk_report={
                                        "brier_score": brier,
                                        "ece": ece,
                                        "interval_expansion_factor": expansion,
                                        "basel_traffic_light": "yellow" if brier < 0.35 else "red",
                                        "timestamp": now.isoformat(),
                                    },
                                )
                            )
                            self._in_flight_tasks.add(t_risk)
                            t_risk.add_done_callback(self._in_flight_tasks.discard)
                        except Exception as exc:
                            logger.debug("stratex_risk_dispatch_skipped", error=str(exc))
                    else:
                        metrics["overconfidence_penalized"] = False
                        metrics["interval_expansion_factor"] = 1.0

                    # 3. Record evaluation run
                    if scope.evaluation_repo:
                        model_v = (
                            pairs[0][0].model_version if pairs else "statsforecast.AutoARIMA:v1.0"
                        )
                        eval_metrics = {
                            "brier_score": float(metrics.get("brier_score", 0.0)),
                            "ece": float(metrics.get("ece", 0.0)),
                            "interval_expansion_factor": float(
                                metrics.get("interval_expansion_factor", 1.0)
                            ),
                        }
                        await scope.evaluation_repo.save_run(
                            model_version=model_v,
                            dataset_name="live_telemetry_calibration",
                            metrics=eval_metrics,
                        )

            # TASK-FUT-025: commit the evaluation run before broadcasting
            # completion, so the broadcast never claims a run the store
            # does not hold.
            await scope.commit()

            # Broadcast calibration sweep completed event over stream hub
            try:
                from futuris.api.routers.streaming import stream_hub

                await stream_hub.broadcast("calibration_sweep_completed", metrics)
            except Exception as b_err:
                logger.debug("calibration_sweep_broadcast_failed", error=str(b_err))

            logger.info("calibration_sweep_job_completed", metrics=metrics)
            return metrics

    async def _score_matured_forecasts(
        self, *, source: str, _scope: _JobScope | None = None
    ) -> dict[str, Any]:
        """Score matured forecasts as part of the calling cycle (TASK-FUT-017).

        Best-effort by design: scoring reads the tracker store and must
        never abort the cycle that called it. The result is recorded as
        the last cycle scoring summary either way, so the status surface
        shows what the last cycle actually did -- including a failure.

        TASK-FUT-025: when the caller already holds a job scope, scoring
        runs inside it (same transaction, sequential -- the caller
        committed its resolutions first); otherwise scoring opens its
        own scope, so a standalone scoring job never shares a session
        with a concurrent sweep.
        """
        try:
            if _scope is not None:
                result = await self.forecast_scoring_job(_scope=_scope)
            else:
                result = await self.forecast_scoring_job()
        except Exception as exc:  # scoring must never break a cycle
            result = {"scored": 0, "status": "error", "error": str(exc)}
            logger.warning("cycle_scoring_failed", source=source, error=str(exc))
        self.last_cycle_scoring = {
            **result,
            "source": source,
            "at": datetime.now(UTC).isoformat(),
        }
        return self.last_cycle_scoring

    async def forecast_scoring_job(
        self, _scope: _JobScope | None = None
    ) -> dict[str, Any]:
        """TASK-FUT-006: score resolved forecasts into the live tracker store.

        Runs alongside the calibration sweep, which records outcomes: every
        resolved forecast with a numeric actual gets exactly one
        forecast-vs-actual score row (point error, interval hit, Winkler)
        in ``forecast_scores``, which is what the live calibration report
        aggregates. Scoring is idempotent, so cadence overlaps are
        harmless; a scoring failure is logged and reported, never raised
        into the scheduler.

        TASK-FUT-017: this is also the standing per-cycle scoring step --
        the lifecycle and calibration sweeps call it at the end of the
        cycle that resolves matured forecasts, so a forecast is scored
        by the cycle its horizon passed in, not by a later job.

        TASK-FUT-025: the job runs on its own session (or the caller's
        scope when invoked as a sweep's tail call). The standalone job
        and a sweep's tail call are two APScheduler job ids, so they can
        run concurrently -- the scoring body is serialised by
        ``_scoring_lock`` and each run commits before it reports, so the
        reported counts can only describe persisted rows (the 17:45
        drain logged scored 8 / n=374 from an uncommitted session while
        the store still held 366).
        """
        logger.info("forecast_scoring_job_started")
        if _scope is not None:
            return await self._run_forecast_scoring(_scope)
        async with self._job_scope() as scope:
            return await self._run_forecast_scoring(scope)

    async def _run_forecast_scoring(self, scope: _JobScope) -> dict[str, Any]:
        """Scoring body, split out so the caller owns the session scope."""
        if not scope.outcome_repo:
            result: dict[str, Any] = {"scored": 0, "status": "no_storage"}
            self.last_scoring_summary = {
                **result,
                "scored_at": datetime.now(UTC).isoformat(),
            }
            return result
        try:
            async with self._scoring_lock:
                from futuris.services.forecast_tracker import ForecastTracker

                tracker = ForecastTracker(scope.outcome_repo.session)
                result = dict(await tracker.score_resolved())
                # Commit the scores BEFORE reporting them, and report the
                # counts read back from the committed store: the 17:45
                # drain's n_scored_total came from the same uncommitted
                # session that held the flushed-but-unpersisted rows.
                await scope.commit()
                report = await tracker.calibration_report()
                result["report_status"] = report["status"]
                result["n_scored_total"] = report["n_scored"]
                result["rolling_hit_rate_30d"] = report["rolling_hit_rate_30d"]
            self.last_scoring_summary = {
                **result,
                "scored_at": datetime.now(UTC).isoformat(),
            }
            logger.info("forecast_scoring_job_completed", metrics=result)
            return result
        except Exception as exc:
            logger.warning("forecast_scoring_job_failed", error=str(exc))
            result = {"scored": 0, "status": "error", "error": str(exc)}
            self.last_scoring_summary = {
                **result,
                "scored_at": datetime.now(UTC).isoformat(),
            }
            return result

    async def stream_risk_pulse_job(self) -> dict[str, Any]:
        """Periodic pulse computing portfolio tail-risk and forward Monte Carlo fan charts.

        Dispatches live metrics to Server-Sent Events (SSE) and WebSockets every 5 minutes.
        Safety Invariant: prediction_is_not_authorization.
        """
        logger.info("stream_risk_pulse_job_started")
        from futuris.api.routers.risk import calculate_portfolio_risk_payload
        from futuris.api.routers.streaming import stream_hub

        try:
            # TASK-FUT-025: the store read runs on this job's own session.
            async with self._job_scope() as scope:
                risk_payload = await calculate_portfolio_risk_payload(
                    obs_repo=scope.observation_repo,
                    window_days=30,
                    confidence_level=0.95,
                )
            await stream_hub.broadcast("risk_portfolio_update", risk_payload)

            summary = risk_payload.get("portfolio_summary", {})
            highest_risk = summary.get("highest_risk_asset", "BTCUSDT")

            # Determine base mark price for highest risk asset
            positions = risk_payload.get("positions", [])
            matching_pos = next(
                (p for p in positions if p.get("symbol") == highest_risk), None
            )
            # TASK-FUT-005: the fallback constants below are stale hardcoded
            # estimates, not a price feed. When no verified position carries
            # a current price the fan chart must say so: broadcasting 67000
            # as "current_price" for BTC presented an invented price as live
            # (production positions were unauthorized on 2026-11-15, so this
            # fallback was the live path).
            has_verified_price = bool(
                matching_pos and float(matching_pos.get("current_price", 0.0)) > 0
            )
            price_source = (
                "verified_position_price" if has_verified_price else "hardcoded_fallback_estimate"
            )
            base_price = (
                float(matching_pos.get("current_price", 0.0))
                if has_verified_price
                else (
                    67000.0
                    if "BTC" in highest_risk
                    else 2600.0
                    if "ETH" in highest_risk
                    else 170.0
                )
            )

            # Assets risk report to get cvar_95 or var_95 for hourly volatility
            assets = risk_payload.get("assets", [])
            matching_asset = next((a for a in assets if a.get("symbol") == highest_risk), None)
            vol_daily = (
                float(matching_asset.get("var_95", 0.03)) if matching_asset else 0.03
            )
            vol_hourly = max(0.005, vol_daily / (24.0**0.5))

            # Forward 24-step Monte Carlo quantile trajectories
            p10: list[float] = []
            p25: list[float] = []
            p50: list[float] = []
            p75: list[float] = []
            p90: list[float] = []

            for step in range(1, 25):
                sigma = vol_hourly * (step**0.5)
                # Standard normal quantiles: p10=-1.282, p25=-0.674, p50=0, p75=+0.674, p90=+1.282
                p10.append(round(base_price * (1.0 - 1.282 * sigma), 2))
                p25.append(round(base_price * (1.0 - 0.674 * sigma), 2))
                p50.append(round(base_price * (1.0 + 0.0001 * step), 2))
                p75.append(round(base_price * (1.0 + 0.674 * sigma), 2))
                p90.append(round(base_price * (1.0 + 1.282 * sigma), 2))

            fan_chart_payload = {
                "target": f"trading:{highest_risk}:price",
                "asset": highest_risk,
                "current_price": round(base_price, 2),
                "price_source": price_source,
                "evidence_class": "live" if has_verified_price else "synthetic",
                "horizon_hours": 24,
                "quantiles": {
                    "p10": p10,
                    "p25": p25,
                    "p50": p50,
                    "p75": p75,
                    "p90": p90,
                },
                "prediction_is_not_authorization": True,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            await stream_hub.broadcast(
                "fan_chart_simulation",
                fan_chart_payload,
                target=f"trading:{highest_risk}:price",
            )
            logger.info(
                "stream_risk_pulse_job_completed",
                highest_risk=highest_risk,
                base_price=base_price,
            )
            return {
                "risk_payload": risk_payload,
                "fan_chart": fan_chart_payload,
            }
        except Exception as exc:
            logger.warning("stream_risk_pulse_job_failed", error=str(exc))
            return {}

    def start(self) -> None:
        """Start scheduler with registered recurring jobs."""
        self.scheduler.add_job(self.ingest_job, "interval", minutes=15, id="ingest_job")
        self.scheduler.add_job(
            self.forecast_refresh_job, "interval", minutes=60, id="forecast_refresh_job"
        )
        self.scheduler.add_job(
            self.universe_provider_refresh_job,
            "interval",
            minutes=60,
            id="universe_provider_refresh_job",
        )
        self.scheduler.add_job(
            self.lifecycle_sweep_job, "interval", minutes=30, id="lifecycle_sweep_job"
        )
        self.scheduler.add_job(
            self.calibration_sweep_job, "interval", minutes=30, id="calibration_sweep_job"
        )
        self.scheduler.add_job(
            self.forecast_scoring_job, "interval", minutes=30, id="forecast_scoring_job"
        )
        self.scheduler.add_job(
            self.stream_risk_pulse_job, "interval", minutes=5, id="stream_risk_pulse_job"
        )
        self.scheduler.add_job(self.backtest_nightly_job, "cron", hour=2, id="backtest_nightly_job")
        self.scheduler.start()
        logger.info("scheduler_started")

    async def shutdown(self) -> None:
        """Gracefully drain running jobs and shutdown scheduler."""
        logger.info("scheduler_shutdown_requested")
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            await asyncio.sleep(0.01)
        if self._in_flight_tasks:
            await asyncio.gather(*self._in_flight_tasks, return_exceptions=True)
        logger.info("scheduler_shutdown_complete")
