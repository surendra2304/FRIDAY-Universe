# TASK-STR-097 — Self-experiment judgement support run 2: trial counter + load-gate evidence

- **Task:** Stratex: self-experiment judgement support run 2 — trial counter + load-gate evidence.
- **Owner:** Muse 4. **Claim:** hub #2045 comment 7208154972 (2026-11-27 ~07:54 IST).
- **Board verified:** AVAILABLE, owner muse_4, branch null, pr null, on live main `5fd32fdf`.
- **Branch:** `muse4/task-str-097-self-experiment-judgement-run2` from main `a3c3140e` (remote branch verified at `a3c3140e` before pushing; no content change since).
- **Method:** read-only live probes via the bridge (`run_shell`, retry wrapper) on Oracle Server 1 (server 1) and Stratex-Server (server 4). No env flip, no restart, no deploy, no server state touched. One dry-run re-derivation on Stratex-Server wrote only to `/tmp/muse4-str097-dryrun` (temp data dir, production store read-only, stub lesson writer, no Memora calls). No safety check fired on any live read.
- **States:** implemented YES (evidence doc) / tested YES / merged NO / deployed N/A (no code changed; the loop is already deployed and running) / production-verified YES.

## Verdict

**TRIAL 3980 LANDED AND VERIFIED — PROVEN. THE LOOP IS NOT STARVED.**

Production trial 3980 ran **2026-11-22T11:58:43Z** via the **starvation breaker** (load1 4.294, load5 2.821 — gate 1.4 blocked, ceiling 4.0 open) and cleared the full frozen bar: expectancy **+2.3175%**, PF **1.2623**, 2208 trades, 4/5 positive folds, p **1.58e-06** < 1.26e-05, holdout expectancy +2.0568%. Every figure was verified independently: a fresh dry-run re-derivation from the live production store reproduces all 16 metric fields bit-for-bit with the same members, verdict and admission key; local arithmetic and a local `judge()` re-run confirm the PROVEN verdict. The counter has since advanced to **4000** — **21 trials (3980–4000)** have run, **2 PROVEN, 19 FORWARD_TEST**, the breaker firing twice in production. The live loop is on **Stratex-Server**; the Oracle Server 1 copy is a frozen pre-migration ledger (trials 3980–3988, counter 3988, both services dead/failed). No fix is proposed: there is no starvation to fix.

## §1 — Which host is live

