"""ForecastEngine: Pipeline orchestration with calibration confidence and drivers."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from futuris.connectors.base import BaseConnector, Observation
from futuris.connectors.factory import build_scheduler_connector
from futuris.connectors.intelx_context import IntelXContextInjector
from futuris.connectors.provenance import DataProvenance, resolve_provenance
from futuris.core.enums import EvidenceClass, ForecastStatus, SignalClass
from futuris.core.schemas import Driver, Forecast
from futuris.evaluation.confidence import ConfidenceAssessor, confidence_assessor
from futuris.evidence.snapshots import EvidenceSnapshotter
from futuris.features.contextualize import ContextLayer
from futuris.features.drivers import DriverAnalyzer
from futuris.features.normalize import Normalizer
from futuris.infra.config import settings
from mesh.heavy_task import HeavyTaskCoordinator, HeavyTaskLease, coordinator_from_environment
from futuris.infra.cpu import (
    cpu_saturated,
    run_cpu,
    run_cpu_process,
    run_cpu_process_cancellable,
)
from futuris.infra.logging import get_logger
from futuris.models.ai_universe_enhanced import AIUniverseModelEnhancer
from futuris.models.base import ModelPrediction
from futuris.models.registry import model_registry
from futuris.models.routing import ModelRouter, SeriesMetadata
from futuris.models.selection import select_best_adapter

logger = get_logger("futuris.core.engine")


class ForecastEngine:
    """Orchestrates features, model selection, calibration, drivers, and forecast assembly."""

    def __init__(
        self,
        connector: BaseConnector | None = None,
        snapshotter: EvidenceSnapshotter | None = None,
        normalizer: Normalizer | None = None,
        context_layer: ContextLayer | None = None,
        router: ModelRouter | None = None,
        assessor: ConfidenceAssessor | None = None,
        driver_analyzer: DriverAnalyzer | None = None,
        intelx_injector: IntelXContextInjector | None = None,
        enhancer: AIUniverseModelEnhancer | None = None,
        heavy_task_coordinator: HeavyTaskCoordinator | None = None,
    ) -> None:
        # TASK-REL-018: default to the CONFIGURED telemetry source
        # (FUTURIS_TELEMETRY_SOURCE via the connector factory), not a
        # hardcoded synthetic generator; provenance is derived per run and
        # labels the forecast honestly either way.
        self.connector = connector or build_scheduler_connector()
        self.snapshotter = snapshotter or EvidenceSnapshotter()
        self.normalizer = normalizer or Normalizer()
        self.context_layer = context_layer or ContextLayer()
        self.router = router or ModelRouter()
        self.confidence_assessor = assessor or confidence_assessor
        self.driver_analyzer = driver_analyzer or DriverAnalyzer()
        self.intelx_injector = intelx_injector or IntelXContextInjector(
            base_url=settings.INTELX_URL,
            api_key=settings.INTELX_API_KEY,
        )
        self.enhancer = enhancer or AIUniverseModelEnhancer()
        self.heavy_task_coordinator = (
            heavy_task_coordinator
            if heavy_task_coordinator is not None
            else coordinator_from_environment()
        )

    async def orchestrate(
        self,
        target: str,
        as_of: datetime,
        horizon: timedelta,
        capacity_threshold: float = 4000.0,
        history_lookback_days: int = 14,
        evidence_scope: str | None = None,
        historical_resolved_count: int = 0,
        model_budget_seconds: float | None = None,
    ) -> list[Forecast]:
        """Produce a draft Forecast object for the target with zero future-data leakage.

        I/O (telemetry fetch, IntelX research) stays on the event loop. The
        CPU-bound core -- normalization, feature building, candidate backtest,
        refit, driver analysis and assembly -- runs on the shared CPU gate, so
        one forecast no longer freezes every other request.
        """
        as_of = as_of.replace(tzinfo=UTC) if as_of.tzinfo is None else as_of.astimezone(UTC)

        start_time = as_of - timedelta(days=history_lookback_days)

        # 1. Ingest raw observations
        raw_observations = await self.connector.fetch(start_time, as_of)

        # TASK-REL-018: provenance is DERIVED from the connector and the
        # observations it actually returned. A caller-supplied
        # ``evidence_scope`` label is accepted for signature compatibility
        # but never trusted -- a string claim must not be able to relabel
        # synthetic data as measured (or vice versa).
        if evidence_scope is not None:
            logger.warning(
                "caller_evidence_scope_ignored",
                target=target,
                claimed=evidence_scope,
                reason="provenance is derived from the actual connector and observations",
            )
        provenance = resolve_provenance(self.connector, raw_observations)

        # 1.1 Ingest qualitative exogenous research from IntelX
        intelx_reports: list[Any] = []
        exogenous_adj: dict[str, float] = {
            "sentiment_multiplier": 1.0,
            "volatility_multiplier": 1.0,
            "confidence_penalty": 0.0,
        }
        try:
            intelx_reports = await self.intelx_injector.fetch_recent_research(target, as_of=as_of)
            exogenous_adj = self.intelx_injector.compute_exogenous_adjustments(intelx_reports)
        except Exception as exc:
            logger.warning("intelx_context_injection_skipped", target=target, error=str(exc))

        degraded = cpu_saturated()
        coordinator = self.heavy_task_coordinator

        if coordinator is not None:
            if not self._supports_process_isolation():
                # Injected component graphs can include non-picklable or
                # non-cancellable native work. Do not claim fleet-wide
                # serialization for a workload we cannot stop on lease loss.
                raise RuntimeError(
                    "distributed forecast execution requires default, process-isolatable "
                    "components or an explicit cancellable worker adapter"
                )

            async def run_coordinated_forecast(lease: HeavyTaskLease) -> list[Forecast]:
                lease.ensure_valid()
                result = await run_cpu_process_cancellable(
                    "orchestrate",
                    _orchestrate_with_default_components,
                    str(self.snapshotter.base_storage_path),
                    sorted(self.snapshotter.denied_fields),
                    float(self.enhancer.confidence_scaling),
                    _exclusive=True,
                    target=target,
                    as_of=as_of,
                    horizon=horizon,
                    capacity_threshold=capacity_threshold,
                    raw_observations=raw_observations,
                    intelx_reports=intelx_reports,
                    exogenous_adj=exogenous_adj,
                    provenance_source_id=provenance.source_id,
                    provenance_evidence_class=provenance.evidence_class.value,
                    provenance_connector=provenance.connector,
                    provenance_synthetic=provenance.synthetic,
                    historical_resolved_count=historical_resolved_count,
                    model_budget_seconds=model_budget_seconds,
                    cpu_saturated=degraded,
                )
                lease.ensure_valid()
                return result

            return await coordinator.run(
                task_id="futuris:forecast-engine",
                owner="futuris",
                operation=run_coordinated_forecast,
                wait_timeout=None,
            )

        if self._supports_process_isolation():
            return await run_cpu_process(
                "orchestrate",
                _orchestrate_with_default_components,
                str(self.snapshotter.base_storage_path),
                sorted(self.snapshotter.denied_fields),
                float(self.enhancer.confidence_scaling),
                _exclusive=not degraded,
                target=target,
                as_of=as_of,
                horizon=horizon,
                capacity_threshold=capacity_threshold,
                raw_observations=raw_observations,
                intelx_reports=intelx_reports,
                exogenous_adj=exogenous_adj,
                provenance_source_id=provenance.source_id,
                provenance_evidence_class=provenance.evidence_class.value,
                provenance_connector=provenance.connector,
                provenance_synthetic=provenance.synthetic,
                historical_resolved_count=historical_resolved_count,
                model_budget_seconds=model_budget_seconds,
                cpu_saturated=degraded,
            )
        return await run_cpu(
            "orchestrate",
            self._orchestrate_sync,
            _exclusive=not degraded,
            target=target,
            as_of=as_of,
            horizon=horizon,
            capacity_threshold=capacity_threshold,
            raw_observations=raw_observations,
            intelx_reports=intelx_reports,
            exogenous_adj=exogenous_adj,
            provenance_source_id=provenance.source_id,
            provenance_evidence_class=provenance.evidence_class.value,
            provenance_connector=provenance.connector,
            provenance_synthetic=provenance.synthetic,
            historical_resolved_count=historical_resolved_count,
            model_budget_seconds=model_budget_seconds,
            cpu_saturated=degraded,
        )

    def _supports_process_isolation(self) -> bool:
        """Use a fresh worker only when all CPU-stage dependencies are known defaults."""
        return (
            type(self.snapshotter) is EvidenceSnapshotter
            and type(self.normalizer) is Normalizer
            and type(self.context_layer) is ContextLayer
            and type(self.router) is ModelRouter
            and type(self.confidence_assessor) is ConfidenceAssessor
            and type(self.driver_analyzer) is DriverAnalyzer
            and type(self.enhancer) is AIUniverseModelEnhancer
        )

    def _orchestrate_sync(
        self,
        *,
        target: str,
        as_of: datetime,
        horizon: timedelta,
        capacity_threshold: float,
        raw_observations: list[Observation],
        intelx_reports: list[Any],
        exogenous_adj: dict[str, float],
        historical_resolved_count: int,
        model_budget_seconds: float | None = None,
        cpu_saturated: bool = False,
        provenance_source_id: str | None = None,
        provenance_evidence_class: str | None = None,
        provenance_connector: str | None = None,
        provenance_synthetic: bool | None = None,
    ) -> list[Forecast]:
        """CPU-bound core of :meth:`orchestrate`; runs in a worker thread."""
        # TASK-REL-018: provenance normally arrives pre-derived from
        # ``orchestrate`` (the worker's own default connector must never
        # relabel the parent's input). Direct callers get it derived from
        # this engine's connector and the observations themselves.
        if provenance_source_id is not None:
            provenance = DataProvenance(
                connector=provenance_connector or "unknown",
                source_id=provenance_source_id,
                evidence_class=EvidenceClass(provenance_evidence_class or "synthetic"),
                synthetic=bool(provenance_synthetic),
            )
        else:
            provenance = resolve_provenance(self.connector, raw_observations)

        # 2. Normalize and align grid
        signal_set = self.normalizer.normalize(raw_observations)

        # 3. Contextualize features (strictly up to as_of)
        features_df = self.context_layer.build_feature_table(signal_set, as_of=as_of)

        # 4. Freeze immutable point-in-time snapshot
        forecast_id = uuid4()
        evidence_ref = self.snapshotter.freeze_snapshot(
            signal_set=signal_set,
            as_of=as_of,
            forecast_id=forecast_id,
            source_id=provenance.source_id,
            signal_class=SignalClass.TELEMETRY,
            evidence_class=provenance.evidence_class,
        )

        # 5. Route candidate models
        step_minutes = signal_set.grid_step_minutes
        horizon_steps = max(1, int(horizon.total_seconds() // (step_minutes * 60)))
        metadata = SeriesMetadata(
            history_points=len(features_df),
            frequency_minutes=step_minutes,
            has_weekly_seasonality=len(features_df) >= 2016,
        )
        candidates = self.router.select_candidates(
            metadata, horizon_steps, signal_set.quality_report
        )

        # 6. Held-out backtest selection over candidates
        y_series = features_df["value"]
        x_df = features_df.drop(columns=["value"])

        val_steps = min(horizon_steps, max(12, len(y_series) // 5))
        y_train = y_series.iloc[:-val_steps]
        x_train = x_df.iloc[:-val_steps]
        y_val = y_series.iloc[-val_steps:].to_numpy()

        selection = select_best_adapter(
            candidates,
            x_train=x_train,
            y_train=y_train,
            y_val=y_val,
            as_of=as_of,
            val_steps=val_steps,
            step_minutes=step_minutes,
            budget_seconds=model_budget_seconds,
            cpu_saturated=cpu_saturated,
        )
        best_adapter = selection.adapter
        best_score = selection.score
        is_fallback = selection.is_fallback

        # 7. Refit best adapter on complete historical dataset
        best_adapter.fit(x_df, y_series, as_of=as_of)
        final_prediction: ModelPrediction = best_adapter.predict(
            horizon=horizon_steps,
            capacity_threshold=capacity_threshold,
            probability_method="empirical",
        )

        model_version_str = model_registry.get_version_string(best_adapter)
        if is_fallback:
            model_version_str = f"{model_version_str}:fallback_after_candidate_failures"

        # 7.1 Enhance uncertainty intervals with IntelX qualitative research
        enhanced_ctx = self.enhancer.enhance_forecast(
            base_prediction=final_prediction.central_estimate,
            range_lower=final_prediction.range_lower,
            range_upper=final_prediction.range_upper,
            context_factors=exogenous_adj,
        )

        # 8. Compute Meta-Confidence via ConfidenceAssessor
        confidence_result = self.confidence_assessor.evaluate(
            historical_resolved_count=historical_resolved_count,
            backtest_sample_size=len(y_train),
            long_run_mae=best_score,
            recent_30d_mae=best_score,
            quality_report=signal_set.quality_report,
        )

        # 9. Extract Explanatory Drivers using DriverAnalyzer
        drivers = self.driver_analyzer.analyze_drivers(
            features_df=features_df,
            target_column="value",
            evidence_id=evidence_ref.evidence_id,
        )
        if not drivers:
            mean_val = float(y_series.mean())
            is_pos = final_prediction.central_estimate > mean_val
            drivers = [
                Driver(
                    name="diurnal_traffic_cycle",
                    direction="positive" if is_pos else "neutral",
                    strength=0.85,
                    leading_or_lagging="leading",
                    evidence_refs=[evidence_ref.evidence_id],
                )
            ]

        # 9.1 Inject IntelX Exogenous Research Driver if available
        if intelx_reports and intelx_reports[0].key_findings:
            top_finding = intelx_reports[0].key_findings[0]
            sentiment_positive = exogenous_adj.get("sentiment_multiplier", 1.0) >= 1.0
            drivers.append(
                Driver(
                    name=f"intelx:{top_finding[:28]}",
                    direction="positive" if sentiment_positive else "negative",
                    strength=min(
                        0.95, round(exogenous_adj.get("volatility_multiplier", 1.0) * 0.70, 2)
                    ),
                    leading_or_lagging="leading",
                    evidence_refs=[evidence_ref.evidence_id],
                )
            )

        # 10. Assemble Forecast Domain Object
        expires_at = as_of + horizon
        review_at = as_of + (horizon / 4)

        assumptions_list = [
            "traffic regime stable",
            "service architecture unchanged",
            enhanced_ctx.qualitative_nuance,
        ]
        if enhanced_ctx.risk_factors:
            assumptions_list.extend(enhanced_ctx.risk_factors)

        forecast = Forecast(
            forecast_id=forecast_id,
            target=target,
            as_of=as_of,
            horizon=horizon,
            expires_at=expires_at,
            prediction=final_prediction.central_estimate,
            range_lower=enhanced_ctx.adjusted_lower_bound,
            range_upper=enhanced_ctx.adjusted_upper_bound,
            probability=final_prediction.exceedance_probability,
            confidence=confidence_result.level,
            drivers=drivers,
            evidence=[evidence_ref],
            model_version=model_version_str,
            assumptions=assumptions_list,
            review_at=review_at,
            status=ForecastStatus.DRAFT,
            scenario_id=None,
            model_metadata={
                "model_version": model_version_str,
                "family": model_version_str.split(":")[0],
                "prediction_is_not_authorization": True,
                "data_connector": provenance.connector,
                "data_synthetic": provenance.synthetic,
                "data_sources": provenance.source_id,
                **selection.metadata(),
            },
            evidence_class=provenance.evidence_class,
            evidence_source=provenance.describe(),
        )

        return [forecast]



def _orchestrate_with_default_components(
    snapshot_path: str,
    denied_fields: list[str],
    confidence_scaling: float,
    *,
    target: str,
    as_of: datetime,
    horizon: timedelta,
    capacity_threshold: float,
    raw_observations: list[Observation],
    intelx_reports: list[Any],
    exogenous_adj: dict[str, float],
    historical_resolved_count: int,
    model_budget_seconds: float | None = None,
    cpu_saturated: bool = False,
    provenance_source_id: str | None = None,
    provenance_evidence_class: str | None = None,
    provenance_connector: str | None = None,
    provenance_synthetic: bool | None = None,
) -> list[Forecast]:
    """Spawn-safe CPU worker entrypoint; recreates stateless default components."""
    engine = ForecastEngine(
        snapshotter=EvidenceSnapshotter(
            base_storage_path=snapshot_path,
            denied_fields=set(denied_fields),
        ),
        enhancer=AIUniverseModelEnhancer(confidence_scaling=confidence_scaling),
    )
    return engine._orchestrate_sync(
        target=target,
        as_of=as_of,
        horizon=horizon,
        capacity_threshold=capacity_threshold,
        raw_observations=raw_observations,
        intelx_reports=intelx_reports,
        exogenous_adj=exogenous_adj,
        provenance_source_id=provenance_source_id,
        provenance_evidence_class=provenance_evidence_class,
        provenance_connector=provenance_connector,
        provenance_synthetic=provenance_synthetic,
        historical_resolved_count=historical_resolved_count,
        model_budget_seconds=model_budget_seconds,
        cpu_saturated=cpu_saturated,
    )
