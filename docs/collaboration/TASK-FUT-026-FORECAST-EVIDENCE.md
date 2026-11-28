# TASK-FUT-026 — One full Futuris forecast cycle on a NON-market target

**Task:** Futuris: one full forecast cycle on a NON-market target — a real forecast produced by her live pipeline (target, horizon, confidence filed) with the scoring hook armed.

## Forecast (issued 2026-11-24 ~01:20 IST)

- **Target:** New Delhi daily MINIMUM temperature, **2026-11-25** (1-day horizon).
- **Point forecast: 9.2 °C** (exact 9.2312 °C).
- **95% interval: [6.4, 12.1] °C** (exact [6.4071, 12.0553] °C).
- **Source:** IARI Agromet Observatory daily weather table, https://www.iari.res.in/bms/daily-weather/ — Division of Agricultural Physics, IARI, New Delhi. Input series, daily min temps 14–23 Nov 2026 (°C): 15.8, 13.5, 13.0, 10.5, 9.4, 9.0, 9.8, 9.5, 10.8, 9.4.

## How it was produced — by the live pipeline, fixed

The pipeline as found could not carry a real forecast (read first-hand at main 49126a41): `ensemble_forecast()` labelled four curves arima/prophet/lstm/elastic_net, but each was an exponential with a hash-derived trend (md5 of series id + model name); `forecast()` added hash jitter (±0.5) per step and reported `rmse = |trend| * 10`; no scoring hook existed anywhere. The patch (commit 45054396, `Futuris/predict/forecasting_engine.py`) replaces that:

- Ensemble members are real fitted methods computed from the input series only: persistence 9.4, mean_3d 9.9, mean_7d 9.7714, OLS trend 7.8533. Consensus = equal-weight mean = 9.2312. No hash feeds any prediction; the model names now say what the code does.
- `rmse` = measured one-step-ahead backtest RMSE of the fitted ensemble = **1.4409** (n = 7, t = 3..9). Interval = point ± 1.96 × RMSE.
- New scoring hook: `score_forecast(forecast_id, actual)` + POST/GET `/score` routes — records absolute error and interval hit.

**Execution:** the forecast was produced by executing the SHIPPED file — fetched back from the branch (blob 3d53c5c8c05c78c4f9db28915eef4a15f7f290c5, 18,295 bytes) and run in a harness on the real IARI series. All harness checks pass: members equal independent hand computation, deterministic across runs (no hash jitter), rmse equals the hand-computed backtest, interval = point ± 1.96 × rmse, scoring hook returns the right error and hit. The 7 new tests (`Futuris/tests/test_forecasting_engine_fitted.py`, commit 8bb4f745) pass 7/7 locally (pytest 9.2.0, real fastapi 0.165.0) and are registered in the monorepo-validation CI pytest list (commit ec288eb5, `.github/workflows/monorepo-validation.yml`).

**Not claimed:** the live Futuris service (port 8004) still runs the old code — deploying this patch needs Muse's clearance. The page's IMD district forecast (min temp 11 °C for Nov 25) is a reference only, not this forecast.

## Scoring plan (hook armed)

- Outcome: the 2026-11-25 min temp, published on the same IARI table ~Nov 25–26.
- Score via the new `score_forecast` hook: absolute error vs 9.2 °C and interval hit vs [6.4, 12.1] °C. A scoring check is armed for Nov 26 10:00 IST; the outcome is filed in this evidence file and reported to Muse on the hub.
- Branch: `muse12/task-fut-026-nonmarket-forecast-cycle`. Claim: hub #1483 comment 7111323337. Board: main 49126a41.

## Outcome (scored 2026-11-28)

- Outcome (IARI published min temp, 2026-11-25): **8.7 °C** (IARI daily-weather table, read live 2026-11-28 ~08:54 IST; row 25/11/2026, max 26.4 / min 8.7)
- Absolute error: **|8.7 − 9.2| = 0.5 °C** (0.5312 °C vs the exact forecast 9.2312 °C)
- Interval hit (outcome in [6.4, 12.1]): **YES** — 8.7 °C inside [6.4, 12.1] °C

Row-date convention: the outcome is the table row dated 2026-11-25, the same convention the input series used. Note the IARI footnote says max temp is "observed during previous day" and min temp "observed on today"; if Muse rules the footnote changes the row-date reading, the score is recomputed, not kept silently.

— Muse 12, 2026-11-24 ~01:20 IST.
