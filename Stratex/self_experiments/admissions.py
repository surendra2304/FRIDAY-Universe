"""FORWARD_TEST lane admissions (TASK-STR-EXP-001).

When a judged combination clears the second tier (or the full bar),
the loop admits it to the FORWARD_TEST lane by writing an entry in
exactly the FWD-003 registry shape (config_strategy.py's lane
entries: status FORWARD_TEST, forward_protocol True, forward_lane
"FORWARD_TEST", lane_assets, the frozen FWD-006 lane terms, and a
reason string carrying the judged figures) into the loop's own
admissions registry — a JSON file in the loop's data directory.

merged_registry() is the registry path the daemon side consumes: the
production registry dict with the loop's admissions merged in. It
NEVER overwrites a governed entry — a key collision raises.

Two honesty limits, stated here and in every admission's reason
string:
1. The risk fields on an admission are the frozen lane constants from
   bounds.py. They are stamped, never chosen: admit() takes no risk
   input, and any caller-supplied extra field is risk-scanned.
2. An admitted combination has no executable ensemble module yet, so
   the daemon's governance fail-closes it (unregistered module) and
   it cannot place an order until the slice-2 ensemble module lands.
   The entry carries "execution": "PENDING_ENSEMBLE_MODULE" so this
   state is machine-visible, not buried in prose. This mirrors
   FRG-017: the loop maintains the registry; production adoption is a
   separate gated step.

Admissions are reversible: revoke() removes an entry (the loop's
caller logs the revocation in the experiment ledger).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import bounds
from .bounds import assert_no_risk_touch
from .judge import Verdict
from .runner import PooledMetrics
from .store import StreamRecord

UTC = timezone.utc


class AdmissionError(Exception):
    """An admission was refused (fail-closed)."""


def default_lane_assets(panel: str) -> list[str] | None:
    """The judged universe's symbol list for a panel, read (never
    written) from config_strategy — the same source the FWD-003 lane
    entries use. Slice 1 supports crypto30; other panels return None
    and their admissions are refused until their symbol list is on
    record in the same place."""
    if panel == "crypto30":
        try:
            from config_strategy import CRYPTO30_SYMBOLS

            return list(CRYPTO30_SYMBOLS)
        except Exception:
            return None
    return None


def key_for(members: tuple[str, ...]) -> str:
    digest = hashlib.sha256(
        ",".join(sorted(members)).encode("utf-8")
    ).hexdigest()
    return f"selfexp_combo_{digest[:12]}"


class AdmissionsRegistry:
    """The loop's lane admissions, persisted as one JSON object."""

    def __init__(
        self,
        path: Path,
        lane_assets_resolver: Callable[[str], list[str] | None] | None = None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._resolver = lane_assets_resolver or default_lane_assets
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._entries: dict[str, dict[str, Any]] = dict(
                    data.get("entries", {})
                )
            except Exception as exc:
                raise AdmissionError(
                    f"admissions registry at {self.path} is unreadable: {exc}"
                ) from exc
        else:
            self._entries = {}
            self._persist()

    # -- persistence ------------------------------------------------------

    def _persist(self) -> None:
        payload = {
            "owner": "stratex_self_experiments",
            "updated_at": datetime.now(UTC).isoformat(),
            "entries": self._entries,
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    # -- access -------------------------------------------------------------

    def entries(self) -> dict[str, dict[str, Any]]:
        return dict(self._entries)

    def get(self, key: str) -> dict[str, Any] | None:
        return self._entries.get(key)

    # -- admission ----------------------------------------------------------

    def admit(
        self,
        *,
        members: list[StreamRecord],
        metrics: PooledMetrics,
        verdict: Verdict,
        declaration_id: str,
        n_global: int,
        panel: str,
        timeframe: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Admit a judged combination to the lane; returns its key.

        Refuses (AdmissionError) for a FAIL verdict, an unsupported
        panel, or a key collision with different members. Any
        caller-supplied extra fields are risk-scanned first.
        """
        if extra:
            assert_no_risk_touch(extra)
        if verdict.verdict not in ("FORWARD_TEST", "PROVEN"):
            raise AdmissionError(
                f"verdict {verdict.verdict} is not admissible — only "
                f"second-tier and full-bar passers enter the lane"
            )
        member_ids = tuple(sorted(r.stream_id for r in members))
        key = key_for(member_ids)
        existing = self._entries.get(key)
        if existing is not None:
            if tuple(sorted(existing.get("members", []))) != member_ids:
                raise AdmissionError(
                    f"admission key collision at {key} with different "
                    f"members — refusing to overwrite"
                )
            return key  # already admitted on the same evidence shape
        lane_assets = self._resolver(panel)
        if lane_assets is None:
            raise AdmissionError(
                f"no lane symbol list on record for panel {panel!r} — "
                f"admission refused rather than substituted"
            )
        cost_values: set[float] = set()
        for r in members:
            if isinstance(r.costs_rt_bps, list):
                cost_values.update(float(c) for c in r.costs_rt_bps)
            else:
                cost_values.add(float(r.costs_rt_bps))
        costs = sorted(cost_values)
        entry: dict[str, Any] = {
            "status": "FORWARD_TEST",
            "version": "v1.0.0 (TASK-STR-EXP-001)",
            "timeframe": timeframe,
            "execution_model": "RULE_BASED",
            "entry_conditions": (
                "Self-experiment ensemble of admitted streams "
                + ", ".join(member_ids)
                + ": each member trades its own judged signal and "
                "bracket; the lane books the union of member trades."
            ),
            "sl_method": "Each member's own judged bracket (member records govern)",
            "tp_method": "Each member's own judged bracket (member records govern)",
            "oos_win_rate_prior": round(metrics.win_rate, 4),
            "total_friction_bps": costs[0] if len(costs) == 1 else costs,
            "expected_net_edge_bps": round(metrics.expectancy * 10000.0, 1),
            "minimum_required_edge": bounds.LANE_MINIMUM_REQUIRED_EDGE,
            "lane_assets": lane_assets,
            "validated_assets": [],
            "forward_protocol": True,
            "risk_per_trade_pct": bounds.LANE_RISK_PER_TRADE_PCT,
            "max_heat_pct": bounds.LANE_MAX_HEAT_PCT,
            "forward_lane": "FORWARD_TEST",
            "self_experiment": True,
            "self_experiment_verdict": verdict.verdict,
            "declaration_id": declaration_id,
            "members": list(member_ids),
            "execution": "PENDING_ENSEMBLE_MODULE",
            "reason": (
                f"TASK-STR-EXP-001 SELF-EXPERIMENT admission "
                f"({verdict.verdict}): combination of "
                f"{', '.join(member_ids)} @ {panel} {timeframe} judged "
                f"pooled on stored OOS trades (declaration "
                f"{declaration_id}, global trial N={n_global}): "
                f"expectancy {metrics.expectancy:+.4%}/trade, PF "
                f"{metrics.pf:.4f}, {metrics.trades} OOS trades, "
                f"{metrics.positive_folds}/{metrics.folds_with_trades} "
                f"positive folds. FORWARD_TEST lane terms as for the "
                f"FWD-003 entries (0.1% per-trade risk on venue equity, "
                f"2% heat cap, {bounds.LANE_KILL_CRITERIA}), fills "
                f"tagged FORWARD_TEST. Execution pending the ensemble "
                f"module (slice 2): the registry fail-closes "
                f"unregistered modules, so this entry cannot trade "
                f"until that module lands — registered, not substituted."
            ),
        }
        if extra:
            entry.update(extra)
        # Internal invariant: the stamped risk fields are the frozen
        # constants, whatever happened above.
        if (
            entry["risk_per_trade_pct"] != bounds.LANE_RISK_PER_TRADE_PCT
            or entry["max_heat_pct"] != bounds.LANE_MAX_HEAT_PCT
        ):
            raise AdmissionError(
                "admission risk fields diverged from the frozen lane "
                "terms — refused"
            )
        self._entries[key] = entry
        self._persist()
        return key

    def revoke(self, key: str) -> dict[str, Any] | None:
        """Remove an admission (every admission is reversible)."""
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._persist()
        return entry


def merged_registry(
    base_registry: dict[str, Any], admissions: AdmissionsRegistry
) -> dict[str, Any]:
    """The daemon-side registry view: base entries plus admissions.

    Returns a NEW dict; the base is never mutated. A key collision
    with a governed base entry raises AdmissionError — the loop's
    admissions can add lane entries, never shadow governed ones.
    """
    merged = dict(base_registry)
    for key, entry in admissions.entries().items():
        if key in merged:
            raise AdmissionError(
                f"admission key {key} collides with a governed registry "
                f"entry — refusing to shadow it"
            )
        merged[key] = entry
    return merged
