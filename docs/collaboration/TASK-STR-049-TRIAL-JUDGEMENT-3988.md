# TASK-STR-049 — Trial judgement verification past counter 3980 (Muse 13)

- **Assignment:** coordinator watch054 (hub #1483 comment 7142399844, 01:09 IST 2026-11-25), nudged in watch055 (7142822375).
- **Claim:** hub #1483 comment 7143153454, 2026-11-25 ~01:40 IST. Branch `muse13/task-str-049` from main `ce3c817f`. Board flip rides in this work PR (owner order 7143628341 rule 4 — coordinator board PR abolished).
- **Board verified first-hand:** TASK-STR-049 AVAILABLE, owner null, on main `ce3c817f` (board blob `383d017d`, 913 tasks, 0 dup ids) and unchanged on main `8fc427a7` (board blob `39fa817d`). No prior claim, branch or PR.
- **Correction (this run, 2026-11-25 ~02:40–02:55 IST):** coordinator watch058 (hub #1483 comment 7144369853) HELD PR #1717 — the first probe verified the WRONG server. The live trial counter sits on **Stratex-Server (server 4)**, not the frozen Oracle Server 1 copy. Everything below under "Correction probe" is from server 4, first-hand via bridge `run_shell`. The S1 trial-3988 numbers in the original section stand (they agree exactly with server 4's copy of trial 3988) but the headline, latest-trial claim and daemon-risk assessment in that section are superseded by the correction. M2 is the assigned verifier for STR-049.

## Verdict (corrected): TRIAL 3991 VERIFIED — LATEST; TRIAL 3989 PROVEN (FULL BAR CLEARED)

- **Live counter, Stratex-Server** (`/opt/friday_universe/Stratex/self_experiments_data/trial_counter.json`, 735 bytes, md5 `2e143ec2433c25fb2be36305c0f306a8`, mtime 2026-11-24 08:27 UTC): **value 3991**, seed 3979, `updated_at 2026-11-24T08:27:43.522772+00:00`.
- **Latest judgement on file is trial 3991** (`experiments.jsonl`, 47,833 bytes, md5 `16f57b2fd83bac9423cf9af58d0652a6`; `admissions.json` 31,156 bytes, md5 `b107f7a85b022ca528a556be405e5be3`; `lessons.jsonl` 19,289 bytes, md5 `8bb990a0a0d7e0bf0be6fcae282ff041`). `experiments.jsonl` covers trials 3980–3991 (48 lines: 12 declarations + 36 evaluation/admission/result records). Counter value == latest trial number; counter `updated_at` == trial 3991 judgement second (08:27:43Z). **The counter and the judgement stream agree.**
- **Trial 3989 is PROVEN** — the first full frozen-bar clearance in this window (expectancy +0.9700%, PF 1.2337, 4,208 trades, 5/5 positive folds, p 4.02e-07). Trials 3990 and 3991 are FORWARD_TEST (second tier).
- **Cadence on the live box:** trials 3989–3991 ran 2026-11-24 at 05:24:45Z, 07:42:42Z and 08:27:43Z — three trials in ~3 h after the move to Stratex-Server, load-gate scheduled. At correction-probe time (~02:45 IST Nov 25 / 21:15Z Nov 24) the last trial is ~13 h old; there is no fixed 24 h cadence on the live box, so no starvation call is made from this run — the next verification watches for trial 3992.

## Trial 3989 judgement — PROVEN (filed numbers)

Combination pair, `declaration_id decl_0010_b111752515`, admission key `selfexp_combo_7277cd6bf45e`, scheduling `load_gate` (load1 0.38, load5 0.08 at judgement time).

- **Members:** `bar_patterns/engulfing@crypto30/1d` + `dow_effect/reversal@crypto30/1d`, equal-standing union of judged OOS trade streams, RD-002 OOS folds W1–W5 (2024-07-01..2026-07-01).
- **Trades: 4,208** (wins 2,124, win rate 50.48%).
- **Expectancy: +0.0097003 = +0.9700% per trade.**
- **Profit factor: 1.2337** (gross profit 215.4703, gross loss 174.6514).
- **Per-fold expectancy:** W1 +0.0121 (958 trades), W2 +0.0151 (843), W3 +0.0156 (916), W4 +0.0002 (890), W5 +0.0034 (601). Positive folds 5/5.
- **Holdout:** 1,402 untouched trades, expectancy +0.00849. t-stat 4.9346, one-sided p 4.02e-07.
- **Verdict: PROVEN** — all eight checks true, including `pf_gte_full_bar` and `bonferroni` — "full frozen bar cleared at N=3989: expectancy +0.9700%, PF 1.2337, 4208 trades, 5/5 positive folds, p 4.02e-07 < 1.25e-05, holdout expectancy +0.8493%". Admitted to the PROVEN lane; do not re-propose this member set.

## Trial 3990 judgement — FORWARD_TEST (filed numbers)

Combination pair, `declaration_id decl_0011_6677862ad3`, admission key `selfexp_combo_ad42b763e60f`, scheduling `load_gate` (load1 0.39, load5 0.40).

- **Members:** `bar_patterns/engulfing@crypto30/1d` + `ha_trend/one_candle@crypto30/1d`.
- **Trades: 1,425** (wins 514, win rate 36.07%).
- **Expectancy: +0.0100053 = +1.0005% per trade.**
- **Profit factor: 1.1087** (gross profit 145.4044, gross loss 131.1468).
- **Per-fold expectancy:** W1 +0.0148 (449 trades), W2 −0.0041 (210), W3 +0.0595 (263), W4 −0.0111 (250), W5 −0.0173 (253). Positive folds 2/5.
- **Holdout:** 477 untouched trades, expectancy +0.00648. t-stat 1.6928, one-sided p 0.0452.
- **Verdict: FORWARD_TEST** — second tier cleared (expectancy +1.0005%, PF 1.1087, 1,425 trades); full bar NOT met on `pf_gte_full_bar`, `folds_gte_4_of_5`, `bonferroni` — "demo forward evidence decides it".

## Trial 3991 judgement — FORWARD_TEST (filed numbers, latest)

Combination pair, `declaration_id decl_0012_4e8e218239`, admission key `selfexp_combo_7280040bc8ad`, scheduling `load_gate` (load1 0.37, load5 0.39).

- **Members:** `bar_patterns/engulfing@crypto30/1d` + `ha_trend/two_candle@crypto30/1d`.
- **Trades: 1,323** (wins 493, win rate 37.26%).
- **Expectancy: +0.0163627 = +1.6363% per trade.**
- **Profit factor: 1.1822** (gross profit 140.4911, gross loss 118.8433).
- **Per-fold expectancy:** W1 +0.0206 (399 trades), W2 +0.0053 (202), W3 +0.0605 (257), W4 +0.0064 (232), W5 −0.0200 (233). Positive folds 4/5.
- **Holdout:** 435 untouched trades, expectancy +0.01605. t-stat 2.6357, one-sided p 0.00420.
- **Verdict: FORWARD_TEST** — second tier cleared (expectancy +1.6363%, PF 1.1822, 1,323 trades); full bar NOT met on `pf_gte_full_bar`, `bonferroni` — "demo forward evidence decides it". Admitted to the FORWARD_TEST lane.

### Cross-checks, correction probe (first-hand, server 4)

1. **Arithmetic reproduces from each record's own gross figures:**
   - 3989: (215.47025794344296 − 174.65135662077375) / 4208 = 0.0097003 (matches expectancy); 215.47025794344296 / 174.65135662077375 = 1.23372 (matches PF).
   - 3990: (145.40442358201315 − 131.1468273338514) / 1425 = 0.0100053 (matches); 145.40442358201315 / 131.1468273338514 = 1.10871 (matches).
   - 3991: (140.49108527820323 − 118.84328542270227) / 1323 = 0.0163627 (matches); 140.49108527820323 / 118.84328542270227 = 1.18215 (matches).
2. **Three files agree exactly:** expectancy and PF for 3989–3991 appear identically in `experiments.jsonl` (evaluation + result records), in `admissions.json` entries keyed by admission key (`selfexp_combo_7277cd6bf45e` PROVEN, `selfexp_combo_ad42b763e60f` FORWARD_TEST, `selfexp_combo_7280040bc8ad` FORWARD_TEST, each reason line naming the verdict + member pair), and in the `lessons.jsonl` entries (3989 PROVEN 05:24:46Z, 3990 FORWARD_TEST 07:42:43Z, 3991 FORWARD_TEST 08:27:43Z).
3. **Trial 3988 agrees across servers:** server 4's `experiments.jsonl` carries trial 3988 with expectancy `0.012668115899715216`, PF `1.1665497023924283`, 983 trades — identical to the S1 copy verified in the original probe. The S1 numbers were right; the S1 copy was simply frozen at 3988.

## Daemon-risk assessment — CORRECTED (original flag withdrawn)

- **`Stratex-Daemon.service` on Stratex-Server is UP:** verified first-hand this run — ActiveState `active`, SubState `running`, ExecMainStatus 0, NRestarts 0, active since 2026-11-24 06:57:34 UTC, Main PID 13273. Journal tail 21:13:06 UTC Nov 24 shows the daemon scanning live (strategy NO_SIGNAL/SIGNAL lines across symbols, minutes before this probe). **The live daemon is running; no restart is needed anywhere.**
- **The S1 daemon failure is the sleeping backup copy:** `Stratex-Daemon.service` on Oracle Server 1 FAILED (13:33 start / 13:42 SIGKILL Nov 24) — no live impact, per watch058. The 13:33 start / 13:42 SIGKILL on the sleeping box is unexplained (no actor named). The original section's "next trial at risk" assessment does NOT hold for the live system and is withdrawn.
- **Why the first probe went wrong:** the board evidence at claim time said the live counter had moved to Oracle S1 (counter 3987 at the move); the counter has since moved on to Stratex-Server, and S1's copy froze at 3988. The acceptance asks for the judgement "from the live counter" — that is server 4.

## Original probe (superseded headline, retained for the record)

- **Probe run:** 2026-11-25 ~01:43–01:50 IST, bridge `run_shell` server 1 (Oracle Server 1, host `friday-universe-vnic`), cwd `/opt/friday_universe`. Bridge flaked empty on several calls (known SSE behaviour); every result below is from a call that returned output, retried until it did.
- **Route note:** U1 read path is gone (AWS U1/U2 deleted 2026-11-23 ~18:09 IST, per board note). No env flips, no deploys, no writes to any server.

### Trial 3988 judgement (S1 copy — numbers agree with server 4, headline superseded)

- **Live counter (S1 copy)** (`/opt/friday_universe/Stratex/self_experiments_data/trial_counter.json`, 735 bytes, md5 `a7eba47b68db15b54e2482f851e6c205`, mtime 2026-11-24 08:30:27 IST): **value 3988**, seed 3979, `updated_at 2026-11-24T03:00:27.109141+00:00`.
- **S1 files:** `experiments.jsonl` 36,079 bytes, md5 `fc267aa799bbb19894b4239f0dbd5ec5`; `admissions.json` md5 `dc3c1ab6dbe60e6cf69d41795419ab15`; `lessons.jsonl` md5 `3236d6a19cab431669f6461819833476`. S1 `experiments.jsonl` covers trials 3980–3988.
- Combination pair, `declaration_id decl_0009_ae35c179ef`, admission key `selfexp_combo_5399d0ee357a`, scheduling `starvation_breaker` (load1 6.35, load5 3.84 at judgement time). Members: `bar_patterns/engulfing@crypto30/1d` + `donchian_turtle/n55_trail@crypto30/1d`.
- **Trades: 983** (wins 369, win rate 37.54%). **Expectancy: +0.0126681 = +1.2668% per trade. Profit factor: 1.1665** (gross profit 87.2218, gross loss 74.7690).
- **Per-fold expectancy:** W1 +0.0198 (285 trades), W2 −0.0216 (189), W3 +0.0492 (195), W4 +0.0345 (162), W5 −0.0281 (152). Positive folds 3/5.
- **Holdout:** 334 untouched trades, expectancy +0.00879. t-stat 1.9357, one-sided p 0.0265.
- **Verdict: FORWARD_TEST** — second tier cleared; full bar NOT met on `pf_gte_full_bar`, `folds_gte_4_of_5`, `bonferroni`. Admitted to the FORWARD_TEST lane; do not re-propose this member set (per lessons.jsonl entry 2026-11-24T03:03:17Z).
- **Cross-checks:** arithmetic reproduces ((87.22177733047805 − 74.76901940105812) / 983 = 0.0126681; 87.22177733047805 / 74.76901940105812 = 1.16655); expectancy `0.012668115899715216` and PF `1.1665497023924283` appear identically in S1 `experiments.jsonl` and `lessons.jsonl`; trial 3987 (previous): expectancy +3.0053%, PF 1.3363, 846 trades, 4/5 positive folds, p 0.000188 — also FORWARD_TEST.
- **S1 daemon flag (withdrawn — see correction above):** S1 `Stratex-Daemon.service` failed 13:42:26 IST Nov 24 (SIGKILL after stop-sigterm timeout, NRestarts=0); `daemon_heartbeat.json` stale ~12 h, pid 3578584 gone; no Stratex python process on S1; box idle. That is the sleeping backup copy — no live impact.

## Scope kept

- Read-only probes only (bridge `run_shell` reads, `systemctl show`, `journalctl`, file md5s). No file writes on any server, no service restarts, no env flips.
- This run verified the judgements from the live counter as the acceptance asks. It did NOT re-run any backtest or re-derive the OOS trade streams — the numbers are verified against the live record (counter + three agreeing files + arithmetic), which is what the task's acceptance defines.

## Files

- `~/workspace/muse13/str049/TASK-STR-049-TRIAL-JUDGEMENT-3988.md` (this file)
- Repo copy: `docs/collaboration/TASK-STR-049-TRIAL-JUDGEMENT-3988.md` (work PR #1717, corrected in this run)
