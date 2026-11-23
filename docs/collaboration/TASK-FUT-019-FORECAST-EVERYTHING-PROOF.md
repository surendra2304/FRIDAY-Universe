# TASK-FUT-019 — Forecast-Everything Proof (Muse 4 pick-up)

- **Task:** TASK-FUT-019, Futuris forecast-everything proof (one real non-market forecast end to end: forecast, outcome, score).
- **Re-slot:** Muse 12 → Muse 4 by coordinator enforcement 2026-11-23 ~22:40 IST (Muse 12 silent, newest tip 15:00 IST). Board on main 49126a41: CLAIMED, owner muse_4.
- **Claim:** hub #1483 comment 7111356187, 2026-11-24 ~00:55 IST.
- **Branch:** muse4/task-fut-019-forecast-everything-proof, from main 49126a41.
- **Forecast:** New Delhi daily maximum temperature 2026-11-24 — point **26.0 °C**, 95% interval **[25.1, 26.9] °C** — issued by Muse 12 on 2026-11-23 15:00 IST, before the outcome day. Filed in `docs/collaboration/TASK-FUT-019-FORECAST-EVIDENCE.md`, carried over unchanged from branch `muse12/task-fut-019-forecast-everything-proof` @61483aff (blob eb3e5045).

## Pick-up verification (Muse 4, 2026-11-24 ~00:50 IST, first-hand)

- **Input series re-read live** from the IARI daily-weather table (https://www.iari.res.in/bms/daily-weather/): the 14–23 Nov max temps match Muse 12's input table exactly — 30.6, 29.0, 28.5, 26.8, 26.6, 26.8, 26.5, 27.0, 26.6, 25.8. The 24/11 outcome row is not yet published (the page still shows the observed table through 23/11 plus the IMD multimodel forecast: 25 °C for 24/11).
- **Members re-computed from that table:** persistence 25.8; 3-day mean (21–23 Nov) (27.0 + 26.6 + 25.8) / 3 = 26.47; 7-day mean (17–23 Nov) 186.1 / 7 = 26.59; OLS trend slope −0.413 °C/day over the 10 points → 25.15. Ensemble mean (25.8 + 26.47 + 26.59 + 25.15) / 4 = 26.00 °C. All four members and the point check out.
- **Interval re-computed:** 26.0 ± 1.96 × RMSE 0.45 = [25.1, 26.9] °C. Checks out (backtest n = 3, indicative, as Muse 12 filed).
- **Reference spread:** IARI multimodel 25 °C, climate-observer.org 25.8 °C, weather15.com 27 °C — this forecast (26.0 °C) sits inside it.
- **Engine note (Muse 12's finding, not re-probed):** `Futuris/predict/forecasting_engine.py` ensemble members are hash-derived, not data-fitted — no Futuris engine code was executed for this forecast, and none is executed here. The engine needs real fitted models before it can be the vehicle for a forecast proof; that is a follow-up, not this task.

## States

- implemented YES (forecast issued 2026-11-23 15:00 IST + filed) / tested YES (pick-up verification above) / merged NO / deployed N/A / production-verified NO — scoring is owed 2026-11-25, after the IARI outcome for 24/11 publishes: absolute error |26.0 − outcome| and interval hit (outcome in [25.1, 26.9]).
- **Scoring owner — awaiting Muse's ruling:** Muse 12's Nov 25 10:00 IST one-off scoring check is still armed (his status 7111226382); he asks whether Muse 4 takes the scoring or his check runs it. No competing scoring PR will be filed until Muse rules.

## Queue

STR-HLT-002 (blocked head — Spotware app Submitted; wait-state filing merged, PR #1413) → STR-046 (in review; work PR #1533 open, mergeable, CI 9/9 green) → FUT-019 (this task).
