"""TASK-STR-RD-001 research programme package.

Built ON the TASK-STR-BT-001 rigorous_backtest harness (same data, same
fold structure, same cost model, same out-of-sample-only discipline).
Everything in here is research-only: nothing imports production engines,
nothing writes to production config, governance or priors.

Anti-Overfit Law (programme law, see RESULTS_RD.md):
- every variant tried is counted and disclosed;
- parameters are selected on in-sample folds only; judgement is OOS only;
- the promotion bar rises with the number of variants tried and is
  pre-registered per stage (see rd.common.PROMOTION_BAR);
- any candidate must additionally pass a holdout check before the name
  "promotion candidate" is used.
"""
