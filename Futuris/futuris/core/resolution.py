"""Outcome resolution rules and snapshot-anchored ground truth verification."""

from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
import fnmatch
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import pandas as pd

from futuris.core.enums import ResolutionMethod
from futuris.core.schemas import Forecast, Outcome


class ResolutionNotReadyError(RuntimeError):
    """A forecast cannot be resolved yet -- a deferral, not a failure.

    Raised when the ground truth for a forecast's horizon is not complete
    at resolution time (TASK-FUT-043: the fleet target's expiry day is
    still in progress, so its daily count is partial). The sweeps treat
    this as "leave the forecast ACTIVE and try again on a later sweep",
    never as a resolution failure and never as a licence to record a
    partial count as ground truth.
    """


@dataclass(frozen=True)
class ResolutionRuleMeta:
    """Metadata describing a specific versioned resolution rule."""

    rule_id: str
    version: str
    target_pattern: str
    description: str


class ResolutionRule(Protocol):
    """Protocol for versioned target resolution logic."""

    @property
    def meta(self) -> ResolutionRuleMeta: ...

    def resolve(
        self,
        forecast: Forecast,
        observation_records: pd.DataFrame,
        evidence_snapshot_data: pd.DataFrame | None = None,
    ) -> Outcome: ...


class CapacityExceedanceResolutionRuleV1:
    """Rule v1 for capacity exceedance targets:

    capacity_exceedance_24h resolves TRUE iff observed max demand in the window
    [as_of, expires_at] exceeds the capacity threshold; observed max demand is the outcome value.
    If observations have > 20% data gaps, marks resolution_method=ambiguous.
    """

    meta = ResolutionRuleMeta(
        rule_id="rule:capacity_exceedance",
        version="v1.0",
        target_pattern="service:*:capacity_exceedance_*",
        description="Resolves TRUE if observed demand >= capacity threshold in window.",
    )

    def resolve(
        self,
        forecast: Forecast,
        observation_records: pd.DataFrame,
        evidence_snapshot_data: pd.DataFrame | None = None,
        max_allowed_gap_pct: float = 20.0,
    ) -> Outcome:
        as_of = pd.to_datetime(forecast.as_of, utc=True)
        expires_at = pd.to_datetime(forecast.expires_at, utc=True)

        # Ensure datetime index in UTC
        df = observation_records.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                df.set_index("timestamp", inplace=True)
            elif "observed_at" in df.columns:
                df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
                df.set_index("observed_at", inplace=True)

        # Slice exact window [as_of, expires_at]
        window_df = df[(df.index > as_of) & (df.index <= expires_at)]

        # Calculate expected number of 5m steps
        total_seconds = (expires_at - as_of).total_seconds()
        expected_points = max(1, int(total_seconds // 300))
        actual_points = len(window_df)

        gap_pct = max(0.0, (1.0 - (actual_points / expected_points)) * 100.0)

        # 1. Ambiguity handling for missing data
        if gap_pct > max_allowed_gap_pct or window_df.empty:
            msg = (
                f"Excessive observation gaps ({gap_pct:.1f}% > {max_allowed_gap_pct}%) "
                "in evaluation window"
            )
            return Outcome(
                outcome_id=uuid4(),
                forecast_id=forecast.forecast_id,
                observed_value=float(window_df["value"].max()) if not window_df.empty else None,
                event_occurred=None,
                resolved_at=datetime.now(UTC),
                resolution_method=ResolutionMethod.AMBIGUOUS,
                ambiguity_note=msg,
                resolution_rule_version=f"{self.meta.rule_id}:{self.meta.version}",
            )

        # 2. Extract capacity threshold from assumptions or default to 4000.0
        capacity_threshold = 4000.0
        if (
            evidence_snapshot_data is not None
            and "capacity_limit" in evidence_snapshot_data.columns
        ):
            capacity_threshold = float(evidence_snapshot_data["capacity_limit"].iloc[-1])

        max_observed = float(window_df["value"].max())
        event_occurred = bool(max_observed >= capacity_threshold)

        return Outcome(
            outcome_id=uuid4(),
            forecast_id=forecast.forecast_id,
            observed_value=round(max_observed, 2),
            event_occurred=event_occurred,
            resolved_at=datetime.now(UTC),
            resolution_method=ResolutionMethod.AUTOMATIC,
            ambiguity_note=None,
            resolution_rule_version=f"{self.meta.rule_id}:{self.meta.version}",
        )


class FleetForecastDemandResolutionRuleV1:
    """Rule v1 for the fleet's daily forecast-demand count (TASK-FUT-043).

    ``friday:fleet:forecast_demand_24h`` forecasts the DAILY COUNT of
    forecasts Futuris produced (``series_provider="forecast_requests"``:
    one point per UTC day, counted out of the ``forecasts`` table). Its
    outcome is therefore that same count for the UTC day the 24h horizon
    ends on -- not the maximum of the telemetry stream.

    Before this rule existed the resolver applied the capacity-exceedance
    rule to every target, so the "observed" daily demand was the maximum
    synthetic checkout-rpm value in the window (~1700-2500) while the
    forecasts predicted ~190-270 counts/day. All 136 live scores missed
    (coverage_90 0.0, MAE ~1922) because the two sides measured different
    quantities, not because the intervals were narrow.

    ``observation_records`` is the daily-counts frame: rows with a
    ``timestamp`` (UTC day start) and a ``value`` (forecasts produced
    that day), over complete UTC days only. A forecast whose expiry day
    has no row yet (the day is still in progress) raises
    :class:`ResolutionNotReadyError`: the sweep leaves it ACTIVE so a
    later sweep resolves it once the day completes, instead of recording
    a partial count as ground truth.
    """

    meta = ResolutionRuleMeta(
        rule_id="rule:fleet_forecast_demand",
        version="v1.0",
        target_pattern="friday:fleet:forecast_demand_24h",
        description="Resolves the daily forecast-demand count: observed = forecasts produced on the UTC day of expires_at.",
    )

    def resolve(
        self,
        forecast: Forecast,
        observation_records: pd.DataFrame,
        evidence_snapshot_data: pd.DataFrame | None = None,
    ) -> Outcome:
        expiry_day = pd.to_datetime(forecast.expires_at, utc=True).normalize()

        df = observation_records.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                df = df.set_index("timestamp")
            else:
                msg = (
                    "fleet demand resolution needs a daily-counts frame "
                    "with a timestamp column"
                )
                raise ValueError(msg)

        day_rows = df[df.index.normalize() == expiry_day]
        if day_rows.empty:
            msg = (
                f"daily forecast count for expiry day {expiry_day.date()} is "
                "not complete yet; deferring resolution until the day closes"
            )
            raise ResolutionNotReadyError(msg)

        observed = float(day_rows["value"].iloc[0])
        return Outcome(
            outcome_id=uuid4(),
            forecast_id=forecast.forecast_id,
            observed_value=round(observed, 2),
            event_occurred=None,
            resolved_at=datetime.now(UTC),
            resolution_method=ResolutionMethod.AUTOMATIC,
            ambiguity_note=None,
            resolution_rule_version=f"{self.meta.rule_id}:{self.meta.version}",
        )


class OutcomeResolver:
    """Registry and executor for versioned target resolution rules.

    Resolution is dispatched on the forecast's target: each rule declares
    the target pattern it resolves, and a target with no rule raises
    instead of silently falling through to another target's rule. That
    fall-through is exactly how the fleet target's outcomes were resolved
    by the capacity-exceedance rule for 136 rows (TASK-FUT-043): the
    resolver had one rule and applied it to everything.
    """

    def __init__(self) -> None:
        self.rules: dict[str, ResolutionRule] = {
            "capacity_exceedance": CapacityExceedanceResolutionRuleV1(),
            "fleet_forecast_demand": FleetForecastDemandResolutionRuleV1(),
        }

    def _rule_for(self, target: str) -> ResolutionRule:
        for rule in self.rules.values():
            if fnmatch.fnmatchcase(target, rule.meta.target_pattern):
                return rule
        msg = (
            f"No resolution rule for target {target!r}: refusing to resolve "
            "against another target's rule (see TASK-FUT-043)"
        )
        raise ValueError(msg)

    def resolve_forecast(
        self,
        forecast: Forecast,
        observations: pd.DataFrame,
        *,
        daily_counts: pd.DataFrame | None = None,
    ) -> Outcome:
        """Resolve a forecast against observation data and evidence snapshots.

        ``observations`` is the telemetry frame the capacity rule reads.
        ``daily_counts`` is the daily-counts frame the fleet-demand rule
        reads (one row per complete UTC day). A fleet forecast resolved
        without it raises :class:`ResolutionNotReadyError`, so the sweep
        defers it instead of resolving it against the telemetry frame.
        """
        # Load evidence snapshot if present
        evidence_df = None
        if forecast.evidence:
            snap_path = Path(forecast.evidence[0].snapshot_path)
            if snap_path.exists():
                try:
                    evidence_df = pd.read_parquet(snap_path)
                except Exception:
                    evidence_df = None

        rule = self._rule_for(forecast.target)
        if isinstance(rule, FleetForecastDemandResolutionRuleV1):
            if daily_counts is None:
                msg = (
                    f"fleet demand target {forecast.target!r} needs the "
                    "daily-counts frame to resolve; refusing to resolve it "
                    "against the telemetry frame (see TASK-FUT-043)"
                )
                raise ResolutionNotReadyError(msg)
            return rule.resolve(
                forecast=forecast,
                observation_records=daily_counts,
                evidence_snapshot_data=evidence_df,
            )

        return rule.resolve(
            forecast=forecast,
            observation_records=observations,
            evidence_snapshot_data=evidence_df,
        )


outcome_resolver = OutcomeResolver()
