"""Data provenance resolution for forecast inputs (TASK-REL-018).

A forecast is only as honest as the label on its input data. Before this
module, the serving paths labelled their evidence with a hardcoded
``telemetry:synthetic`` string in one place and with schema defaults in
another, while the connector actually feeding the forecast went unnamed --
so a synthetic-data forecast and a measured-data forecast were
indistinguishable in the payload, and either could be mislabelled by a
caller-supplied string.

Provenance is now DERIVED from the two ground truths available at run time:

* the connector instance that produced the observations, and
* the ``source`` strings the observations themselves carry.

Rules (fail-closed toward "synthetic": data is only ever labelled LIVE when
nothing about it was fabricated):

* the synthetic generator (``SyntheticTelemetryConnector``) is synthetic;
* an observation source is fabricated when it names a synthetic generator or
  a generated fallback (e.g. ``vyralx:fallback`` fabricates observations when
  the VyralX service is unreachable);
* if ANY consumed observation is fabricated, the forecast's evidence class
  is SYNTHETIC -- a forecast is only as real as its weakest input;
* otherwise the evidence class is LIVE and the payload names the connector
  and every source that fed it.
"""

from __future__ import annotations

from dataclasses import dataclass

from futuris.connectors.base import BaseConnector, Observation
from futuris.connectors.synthetic_telemetry import SyntheticTelemetryConnector
from futuris.core.enums import EvidenceClass

_FABRICATED_MARKERS = ("synthetic", "fallback", "simulated", "mock")


def _is_fabricated_source(source: str) -> bool:
    lowered = source.lower()
    return any(marker in lowered for marker in _FABRICATED_MARKERS)


@dataclass(frozen=True)
class DataProvenance:
    """Resolved provenance of one forecast's input data."""

    connector: str
    """Class name of the connector that produced the observations."""

    source_id: str
    """The observation source(s) consumed, comma-joined when several."""

    evidence_class: EvidenceClass
    """SYNTHETIC when any input was fabricated; LIVE when all was measured."""

    synthetic: bool
    """True when the input data was generated rather than measured."""

    def describe(self) -> str:
        """Human-readable origin string for payloads (``evidence_source``)."""
        label = "SYNTHETIC" if self.synthetic else "LIVE"
        return f"{self.source_id} via {self.connector} [{label} data]"


def resolve_provenance(
    connector: BaseConnector | None,
    observations: list[Observation],
) -> DataProvenance:
    """Derive provenance from the actual connector and observations consumed.

    With no observations (e.g. a request refused before ingestion), the
    connector alone decides: the synthetic generator is synthetic, any other
    configured connector is taken at face value, and an unknown connector
    fails closed to synthetic.
    """
    connector_name = type(connector).__name__ if connector is not None else "unknown"
    sources = sorted({obs.source for obs in observations if obs.source})

    if isinstance(connector, SyntheticTelemetryConnector):
        synthetic = True
    elif sources:
        synthetic = any(_is_fabricated_source(s) for s in sources)
    elif connector is None:
        synthetic = True
    else:
        synthetic = False

    if sources:
        source_id = ",".join(sources)
    elif isinstance(connector, SyntheticTelemetryConnector):
        source_id = "telemetry:synthetic"
    else:
        source_id = f"connector:{connector_name}"

    return DataProvenance(
        connector=connector_name,
        source_id=source_id,
        evidence_class=EvidenceClass.SYNTHETIC if synthetic else EvidenceClass.LIVE,
        synthetic=synthetic,
    )
