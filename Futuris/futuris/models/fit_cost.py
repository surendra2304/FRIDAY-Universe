"""Pre-fit memory estimate + model shortlist (TASK-FUT-017).

The OOM saga this caps: Futuris's fit cost had no control at all. The
candidate backtest in :mod:`futuris.models.selection` fitted every routed
candidate (``mean_ensemble`` and ``auto_ets`` ~4.5s each, ``auto_arima`` a
stepwise search over many orders) and the winner was then refit on the
full series, with nothing bounding the memory any of it could take. The
only guard was the systemd ``MemoryMax`` — raised 180M to 512M on a
956MB box — which kills the process *after* the memory is already gone.
That is a backstop, not a control.

This module is the control. Before any fit starts, the caller estimates
what the fit will cost and shortlists the candidates to fit inside an
explicit budget (``FUTURIS_FIT_MEMORY_BUDGET_MB``, default 256MB — half
the 512M backstop, so the cap binds long before the killer does):

* :func:`estimate_fit_memory_mb` -- a conservative upper-bound estimate
  for one candidate fit, from the frame size and the family. It is an
  *estimate*, not a measurement: the coefficients are planning bounds
  (float64 working copies per family, documented per family below), and
  the estimate is always labelled as one wherever it is recorded. What
  it must get right is the ordering (naive < seasonal_naive < auto_ets
  < mean_ensemble < auto_arima) and the scaling (linear in rows and
  columns), so the shortlist drops the expensive fits first on big data.
* :func:`shortlist_candidates` -- router rank order in, the affordable
  prefix of it out, with the dropped names and every estimate recorded.
  At least one candidate is always kept (the cheapest), because the
  frame itself is already in memory: a cheap baseline fit adds about
  one series copy on top of data the process already holds, so refusing
  it would lose the forecast without saving the process.
* :func:`final_fit_within_budget` -- the same estimate for the winner's
  full-data refit, so the pipeline can fall back to the naive baseline
  instead of refitting an expensive winner it cannot afford.

The cap is enforced in :func:`futuris.models.selection.select_best_adapter`
(candidate fits) and in ``ModelingStage._fit_and_predict`` (final refit).
Both record the decision in ``Forecast.model_metadata``, so a capped
forecast says so instead of silently changing model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Explicit pre-fit memory budget (MB) for one forecast's model fits.
#: Half the 512M MemoryMax backstop: the cap must bind while there is
#: still headroom, not at the point the OOM killer fires.
DEFAULT_FIT_MEMORY_BUDGET_MB = 256.0

#: Fixed per-fit overhead (MB): adapter objects, statsforecast model
#: state, and the residual arrays every adapter keeps.
_BASE_OVERHEAD_MB = 0.5

#: Extra fixed overhead (MB) for the AutoARIMA stepwise search: the
#: candidate-order table and the best-model bookkeeping it holds while
#: trialling orders.
_ARIMA_SEARCH_OVERHEAD_MB = 4.0

#: Bytes per float64 cell. Every frame the pipeline hands a fit is
#: float64; working copies are counted in the same unit.
_BYTES_PER_CELL = 8.0

#: Working-copy multipliers on the fit frame, per adapter family. A fit
#: holds the frame plus its working copies: naive-family adapters keep
#: the series and one residual copy (2x); AutoETS keeps level/trend/
#: seasonal states, fitted values, residuals and optimiser workspace
#: (12x); AutoARIMA trials many (p,d,q) orders, each allocating
#: differenced series plus the exogenous regressor matrix (48x, plus a
#: per-exogenous-column term in :func:`estimate_fit_memory_mb`).
#: MeanEnsemble fits AutoETS + SeasonalNaive, so its multiplier is the
#: sum of its members. Unlisted adapters take the AutoARIMA bound:
#: an unknown fit is assumed expensive until it proves otherwise.
_FRAME_MULTIPLIERS: dict[str, float] = {
    "naive": 2.0,
    "drift": 2.0,
    "seasonal_naive": 2.0,
    "auto_ets": 12.0,
    "mean_ensemble": 14.0,  # auto_ets (12x) + seasonal_naive (2x)
    "auto_arima": 48.0,
}

#: Multiplier applied to unlisted adapter names (bass_diffusion,
#: hawkes_cascade, garch_volatility, and anything registered later).
DEFAULT_FRAME_MULTIPLIER = 48.0

#: Adapters whose fit is cheap enough that the estimate is dominated by
#: the frame itself: a final refit with one of these is never refused.
CHEAP_FIT_CANDIDATES = frozenset({"naive", "drift", "seasonal_naive"})


def resolve_fit_memory_budget(memory_budget_mb: float | None) -> float:
    """Explicit caller budget wins; else the configured cap; else the default.

    The settings import is lazy and guarded: callers must keep working
    in harnesses that import them without a configured environment, and
    the documented 256MB default is the fallback either way.
    """
    if memory_budget_mb is not None:
        return float(memory_budget_mb)
    try:
        from futuris.infra.config import settings

        return float(settings.FUTURIS_FIT_MEMORY_BUDGET_MB)
    except Exception:
        return DEFAULT_FIT_MEMORY_BUDGET_MB


def estimate_fit_memory_mb(
    candidate: str,
    n_rows: int,
    n_features: int,
    *,
    n_exog: int = 0,
) -> float:
    """Conservative upper-bound estimate (MB) for fitting ``candidate``.

    ``n_rows`` is the training rows, ``n_features`` the feature columns
    of the fit frame (excluding the ``value`` target), ``n_exog`` the
    exogenous regressor columns the adapter actually consumes (only
    AutoARIMA does; every other adapter ignores them, so its estimate
    does not count them). The frame is ``n_rows * (1 + n_features)``
    float64 cells; the family multiplier counts the working copies a
    fit of that family holds at once.
    """
    if n_rows < 0 or n_features < 0 or n_exog < 0:
        raise ValueError("n_rows, n_features and n_exog must be non-negative")
    frame_mb = n_rows * (1 + n_features) * _BYTES_PER_CELL / 1_000_000.0
    multiplier = _FRAME_MULTIPLIERS.get(candidate, DEFAULT_FRAME_MULTIPLIER)
    estimate = _BASE_OVERHEAD_MB + frame_mb * multiplier
    if candidate == "auto_arima":
        # The stepwise search re-allocates the regressor matrix per trial
        # order; its cost grows with the exogenous width, not just the
        # frame. 10x the exog cells is the planning bound for that.
        exog_mb = n_rows * max(n_exog, 0) * _BYTES_PER_CELL * 10.0 / 1_000_000.0
        estimate += _ARIMA_SEARCH_OVERHEAD_MB + exog_mb
    return round(estimate, 6)


@dataclass(frozen=True)
class FitCostShortlist:
    """Result of shortlisting candidates against the fit-cost budget."""

    kept: list[str]
    dropped: list[str]
    estimates_mb: dict[str, float]
    budget_mb: float
    total_kept_mb: float
    capped: bool = field(default=False)

    def as_metadata(self) -> dict[str, object]:
        """Provenance fragment for ``Forecast.model_metadata``."""
        meta: dict[str, object] = {
            "fit_memory_budget_mb": self.budget_mb,
            "fit_memory_estimates_mb": dict(self.estimates_mb),
            "fit_memory_kept_total_mb": round(self.total_kept_mb, 6),
            "fit_cost_capped": self.capped,
        }
        if self.dropped:
            meta["candidates_dropped_by_fit_cost_cap"] = sorted(self.dropped)
        return meta


def shortlist_candidates(
    candidates: list[str],
    *,
    n_rows: int,
    n_features: int,
    budget_mb: float,
    n_exog: int = 0,
) -> FitCostShortlist:
    """Keep the affordable candidates, in router rank order.

    A candidate is kept when the running total of kept estimates stays
    within ``budget_mb``; one that would overflow is dropped and the
    next-ranked candidate is tried, so a cheap baseline later in the
    ranking still fits when an expensive leader does not. At least one
    candidate is always kept -- the cheapest by estimate -- because the
    frame is already in memory and a cheap baseline fit adds about one
    series copy on top of it. The shortlist is a planning decision on
    estimates; the estimates themselves are recorded so the cap can be
    audited against real memory later.
    """
    if not candidates:
        raise ValueError("shortlist_candidates needs at least one candidate")
    if budget_mb <= 0:
        raise ValueError("budget_mb must be positive")
    estimates = {
        name: estimate_fit_memory_mb(name, n_rows, n_features, n_exog=n_exog)
        for name in candidates
    }
    kept: list[str] = []
    dropped: list[str] = []
    running = 0.0
    for name in candidates:
        estimate = estimates[name]
        if running + estimate > budget_mb:
            dropped.append(name)
            continue
        kept.append(name)
        running += estimate
    if not kept:
        # Every candidate alone exceeds the budget (a budget smaller than
        # one cheap fit, or a frame so large no fit is affordable): keep
        # the cheapest so the forecast still has a model, and say so.
        cheapest = min(candidates, key=lambda n: (estimates[n], candidates.index(n)))
        kept = [cheapest]
        dropped = [n for n in candidates if n != cheapest]
        running = estimates[cheapest]
    return FitCostShortlist(
        kept=kept,
        dropped=dropped,
        estimates_mb=estimates,
        budget_mb=budget_mb,
        total_kept_mb=round(running, 6),
        capped=bool(dropped),
    )


def final_fit_within_budget(
    adapter_name: str,
    n_rows: int,
    n_features: int,
    budget_mb: float,
    *,
    n_exog: int = 0,
) -> tuple[bool, float]:
    """Whether the winner's full-data refit fits the budget.

    Returns ``(within_budget, estimate_mb)``. Cheap baselines always
    fit: their incremental memory over the already-loaded frame is
    about one series copy, so refusing them would lose the forecast
    without saving the process.
    """
    if adapter_name in CHEAP_FIT_CANDIDATES:
        return True, estimate_fit_memory_mb(
            adapter_name, n_rows, n_features, n_exog=n_exog
        )
    estimate = estimate_fit_memory_mb(
        adapter_name, n_rows, n_features, n_exog=n_exog
    )
    return estimate <= budget_mb, estimate
