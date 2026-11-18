"""The provenance-verified stream store (TASK-STR-EXP-001).

The loop runs on stored research data only — never on live feeds, and
never on numbers it cannot trace. A stream store is a directory:

    manifest.json     {streams: {stream_id: {file, sha256,
                       source_record: {file, sha256, round}}}}
    streams/*.json    one judged stream per file (see exporter)

Every stream file carries its OOS per-trade net returns grouped by
fold, its holdout aggregates, and the pooled metrics recorded for it
by the research programme. Loading verifies: the file's sha256
matches the manifest, the manifest's source-record sha256 matches the
stream file's own provenance block, and the admission label is one of
the recognised classes. Any mismatch refuses the whole store — a
partially verified store is not a store the loop will judge on.

Stores are built by self_experiments.export_stream_store from the
RD-002 backup row files, which asserts that the stored form
reproduces the recorded per-fold aggregates EXACTLY (trades/wins) and
the recorded holdout exactly, before writing anything.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Admission classes a stream may carry. VALIDATED = passed the full
#: frozen bar and trades; FORWARD_TEST = in the demo lane;
#: TIER_ADMITTED = meets the owner's second tier and was admitted to
#: the lane by the 2026-11-18 implement-all order (wiring waves).
ADMISSION_CLASSES = ("VALIDATED", "FORWARD_TEST", "TIER_ADMITTED")


class StoreError(Exception):
    """The stream store failed provenance verification."""


@dataclass
class StreamRecord:
    """One judged strategy stream, in stored form."""

    stream_id: str
    family: str
    variant: str
    panel: str
    timeframe: str
    cluster: str
    admission: str
    costs_rt_bps: float | list[float]
    folds: dict[str, list[float]]  # fold -> OOS per-trade net returns
    fold_windows: dict[str, tuple[str, str]]
    holdout_trades: int | None
    holdout_expectancy: float | None
    recorded_trades: int
    recorded_expectancy: float
    recorded_pf: float
    source_record: dict[str, Any] = field(default_factory=dict)

    @property
    def all_returns(self) -> list[float]:
        out: list[float] = []
        for fold in sorted(self.folds):
            out.extend(self.folds[fold])
        return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StreamStore:
    """A verified, read-only view over a stream store directory."""

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        manifest_path = self.store_dir / "manifest.json"
        if not manifest_path.exists():
            raise StoreError(f"no manifest.json in {self.store_dir}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StoreError(f"manifest unreadable: {exc}") from exc
        self._streams: dict[str, StreamRecord] = {}
        for stream_id, entry in sorted(manifest.get("streams", {}).items()):
            self._streams[stream_id] = self._load(stream_id, entry)

    def _load(self, stream_id: str, entry: dict[str, Any]) -> StreamRecord:
        rel = entry.get("file", "")
        path = self.store_dir / rel
        if not path.exists():
            raise StoreError(f"stream file missing for {stream_id}: {rel}")
        digest = _sha256(path)
        if digest != entry.get("sha256"):
            raise StoreError(
                f"stream file hash mismatch for {stream_id}: manifest "
                f"{entry.get('sha256')}, actual {digest}"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StoreError(f"stream file unreadable for {stream_id}: {exc}") from exc
        provenance = raw.get("source_record") or {}
        manifest_source = entry.get("source_record") or {}
        if provenance.get("sha256") != manifest_source.get("sha256"):
            raise StoreError(
                f"provenance mismatch for {stream_id}: the stream file "
                f"and the manifest name different source records"
            )
        if not provenance.get("file") or not provenance.get("sha256"):
            raise StoreError(f"stream {stream_id} carries no provenance")
        admission = str(raw.get("admission", ""))
        if admission not in ADMISSION_CLASSES:
            raise StoreError(
                f"stream {stream_id} has unrecognised admission class "
                f"{admission!r} — only admitted streams enter the store"
            )
        folds = {
            str(fold): [float(x) for x in values]
            for fold, values in (raw.get("folds") or {}).items()
        }
        if not folds or sum(len(v) for v in folds.values()) == 0:
            raise StoreError(f"stream {stream_id} carries no OOS trades")
        holdout = raw.get("holdout") or {}
        return StreamRecord(
            stream_id=str(raw.get("stream_id", stream_id)),
            family=str(raw.get("family", "")),
            variant=str(raw.get("variant", "")),
            panel=str(raw.get("panel", "")),
            timeframe=str(raw.get("timeframe", "")),
            cluster=str(raw.get("cluster", "other")),
            admission=admission,
            costs_rt_bps=raw.get("costs_rt_bps", 16.0),
            folds=folds,
            fold_windows={
                str(k): (str(v[0]), str(v[1]))
                for k, v in (raw.get("fold_windows") or {}).items()
            },
            holdout_trades=(
                int(holdout["trades"]) if holdout.get("trades") is not None else None
            ),
            holdout_expectancy=(
                float(holdout["expectancy"])
                if holdout.get("expectancy") is not None
                else None
            ),
            recorded_trades=int(raw.get("recorded_trades", 0)),
            recorded_expectancy=float(raw.get("recorded_expectancy", 0.0)),
            recorded_pf=float(raw.get("recorded_pf", 0.0)),
            source_record=provenance,
        )

    # -- access ---------------------------------------------------------

    def stream(self, stream_id: str) -> StreamRecord:
        try:
            return self._streams[stream_id]
        except KeyError:
            raise StoreError(f"unknown stream {stream_id!r}") from None

    def streams(self) -> list[StreamRecord]:
        return [self._streams[k] for k in sorted(self._streams)]

    def groups(self) -> dict[tuple[str, str], list[StreamRecord]]:
        """Admitted streams grouped by (panel, timeframe)."""
        out: dict[tuple[str, str], list[StreamRecord]] = {}
        for record in self.streams():
            out.setdefault((record.panel, record.timeframe), []).append(record)
        return out
