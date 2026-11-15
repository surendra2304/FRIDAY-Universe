"""What-if scenario planning prototype (TASK-FUT-009).

Given a base forecast *path* (per-step central/lower/upper, e.g. the step
intervals a :class:`~futuris.core.schemas.Forecast` already carries), apply a
set of *declared* shocks — e.g. "BTC -20%", "policy rate +1pp", "oil +15%" —
and produce a coherent adjusted path with every assumption printed on the
output.

Design rules (prototype scope):

* **Declared, not estimated.** Each shock carries a caller-declared
  elasticity (how much the target moves, in %, per unit of driver move).
  Nothing here estimates an elasticity from data, and the output says so.
  An elasticity the caller cannot defend is a modelling choice they own;
  this module's job is to make that choice visible, not to hide it.
* **Deterministic transform.** The adjusted path is pure arithmetic on the
  base path: per step, each shock contributes
  ``elasticity * magnitude * profile(step)`` percent, contributions add,
  and the total percentage is applied multiplicatively to the base central
  value. Same inputs -> same outputs, no randomness, no model fitting.
* **Coherence is enforced, not hoped for.** Adjusted bands are rebuilt
  around the adjusted central value from the base band's half-widths,
  widened by a declared factor proportional to the total shock effect, and
  the result is checked so ``lower <= central <= upper`` holds at every
  step. A declared non-negativity floor (for price-like targets) is applied
  before the ordering check and is printed when used.
* **Honest labelling (the FUT-002/FUT-003 standard).** The result inherits
  the base forecast's evidence class and never upgrades it: a LIVE base
  becomes DERIVED, because the adjusted numbers are computed from the base,
  not measured. ``evidence_source`` travels and names this transform. The
  base probability is carried verbatim or reported as
  ``not_recomputed_by_whatif_engine`` — this module does not recompute
  probabilities. ``prediction_is_not_authorization`` stays true.
* **No statsforecast.** statsforecast remains post-ARM (owner decision).
  This module builds on the existing honest forecast path only: it consumes
  a base path the caller obtained from a real Futuris forecast (or declares
  themselves, labelled as such) and never fabricates a base forecast.
"""

from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11: behaviour-identical fallback
    from enum import Enum as _StrEnumBase

    class StrEnum(str, _StrEnumBase):
        """Stand-in for enum.StrEnum (3.11+) on older interpreters."""

        __str__ = str.__str__
        __format__ = str.__format__

        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()
from typing import Any

from pydantic import BaseModel, Field, model_validator

from futuris.core.enums import EvidenceClass

ENGINE_ID = "futuris.scenarios.whatif@v1-prototype"
PROBABILITY_STATUS_NOT_RECOMPUTED = "not_recomputed_by_whatif_engine"


class ShockKind(StrEnum):
    """How a shock's magnitude is measured."""

    PCT_CHANGE = "pct_change"
    """Driver moves by a percentage (e.g. BTC -20 means magnitude=-20)."""

    PP_CHANGE = "pp_change"
    """Driver moves by percentage points (e.g. rates +1pp means magnitude=1.0)."""


class DecayProfile(StrEnum):
    """What happens to a shock's effect after its ramp completes."""

    PERMANENT = "permanent"
    """The full effect persists for the rest of the path."""

    LINEAR_DECAY = "linear_decay"
    """The effect declines linearly to zero over ``decay_steps`` steps."""


