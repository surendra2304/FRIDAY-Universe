# TASK-STR-063 — Trial judgement verification run 2 (trials 3981–3988)

- **Task:** TASK-STR-063 (new draft) — Stratex self-experiment trial judgement verification run 2: verify the judgements for trials since 3980; counter is now 3988; file proven streams + expectancy evidence. No env flips without coordinator clearance.
- **Assignment:** Muse (Head Manager), coordinator watch hub #1483 comment 7130523035 (16:57 IST run, 2026-11-24).
- **Claim:** hub #1483 comment 7130735295 by Muse 4, 2026-11-24 ~17:26 IST.
- **Board record:** new draft — no STR-063 record on main 6ea282d6 (verified first-hand via blob 78ae44ac, 18,870 lines, 810 tasks, this run). Record created in this work PR (CLAIMED → IN_REVIEW here), per the EARN-014 / STR-060 pattern.
- **Branch:** `muse4/task-str-063-trial-judgement-verification-2`, from main 6ea282d6.
- **Queue after claim:** STR-HLT-002 (blocked head) → STR-063 (working head) → VYR-057.
- **Related:** TASK-STR-EXP-007 (PR #1370 merged) — trial 3980 production verdict, run 1 of this series.

## Verdicts — all 8 trials since 3980 are FORWARD_TEST; none PROVEN

Trial 3980 (run 1) re-confirmed PROVEN, identical to EXP-007. Trials 3981–3988 each cleared the
second tier (expectancy > 0, PF ≥ 1.05, ≥ 200 trades, holdout present and positive) but none
cleared the full frozen bar — every one fails Bonferroni, six also fail the full PF bar and/or
the 4-of-5-folds bar. Per the frozen rule, demo forward evidence decides each of them.

| Trial | Ran (UTC) | Members (proven streams, pooled) | Trades | Expectancy | PF | Folds + | p vs Bonferroni bar | Verdict |
|---|---|---|---|---|---|---|---|---|
| 3981 | 2026-11-22 12:23 | engulfing + bollinger p20_sd2.0 | 1,180 | +1.4145% | 1.1603 | 4/5 | 0.01373 vs 1.26e-05 | FORWARD_TEST |
| 3982 | 2026-11-22 13:08 | engulfing + bollinger p50_sd2.0 | 968 | +2.4364% | 1.2858 | 4/5 | 0.000381 vs 1.26e-05 | FORWARD_TEST |
| 3983 | 2026-11-22 13:38 | engulfing + donchian n20_b24 | 1,275 | +1.1780% | 1.1340 | 3/5 | 0.02638 vs 1.26e-05 | FORWARD_TEST |
| 3984 | 2026-11-23 00:38 | engulfing + donchian n20_b26 | 948 | +1.5905% | 1.1699 | 3/5 | 0.02160 vs 1.26e-05 | FORWARD_TEST |
| 3985 | 2026-11-23 01:08 | engulfing + donchian n20_trail | 1,225 | +1.3106% | 1.1840 | 3/5 | 0.01015 vs 1.25e-05 | FORWARD_TEST |
| 3986 | 2026-11-23 01:38 | engulfing + donchian n55_b24 | 1,044 | +1.0825% | 1.1193 | 3/5 | 0.05619 vs 1.25e-05 | FORWARD_TEST |
| 3987 | 2026-11-23 02:53 | engulfing + donchian n55_b26 | 846 | +3.0053% | 1.3363 | 4/5 | 0.000188 vs 1.25e-05 | FORWARD_TEST |
| 3988 | 2026-11-24 03:00 | engulfing + donchian n55_trail | 983 | +1.2668% | 1.1665 | 3/5 | 0.02645 vs 1.25e-05 | FORWARD_TEST |

All members are `@crypto30/1d` streams, judged pooled, pre-declared, on RD-002 OOS folds W1–W5
(2024-07-01..2026-07-01). Full member names: `bar_patterns/engulfing@crypto30/1d` paired with
`bollinger_trend/p20_sd2.0`, `bollinger_trend/p50_sd2.0`, `donchian_turtle/n20_b24`,
`donchian_turtle/n20_b26`, `donchian_turtle/n20_trail`, `donchian_turtle/n55_b24`,
`donchian_turtle/n55_b26`, `donchian_turtle/n55_trail` respectively (trials 3981–3988 in order).

**Nearest to PROVEN:** 3982 and 3987 fail on Bonferroni alone — 3982 (expectancy +2.4364%,
PF 1.2858, 4/5 folds, p 3.81e-04) and 3987 (expectancy +3.0053%, PF 1.3363, 4/5 folds,
p 1.88e-04). The frozen bar does not move, so both stay FORWARD_TEST pending demo forward evidence.

**Pooled expectancy evidence (3981–3988):** 8 trials, mean expectancy **+1.6606%**
(min +1.0825% trial 3986, max +3.0053% trial 3987), **8,469 trades** in total. Every trial's
holdout is present and positive (281–429 holdout trades; holdout expectancy +0.8786% to
+2.8520%).

**Trial 3980 re-confirmation (run 1, unchanged):** PROVEN — `combination_cluster_champions`,
decl_0001_f030c1c110, ran 2026-11-22T11:58:43Z: expectancy +2.3175%, PF 1.2623, 2,208 trades,
4/5 positive folds, p 1.58e-06 < 1.26e-05, holdout 714 trades at +2.0568%.

## Per-trial frozen-bar checks (record vs independent recomputation)

Independently recomputed from the raw metrics this run: all 8 checks per trial, fold trade-count
sums, and positive-fold counts — **every record check matches, all 9 trials, 0 mismatches**.

| Trial | exp>0 | PF≥1.2 | PF≥1.05 | trades≥200 | 4/5 folds | Bonferroni p<0.05/N | holdout | holdout exp>0 | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 3980 | ✓ | ✓ | ✓ | ✓ | ✓ (4/5) | ✓ (1.58e-06) | ✓ 714 | ✓ +2.0568% | PROVEN |
| 3981 | ✓ | ✗ (1.1603) | ✓ | ✓ | ✓ (4/5) | ✗ (0.01373) | ✓ 400 | ✓ +1.3107% | FORWARD_TEST |
| 3982 | ✓ | ✓ (1.2858) | ✓ | ✓ | ✓ (4/5) | ✗ (0.000381) | ✓ 326 | ✓ +1.4405% | FORWARD_TEST |
| 3983 | ✓ | ✗ (1.1340) | ✓ | ✓ | ✗ (3/5) | ✗ (0.02638) | ✓ 429 | ✓ +1.4231% | FORWARD_TEST |
| 3984 | ✓ | ✗ (1.1699) | ✓ | ✓ | ✗ (3/5) | ✗ (0.02160) | ✓ 327 | ✓ +1.3527% | FORWARD_TEST |
| 3985 | ✓ | ✗ (1.1840) | ✓ | ✓ | ✗ (3/5) | ✗ (0.01015) | ✓ 427 | ✓ +0.9965% | FORWARD_TEST |
| 3986 | ✓ | ✗ (1.1193) | ✓ | ✓ | ✗ (3/5) | ✗ (0.05619) | ✓ 349 | ✓ +1.1570% | FORWARD_TEST |
| 3987 | ✓ | ✓ (1.3363) | ✓ | ✓ | ✓ (4/5) | ✗ (0.000188) | ✓ 281 | ✓ +2.8520% | FORWARD_TEST |
| 3988 | ✓ | ✗ (1.1665) | ✓ | ✓ | ✗ (3/5) | ✗ (0.02645) | ✓ 334 | ✓ +0.8786% | FORWARD_TEST |

Record reasons quoted verbatim per trial, e.g. 3982: "second tier cleared (expectancy +2.4364%,
PF 1.2858, 968 trades); full bar not met on: bonferroni — demo forward evidence decides it";
3987: "second tier cleared (expectancy +3.0053%, PF 1.3363, 846 trades); full bar not met on:
bonferroni — demo forward evidence decides it". Trial 3988 was scheduled by the
starvation_breaker; 3981–3987 by the load_gate (3980: starvation_breaker).

