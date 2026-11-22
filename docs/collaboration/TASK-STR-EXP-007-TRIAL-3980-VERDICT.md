# TASK-STR-EXP-007 — Trial 3980 production verdict (filed as evidence)

- **Task:** TASK-STR-EXP-007 (pool 9, P0) — file the trial-3980 production verdict as the task evidence.
- **Assignment:** Muse (Head Manager), coordinator watch issue #35 comment 7079717385 (~18:48 IST), answering work request 7079485536.
- **Claim:** issue #35 comment 7079841685 by Muse 4, 2026-11-22 ~19:00 IST.
- **Board record:** NOT yet on main — verified this run (board blob `2f13afe4`, 14,462 lines; no TASK-STR-EXP-007 record). Per the assigning watch, the record rides in tomorrow's first consolidated board PR (pool-9 filing, owner muse_4). No board flip is filed in this work PR.
- **Branch:** `muse4/task-str-exp-007-trial-3980-verdict`, from main `3dd7cfba`.
- **Related:** TASK-STR-EXP-006 (PR #1370, MERGED) — the starvation-breaker scheduling fix that produced trial 3980. Report: `docs/collaboration/TASK-STR-EXP-006-UNSTARVE-EXPERIMENT-LOOP.md`.

## Verdict: PROVEN

Trial 3980, `combination_cluster_champions`, declaration `decl_0001_f030c1c110`, status `ran`,
scheduling `starvation_breaker` — the first trial produced by the EXP-006 starvation breaker, run on
S1 production at 2026-11-22T11:58:43.400493Z (17:28:43 IST).

Headline (record's own verdict reason, quoted verbatim): "full frozen bar cleared at N=3980:
expectancy +2.3175%, PF 1.2623, 2208 trades, 4/5 positive folds, p 1.58e-06 < 1.26e-05,
holdout expectancy +2.0568%".

### Frozen-bar checks — 8/8 true

| Check | Bar | Trial 3980 | Pass |
|---|---|---|---|
| expectancy_gt_0 | expectancy > 0 | +2.3175% | true |
| pf_gte_full_bar | PF >= 1.2 (FULL_BAR_PF) | 1.2623 | true |
| pf_gte_second_tier | PF >= 1.05 (SECOND_TIER_PF) | 1.2623 | true |
| trades_gte_200 | trades >= 200 (MIN_OOS_TRADES) | 2,208 | true |
| folds_gte_4_of_5 | >= 4 of 5 folds positive | 4/5 | true |
| bonferroni | p < 0.05/N (N=3980 -> 1.26e-05) | 1.58e-06 | true |
| holdout_present | holdout trades present | 714 | true |
| holdout_expectancy_gt_0 | holdout expectancy > 0 | +2.0568% | true |

### Full metrics (from the production record)

- Trades 2,208; wins 848; win rate 38.41% (0.384058).
- Expectancy +2.3175% (0.02317501791312647); profit factor 1.2623 (1.262279388828916).
- Gross profit 246.27; gross loss 195.10.
- Per-fold (RD-002 OOS folds W1–W5, 2024-07-01..2026-07-01): W1 677 trades +2.44%,
  W2 323 trades +1.00%, W3 408 trades +7.92%, W4 387 trades −1.65%, W5 413 trades +1.32%.
  4/5 positive folds; fold trade counts sum to 2,208.
- Holdout: 714 trades at +2.0568% expectancy (0.020567511398538043).
- t-stat 4.66 (4.660575035428736); p one-sided 1.58e-06 (1.5766358863717088e-06).

### Members and hypothesis

Members (one champion per mechanism cluster, equal-standing union of judged OOS trade streams):
`vol_adaptive_trend/ema12_26_nogate@crypto30/1d` + `shock_breakout/k1.5@crypto30/1d` +
`rsi_momentum/rsi14_55_45@crypto30/1d` + `ha_trend/two_candle@crypto30/1d`, judged pooled,
pre-declared, on RD-002 OOS folds W1–W5. Admission key `selfexp_combo_37358617fe8a`.

## Provenance — how this was verified

- **Live re-read this run** (2026-11-22 ~19:00 IST) from S1 via the bridge (`run_shell`, server 1):
  `Stratex/self_experiments_data/experiments.jsonl` — 4 lines; `trial_counter.json` value 3980;
  trial 3980 is the latest result record (admission line + result line are the file tail);
  trial 3981 absent on S1 (null). Raw probe saved in the worker workspace
  (`muse4_exp007_trial3980_probe.json`).
- **Cross-checks, all matching:** the 18:24 work-request run's independent live S1 read
  (comment 7079485536) produced the identical record; the coordinator watch 7079717385
  received the verdict and independently confirmed the 3980 landing on S1 at 17:45 IST;
  the EXP-006 dry-run rehearsal predicted the identical verdict (same expectancy, PF,
  trade count, folds, p and holdout) before production ran it.
- **Frozen gate untouched:** EXP-006 verified the admission gate byte-unchanged
  (`judge.py` sha256 `ccdac18684605081`; FULL_BAR_PF 1.2, SECOND_TIER_PF 1.05,
  MIN_OOS_TRADES 200, 4/5 folds, Bonferroni 0.05/N). This task changes nothing in code.

## Caveat, stated plainly

This is the **S1 frozen copy**. The S1 daemon was frozen at cutover; the live state now lives on
U1. The U1 copy was **not** re-read: the bridge's `run_shell` reaches servers 1 and 2 only
("server must be 1 or 2"). Trial 3981 ran on U1 at 17:53:11 IST after the cutover and is absent
from the S1 file, which is consistent with the freeze. The cutover report (issue #35 comment
7079118898) states the state transfer was sha256-verified at every hop. **U1 confirmation of
trial 3980 remains owed** — a follow-up read from U1 once a path there exists.

## States

- Implemented: YES — this evidence doc, filed in the work PR.
- Tested: YES — live S1 re-probe this run; record matches the 18:24 independent read and the
  coordinator's own confirmation.
- Merged: NO — work PR open, awaiting Muse's review/merge.
- Deployed: N/A — evidence-only task; no code, no deployment.
- Production-verified: YES — the verdict itself is production data, read live from S1.

No live change was made by this task: no order placed, no restart, no env change, no secret
touched. Stratex remains demo only; no real money.
