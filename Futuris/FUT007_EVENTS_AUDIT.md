# TASK-FUT-007 — Futuris events / calendar integration audit

**Question.** How do known future events — market holidays, earnings
seasons, macro releases, the owner's calendar — enter Futuris forecasts,
and does a known event actually change the forecast path?

**Answer (before this task).** It did not. The calendar features were
computed and then thrown away; no other known-event source exists in the
forecast path at all. The wiring that the design intends has been
implemented by this task (see "Fix" below).

## What exists, surface by surface

| Surface | Known-event input | Effect on the forecast path (before) |
|---|---|---|
| `futuris/features/contextualize.py` — `ContextLayer` + `SimpleHolidayCalendar` | 6 fixed US dates (New Year, Jul 4, Thanksgiving ±, Christmas, New Year's Eve) → `is_holiday`, plus hour/dow/weekend/cyclical features | **None.** Features were computed for history only and consumed by no model (proof below). Surfaced only in `DriverAnalyzer` correlation reporting. |
| `futuris/models/adapters.py` — Naive, SeasonalNaive, Drift, AutoETS, AutoARIMA, MeanEnsemble | The full feature frame `x` is passed to every `fit(x, y, as_of)` by the pipeline and the engine | **None.** Every adapter opened with `_ = x`; no adapter ever passed `X` to its statsforecast backend; every backend was fitted univariately on `y` alone. |
| Future horizon | — | **Nothing existed.** `build_feature_table` is point-in-time (≤ `as_of`) by design, and no code built calendar features for the future steps being forecast, so even a willing model had nothing to consume. |
| `futuris/models/routing.py` — `ModelRouter` | — | AutoARIMA — the only statsforecast backend that accepts exogenous regressors — was registered in `models/registry.py` but **never returned as a candidate** by any routing branch, so it could never be selected even if wired. |
| Earnings seasons | — | **Absent.** No earnings calendar, feed, or feature anywhere in Futuris (repository-wide search: no hits outside "learning" false positives). |
| Macro releases (FOMC / CPI / NFP dates) | — | **Absent.** The scheduler forecasts macro *series* (FRED: SPY exceedance, DGS10, T10Y2Y, UNRATE) but has no release-date awareness; nothing marks a forecast window as containing a scheduled release. |
| Market holidays (exchange calendars) | — | Only the 6 generic dates above. No NYSE/NASDAQ/NSE/BSE exchange calendars, no half-days, no per-market mapping. |
| Owner's calendar | — | **Absent.** No connector, import, or reference to any personal/Google calendar anywhere in Futuris. |
| IntelX exogenous research (`connectors/intelx_context.py`, engine + market router) | Qualitative research findings → `sentiment_multiplier`, `volatility_multiplier`, `confidence_penalty` | **Partial — the only exogenous input that did anything.** In `ForecastEngine` it widens/narrows the served interval bounds (via `AIUniverseModelEnhancer`) and adds a driver label; in the market router it scales the telemetry heuristic. It never moved the central estimate / point forecast, and it is *research sentiment*, not a known scheduled event. |
| `predict/event_probability_forecaster.py`, `predict/realtime_event_impact.py` | — | Legacy `predict/` layer; **not mounted** in the live app (see `futuris/api/app.py` and TASK-TRUST-001). Not part of the served forecast path. |
| `futuris/api/routers/events.py` | — | Despite the name: Futuris's own audit-event stream and webhook subscriptions (events *out*), not known events *in*. |

## Proof (before)

Experiment (recording stand-ins for the statsforecast classes, real
`ContextLayer` feature table whose history spans Christmas 2026):

- `is_holiday` on 2026-12-25: **1 for all 288 five-minute rows**; 0 on the
  surrounding days — the calendar itself works.
- Every adapter (Naive, SeasonalNaive, Drift, AutoETS, AutoARIMA,
  MeanEnsemble) produced **byte-identical point forecasts** with the real
  feature frame vs the same frame with `is_holiday` zeroed.
- **No adapter ever passed `X`** to its backend at fit or predict.

Verdict: a known event inside the horizon changed nothing, anywhere.

## Fix (this task)

Design intent is explicit in the code: the `ModelAdapter` protocol takes
the full feature frame at `fit`, and `ContextLayer` exists to compute
calendar features for models. The missing wiring, implemented:

1. **`futuris/features/contextualize.py`**
   - `CALENDAR_FEATURE_COLUMNS` — the 8 timestamp-only features that are
     knowable for future steps without leakage. Value-dependent features
     (lags, rolling stats, regime flags) are deliberately excluded: they
     depend on future *values* and must never be fabricated forward.
   - `calendar_features_for_index()` — single source of the calendar
     formulas, now used by both the historical table and the future frame
     (a test pins them identical on the same timestamps).
   - `ContextLayer.build_future_calendar_features(start, steps,
     step_minutes)` — the future frame that did not exist.
   - `summarize_known_events()` — holiday/weekend step counts for
     prediction metadata.
2. **`futuris/models/adapters.py`**
   - `supports_exogenous` declared per adapter (only AutoARIMA: `True`).
   - Adapters record the history grid (last timestamp + step) at fit —
     the information needed to derive future timestamps — instead of
     discarding the frame silently.
   - `AutoARIMAAdapter.fit` passes the historical calendar columns as `X`
     (with an honest univariate fallback + warning if a backend build
     rejects regressors); `predict` passes the future calendar frame —
     derived from the recorded grid, or an explicit `future_x` — and the
     prediction metadata now carries `exogenous_features` and
     `known_event_steps` (e.g. `holiday_steps: 288`), so a served
     forecast states which known events its horizon contains.
   - Univariate adapters accept `future_x` for a uniform contract and
     document that known events cannot move them; a misaligned
     `future_x` is refused with `ValueError` instead of being silently
     misaligned with forecast steps.
   - The TASK-REL-018 honesty contract is untouched: with no
     statsforecast backend, fit still raises
     `StatsForecastUnavailableError`; nothing substitutes numbers.
3. **`futuris/models/routing.py`** — `auto_arima` added as a candidate in
   the moderate and rich-history branches (ranked behind incumbents;
   held-out validation MAE still decides whether it ever serves).
4. **`futuris/models/base.py`** — protocol `predict` gains the optional
   `future_x` parameter with its contract documented.
5. **Tests** — `tests/models/test_fut007_event_wiring.py` (10 tests) and
   the disclosed update of `test_router_heuristics_policy_branches` in
   `tests/models/test_engine.py` to the new routing policy.

## Proof (after)

With an X-aware AutoARIMA stand-in (fixed +25.0 holiday effect, the real
library's regressor contract):

- Fit receives `X` with exactly the 8 calendar columns; predict receives
  the future frame for the horizon.
- History ending 2026-12-24 12:00, horizon 288 steps: the forecast path
  differs from the no-event control **at exactly the Christmas steps**
  (difference = +25.0 where `is_holiday` = 1, 0.0 elsewhere), and
  metadata reports the exact holiday-step count of the window.
- A November control window reports `holiday_steps: 0`.
- Univariate adapters: identical output with/without a future frame
  (documented limitation, not a silent one).

## What this does NOT claim

- **Not production-verified.** Production still has no `statsforecast`
  (owner decision: it waits for the ARM host). Until then every adapter
  refuses to fit and forecasts surface as degraded/BLOCKED — unchanged.
  The wiring activates the first time a real backend serves, and the
  metadata makes its use visible in every served forecast.
- The holiday calendar remains the 6 generic US dates. Exchange-grade
  calendars, earnings seasons, macro release dates, and any owner-calendar
  input remain **absent by design of this task's scope** — they are data
  sources to add behind the same `CALENDAR_FEATURE_COLUMNS` seam, not
  wiring defects. They are recorded here plainly as gaps, not silently
  implied to exist.
- AutoARIMA only wins serving when validation says so; on series where
  calendar effects do not help, the incumbent models keep serving and the
  forecast path is (correctly) unmoved by events.
