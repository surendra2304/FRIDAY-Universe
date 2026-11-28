# TASK-STR-106 — Self-experiment judgement support run 3: trial counter + load-gate evidence

- **Task:** Stratex: self-experiment judgement support — verify trial counter 3980 if landed, else file load-gate evidence + smallest safe fix.
- **Owner:** Muse 14. **Claim:** hub #2045 comment 7231345893 (2026-11-28 ~06:30 IST), fresh claim from the pool (Stratex first in the priority order; VYR-098 → Muse 9 and FRG-038 → Muse 11 in WATCH248 §B).
- **Board verified:** AVAILABLE, owner null, branch null, pr null, blockers [], P1, on live main `98215372` (WATCH248 board v2).
- **Branch:** `muse14/task-str-106` from main `98215372` (remote branch verified at `98215372` before pushing; no content change since).
- **Method:** read-only live probes via the bridge (`run_shell`, standing clearance 7200564540) on Stratex-Server (server 4) and Oracle Server 1 (server 1). No env flip, no restart, no deploy, no server state touched. No safety check fired on any live read.
- **States:** implemented YES (evidence doc) / tested YES / merged NO / deployed N/A (no code changed; the loop is already deployed and running) / production-verified YES.

## Verdict

**TRIAL 3980 LANDED AND VERIFIED — PROVEN (STR-097 run 2). THE LOOP IS NOT STARVED.**

Trial 3980 was verified PROVEN in run 2 (STR-097). Since then the counter has advanced from **4000 to 4004** — **4 new trials (4001–4004)** in ~24 h, all FORWARD_TEST via the load gate; the last, trial 4004, landed **2026-11-28T00:57:43Z**, ~7 minutes before the first probe. **25 trials total (3980–4004): 2 PROVEN, 23 FORWARD_TEST**; the starvation breaker has fired twice (3980, 3988) and not since. The live loop is on **Stratex-Server**; the Oracle Server 1 copy is a frozen pre-migration ledger (trials 3980–3988, counter 3988, both services dead/failed). No fix is proposed: there is no starvation to fix.

## §1 — Which host is live

| | Stratex-Server (server 4) | Oracle Server 1 (server 1) |
|---|---|---|
| Hostname | stratex-server | friday-universe-vnic |
| CPUs / load at probe | 2 / 0.60, 0.47, 0.46 | n/a (frozen copy) |
| `Stratex.service` | active, PID 74530, since 2026-11-27 15:27:19 UTC | inactive (dead) |
| `Stratex-Daemon.service` | active, PID 74531, since 2026-11-27 15:27:19 UTC | **failed** |
| Live checkout | `3db55adf` (contains EXP-006 merge `0dd921b8`) | `bf3c76c9` (PR #2013 merge) |
| Counter | **4004**, updated 2026-11-28T00:57:43Z | 3988, updated 2026-11-24T03:00:27Z |
| `experiments.jsonl` | 100 rows, trials 3980–4004 | 36 rows, trials 3980–3988 |
| `STRATEX_SELF_EXPERIMENTS` | `on` (daemon environ) | n/a (daemon dead) |

Note: the S4 daemon incarnation changed since run 2 (was PIDs 13272/13273 since 2026-11-24 06:57:34 UTC) — see G9. The loop demonstrably works under the new incarnation (trials 4002–4004 judged after the restart).

## §2 — The counter and the ledger agree

- Counter file (`Stratex/self_experiments_data/trial_counter.json` on Stratex-Server): value **4004**, seed 3979, `updated_at` **2026-11-28T00:57:43.159907Z**, owner `stratex_self_experiments`.
- Ledger (`experiments.jsonl`): **100 rows** — 25 declaration + 25 evaluation + 25 admission + 25 result. Trial numbers **3980–4004, contiguous** (verified: sorted trial list == `range(3980, 4005)`).
- Counter **4004 == latest trial 4004**; counter `updated_at` == trial 4004's judgement second (result row ts 2026-11-28T00:57:43.162198Z — the counter increments ~2 ms before the result row, per `counter.py`'s increment-before-judgement).
- Admissions registry: **25 entries** (one per trial). `lessons.jsonl`: **25 rows**, one per trial; the last is trial 4004 (`decl_0025_208b50b5fa`, FORWARD_TEST, 2026-11-28T00:57:43.162961Z).
- Seed chain (from `counter.py`, unchanged): 3979 = 3,899 (programme counter at RD-020) + 4 (RD-021 floor reservation — trials 3,900–3,903 allocated but UNEXECUTED) + 76 (RD-025 executed trials 3,904–3,979). The strictly-executed total is 3,975; the counter stays at the conservative 3,979.

## §3 — Trials 4001–4004 (new since run 2)

All `combination_pair`, all via `load_gate`, all FORWARD_TEST. Members are all `bar_patterns/engulfing@crypto30/1d` + a second member.

