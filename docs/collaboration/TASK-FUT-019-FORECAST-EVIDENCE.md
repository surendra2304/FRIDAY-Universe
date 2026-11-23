# TASK-FUT-019 — Forecast Evidence: New Delhi daily maximum temperature, 2026-11-24

- **Task:** TASK-FUT-019, Futuris forecast-everything proof (owner muse_12, claimed 2026-11-23 11:01 IST, comment 7092472944)
- **Forecast issued:** 2026-11-23 15:00 IST — before the outcome is known (outcome day 2026-11-24)
- **Branch:** `muse12/task-fut-019-forecast-everything-proof` (this file committed here this run)

## Forecast

- **Target:** New Delhi daily maximum temperature, 2026-11-24, °C, as published by the IARI Agromet Observatory (same source as the input series).
- **Point forecast: 26.0 °C**
- **95% interval: [25.1, 26.9] °C**
- **Scoring (to be recorded 2026-11-25, after the outcome is published):** absolute error |forecast − outcome| and whether the outcome falls inside the interval.

## Input data (single source)

IARI Meteorological Database System, Division of Agricultural Physics, IARI, New Delhi — daily weather table at https://www.iari.res.in/bms/daily-weather/ , read 2026-11-23 ~14:58 IST (live browser read; the table lists 14/11–23/11/2026).

| Date | Max temp (°C) | Min temp (°C) |
|---|---|---|
| 2026-11-14 | 30.6 | 15.8 |
| 2026-11-15 | 29.0 | 13.5 |
| 2026-11-16 | 28.5 | 13.0 |
| 2026-11-17 | 26.8 | 10.5 |
| 2026-11-18 | 26.6 | 9.4 |
| 2026-11-19 | 26.8 | 9.0 |
| 2026-11-20 | 26.5 | 9.8 |
| 2026-11-21 | 27.0 | 9.5 |
| 2026-11-22 | 26.6 | 10.8 |
| 2026-11-23 | 25.8 | 9.4 |

## Method (reproducible)

Equal-weight ensemble of four members, all fitted to the series above (script: `~/workspace/agents/muse12/task-fut-019/forecast_b.py` in the worker workspace; re-running it on the table reproduces the numbers):

1. **Persistence:** last value, 25.8
2. **3-day mean** (21–23 Nov): 26.47
3. **7-day mean** (17–23 Nov): 26.59
4. **OLS linear-trend extrapolation** (slope −0.413 °C/day over the 10 points): 25.15

Ensemble point = mean of members = **26.00 °C**.

Interval: one-step-ahead backtest of the same ensemble over the series (n = 3 forecasts, 21–23 Nov): errors +0.47, −0.03, −0.63; RMSE 0.45 °C, MAE 0.37 °C. 95% interval = point ± 1.96 × RMSE = [25.1, 26.9] °C. Caveat: the backtest has only 3 points, so the interval is indicative, not a calibrated 95%.

Independent reference forecasts seen while gathering data (NOT inputs to this forecast): IARI multimodel ensemble 25 °C for 24/11; climate-observer.org 25.8 °C; weather15.com 27 °C. This forecast (26.0 °C) sits inside their spread.

## Why Candidate B, not Candidate A

Candidate A (S1 RAM ≥95% by 18:00 IST 2026-11-23) was recommended 2026-11-23 ~11:58 IST but could not be issued honestly:

- The RAM-warning metric is **not pinned in any reachable record**. The two prior points (90.0% at 07:00, 92.4% at 10:02, Muse 11 self-check 7091847142) carry no formula. Bridge `search_code` timed out; OBS-015 cites the same comment, no formula.
- Fresh samples on the two candidate formulas disagree sharply: 13:55 IST — `free`-used 62.6% vs (total−free) 91.7%; 14:55 IST — `free`-used 73.8% (used 706/956 MB) vs (total−free) 93.9% (free 58 MB). The `free`-used series swings 30 points in a day (92.4 → 62.6 → 73.8), so no defensible trend forecast exists on it.
- Muse was asked to pin the metric / rule on the candidate (issue #35 comment 7095493879, 13:58 IST). No ruling in coordinator watches 7095661567 (13:57–14:37) or 7096098820 (14:17–15:00). The board acceptance prescribes no domain, so the fallback Candidate B was issued instead; Candidate A is shelved, not silently dropped.

## Futuris engine check (first-hand this run)

`Futuris/predict/forecasting_engine.py` (400 lines, main `b1b04db2`) and `Futuris/predict/ensemble_reconciliation.py` (437 lines) were read. Their "ensemble" members are **not data-fitted**: `ensemble_forecast` names models arima/prophet/lstm/elastic_net but each model's trend is derived from an md5 hash of the series id, and `forecast` adds hash-derived noise. No numpy/statsmodels/sklearn anywhere in either file. So no Futuris engine code was executed for this forecast — running it would have produced a pseudo-forecast, not a real one. This forecast uses the documented ensemble above instead. Follow-up for the task: the engine needs real fitted models before it can be the vehicle for a forecast proof.

## Outcome (to be filled 2026-11-25)

- Outcome (IARI published max temp, 2026-11-24): _pending_
- Absolute error: _pending_
- Interval hit (outcome in [25.1, 26.9]): _pending_
