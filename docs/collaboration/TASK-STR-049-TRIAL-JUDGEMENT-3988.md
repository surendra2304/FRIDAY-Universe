# TASK-STR-049 — Trial judgement verification past counter 3980 (Muse 13)

- **Assignment:** coordinator watch054 (hub #1483 comment 7142399844, 01:09 IST 2026-11-25), nudged in watch055 (7142822375).
- **Claim:** hub #1483 comment 7143153454, 2026-11-25 ~01:40 IST. Branch `muse13/task-str-049` from main `ce3c817f` (verified via API re-read). Board flip rides in the consolidated board PR per watch054.
- **Board verified first-hand:** TASK-STR-049 AVAILABLE, owner null, on main `ce3c817f` (board blob `383d017d`, 913 tasks, 0 dup ids). No prior claim, branch or PR.
- **Probe run:** 2026-11-25 ~01:43–01:50 IST, bridge `run_shell` server 1 (Oracle Server 1, host `friday-universe-vnic`), cwd `/opt/friday_universe`. Bridge flaked empty on several calls (known SSE behaviour); every result below is from a call that returned output, retried until it did.
- **Route note:** U1 read path is gone (AWS U1/U2 deleted 2026-11-23 ~18:09 IST, per board note). Live counter now on S1, read via the bridge as directed. No env flips, no deploys, no writes to any server.

## Verdict: TRIAL 3988 VERIFIED

- **Live counter** (`/opt/friday_universe/Stratex/self_experiments_data/trial_counter.json`, 735 bytes, md5 `a7eba47b68db15b54e2482f851e6c205`, mtime 2026-11-24 08:30:27 IST): **value 3988**, seed 3979, `updated_at 2026-11-24T03:00:27.109141+00:00`.
- **Latest judgement on file is trial 3988** (`experiments.jsonl`, 36,079 bytes, md5 `fc267aa799bbb19894b4239f0dbd5ec5`; `admissions.json` md5 `dc3c1ab6dbe60e6cf69d41795419ab15`; `lessons.jsonl` md5 `3236d6a19cab431669f6461819833476`). `experiments.jsonl` covers trials 3980–3988; the last three records are the 3988 declaration (03:00:27.102883Z), evaluation (03:00:27.111261Z), admission + result (03:00:27.1137–1138Z). Counter value == latest trial number; counter `updated_at` == trial 3988 judgement second. **The counter and the judgement stream agree.**
- **Trial 3987** ran 2026-11-23T02:53:16Z; **trial 3988** ran 2026-11-24T03:00:27Z — daily cadence, ~24 h apart. The loop has NOT missed a slot yet: at check time (~01:45 IST Nov 25) the last trial is ~17 h old and the next is due ~03:00Z Nov 25 (~7 h away).

## Trial 3988 judgement (filed numbers)

Combination pair, `declaration_id decl_0009_ae35c179ef`, admission key `selfexp_combo_5399d0ee357a`, scheduling `starvation_breaker` (load1 6.35, load5 3.84 at judgement time).

- **Members:** `bar_patterns/engulfing@crypto30/1d` + `donchian_turtle/n55_trail@crypto30/1d`, equal-standing union of judged OOS trade streams, RD-002 OOS folds W1–W5 (2024-07-01..2026-07-01).
- **Trades: 983** (wins 369, win rate 37.54%).
- **Expectancy: +0.0126681 = +1.2668% per trade.**
- **Profit factor: 1.1665** (gross profit 87.2218, gross loss 74.7690).
- **Per-fold expectancy:** W1 +0.0198 (285 trades), W2 −0.0216 (189), W3 +0.0492 (195), W4 +0.0345 (162), W5 −0.0281 (152). Positive folds 3/5.
- **Holdout:** 334 untouched trades, expectancy +0.00879. t-stat 1.9357, one-sided p 0.0265.
- **Verdict: FORWARD_TEST** — second tier cleared (expectancy +1.2668%, PF 1.1665, 983 trades); full bar NOT met on `pf_gte_full_bar`, `folds_gte_4_of_5`, `bonferroni` — "demo forward evidence decides it". Admitted to the FORWARD_TEST lane; do not re-propose this member set (per lessons.jsonl entry 2026-11-24T03:03:17Z).

### Cross-checks (first-hand)

1. **Arithmetic reproduces from the record's own gross figures:** (87.22177733047805 − 74.76901940105812) / 983 = 0.0126681 (matches expectancy); 87.22177733047805 / 74.76901940105812 = 1.16655 (matches PF).
2. **Three files agree exactly:** expectancy `0.012668115899715216` and PF `1.1665497023924283` appear identically in `experiments.jsonl` (evaluation + result records) and in the `lessons.jsonl` trial-3988 entry metadata (`trial 3988, pf 1.1665497023924283, expectancy 0.012668115899715216, trades 983`).
3. **Trial 3987 (previous) for scale:** expectancy +3.0053%, PF 1.3363, 846 trades, 4/5 positive folds, p 0.000188 — also FORWARD_TEST. Trial 3988 is weaker than 3987 on every headline number but still clears the second tier.

## Flag: S1 Stratex daemon is DOWN — next trial at risk (no restart taken)

- `Stratex-Daemon.service` on S1: **failed**, Result=`timeout`, ExecMainStatus=9 (SIGKILL). Active 2026-11-24 13:33:05 IST → inactive 13:42:26 IST. Journal: the daemon was scanning normally (strategy NO_SIGNAL lines at 13:42:26), then "State 'stop-sigterm' timed out. Killing." — SIGKILL to pid 3578584 and children. `NRestarts=0` — systemd did not restart it. `Stratex.service` is inactive/dead (last active 13:32:40 IST Nov 24).
- `daemon_heartbeat.json` (state/) still says RUNNING, pid 3578584, last update 2026-11-24T08:12:21Z — **stale ~12 h at check time, and pid 3578584 does not exist** (`ps -p` empty). No Stratex/advisory python process is running on S1; load average 0.00/0.04/0.07 (box idle). The heartbeat file is not a live signal.
- **Why this matters for the trial loop:** there is no separate trial/experiment systemd service or timer on S1 (only `friday-self-heal.timer`, daily 07:30 IST, unrelated). The loop lives in `Stratex/self_experiments/loop.py`, and `tests/test_exp004_daemon_wiring.py` names it daemon-wired. If the runner lives in the daemon, the next trial (~03:00Z Nov 25) will not run while the daemon is down. Whether the stop was deliberate (a stop was issued — SIGTERM precedes the kill) is NOT established from the journal; no actor is named. **No restart attempted:** a daemon restart is a live-server move and needs Muse's clearance on the hub; the owner stop order is still in force (watch055). This is filed as a flag for the coordinator, not fixed by this run.
- **Starvation assessment:** the loop is NOT starved at check time (last trial 17 h ago on a ~24 h cadence; next slot not yet missed). If trial 3989 does not land by ~03:00Z Nov 25, the loop is starved and the load-gate evidence + smallest safe fix proposal are owed — that check belongs to the next STR-049 verification or the coordinator's next watch.

## Scope kept

- Read-only probes only (bridge `run_shell` reads, `systemctl show`, `journalctl`, file md5s). No file writes on any server, no service restarts, no env flips.
- This run verified the judgement from the live counter as the acceptance asks. It did NOT re-run the backtest or re-derive the OOS trade streams — the numbers are verified against the live record (counter + three agreeing files + arithmetic), which is what the task's acceptance defines.

## Files

- `~/workspace/muse13/str049/TASK-STR-049-TRIAL-JUDGEMENT-3988.md` (this file)
- Repo copy: `docs/collaboration/TASK-STR-049-TRIAL-JUDGEMENT-3988.md` (work PR to follow)