class Shock(BaseModel):
    """One declared exogenous shock.

    ``elasticity`` is the declared sensitivity of the *target* to this
    driver: the target moves ``elasticity`` percent for each 1% driver move
    (``pct_change``) or each 1pp driver move (``pp_change``). It is an
    assumption supplied by the caller, printed verbatim on every output.
    """

    name: str = Field(..., min_length=1)
    driver: str = Field(..., min_length=1, description="Driver being shocked, e.g. 'BTC', 'policy_rate', 'oil'.")
    kind: ShockKind = ShockKind.PCT_CHANGE
    magnitude: float = Field(
        ...,
        description="Driver move: percent for pct_change (e.g. -20 = -20%), percentage points for pp_change (e.g. 1.0 = +1pp).",
    )
    elasticity: float = Field(
        ...,
        description="Declared target sensitivity: % target move per 1% (pct_change) or per 1pp (pp_change) driver move.",
    )
    onset_step: int = Field(default=1, ge=1, description="First step (1-based) at which the shock starts to bite.")
    ramp_steps: int = Field(default=1, ge=1, description="Steps over which the effect ramps linearly from 0 to full.")
    decay: DecayProfile = DecayProfile.PERMANENT
    decay_steps: int | None = Field(
        default=None,
        ge=1,
        description="Required when decay=linear_decay: steps over which the effect fades to zero after the ramp.",
    )
    rationale: str = ""

    @model_validator(mode="after")
    def _validate_decay(self) -> Shock:
        if self.decay is DecayProfile.LINEAR_DECAY and self.decay_steps is None:
            msg = f"Shock '{self.name}': decay=linear_decay requires decay_steps"
            raise ValueError(msg)
        if self.decay is DecayProfile.PERMANENT and self.decay_steps is not None:
            msg = f"Shock '{self.name}': decay_steps set but decay=permanent"
            raise ValueError(msg)
        return self

    def profile(self, step: int) -> float:
        """Fraction of the full effect active at ``step`` (0.0 .. 1.0)."""
        if step < self.onset_step:
            return 0.0
        steps_in = step - self.onset_step + 1
        if steps_in < self.ramp_steps:
            return steps_in / self.ramp_steps
        if self.decay is DecayProfile.LINEAR_DECAY:
            assert self.decay_steps is not None  # enforced by the validator
            steps_past_ramp = steps_in - self.ramp_steps
            return max(0.0, 1.0 - steps_past_ramp / self.decay_steps)
        return 1.0

    def effect_pct(self, step: int) -> float:
        """Percentage change this shock applies to the target at ``step``."""
        return self.elasticity * self.magnitude * self.profile(step)

    def describe(self) -> str:
        unit = "%" if self.kind is ShockKind.PCT_CHANGE else "pp"
        mag = f"{self.magnitude:+g}{unit}"
        decay = (
            "permanent after ramp"
            if self.decay is DecayProfile.PERMANENT
            else f"linear decay to zero over {self.decay_steps} steps after ramp"
        )
        return (
            f"shock '{self.name}': driver {self.driver} {mag}, declared elasticity "
            f"{self.elasticity:g} (% target move per 1{unit} driver move), "
            f"onset step {self.onset_step}, ramp {self.ramp_steps} step(s), {decay}"
        )


class PathPoint(BaseModel):
    """One step of a forecast path."""

    step: int = Field(..., ge=1)
    label: str | None = Field(default=None, description="Optional period/timestamp label, carried through unchanged.")
    central: float
    lower: float
    upper: float

    @model_validator(mode="after")
    def _validate_ordering(self) -> PathPoint:
        if not (self.lower <= self.central <= self.upper):
            msg = (
                f"PathPoint step {self.step}: require lower <= central <= upper, "
                f"got lower={self.lower}, central={self.central}, upper={self.upper}"
            )
            raise ValueError(msg)
        return self


class AdjustedPoint(BaseModel):
    """One step of the adjusted path, with per-shock attribution."""

    step: int
    label: str | None = None
    base_central: float
    base_lower: float
    base_upper: float
    adjusted_central: float
    adjusted_lower: float
    adjusted_upper: float
    total_effect_pct: float
    contributions_pct: dict[str, float] = Field(default_factory=dict)


class WhatIfRequest(BaseModel):
    """Input for :func:`apply_whatif`."""

    target: str = Field(..., min_length=1)
    base_path: list[PathPoint] = Field(..., min_length=1)
    shocks: list[Shock] = Field(..., min_length=1)
    band_widening_per_effect_pct: float = Field(
        default=0.5,
        ge=0.0,
        description=(
            "Declared uncertainty growth: each side of the band widens by this "
            "fraction of the base half-width per 1% of |total shock effect| "
            "(0.5 = a 20% shock effect widens each half-width by 10%)."
        ),
    )
    non_negative_floor: bool = Field(
        default=False,
        description="Declared: clamp adjusted values at 0 (for price-like targets that cannot go negative).",
    )
    base_evidence_class: EvidenceClass = EvidenceClass.SYNTHETIC
    base_evidence_source: str | None = None
    base_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    base_model_version: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_steps(self) -> WhatIfRequest:
        steps = [p.step for p in self.base_path]
        if steps != sorted(steps) or len(set(steps)) != len(steps):
            msg = "base_path steps must be strictly increasing"
            raise ValueError(msg)
        names = [s.name for s in self.shocks]
        if len(set(names)) != len(names):
            msg = "shock names must be unique (they key the per-step attribution)"
            raise ValueError(msg)
        return self