| Trial | Result (UTC) | Verdict | Via | load1 | load5 | Expectancy | PF | Trades | +Folds |
|---|---|---|---|---|---|---|---|---|---|
| 4001 | 2026-11-27 07:44:01 | FORWARD_TEST | load_gate | 0.361 | 0.388 | +1.1746% | 1.1284 | 1257 | 2 |
| 4002 | 2026-11-27 15:27:36 | FORWARD_TEST | load_gate | 1.244 | 0.786 | +2.2210% | 1.2539 | 1280 | 4 |
| 4003 | 2026-11-27 16:12:40 | FORWARD_TEST | load_gate | 0.882 | 0.633 | +2.1624% | 1.2458 | 1034 | 2 |
| 4004 | 2026-11-28 00:57:43 | FORWARD_TEST | load_gate | 0.639 | 0.500 | +0.9917% | 1.1024 | 1236 | 4 |

- 4001: `engulfing` + `rsi_momentum/rsi7_60_40@crypto30/1d`, `decl_0022_4158a6402b`, admission `selfexp_combo_826da8754d61`. Full bar not met on: pf_gte_full_bar, folds_gte_4_of_5, bonferroni.
- 4002: `engulfing` + `shock_breakout/k1.0@crypto30/1d`, `decl_0023_ab8d5e9e2a`, admission `selfexp_combo_1f4ebf1ce881`. Full bar not met on: bonferroni only (see §4).
- 4003: `engulfing` + `shock_breakout/k1.5@crypto30/1d`, `decl_0024_ed0f08d8ff`, admission `selfexp_combo_50f8c3680223`. Full bar not met on: folds_gte_4_of_5, bonferroni.
- 4004: `engulfing` + `stoch_reversion/k14_raw@crypto30/1d`, `decl_0025_208b50b5fa`, admission `selfexp_combo_204d6a450ec2`. Full bar not met on: pf_gte_full_bar, bonferroni.

Totals since the loop armed: **25 trials, 2 PROVEN (3980, 3989), 23 FORWARD_TEST**; scheduling **starvation_breaker 2, load_gate 23**.

## §4 — Trial 4002, verified figure by figure (independent check)

Full stored metrics: trades 1280, wins 496, win rate 0.3875, expectancy +2.2210% (0.022209740605587468), PF 1.2539 (1.2539292655328096), gross profit 140.3827475084771 / gross loss 111.95427953332504; per-fold W1 390/+0.0281, W2 209/+0.0088, W3 230/+0.0645, W4 212/+0.0127, W5 239/−0.0078 (4/5 positive); holdout 442 trades, expectancy +0.020291539433198637; t 3.537072120741671, p_one_sided 0.00020229458422926395.

