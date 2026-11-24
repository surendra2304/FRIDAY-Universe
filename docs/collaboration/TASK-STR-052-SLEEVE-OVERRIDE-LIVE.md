# TASK-STR-052 — sleeve_shock_breakout forward proof: FWD-012 override live on S1 + first sleeve executions filed

- **Task:** verify the TASK-STR-FWD-012 per-strategy `max_stop_pct` override is live on S1 and file the first sleeve executions, or the continued max-stop block with stop evidence.
- **Claim:** hub #1483 comment 7120261042 by Muse 9, 2026-11-24 ~07:57 IST, queue head after STR-045 merged (PR #1609, merge 453686d0); INT-023 IN_REVIEW, final 7-day compilation due 2026-11-27 — claimed under the blocked-head rule. Branch `muse9/task-str-052` from main `8f8796c`.
- **Verification window:** 2026-11-24 ~08:11–08:35 IST, read-only live probes on Server 1 via the bridge (no writes, no venue orders, no restarts). Probe scripts: `~/workspace/friday-bridge/str052_probe.py`, `run_str052_probe.py`, `str052_atr_probe.py`, `run_str052_atr_probe.py`, `str052_open_probe.py`.

## Verdict

**ACCEPTANCE MET (first leg): override live-verified + first sleeve executions filed.** The FWD-012 override (`max_stop_pct 0.90` for `sleeve_shock_breakout`) is live in the running S1 daemon, and the sleeve has its first two lifetime executions — both still open. No continued max-stop block exists: zero max-stop skip lines for the sleeve in all surviving logs, and both executions' judged stops were far above the 0.15 global cap, which the old code would have rejected.

## 1. Override live on S1 — verified first-hand

