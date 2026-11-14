"""TASK-REL-018: a missing statsforecast backend must degrade explicitly.

Production ran for an unknown period with ``statsforecast`` absent from the
fleet environment: every adapter silently fell back to a mock whose
``predict`` returned the last observed value repeated across the horizon --
a flat line presented as a model forecast. These tests pin the replacement
behaviour: fitting raises :class:`StatsForecastUnavailableError`, the
pipeline and engine let it propagate, and no code path substitutes numbers.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

from futuris.connectors.synthetic_telemetry import SyntheticTelemetryConnector
from futuris.core.engine import ForecastEngine
from futuris.core.enums import EvidenceClass
from futuris.core.pipeline import ForecastingPipeline
from futuris.models import adapters
from futuris.models.adapters import NaiveAdapter, StatsForecastUnavailableError


class _UnavailableSFModel:
    """Stands in for the statsforecast classes when the import failed."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def fit(self, y: Any = None, *_args: Any, **_kwargs: Any) -> Any:
        raise StatsForecastUnavailableError("forced unavailable for test")

    def predict(self, h: int = 1, *_args: Any, **_kwargs: Any) -> Any:
        raise StatsForecastUnavailableError("forced unavailable for test")


@pytest.fixture
def backend_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the exact state a statsforecast-less deployment runs in."""
    for name in (
        "_SF_Naive",
        "_SF_SeasonalNaive",
        "_SF_RandomWalkWithDrift",
        "_SF_AutoETS",
        "_SF_AutoARIMA",
    ):
        monkeypatch.setattr(adapters, name, _UnavailableSFModel)


class _StubSnapshotter:
    """Evidence-freeze stand-in: the degradation under test happens in the
    modeling stage, long after snapshotting, and a parquet freeze would
    need pyarrow (absent from the minimal CI surface)."""

    def freeze_snapshot(self, **kwargs: Any) -> Any:
        from futuris.core.enums import EvidenceClass, SignalClass, SourceTrust
        from futuris.core.schemas import EvidenceRef

        return EvidenceRef(
            source=kwargs.get("source_id", "telemetry:synthetic"),
            source_trust=SourceTrust.MEDIUM,
            signal_class=kwargs.get("signal_class", SignalClass.TELEMETRY),
            as_of=kwargs["as_of"],
            snapshot_path="stub://snapshot",
            content_hash="stub-hash",
            evidence_class=kwargs.get("evidence_class", EvidenceClass.SYNTHETIC),
        )


def _series(n: int = 400) -> tuple[pd.DataFrame, pd.Series]:
    idx = pd.date_range("2026-11-01", periods=n, freq="5min", tz="UTC")
    y = pd.Series(1000.0 + 50.0 * np.sin(np.arange(n) / 12.0), index=idx)
    return pd.DataFrame(index=idx), y


def test_adapter_fit_raises_instead_of_mock_flatline(backend_unavailable: None) -> None:
    x, y = _series()
    with pytest.raises(StatsForecastUnavailableError):
        NaiveAdapter().fit(x, y, as_of=datetime(2026, 11, 14, tzinfo=UTC))


def test_availability_flag_matches_reality() -> None:
    """When statsforecast genuinely cannot be imported (production fleet
    venv, minimal CI), the flag must say so and fits must refuse."""
    if adapters.STATSFORECAST_AVAILABLE:
        pytest.skip("statsforecast is importable in this environment")
    assert adapters.STATSFORECAST_IMPORT_ERROR
    x, y = _series()
    with pytest.raises(StatsForecastUnavailableError):
        NaiveAdapter().fit(x, y, as_of=datetime(2026, 11, 14, tzinfo=UTC))


@pytest.mark.asyncio
async def test_pipeline_propagates_backend_unavailable(
    backend_unavailable: None,
) -> None:
    from futuris.core.pipeline import ContextualizationStage, ModelingStage
    from futuris.models.routing import ModelRouter

    class _InProcessRouter(ModelRouter):
        """A non-default router keeps modeling in this process, so the
        monkeypatched backend state is the one under test (the default
        router runs the fit in a worker subprocess)."""

    pipeline = ForecastingPipeline(
        contextualization=ContextualizationStage(snapshotter=_StubSnapshotter()),
        modeling=ModelingStage(router=_InProcessRouter()),
    )
    with pytest.raises(StatsForecastUnavailableError):
        await pipeline.run(
            target="service:checkout:capacity_exceedance_24h",
            as_of=datetime(2026, 11, 14, tzinfo=UTC),
            horizon=timedelta(hours=24),
            lookback_days=2,
        )


@pytest.mark.asyncio
async def test_engine_propagates_backend_unavailable(
    backend_unavailable: None,
) -> None:
    # The stub snapshotter is a non-default component, which also keeps
    # orchestration in this process (the default component graph runs in a
    # worker subprocess where the monkeypatched backend state would not
    # apply).
    engine = ForecastEngine(
        connector=SyntheticTelemetryConnector(seed=42),
        snapshotter=_StubSnapshotter(),
    )
    with pytest.raises(StatsForecastUnavailableError):
        await engine.orchestrate(
            target="service:checkout:capacity_exceedance_24h",
            as_of=datetime(2026, 11, 14, tzinfo=UTC),
            horizon=timedelta(hours=24),
            history_lookback_days=2,
        )


@pytest.mark.asyncio
async def test_engine_forecast_carries_derived_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """With a working backend, the forecast's provenance fields are SET from
    the actual input -- not left at the schema defaults that used to make
    every forecast look identical."""
    pytest.importorskip("statsforecast")
    pytest.importorskip("pyarrow")
    from futuris.infra.config import settings

    monkeypatch.setattr(settings, "OBJECT_STORE_PATH", str(tmp_path))
    engine = ForecastEngine(connector=SyntheticTelemetryConnector(seed=42))
    forecasts = await engine.orchestrate(
        target="service:checkout:capacity_exceedance_24h",
        as_of=datetime(2026, 11, 14, tzinfo=UTC),
        horizon=timedelta(hours=24),
        history_lookback_days=2,
    )
    f = forecasts[0]
    assert f.evidence_class is EvidenceClass.SYNTHETIC
    assert f.evidence_source is not None
    assert "SyntheticTelemetryConnector" in f.evidence_source
    assert "SYNTHETIC" in f.evidence_source
    assert f.model_metadata["data_connector"] == "SyntheticTelemetryConnector"
    assert f.model_metadata["data_synthetic"] is True
    # The frozen evidence agrees with the forecast-level label.
    assert f.evidence[0].evidence_class is EvidenceClass.SYNTHETIC
    assert f.evidence[0].source == "telemetry:synthetic"


@pytest.mark.asyncio
async def test_pipeline_forecast_carries_derived_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    pytest.importorskip("statsforecast")
    pytest.importorskip("pyarrow")
    from futuris.infra.config import settings

    monkeypatch.setattr(settings, "OBJECT_STORE_PATH", str(tmp_path))
    pipeline = ForecastingPipeline()
    result = await pipeline.run(
        target="service:checkout:capacity_exceedance_24h",
        as_of=datetime(2026, 11, 14, tzinfo=UTC),
        horizon=timedelta(hours=24),
        lookback_days=2,
    )
    f = result.forecast
    assert f.evidence_class is EvidenceClass.SYNTHETIC
    assert f.evidence_source is not None
    assert "SyntheticTelemetryConnector" in f.evidence_source
    assert f.model_metadata["data_synthetic"] is True
