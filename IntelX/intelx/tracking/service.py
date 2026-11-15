"""Tracking service (TASK-IG-INT-03): one snapshot across all layers.

This is the DATA layer behind the God's-Eye-style ideas in the corpus
(items Dcto0vKzJxJ, DccLLkoPCT1: live flights/ships/satellites/events on a
map). The UI candidate itself is stored separately by the coordinator and
is NOT part of this task — this service produces the normalised snapshot
any UI (or agent answer) consumes.

Failure discipline: layers are fetched concurrently and fail independently.
A failed layer contributes a ``LayerReport`` with the error and count 0 —
the snapshot never fabricates positions for a layer that did not answer,
and every layer carries its scope note (the ships layer is regional, the
flight layer is rate-limited, and both say so in the data itself).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from intelx.tracking.models import BoundingBox, LayerReport, TrackedObject, TrackingSnapshot
from intelx.tracking.sources import (
    DigitrafficShipsSource,
    OpenSkyFlightsSource,
    SatelliteSource,
    UsgsEventsSource,
)

logger = logging.getLogger("intelx.tracking")
UTC = timezone.utc


class TrackingService:
    """Aggregates the live tracking layers into unified snapshots."""

    def __init__(self, sources: list | None = None) -> None:
        self._sources = sources if sources is not None else self.default_sources()

    @staticmethod
    def default_sources() -> list:
        return [
            OpenSkyFlightsSource(),
            SatelliteSource(),
            DigitrafficShipsSource(),
            UsgsEventsSource(),
        ]

    async def snapshot(self, bbox: BoundingBox | None = None, kinds: set[str] | None = None) -> TrackingSnapshot:
        selected = [s for s in self._sources if kinds is None or s.kind in kinds]

        async def run(source) -> tuple[object, list[TrackedObject] | Exception]:
            try:
                return source, await source.fetch(bbox)
            except Exception as exc:  # per-layer isolation is the design
                return source, exc

        results = await asyncio.gather(*(run(s) for s in selected))
        objects: list[TrackedObject] = []
        layers: list[LayerReport] = []
        for source, result in results:
            if isinstance(result, Exception):
                logger.warning("tracking layer %s failed: %s", source.source_id, result)
                layers.append(
                    LayerReport(
                        kind=source.kind,
                        source=source.source_id,
                        count=0,
                        scope_note=source.scope_note,
                        error=str(result),
                    )
                )
            else:
                objects.extend(result)
                layers.append(
                    LayerReport(
                        kind=source.kind,
                        source=source.source_id,
                        count=len(result),
                        scope_note=source.scope_note,
                    )
                )
        objects.sort(key=lambda o: (o.kind, o.object_id))
        return TrackingSnapshot(generated_at=datetime.now(UTC), objects=objects, layers=layers)


__all__ = ["TrackingService"]
