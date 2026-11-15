"""Shared models for the IntelX live tracking data layer (TASK-IG-INT-03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    """Latitude/longitude window. ``contains`` is inclusive on all edges."""

    lamin: float
    lomin: float
    lamax: float
    lomax: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.lamin <= lat <= self.lamax and self.lomin <= lon <= self.lomax


@dataclass(frozen=True)
class TrackedObject:
    """One live tracked object, normalised across all layers.

    Units are normalised: altitude in metres, speed in m/s, heading in
    degrees. Layer-native values are preserved in ``properties`` so nothing
    the source said is lost or silently re-scaled.
    """

    kind: str  # flight | satellite | ship | event
    object_id: str
    name: str
    lat: float
    lon: float
    observed_at: datetime
    source: str  # layer source id, e.g. "opensky"
    altitude_m: float | None = None
    speed_mps: float | None = None
    heading_deg: float | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "object_id": self.object_id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "altitude_m": self.altitude_m,
            "speed_mps": self.speed_mps,
            "heading_deg": self.heading_deg,
            "observed_at": self.observed_at.isoformat(),
            "source": self.source,
            "properties": self.properties,
        }


@dataclass(frozen=True)
class LayerReport:
    """Per-layer outcome of one snapshot: count, scope note, or the error."""

    kind: str
    source: str
    count: int
    scope_note: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source": self.source,
            "count": self.count,
            "scope_note": self.scope_note,
            "error": self.error,
        }


@dataclass(frozen=True)
class TrackingSnapshot:
    generated_at: datetime
    objects: list[TrackedObject]
    layers: list[LayerReport]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_objects": len(self.objects),
            "objects": [o.to_dict() for o in self.objects],
            "layers": [layer.to_dict() for layer in self.layers],
        }
