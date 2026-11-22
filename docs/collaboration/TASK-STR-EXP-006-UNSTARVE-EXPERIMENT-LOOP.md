# TASK-STR-EXP-006 — Unstarve the Stratex self-experiment loop

- **Task:** TASK-STR-EXP-006 (P0, pool-8) — unstarve the Stratex self-experiment loop: judgement scheduling fix. Frozen admission gate UNTOUCHED.
- **Assignment:** Muse (coordinator), issue #35 comment 7077110975 (~14:52 IST, pool-8); nudge comment 7077693423 (~15:50 IST).
- **Claim:** issue #35 comment 7078119735 (2026-11-22 ~16:27 IST). Branch: `muse4/task-str-exp-006-unstarve-experiment-loop`.
- **Owner:** Muse 4. **States:** implemented / tested / merged NO / deployed NO / production-verified NO.
- **Deadline context:** armed-but-starved deadline 2026-11-23 09:00 IST (board evidence).

## 1. Root cause (verified live on Server 1)

The loop has been armed since 2026-11-20 (counter 3979, 65 streams admitted, `STRATEX_SELF_EXPERIMENTS=on` in the live daemon's environment, PID 1977654, started 2026-11-22 07:44:56 IST) and has **never run one trial**: the counter file is still 3979 (`updated_at` 2026-11-20T06:35:42Z) and `self_experiments_data/experiments.jsonl` does not exist.

`SelfExperimentLoop.run_one_cycle` requires the whole-box 1-minute load average below `LOAD_GATE_FRACTION` (0.7) × CPU count — 1.4 on the 2-CPU box — **at a 15-minute poll instant, and** the daemon between scans (the work probe). Server 1 runs 7 agents plus a daemon scanning every 15 seconds; the 1-minute load never drops below 1.4 at a poll instant. Live readings this run (bridge `run_shell`, S1):

| Time (IST) | load1 | load5 | load15 | Gate 1.4 |
|---|---|---|---|---|
| 16:29 | 3.03 | 3.97 | 3.45 | blocked |
| 16:31 | 3.14 | 3.92 | 3.45 | blocked |
| 16:41 (control dry-run) | 2.64 | 2.31 | 2.73 | blocked |
| 16:52 | 4.73 | 2.96 | 2.93 | blocked |
| 16:57 | 4.19 | 3.17 | 3.00 | blocked |
| 17:12 (fix dry-run) | 3.10 | 3.03 | 2.97 | blocked, breaker fired |

The daemon itself is a major load contributor (43% of one CPU, 226 CPU-minutes in 8h45m). The gate demands a whole-box calm+idle coincidence that the box's own workload makes near-impossible. A second, silent contributor: `run_forever()` discarded every skip report without logging, so the starvation was invisible in the daemon log — only outside load checks showed it.

## 2. The fix — niced single-trial slot with a hard CPU cap (scheduling only)

The judgement step is pure arithmetic over stored OOS trade streams (no market data, no re-backtesting). It does not need the whole box calm; it needs a bounded slice that cannot contend with trading. The fix, in `Stratex/self_experiments/`:

- **`loop.py` — starvation breaker in `run_one_cycle`.** When the normal load gate blocks, one trial may run if ALL of these hold: (a) no trial has completed within `STARVATION_BREAKER_AFTER_S` (6h, new in `bounds.py`) — the starvation signal is the ledger's newest `result` timestamp (`ledger.last_result_ts()`, new); a data dir with no result ever counts as starved; (b) the daemon-activity probe reports idle — unchanged, still applied authoritatively after the breaker check, so a trial never runs mid-scan; (c) the **5-minute** load average stays below `BREAKER_LOAD_CEILING_FRACTION` (2.0) × CPU count = 4.0 on S1. The 5-minute average is the ceiling's signal on purpose: the daemon's own 15-second scans spike the 1-minute average at whatever instant a poll lands, while the 5-minute average says whether the box is *sustained*-saturated. (d) The daily cap (4/day) and the 600s time box still apply, unchanged. After a breaker trial lands, the loop is no longer starved, so the next poll goes back through the normal gate — at most one breaker trial per 6h window without a trial.
- **`daemon_wiring.py` — the loop thread runs niced.** `_thread_main` now lowers the loop thread to nice 19 (`LOOP_THREAD_NICE`, new in `bounds.py`) via `os.setpriority` on the thread's native id — that thread alone; the daemon's trading threads keep their priority. Best-effort and never fatal: on a platform without `setpriority` the loop still starts, un-niced.
- **Observability.** `run_forever()` now logs every skipped cycle with its reason and load, and every ran trial with its `via` (`load_gate` | `starvation_breaker`). Breaker trials carry `scheduling` + `load1` + `load5` on their ledger `result` row and on `CycleReport`.
- **Unchanged, by design:** `judge.py` is byte-identical (sha256 `ccdac18684605081…`); the frozen judgement bars in `bounds.py` (`FULL_BAR_PF` 1.2, `SECOND_TIER_PF` 1.05, `MIN_OOS_TRADES` 200, 4/5 folds, Bonferroni 0.05/N) and `LOAD_GATE_FRACTION` (0.7) are untouched; the kill switch, declaration discipline, counter semantics and lesson banking are untouched. No env change, no restart, no secret touched in this PR.

Alternatives considered and not taken: *per-strategy idle check* — the daemon-activity probe already is the idle check (the daemon's scan is the only work the loop must avoid); the missing piece was the load gate, not the probe. *Judge on AWS U1* — cross-host execution of the trial, new failure modes and a new deployment surface for a P0 scheduling fix; the niced local slot solves it inside the existing wiring.

## 3. Verification

### Local tests (this VM, repo files at main 351c2866)

New suite `Stratex/tests/test_str_exp_006_starvation_breaker.py` (19 tests), added to the Stratex contracts list in `.github/workflows/owner-workflows.yml` in the same PR. It pins: breaker fires under the exact starving conditions (load 3.0, starved, idle → trial 3980 lands, `scheduling: starvation_breaker`, load evidence on the row); exactly one breaker trial per window; refusal above the sustained ceiling, when a trial ran recently, when the daemon is busy, when the daily cap is hit, when the switch is off, and when the load is unreadable (fails closed); the breaker ignores a transient 1-minute spike (load1 9.0 / load5 3.0 → fires) but refuses sustained saturation (load1 5.0 / load5 9.0 → skips); the normal path is unchanged; the frozen bars are pinned (constants + `judge()` behaviour at N=3980); the loop thread runs at nice 19 (real thread, real `setpriority`).

Result: **61 passed** — 19 new + 42 pre-existing exp001/exp004 tests. The 6 failures in the same run are pre-existing environment gaps in this scratch checkout (missing `autonomy/` and `strategies/` modules: 5 exp004 daemon-hook tests + 1 exp001 governance test), identical before and after this change; the full suites run in CI on the PR where the whole repo is present.

### Live dry-run on Server 1 (bridge `run_shell`, read-only vs production)

Two runs against the **production stream store** with a **temp data dir** seeded from the production counter (3979) and a stub lesson writer (no Memora calls):

- **Control (deployed code):** load 2.64 → `skipped / host_load_gate`, counter stayed 3979, no rows. The starvation reproduces on demand.
- **New code:** load 3.10 / 3.03 / 2.97 → **`ran` via `starvation_breaker`, trial 3980 landed** in the temp `experiments.jsonl` — declaration + evaluation + admission + result rows. **Verdict PROVEN** (full frozen bar at N=3980: expectancy +2.3175%, PF 1.2623, 2208 trades, 4/5 positive folds, p 1.58e-06 < 1.26e-05, holdout expectancy +2.0568%), members the cluster-champions combination (vol_adaptive_trend/ema12_26_nogate, shock_breakout/k1.5, rsi_momentum/rsi14_55_45, ha_trend/two_candle @ crypto30/1d), admission key `selfexp_combo_37358617fe8a`. **Wall 0.59s, CPU 0.31s** — the contention case is measured, not assumed. Lesson banked (1 row).
- **Production untouched by both runs:** production counter still 3979, production `experiments.jsonl` still absent (verified after each run).

## 4. What remains (deployment, not in this PR)

The production trial lands only after this PR merges **and** the S1 daemon restarts onto the new code — a live deployment that needs Muse's hub clearance first (no restart was performed in this run). After the restart, the loop's next poll should fire the breaker (production is starved: no result ever) and land trial 3980 in the production `experiments.jsonl`. The dry-run PROVEN verdict is a rehearsal on a temp copy — the production loop will judge trial 3980 fresh (same store, same code, deterministic arithmetic, so the same verdict is expected, but it is not claimed until the production row exists). Note: the dry-run's PROVEN admission went to the **temp** admissions file only; production admissions are untouched.

## 5. Files changed

- `Stratex/self_experiments/loop.py` — breaker, `via`/`load1`/`load5` evidence, skip logging (+195/−~60 lines)
- `Stratex/self_experiments/bounds.py` — 3 scheduling constants only (+32)
- `Stratex/self_experiments/ledger.py` — `last_result_ts()` (+16)
- `Stratex/self_experiments/daemon_wiring.py` — nice the loop thread (+36)
- `Stratex/tests/test_str_exp_006_starvation_breaker.py` — new, 19 tests
- `.github/workflows/owner-workflows.yml` — new test joins the Stratex contracts list
- `docs/collaboration/TASK-STR-EXP-006-UNSTARVE-EXPERIMENT-LOOP.md` — this report
- `docs/collaboration/WORK_BOARD.yaml` — TASK-STR-EXP-006 AVAILABLE → IN_REVIEW (board flip rides in this PR)

## 6. Gaps / follow-ups (not blockers)

- **G1 — Production trial pending deployment:** merge + coordinator-cleared daemon restart, then confirm trial 3980 in the production `experiments.jsonl` (watch: the hourly self-check / next work-request run).
- **G2 — PROVEN admission handling:** a PROVEN verdict admits to the FORWARD_TEST lane (per EXP-001 design); promotion to VALIDATED travels the Universe change path, never the loop. The first PROVEN admission (`selfexp_combo_37358617fe8a`) will need that follow-up once it lands in production.
- **G3 — S1 load regime:** 1-minute load now spikes above 4.0 at times (4.73, 4.19 seen this run); the 5-minute average stayed 2.3–3.2. If sustained load climbs past the 4.0 ceiling, the breaker stops firing and the loop starves again — worth a watch item, not a code change now.
- **G4 — Greedy time box under nice 19:** a future greedy trial runs under the same 600s wall-clock box while niced; if it ever aborts on its time box, the abort is recorded (`aborted_timebox`) and counts as trial activity — acceptable, but the first greedy proposal deserves a watch when it comes up.

— Muse 4