- **Arithmetic:** expectancy (140.3827475084771 − 111.95427953332504)/1280 = 0.022209740605587558 vs stored 0.022209740605587468 (differs at 1e-16 — float summation order, the same note as STR-097's trial 3980 check); PF exact; win rate 496/1280 = 0.3875 exact; per-fold trades sum 1280 ✓.
- **Bonferroni:** p 2.02e-04 vs threshold 0.05/4002 = 1.249375e-05 — p is above the threshold, so the bonferroni check is false, the only failed full-bar check; the other 7 checks are true.
- **Local `judge()` re-run** on the stored metrics at N=4002 (worktree at main `98215372`, frozen `judge.py`) reproduces the stored verdict **exactly**: verdict FORWARD_TEST, all 8 checks identical, reason string identical — "second tier cleared (expectancy +2.2210%, PF 1.2539, 1280 trades); full bar not met on: bonferroni — demo forward evidence decides it".
- **Arithmetic spot-check, trial 4004:** expectancy computed 0.009916941945463416 vs stored 0.00991694194546342 (1e-17); PF exact 1.1024393991437627; win rate 466/1236 = 0.37702265 vs stored 0.377023 (6 dp); per-fold trades sum 1236 ✓.

## §5 — Load-gate evidence (why there is no starvation to fix)

- **Stratex-Server now:** load 0.60/0.47/0.46 at probe — the normal gate (1.4 on 2 CPUs, `LOAD_GATE_FRACTION = 0.7` in `bounds.py`) is wide open, and all four new trials ran through it with load1 0.36–1.24, load5 0.39–0.79.
- **The breaker works in production:** it fired twice — trial 3980 (load1 4.29/load5 2.82) and trial 3988 (load1 6.35/load5 3.84) — and has not fired since; no trial has needed it since run 2.
- **Daily cap (4/day):** Nov 27 UTC saw 3 trials (4001–4003), Nov 28 UTC 1 trial so far (4004) — not binding.
- **Cadence:** 4 trials in ~24 h (4000 at 2026-11-27T00:58:07Z → 4004 at 2026-11-28T00:57:43Z); the loop polls continuously and the last trial landed ~7 minutes before the first probe.
- **Deployed code:** all six `Stratex/self_experiments/` files on Stratex-Server are byte-identical to main `98215372` — `counter.py bd74f103…`, `loop.py c22615a0…`, `daemon_wiring.py 391aac8f…`, `judge.py ccdac186…` (frozen judge hash, matches the EXP-006 report), `bounds.py c13c3c40…`, `ledger.py 574d8098…`. No diff in `Stratex/self_experiments/` between `a3c3140e` (STR-097 base) and `98215372`. S4 checkout HEAD `3db55adf` (unchanged since run 2).
- **Smallest safe fix proposal: none.** No code change, no env flip, no restart is proposed or needed. The only follow-ups are the carried G2/G4 and the new gaps below.

## §6 — Tests (local, this VM, worktree at main `98215372`)

- `Stratex/tests/test_str_exp_006_starvation_breaker.py`: **19 passed** (pytest 9.2.0, 0.71s).
- `Stratex/tests/test_exp001_self_experiments.py` + `test_exp004_daemon_wiring.py`: **42 passed, 6 failed** — the 6 failures are the pre-existing environment gaps already recorded in STR-097 (`ModuleNotFoundError: No module named 'pandas'` from `strategies/strategy_registry.py`), the same 6 test names. No code changed in this task, so no new tests were added.
- Local `judge()` re-run (trial 4002): verdict + checks + reason reproduced exactly (see §4).

## §7 — Gaps / follow-ups

- **G2 — OPEN (carried from EXP-006 via STR-097):** a PROVEN verdict admits to the FORWARD_TEST lane (per EXP-001 design); promotion to VALIDATED travels the Universe change path, never the loop. Still **two** PROVEN admissions await that follow-up: `selfexp_combo_37358617fe8a` (trial 3980) and `selfexp_combo_7277cd6bf45e` (trial 3989). No new PROVEN in run 3. Coordinator to scope.
- **G4 — OPEN (carried from EXP-006):** greedy time box under nice 19 — no greedy trial has run yet (all 25 trials are combination proposals); the first greedy proposal still deserves a watch.
- **G5 — OPEN (carried):** the S1 daemon restart onto the merged EXP-006 code is not directly evidenced (S1 journal rotated). Unchanged; S1 is frozen and no longer live, so this is a record gap only.
- **G6 — OPEN (carried):** trial 3989's exact host process is still unidentified. Unchanged.
- **G7 — OPEN (carried from STR-097, not re-probed this run):** loop cycle logs do not reach `bot.log` on either host. Cycle-level log evidence for trials after 3980/3988 therefore rests on the ledger rows and their recorded load fields, not on log lines.
- **G9 — NEW:** the S4 daemon incarnation changed between run 2 and run 3. `Stratex.service` + `Stratex-Daemon.service` stopped and restarted **2026-11-27 15:27:19 UTC** (new PIDs 74530/74531, NRestarts=0). The journal shows a deliberate stop — systemd "Stopping Stratex-Daemon.service" at 15:27:04, then "Started" for both units at 15:27:19 — **not a crash**; no deploy (checkout unchanged at `3db55adf`); the initiator is not named in the journal lines pulled. The stop took 15 s and needed SIGKILL ("State 'stop-sigterm' timed out. Killing." — the daemon does not exit promptly on SIGTERM). Trial 4002 was judged 17 s after the restart (15:27:36Z); trials 4002–4004 all ran under the new incarnation, so the loop demonstrably works under it. No trial was lost: the counter advanced monotonically 4000 → 4004 and the ledger is contiguous.
- **G10 — NEW, observation:** at the restart, the new `Stratex.service` logged CRITICAL "SECURITY_SECRET_KEY is NOT set. Generated an ephemeral per-process audit secret: control-audit signatures cannot be verified across restarts or processes." Standing config warning (appears at start); no action taken here (no env flips without coordinator clearance). In the same journal window the advisory scheduler's AI-Universe consult repeatedly fails (connection refused to 127.0.0.1:8001 — Inference is not on Stratex-Server); the scheduler retains last validated parameters. Neither affects the self-experiment loop.

## §8 — Probe record

- Bridge `run_shell` probes (read-only): S4 counter + data dir 2026-11-28 ~01:05 UTC (~06:35 IST); S4 ledger detail + daemon + env ~01:08 UTC; S4 trial metrics + code hashes + restart journal ~01:12 UTC; S1 frozen-copy check ~01:08 UTC. Raw outputs: `~/workspace/agents/muse14/task-str-106/str106_probe_s4.txt`, `str106_probe_s4b.txt`, `str106_probe_s4c.txt`, `str106_probe_s1.txt`.
- No env flip, no restart, no deploy, no server state touched. One bridge note: the daemon environ read redacted `STRATEX_API_KEY` as `<redacted>` — no key value was read, printed, logged, or stored by this run.
- No board hunk in this PR — board flips are coordinator-only per WATCH182 §3. Paired verifier: none named yet — Muse to name one.

— Muse 14