| # | Check | Result |
|---|-------|--------|
| A1 | S1 checkout HEAD | `ed611a9e9f89349b3ad99b6a859f0deb713937e4`, dated 2026-11-24 07:15:38 IST; contains FWD-012 merge `2943852` (2026-11-21 12:51 IST, PR #1184). No modified tracked files (11 untracked state/scratch entries only). |
| A2 | Deployed registry (service venv import of `config_strategy`) | `sleeve_shock_breakout max_stop_pct = 0.90`, `dow_effect = 0.90`, sleeve status VALIDATED, timeframe 1w. |
| A3 | Deployed daemon source | `_max_stop_pct_for_strategy` present; max-stop skip line names the strategy (`Skip {symbol}: {cap_strat} stop … > max …`). |
| A4 | Running daemon | PID 3326500, `/opt/friday_universe/venv/bin/python -u /opt/friday_universe/Stratex/autonomy/run_daemon.py`, started ~2026-11-24 04:59 IST (elapsed 03:12:46 at probe time) — after the Nov 21 merge — loading from `/opt/friday_universe/Stratex`. Heartbeat RUNNING, fresh (`2026-11-24T02:41:13Z`), last cycle scanned 2310 / signals 0 / executed 0 / errors 0, 30 symbols, 29 open positions. |
| A5 | Effective global cap (running process environ, single key) | `STRATEX_MAX_STOP_PCT=0.15` — the global cap is intact; the override is per-strategy only. |
| A6 | Allowlist (running process environ) | Includes `strategy_sleeve_shock_breakout` and `strategy_dow_effect`. |
| A7 | Daemon actively scanning the sleeve | 450 `strategy_sleeve_shock_breakout` mentions in today's `bot.log` window; live 1w SELL signals on BTC/BNB/LTC/AVAX every scan cycle (e.g. BTCUSDT 1w SELL 2026-11-24T02:43:35Z). |
| A8 | S1 pull cadence | Reflog shows fast-forward pulls every ~20 min through Nov 23–24; `config_strategy.py` mtime 2026-11-21 19:36 IST, `run_daemon.py` mtime 2026-11-22 18:04 IST — both after the FWD-012 merge. |

Observation (not this task's to fix): the repo unit file `Stratex/deployment/friday-stratex.service` is **inactive** on S1 (`ActiveState inactive`, MainPID 0). The trading daemon (PID 3326500, PPID 1) is not that unit's main process — `Stratex.service`'s MainPID is `dashboard.py` (3326149) — and the daemon's stdout/stderr go to a socket, not the `Stratex.service` journal (552 lines since Nov 21 there are mostly the cTrader engine's). The daemon's own log is `Stratex/bot.log` (JSON lines, ~10 MB rotation, 5 backups, back to ~06:21 IST today).

## 2. First sleeve executions — filed

Source: `Stratex/state/position_tags.jsonl` ("ownership tag for every position opened", written on order placement with the venue order id; both tags carry `note: ""`, i.e. genuine placement tags, not adoption/sweep attributions). FWD-012 defect (2026-11-17): 0 executions in the leg's life. Fill ledger: 80 rows, **0 `sleeve_shock_breakout` rows all-time** (the ledger records closes; both positions are still open, so no close rows exist yet).

| Symbol | Side | Qty | Entry | Order id | Opened (UTC) | Timeframe | Still open? |
|--------|------|-----|-------|----------|--------------|-----------|-------------|
| BNBUSDT | SHORT | 0.08 | 590.59 | 2682377290 | 2026-11-19T09:49:24Z | 1wk | Yes — `position_closed_in_ledger` False |
| AVAXUSDT | SHORT | 3.0 | 7.015 | 560782270 | 2026-11-23T14:12:35Z | 1w | Yes — `position_closed_in_ledger` False |

Corroboration: sleeve guard line 2026-11-24T02:43:30Z — `components=['strategy_sleeve_shock_breakout', 'strategy_sleeve_tsmom2_dual'] trades=2 net=$-0.05 unrealized=$3.29 dd=$0.05/$526.58 breached=False` (open sleeve unrealized PnL present). The other sleeve component (`sleeve_tsmom2_dual`) has 2 ledger (close) rows; the shock leg has 0 closes because both its positions are still open.

## 3. Causal proof — the override is what unblocked them

Recomputed with the daemon's OWN functions (`strategy_sleeve_shock_breakout.weekly_candles` + `atr14`, Wilder ewm alpha 1/14) over public Binance demo daily klines (limit 1000, 143 weekly bars from 2024-03-02). Buckets are 7-day spans anchored 1640995200 (2022-01-01); at each execution the forming bucket was dropped by `_closed_frame`, so the signal bar is the last closed bucket.

| Execution | Signal bar (weekly bucket) | Close | ATR(14) | Judged stop = 2×ATR | Stop % vs close | Stop % vs entry | Side |
|-----------|---------------------------|-------|---------|---------------------|-----------------|-----------------|------|
| BNB 2026-11-19 | 253 (open Nov 7, close Nov 14) | 630.7 | 63.03 | 126.06 | **19.99%** | **21.35%** | SELL ✓ |
| AVAX 2026-11-23 | 254 (open Nov 14, close Nov 21) | 6.516 | 1.622 | 3.244 | **49.77%** | **46.23%** | SELL ✓ |

Both judged stops are far above the 0.15 engine-global cap. Under pre-FWD-012 code the max-stop gate (`stop_pct > max_stop`, `max_stop = 0.15`) would have skipped both — the FWD-012 defect's own window showed exactly that (24 max-stop rejections, stops 21.2–22.3%). Their execution proves the 0.90 override was live in the running daemon at execution time. Same geometry on the live bar: BTCUSDT bucket 254 stop 25.09%, SELL — matching the SELL signals firing now.

## 4. Why nothing since Nov 23 — no max-stop block

- Zero `Signal detected: strategy_sleeve_shock_breakout` lines and zero sleeve max-stop skip lines in all surviving logs (`bot.log` + `.1`–`.5`, back to ~06:21 IST). The signals are latch-suppressed after first processing per weekly bar (`latch_key` includes the last closed bar; one processing per bar per process lifetime — restarts re-arm it, which is how the Nov 19 and Nov 23 executions happened on the same bucket-253/254 signals days apart).
- The sleeve needs `entry_confluence = 2` distinct strategies on the same venue+symbol+side, and it cannot re-enter a symbol that already holds a position. Current state for the four firing symbols:
  - BTCUSDT: LONG open (`strategy_bar_patterns_inside_bar_4h` @ 59889.32, Nov 21) — sleeve SELL blocked by the open opposite position; 1d strategies signal BUY, opposite side.
  - LTCUSDT: SHORT open (`strategy_donchian_turtle_n20_b26_4h` @ 42.86, Nov 19) — already held.
  - BNBUSDT / AVAXUSDT: SHORT open — held by the sleeve itself.
- So the absence of new executions is confluence + already-held positions, **not** the max-stop cap. Next execution opportunity: a new symbol firing, or one of these positions closing first. (The decisive first-processing cycle for the current bucket-255 bar, ~05:30 IST today, is in rotated-away logs — its gate outcome is not recoverable from surviving logs; the open-position state above is consistent with the observed outcome.)

## 5. Open questions / unverified — stated plainly

1. **BNB Nov 19 predates the merge.** The BNB execution (stop ~21%) happened 2026-11-19, two days BEFORE the FWD-012 merge to main (2026-11-21 12:51 IST). The running code on Nov 19 must already have carried the override — most likely a pre-merge branch deploy by the FWD-012 crew (branch `claude/task-str-fwd-012-max-stop-override`, head `7b62260b`, which is NOT an ancestor of main; the substance arrived via merge 2943852). **Unverified:** S1's reflog only reaches Nov 23 11:41 IST and the Nov 19 daemon logs rotated away, so the Nov 19 deploy state cannot be confirmed from surviving records. The AVAX Nov 23 execution (post-merge) is the clean proof.
2. **Live unit vs repo unit.** See §1 observation — the trading daemon is not run by the repo's `friday-stratex.service` on S1. Deployment hygiene note for Muse, not a STR-052 finding.
3. **dow_effect not re-probed for execution.** Same 0.90 override, firing daily (ETH/SOL/BNB BUY signals today), but this task's acceptance is the sleeve leg; dow execution proof is not filed here.
4. **No new sleeve execution in this run's window.** Correct per §4 — the task asks to file the first executions, which are the two above; a third execution is not owed by this task.

## 6. Five states

- **Implemented:** YES (repo + live: override in deployed registry and daemon; FWD-012 code on main since 2026-11-21).
- **Tested:** YES — live verification this run: 13 probe checks (registry, daemon source, process environ, allowlist, heartbeat, ledger, journal, open-position reconciliation) + ATR reconstruction of both execution bars with the daemon's own functions. `test_fwd012_max_stop_override.py` asserts the sleeve lookup == 0.90 (repo-side; not re-run this task — no code changed).
- **Merged:** YES (FWD-012 substance on main via merge 2943852, 2026-11-21; this task's work PR carries only this evidence doc + the board flip).
- **Deployed:** YES — override live in the running S1 daemon (PID 3326500, started 2026-11-24 ~04:59 IST from the current checkout).
- **Production-verified:** YES for the override + first executions (2 live sleeve positions opened with stops 21% / 46% vs the 0.15 cap, both still open). The Nov 19 branch-deploy basis is the one unverified sub-point (§5.1).

— Muse 9, 2026-11-24 ~08:35 IST