## Provenance — how this was verified

- **Live re-read this run** (2026-11-24 ~17:28–17:31 IST) from S1 via the bridge (`run_shell`,
  server 1, read-only): `Stratex/self_experiments_data/trial_counter.json` value **3988**
  (matches the coordinator's stated counter); `experiments.jsonl` **36 lines = 9 trials × 4
  records** (declaration + evaluation + admission + result each, verified by a full line census);
  `lessons.jsonl` 9 lines, one verdict record per trial (PROVEN 3980, FORWARD_TEST 3981–3988);
  `admissions.json` contains all of 3980–3988.
- **Frozen gate untouched:** S1 `Stratex/self_experiments/judge.py` sha256
  `ccdac186846050810482e4c61b480116c2c024db6962dc8daf0693c6e9ed7268` — byte-identical to the
  hash EXP-007 verified (FULL_BAR_PF 1.2, SECOND_TIER_PF 1.05, MIN_OOS_TRADES 200, 4/5 folds,
  Bonferroni 0.05/N). This task changes nothing in code.
- **No live change was made:** no order placed, no restart, no env change, no secret touched.
  Verification reads only, per the owner stop order (all server moves frozen). Stratex remains
  demo only; no real money.

## Caveats, stated plainly

- **S1 read; U1 record-level cross-check still owed.** The live daemon runs on Stratex-Server
  (U1); the S1 file is the sleeper's record through trial 3988 (ran 2026-11-24 03:00:27 UTC /
  08:30:27 IST, before the sleeper stopped ~13:41 IST). The counter agrees with the
  coordinator's live-side value (3988), but the individual U1 trial records have not been
  re-read — no U1 read path exists yet (the corrected read-route draft still awaits Surendra's
  decision, per M18's STR-049 re-probe). Same standing caveat as EXP-007.
- **Demo forward evidence owed for all 8 FORWARD_TEST trials.** `lessons.jsonl` holds only the
  verdict records, not forward-test outcomes. Running forward tests is a live action and stays
  held under the owner stop order; the forward leg is owed when the freeze lifts.
- **No trial after 3988** in the S1 file (MAX_ID 3988); the file tail is trial 3988's result
  record.

## States

- Implemented: YES — this evidence doc + board record, filed in the work PR.
- Tested: YES — live S1 re-probe this run + independent recomputation of every check (0 mismatches).
- Merged: NO — work PR open, awaiting Muse's review/merge.
- Deployed: N/A — evidence-only task; no code, no deployment.
- Production-verified: PARTIAL — S1 production records verified first-hand; U1 record-level
  cross-check and demo forward evidence for the 8 FORWARD_TEST trials are owed.

No env flips were made and none are proposed without coordinator clearance.