class WhatIfResult(BaseModel):
    """Output of :func:`apply_whatif`. Assumptions are part of the output."""

    result_kind: str = "what_if_prototype"
    engine: str = ENGINE_ID
    target: str
    base_path: list[PathPoint]
    adjusted_path: list[AdjustedPoint]
    assumptions: list[str]
    warnings: list[str] = Field(default_factory=list)
    evidence_class: EvidenceClass
    evidence_source: str | None = None
    probability_outcome: float | None = None
    probability_status: str = PROBABILITY_STATUS_NOT_RECOMPUTED
    prediction_is_not_authorization: bool = True

    def render_text(self) -> str:
        """Plain-text rendering with the assumptions printed on the output."""
        lines = [
            f"WHAT-IF (prototype) — target: {self.target}",
            f"engine: {self.engine}",
            f"evidence_class: {self.evidence_class.value} | evidence_source: {self.evidence_source}",
            f"probability: {self.probability_outcome} ({self.probability_status})",
            "prediction_is_not_authorization: true",
            "",
            "ASSUMPTIONS (declared by the caller, not estimated by this engine):",
        ]
        lines += [f"  - {a}" for a in self.assumptions]
        if self.warnings:
            lines += ["", "WARNINGS:"] + [f"  - {w}" for w in self.warnings]
        lines += [
            "",
            "step | base central -> adjusted central (effect %) | base band -> adjusted band",
        ]
        for p in self.adjusted_path:
            lines.append(
                f"{p.step} | {p.base_central:.4f} -> {p.adjusted_central:.4f} "
                f"({p.total_effect_pct:+.2f}%) | [{p.base_lower:.4f}, {p.base_upper:.4f}] "
                f"-> [{p.adjusted_lower:.4f}, {p.adjusted_upper:.4f}]"
            )
        return "\n".join(lines) + "\n"


def _result_evidence_class(base: EvidenceClass) -> EvidenceClass:
    """Inherit the base class, never upgrade it.

    A LIVE base becomes DERIVED: the adjusted path is computed
    deterministically from the base path, not measured.
    """
    if base is EvidenceClass.LIVE:
        return EvidenceClass.DERIVED
    return base


def apply_whatif(req: WhatIfRequest) -> WhatIfResult:
    """Apply the declared shocks to the base path. Pure and deterministic."""
    assumptions: list[str] = [s.describe() for s in req.shocks]
    assumptions.append(
        "elasticities are caller-declared assumptions; this engine does not "
        "estimate them from data and does not validate them against history"
    )
    assumptions.append(
        "shock contributions add linearly in percentage terms per step and "
        "the total is applied multiplicatively to the base central value"
    )
    assumptions.append(
        f"band widening: each half-width grows by {req.band_widening_per_effect_pct:g} "
        "x |total effect %| / 100 of itself per step (declared)"
    )
    assumptions.append(
        "probability is not recomputed by this engine; the base forecast's "
        "probability is carried verbatim (or null)"
    )
    if req.non_negative_floor:
        assumptions.append(
            "non-negativity floor declared: adjusted values are clamped at 0 "
            "before the band-ordering check"
        )
    if req.base_model_version:
        assumptions.append(f"base forecast model_version: {req.base_model_version}")
    assumptions += [f"caller note: {n}" for n in req.notes]

    warnings: list[str] = []
    adjusted: list[AdjustedPoint] = []
    for point in req.base_path:
        contributions = {s.name: s.effect_pct(point.step) for s in req.shocks}
        total_effect = sum(contributions.values())
        factor = 1.0 + total_effect / 100.0
        if factor <= 0.0:
            warnings.append(
                f"step {point.step}: total shock effect {total_effect:.2f}% would take the "
                "target to <= 0 under multiplicative application; central clamped at 0 "
                "and the band rebuilt around it — treat this step as a break-down of "
                "the linear-elasticity assumption, not a prediction"
            )
            factor = 0.0
        adj_central = point.central * factor
        widen = 1.0 + req.band_widening_per_effect_pct * abs(total_effect) / 100.0
        lower_half = (point.central - point.lower) * widen * factor
        upper_half = (point.upper - point.central) * widen * factor
        adj_lower = adj_central - lower_half
        adj_upper = adj_central + upper_half
        if req.non_negative_floor:
            adj_lower = max(0.0, adj_lower)
            adj_central = max(0.0, adj_central)
            adj_upper = max(0.0, adj_upper)
        # Coherence: ordering must hold by construction; assert it so a
        # future change to the arithmetic fails loudly instead of silently
        # emitting an incoherent band.
        if not (adj_lower <= adj_central <= adj_upper):
            msg = (
                f"internal coherence failure at step {point.step}: "
                f"{adj_lower} <= {adj_central} <= {adj_upper} does not hold"
            )
            raise RuntimeError(msg)
        adjusted.append(
            AdjustedPoint(
                step=point.step,
                label=point.label,
                base_central=point.central,
                base_lower=point.lower,
                base_upper=point.upper,
                adjusted_central=adj_central,
                adjusted_lower=adj_lower,
                adjusted_upper=adj_upper,
                total_effect_pct=total_effect,
                contributions_pct=contributions,
            )
        )

    evidence_source = req.base_evidence_source
    if evidence_source:
        evidence_source = f"{evidence_source}; +{ENGINE_ID} shock transform"
    else:
        evidence_source = f"caller_supplied_base_path; +{ENGINE_ID} shock transform"

    return WhatIfResult(
        target=req.target,
        base_path=req.base_path,
        adjusted_path=adjusted,
        assumptions=assumptions,
        warnings=warnings,
        evidence_class=_result_evidence_class(req.base_evidence_class),
        evidence_source=evidence_source,
        probability_outcome=req.base_probability,
        probability_status=PROBABILITY_STATUS_NOT_RECOMPUTED,
        prediction_is_not_authorization=True,
    )


