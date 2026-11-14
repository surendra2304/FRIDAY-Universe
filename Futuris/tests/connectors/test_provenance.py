"""TASK-REL-018: provenance is derived from the actual connector + observations.

Before this, serving paths labelled evidence with a hardcoded
``telemetry:synthetic`` string or with schema defaults, and the FRIDAY
payload never carried the forecast's real evidence fields at all -- so
synthetic-data forecasts were indistinguishable from measured ones.
"""

from datetime import UTC, datetime, timedelta

import pytest

from futuris.connectors.base import BaseConnector, Observation
from futuris.connectors.provenance import resolve_provenance
from futuris.connectors.synthetic_telemetry import SyntheticTelemetryConnector
from futuris.core.enums import EvidenceClass

T0 = datetime(2026, 11, 14, 0, 0, 0, tzinfo=UTC)


def _obs(source: str, value: float = 100.0) -> Observation:
    return Observation(
        observed_at=T0,
        source=source,
        series_id="checkout:requests_per_minute",
        value=value,
        unit="rpm",
    )


class _FakeRealConnector(BaseConnector):
    """A connector standing in for a measured telemetry source."""

    def __init__(self, sources: list[str]) -> None:
        self._sources = sources

    async def fetch(self, start: datetime, end: datetime) -> list[Observation]:
        return [_obs(s) for s in self._sources]


@pytest.mark.asyncio
async def test_synthetic_connector_is_labelled_synthetic() -> None:
    connector = SyntheticTelemetryConnector(seed=42)
    observations = await connector.fetch(T0 - timedelta(days=1), T0)
    prov = resolve_provenance(connector, observations)
    assert prov.synthetic is True
    assert prov.evidence_class is EvidenceClass.SYNTHETIC
    assert prov.connector == "SyntheticTelemetryConnector"
    assert "telemetry:synthetic" in prov.source_id
    assert "SYNTHETIC" in prov.describe()


@pytest.mark.asyncio
async def test_real_connector_is_labelled_live_and_named() -> None:
    connector = _FakeRealConnector(["nexus:telemetry"])
    observations = await connector.fetch(T0 - timedelta(days=1), T0)
    prov = resolve_provenance(connector, observations)
    assert prov.synthetic is False
    assert prov.evidence_class is EvidenceClass.LIVE
    assert prov.connector == "_FakeRealConnector"
    assert prov.source_id == "nexus:telemetry"


@pytest.mark.asyncio
async def test_generated_fallback_observations_are_synthetic() -> None:
    """VyralX fabricates fallback observations when unreachable; they must
    never be presented as measured data."""
    connector = _FakeRealConnector(["vyralx:fallback"])
    observations = await connector.fetch(T0 - timedelta(days=1), T0)
    prov = resolve_provenance(connector, observations)
    assert prov.synthetic is True
    assert prov.evidence_class is EvidenceClass.SYNTHETIC


@pytest.mark.asyncio
async def test_mixed_real_and_fabricated_inputs_fail_closed_to_synthetic() -> None:
    connector = _FakeRealConnector(["nexus:telemetry", "vyralx:fallback"])
    observations = await connector.fetch(T0 - timedelta(days=1), T0)
    prov = resolve_provenance(connector, observations)
    assert prov.synthetic is True
    # Both sources stay visible in the payload even though the class is
    # synthetic -- the mix itself is part of the provenance.
    assert "nexus:telemetry" in prov.source_id
    assert "vyralx:fallback" in prov.source_id


def test_unknown_provenance_fails_closed() -> None:
    prov = resolve_provenance(None, [])
    assert prov.synthetic is True
    assert prov.evidence_class is EvidenceClass.SYNTHETIC


def test_connector_only_real_source_is_taken_at_face_value() -> None:
    prov = resolve_provenance(_FakeRealConnector([]), [])
    assert prov.synthetic is False
    assert prov.connector == "_FakeRealConnector"
