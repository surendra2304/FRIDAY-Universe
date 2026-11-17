# TASK-STR-RD-019 — declared run result

**Verdict: FAIL**

The family does not clear the pre-declared bar at both cost levels; per the declaration it closes (strict OOS PF < 1.2 components delete the family).

Declaration: Stratex/rigorous_backtest/rd19/xsrev_declaration.json sha256=a2d5f212308fdd097e968c801c175b9513da3ff24c49456590eec70d324d917b
Trial floor (N_global): 3895

## programme_16bps

OOS trades: 305, expectancy_net: 0.001461028506179598, PF_net: 1.0314344302884833

Checks: {"expectancy_net_gt_0": true, "profit_factor_net_gte_1.2": false, "min_oos_trades_200": true, "positive_folds_gte_4_of_5": false, "holdout_breadth": false, "temporal_holdout_v1": true, "bonferroni": false}

Temporal holdout v1: {"H1_holdout_trades_gte_20": true, "H2_holdout_expectancy_gt_0": true, "H3_dev_oos_expectancy_gt_0": true, "H4_fold_concentration_lte_0.80": true} (H trades 55, H expectancy_net 0.0011930738371639603)

Signals: ranked=1278 climax=385 gated_out=893 skipped_open=0

## shadow_32bps

OOS trades: 305, expectancy_net: -0.00013426359995935856, PF_net: 0.9971621652715942

Checks: {"expectancy_net_gt_0": false, "profit_factor_net_gte_1.2": false, "min_oos_trades_200": true, "positive_folds_gte_4_of_5": false, "holdout_breadth": false, "temporal_holdout_v1": false, "bonferroni": false}

Temporal holdout v1: {"H1_holdout_trades_gte_20": true, "H2_holdout_expectancy_gt_0": false, "H3_dev_oos_expectancy_gt_0": false, "H4_fold_concentration_lte_0.80": false} (H trades 55, H expectancy_net -0.0004172436184426077)

Signals: ranked=1278 climax=385 gated_out=893 skipped_open=0