def base_path_from_forecast(forecast: Any) -> tuple[list[PathPoint], dict[str, Any]]:
    """Build a base path + provenance metadata from a Futuris ``Forecast``.

    Duck-typed on purpose: anything with the Forecast shape works (the
    domain schema, a stored row, a test double). The path comes from the
    forecast's own step ``intervals`` when present — those are the steps
    the producing pipeline itself emitted. When a forecast carries no
    intervals, the path is its single point estimate with its range,
    labelled as such by the caller via the returned metadata; this helper
    never invents intermediate steps.
    """
    intervals = getattr(forecast, "intervals", None) or []
    points: list[PathPoint] = []
    for i, iv in enumerate(intervals):
        if not isinstance(iv, dict) or not {"lower", "central", "upper"} <= set(iv):
            continue
        points.append(
            PathPoint(
                step=int(iv.get("step", i + 1)),
                central=float(iv["central"]),
                lower=float(iv["lower"]),
                upper=float(iv["upper"]),
            )
        )
    path_source = "forecast_intervals"
    if not points:
        points = [
            PathPoint(
                step=1,
                central=float(forecast.prediction),
                lower=float(forecast.range_lower),
                upper=float(forecast.range_upper),
            )
        ]
        path_source = "forecast_point_estimate_single_step"
    meta: dict[str, Any] = {
        "path_source": path_source,
        "evidence_class": getattr(forecast, "evidence_class", None) or EvidenceClass.SYNTHETIC,
        "evidence_source": getattr(forecast, "evidence_source", None),
        "probability": getattr(forecast, "probability", None),
        "model_version": getattr(forecast, "model_version", None),
        "target": getattr(forecast, "target", None),
    }
    return points, meta


def request_from_forecast(
    forecast: Any,
    shocks: list[Shock],
    **overrides: Any,
) -> WhatIfRequest:
    """Assemble a :class:`WhatIfRequest` from a Forecast and declared shocks."""
    points, meta = base_path_from_forecast(forecast)
    kwargs: dict[str, Any] = {
        "target": meta["target"] or "unknown_target",
        "base_path": points,
        "shocks": shocks,
        "base_evidence_class": meta["evidence_class"],
        "base_evidence_source": meta["evidence_source"],
        "base_probability": meta["probability"],
        "base_model_version": meta["model_version"],
        "notes": [f"base path source: {meta['path_source']}"],
    }
    kwargs.update(overrides)
    return WhatIfRequest(**kwargs)