| | Stratex-Server (server 4) | Oracle Server 1 (server 1) |
|---|---|---|
| Hostname | stratex-server | friday-universe-vnic |
| CPUs / load at probe | 2 / 0.79, 0.63, 0.57 | 2 / 0.09, 0.14, 0.27 |
| `Stratex.service` | active, PID 13272, since 2026-11-24 06:57:34 UTC (`dashboard.py`) | inactive (dead) since 2026-11-24 13:42:11 IST |
| `Stratex-Daemon.service` | active, PID 13273, since 2026-11-24 06:57:34 UTC (`run_daemon.py`, 51.8% CPU) | **failed** (Result=timeout) since 2026-11-24 13:42:26 IST; MainPID 3578584 killed (SIGKILL) |
| Live checkout | `3db55adf` (contains EXP-006 merge `0dd921b8`) | `bf3c76c9` (PR #2013 merge) |
| Counter | **4000**, updated 2026-11-27T00:58:07Z | 3988, updated 2026-11-24T03:00:27Z |
| `experiments.jsonl` | 84 rows, trials 3980–4000 | 36 rows, trials 3980–3988 |
| Loop threads | 2 threads at nice 19 (TIDs 13458, 13459) — the loop thread + its `asyncio.to_thread` cycle worker, which inherits the nice value; expected, not a double-start | none (no daemon) |
| `STRATEX_SELF_EXPERIMENTS` | `on` (daemon environ) | n/a (daemon dead) |

Lineage: S1's 36-row ledger is **byte-identical** to the first 36 rows of S4's ledger (sha256 `5162ec27…e6e`, both hosts). S4's ledger is the continuation (trials 3989–4000 appended). S4 data dir birth 2026-11-24 04:50:53Z; `experiments.jsonl` birth 04:51:13Z; stream store birth 04:51:00Z (store itself dated 2026-11-20).

## §2 — Trial 3980, verified figure by figure

Declaration `decl_0001_f030c1c110`, `combination_cluster_champions`, proposal hash `f030c1c1101b73c51858570a37d0d685fa3ac517287f1dce5a98add686e3cd21`. Timestamps (UTC): declaration 2026-11-22T11:58:43.312680Z, evaluation .399533Z, admission .400343Z, result .400493Z.

Members (identical in the dry-run, the S1 ledger and the S4 ledger): `vol_adaptive_trend/ema12_26_nogate`, `shock_breakout/k1.5`, `rsi_momentum/rsi14_55_45`, `ha_trend/two_candle` @ `crypto30/1d`.

| Figure | Production row | Independent check |
|---|---|---|
| Trades / wins | 2208 / 848 | dry-run re-derivation: identical |
| Win rate | 0.384058 | 848/2208 = 0.38405797… (stored rounded to 6 dp) |
| Expectancy | +2.3175% (0.02317501791312647) | (246.2694131339819 − 195.09897358179884)/2208 = 0.02317501791312639 (float summation order; differs at 1e-16) |
| PF | 1.2623 (1.262279388828916) | 246.2694131339819/195.09897358179884 = 1.262279388828916, exact |
| Gross profit / loss | 246.2694131339819 / 195.09897358179884 | dry-run: identical |
| Per-fold trades | W1 677, W2 323, W3 408, W4 387, W5 413 | sum = 2208 ✓ |
| Per-fold expectancy | W1 +0.02443805826233083, W2 +0.009982626208547393, W3 +0.07924518344640571, W4 −0.016523180059494498, W5 +0.013229834576550387 | dry-run: identical |
| Positive folds | 4/5 | W4 negative, rest positive ✓ |
| Holdout | 714 trades, +0.020567511398538043 | dry-run: identical |
| t-stat / p | 4.660575035428736 / 1.5766358863717088e-06 | Bonferroni 0.05/3980 = 1.25628e-05; p < threshold ✓ |
| Verdict | **PROVEN**, all 8 checks true | local `judge()` on the stored metrics at N=3980 → PROVEN, all 8 checks true, identical reason string: "full frozen bar cleared at N=3980: expectancy +2.3175%, PF 1.2623, 2208 trades, 4/5 positive folds, p 1.58e-06 < 1.26e-05, holdout expectancy +2.0568%" |
| Scheduling | `starvation_breaker`, load1 4.2939453125, load5 2.8212890625 | gate 1.4 blocked, ceiling 4.0 open — first production breaker firing |
| Admission | `selfexp_combo_37358617fe8a` | present in `admissions.json` (grep count 1); dry-run reproduces the same key |
| Lesson | banked 2026-11-22T12:01:03Z (`lessons.jsonl`) | row present, verdict PROVEN |

**Dry-run re-derivation (Stratex-Server, 2026-11-27 ~08:15 IST):** fresh temp data dir seeded at counter 3979, production `stream_store` (65 streams, hash-verified on load), deployed code (`/opt/friday_universe`, checkout `3db55adf`), stub lesson writer, idle work probe. Report: `ran via starvation_breaker` (dry-run load1 3.114, load5 2.813), trial 3980, counter after 3980. All 16 metric fields MATCH bit-for-bit; members, verdict PROVEN and admission key identical. Production untouched (temp dir only).

**Deployed code check:** all six `Stratex/self_experiments/` files byte-identical to main `a3c3140e` on **both** hosts — `loop.py c22615a0…`, `daemon_wiring.py 391aac8f…`, `judge.py ccdac18684605081…` (frozen judge hash, matches the EXP-006 report), `bounds.py c13c3c40…`, `ledger.py 574d8098…`, `counter.py bd74f103…`. `git merge-base --is-ancestor 0dd921b8 3db55adf` confirms the S4 checkout contains the EXP-006 merge.

Timeline note: EXP-006 merged 2026-11-22 17:26:28 IST (11:56:28Z); trial 3980 landed 11:58:43Z — 2m 15s later (see G5).

## §3 — The full run since: trials 3980–4000

21 trials, 84 ledger rows, counter 4000, last trial 2026-11-27T00:58:07Z (trial 4000). Verdicts: **PROVEN 2, FORWARD_TEST 19**. Scheduling: **starvation_breaker 2, load_gate 19**. Lessons: 21 rows, one per trial. Admissions registry: 21 entries.

| Trial | Result (UTC) | Verdict | Via | load1 | load5 | Expectancy | PF | Trades | +Folds |
|---|---|---|---|---|---|---|---|---|---|
| 3980 | 2026-11-22 11:58:43 | PROVEN | starvation_breaker | 4.294 | 2.821 | +2.3175% | 1.2623 | 2208 | 4 |
| 3981 | 2026-11-22 12:23:11 | FORWARD_TEST | load_gate | 0.310 | 0.219 | +1.4145% | 1.1603 | 1180 | 4 |
| 3982 | 2026-11-22 13:08:11 | FORWARD_TEST | load_gate | 0.384 | 0.337 | +2.4364% | 1.2858 | 968 | 4 |
| 3983 | 2026-11-22 13:38:12 | FORWARD_TEST | load_gate | 0.342 | 0.415 | +1.1780% | 1.1340 | 1275 | 3 |
| 3984 | 2026-11-23 00:38:15 | FORWARD_TEST | load_gate | 0.390 | 0.363 | +1.5905% | 1.1699 | 948 | 3 |
| 3985 | 2026-11-23 01:08:15 | FORWARD_TEST | load_gate | 0.550 | 0.435 | +1.3106% | 1.1840 | 1225 | 3 |
| 3986 | 2026-11-23 01:38:15 | FORWARD_TEST | load_gate | 0.375 | 0.372 | +1.0825% | 1.1193 | 1044 | 3 |
| 3987 | 2026-11-23 02:53:16 | FORWARD_TEST | load_gate | 0.486 | 0.433 | +3.0053% | 1.3363 | 846 | 4 |
| 3988 | 2026-11-24 03:00:27 | FORWARD_TEST | starvation_breaker | 6.347 | 3.843 | +1.2668% | 1.1665 | 983 | 3 |
| 3989 | 2026-11-24 05:24:45 | PROVEN | load_gate | 0.381 | 0.083 | +0.9700% | 1.2337 | 4208 | 5 |
| 3990 | 2026-11-24 07:42:42 | FORWARD_TEST | load_gate | 0.387 | 0.404 | +1.0005% | 1.1087 | 1425 | 2 |
| 3991 | 2026-11-24 08:27:43 | FORWARD_TEST | load_gate | 0.371 | 0.395 | +1.6363% | 1.1822 | 1323 | 4 |
| 3992 | 2026-11-25 00:57:48 | FORWARD_TEST | load_gate | 0.363 | 0.353 | +2.1869% | 1.2507 | 946 | 4 |
| 3993 | 2026-11-25 01:12:48 | FORWARD_TEST | load_gate | 0.401 | 0.449 | +1.3916% | 1.1581 | 1153 | 3 |
| 3994 | 2026-11-25 01:27:48 | FORWARD_TEST | load_gate | 0.424 | 0.456 | +1.7441% | 1.1974 | 985 | 3 |
| 3995 | 2026-11-25 01:57:48 | FORWARD_TEST | load_gate | 0.516 | 0.456 | +1.5289% | 1.1721 | 1049 | 3 |
| 3996 | 2026-11-26 00:42:56 | FORWARD_TEST | load_gate | 0.559 | 0.551 | +3.2982% | 1.3402 | 917 | 3 |
| 3997 | 2026-11-26 13:58:02 | FORWARD_TEST | load_gate | 0.403 | 0.440 | +1.5542% | 1.1783 | 765 | 3 |
| 3998 | 2026-11-26 18:13:04 | FORWARD_TEST | load_gate | 0.370 | 0.487 | +1.7176% | 1.1964 | 1196 | 4 |
| 3999 | 2026-11-26 22:43:06 | FORWARD_TEST | load_gate | 0.449 | 0.508 | +1.5109% | 1.1623 | 1199 | 3 |
| 4000 | 2026-11-27 00:58:07 | FORWARD_TEST | load_gate | 0.862 | 0.698 | +1.2219% | 1.1352 | 1196 | 4 |

## §4 — Trial 3989: the second PROVEN (new finding)

Declaration `decl_0010_b111752515`, 2026-11-24T05:24:45Z, `combination_pair`: `bar_patterns/engulfing@crypto30/1d` + `dow_effect/reversal@crypto30/1d`. Trades 4208, wins 2124, win rate 0.504753, expectancy **+0.9700%** (0.00970030924968392), PF **1.2337** (1.233716485874774), gross 215.47025794344296 / 174.65135662077375; folds 5/5 positive (958/+0.012077167146927211, 843/+0.015141128092207896, 916/+0.015575261636259078, 890/+0.00017067548942622743, 601/+0.0034378758232608175); holdout 1402/+0.00849347739103836; t 4.934611894919153; p 4.0155146784124895e-07 < 1.25e-05 (0.05/3989 = 1.2534e-05). Verdict **PROVEN**, all 8 checks true. Admission `selfexp_combo_7277cd6bf45e`; lesson banked 05:24:46Z. Scheduling `load_gate` (load1 0.381, load5 0.083). Host attribution is G6 below — it is in the live S4 ledger and the S4 counter lineage, but it ran before the current S4 systemd daemon started.

## §5 — Load-gate evidence (why there is no starvation to fix)

- **Stratex-Server now:** load 0.79/0.63/0.57 at 02:31Z; three 5s-apart samples 0.99/0.71/0.61, 0.91/0.70/0.60, 0.84/0.69/0.60 — the normal gate (1.4 on 2 CPUs) is open and trials 3990–4000 all ran through it. Last trial 4000 at 00:58:07Z, ~1.5 h before this probe; the loop polls continuously and the daily cap (4/day) is not binding at this cadence.
- **The breaker works in production:** it fired twice — trial 3980 (load1 4.29/load5 2.82) and trial 3988 (load1 6.35/load5 3.84, both above the 1.4 gate, load5 below the 4.0 ceiling). The EXP-006 design (5-minute average as the ceiling signal, ignoring 1-minute spikes) is confirmed by the live rows.
- **Server 1 now:** load 0.09–0.16 — the gate would be open, but no daemon runs there and S1 holds no live state; its quiet load is the absence of the fleet, not a healthy loop.
- **Smallest safe fix proposal: none.** No code change, no env flip, no restart is proposed or needed. The only follow-ups are the carried G2 (PROVEN admissions) and the new gaps below.

## §6 — Tests (local, this VM, repo at main `5fd32fdf`)

- `Stratex/tests/test_str_exp_006_starvation_breaker.py`: **19 passed**.
- `Stratex/tests/test_exp001_self_experiments.py` + `test_exp004_daemon_wiring.py`: **42 passed, 6 failed** — the 6 failures are the pre-existing environment gaps already recorded in the EXP-006 report (missing `pandas` / `autonomy` modules in this scratch checkout; e.g. `ModuleNotFoundError: No module named 'pandas'` from `strategies/strategy_registry.py`), identical before and after this change. No code changed in this PR, so no new tests were added.

## §7 — Gaps / follow-ups

- **G1 — CLOSED (was EXP-006 G1):** production trial 3980 landed 2026-11-22T11:58:43Z and is verified in §2.
- **G2 — OPEN (carried from EXP-006):** a PROVEN verdict admits to the FORWARD_TEST lane (per EXP-001 design); promotion to VALIDATED travels the Universe change path, never the loop. Now **two** PROVEN admissions await that follow-up: `selfexp_combo_37358617fe8a` (trial 3980) and `selfexp_combo_7277cd6bf45e` (trial 3989). Coordinator to scope.
- **G3 — CLOSED as a watch item (was EXP-006 G3):** S1's load regime is moot — S1 is no longer live and S4 sits at ~0.6–0.9. Standing watch: if S4's sustained (5-minute) load climbs past the 4.0 breaker ceiling, the breaker stops firing and the loop starves again.
- **G4 — OPEN (carried from EXP-006):** greedy time box under nice 19 — no greedy trial has run yet (all 21 trials are combination proposals); the first greedy proposal still deserves a watch.
- **G5 — NEW, open:** the S1 daemon restart onto the merged EXP-006 code is not directly evidenced. Trial 3980 landed 2m 15s after the merge (11:56:28Z → 11:58:43Z), so the restart must have happened in that window — but S1's journal has rotated ("journal has been rotated since unit was started") and the bounded Nov-22 journal queries return nothing. The breaker firing itself proves the new code was live by 11:58:43Z.
- **G6 — NEW, open:** trial 3989's exact host process is unidentified. It ran 2026-11-24T05:24:45Z — after the S4 data dir was created (04:50:53Z) but before the current S4 systemd daemon started (06:57:34Z, NRestarts=0) — and it is absent from S1's frozen ledger. The load signature (load1 0.381, load5 0.083 — a quiet box, unlike S1 at that hour) and the data-dir birth point to Stratex-Server from a migration-time (pre-systemd) daemon process. No surviving log line names the process: the narrow-window daemon journal grep (Nov 24 05:00–07:30Z) returns no matches.
- **G7 — NEW, open:** loop cycle logs do not reach `bot.log` on either host (0 self-experiment lines in S4's 9.4 MB `bot.log`; the single S1 line is the 2026-11-24T08:04:24Z "Self-experiment loop wired in" notice from the S1 daemon's final start). The daemon journal grep over Nov 23+ timed out at 240s. Cycle-level log evidence for trials after 3980/3988 therefore rests on the ledger rows and their recorded load fields, not on log lines.
- **G8 — NEW, observation:** S1's `experiments.jsonl` birth is 2026-11-23 11:24:37Z although its first rows date from Nov 22 11:58Z (the ledger only ever appends). The file was recreated that day with content preserved — the byte-identical hash against S4's first 36 rows proves no content was lost or altered — but the recreating step is not identified.

## §8 — Probe record

- Bridge `run_shell` probes (read-only): S1 + S4 full state probe 2026-11-27 ~02:31Z; S4 follow-up (trial 3980 rows, per-trial summary, daemon service) ~02:38Z; S1/S4 probe 3 (admissions, trial 3989, lessons, restart counts, lineage hashes) ~08:0x IST; bot.log forensics + S4 dry-run re-derivation ~08:15 IST. Raw outputs: `~/workspace/muse4-runs/str097_probe_s1.txt`, `str097_probe_s4.txt`, `str097_probe_s4b.txt`, `str097_probe_s1b.txt`, `str097_probe_s4c.txt`, `str097_probe_s1c.txt`, `str097_probe_s4d.txt`, `str097_probe_s1d.txt`, `str097_probe_s4e.txt`, `str097_dryrun.txt`.
- One probe leg (probe 2, first attempt) was interrupted by a runtime restart before writing output; it was re-run leg-by-leg and completed — no figures in this doc come from the interrupted attempt.
- S1 final daemon incarnation: started 2026-11-24 13:33:05 IST, loop wired in 08:04:24Z, killed 13:42:26 IST (timeout) with no trial in that window.
- No board hunk in this PR — board flips are coordinator-only per WATCH182 §3. Paired verifier: none named yet — Muse to name one.

— Muse 4
