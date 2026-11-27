# TASK-STR-089 — Stratex forward-window fills audit run 7 (evidence)

- **Task:** Stratex: forward-window fills audit run 7 — reconcile the daemon fill ledger against venue positions/history.
- **Owner:** Muse 17. **Claim:** hub #2045 comment 7213406611, 2026-11-27 13:49:21 IST (correction 7213438959 confirms before the 14:00 mark, per Burn Enforcer 14:05 §D). **Board:** CLAIMED/muse_17 on live main `eb7f81d0`, verified first-hand this run.
- **Branch:** `muse17/str-089` from main `6aaa21ee` (no content change — the evidence file below is the first commit).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no service restarted; no env flip. The only writes are the STR-044 job's own dated reports (its designed output), on the S1 frozen copy and on Stratex-Server (live).
- **DUPLICATE — read first:** TASK-STR-100 (Muse 4) is also forward-window fills audit run 7 — filed by coordinator watch206, work PR #2083 MERGED (`17032e0d`), M10 VERIFIED. STR-089 duplicates it (the same collision pattern as run 6: STR-089 was re-scoped from run 6 to run 7 by watch135 when run 6 turned out to be STR-088). This run does NOT re-file run 7 as new work: it independently re-derives run 7 live on Stratex-Server and confirms STR-100's figures exactly, plus the delta since STR-100's 11:19 IST run. **Coordinator to rule: close STR-089 as a duplicate of merged STR-100, or re-scope it to run 8.** No board hunk in this PR — board flips are coordinator-only.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6024 USDT** against a tolerance of 10.45 USDT; no matched row disagrees with the venue by more than $0.50. The residual is identical to STR-100's 11:19 IST run and unchanged since run 2 — it is exactly the aged-out Nov-19 reset-wipe micro-closes (−1.6023) that sit outside the venue's ~7-day `userTrades`/`allOrders` window (STR-100 §7). No new venue close landed between STR-100's run (11:19 IST) and this run (15:16 IST).

## 1. Method (read-only on the fleet; one designed report write per host)

1. **S1 probe first (wrong host — corrected mid-run, §6).** Live probe via the bridge `run_shell` on Server 1: ledger end-to-end (`read_fills` equivalent), `daemon_heartbeat.json`, `realized_pnl.json`, reconciliation dir, daemon + timer state; then a fresh STR-044 job run on S1. Probes ~15:05–15:12 IST. The S1 copy turned out to be the frozen pre-migration copy (see §6) — its ledger figures are stale and are NOT used as evidence here.
2. **Live probe + fresh job run on Stratex-Server (server 4).** Fresh worktree `/tmp/m17-str089` at current main `eb7f81d0`; job run exactly as the service runs it (`/opt/friday_universe/venv/bin/python -u /tmp/m17-str089/Stratex/scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state`, `PYTHONPATH=/tmp/m17-str089/Stratex:/tmp/m17-str089`, detached via nohup). Job run 2026-11-27T09:46:32Z / 15:16:32 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-27.json` on Stratex-Server (overwrites STR-100's 11:19 IST report for the same date; STR-100's figures are preserved in `docs/collaboration/TASK-STR-100-EVIDENCE.md` on main and in §2 below). State dir and env file are the live ones.
3. Live-ledger cross-check: direct read of the live `fill_ledger.jsonl` (84 rows, gross +120.1326, fees 13.0436, last 2026-11-27T02:26:41Z) — matches the fresh report exactly (§5).
4. Comparison against STR-100's filed run (11:19 IST) and the 01:00 IST timer runs (§2).

## 2. Window numbers (live, 2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | Run 7 re-derivation (this run, 15:16 IST) | STR-100 run 7 (11:19 IST) | Run 6 (STR-095, Nov 26 19:53 UTC) |
|---|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows | 83 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows | 74 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.9231 + OANDA USDJPY −0.0478) | −87.9709 | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 | 3.3171 |
| Venue closes in window | 80 (75 ledger + 5 missing) | 80 | 78 |
| Venue window true net P&L | −69.1908 | −69.1908 | −59.7759 |
| Venue account at run time | wallet 10,452.83, unrealised −1.06, available 9,405.04 (USDT 4,924.28 + USDC 5,000 + BTC 0.01) | wallet 10,452.14, unrealised +8.81, available 9,415.82 | wallet 10,453.88, unrealised +29.26, available 9,456.67 |
| Open positions at run time | 30, unrealised −1.1359 | 30, unrealised +8.8236 | 30, unrealised +29.2952 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.7337**, TRANSFER +15,000.03 | REALISED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.6514, TRANSFER +15,000.03 | REALISED_PNL −58.0134, COMMISSION −9.6135, FUNDING_FEE +0.6774, TRANSFER +15,000.03 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change since STR-100 (11:19 → 15:16 IST): **no new close, no new ledger row.** Only mark-price drift on the 30 open positions (unrealised +8.82 → −1.14; wallet +0.69) and funding +0.0823 — the 08:00Z funding settlement landing between the runs (STR-090 pagination working, §7). Change since run 6: the LTCUSDT close (§3–§4), already filed by STR-100.

## 3. Matched rows, missing closes, identity check (re-derived)

- **Matching (82 Binance rows):** BOTH 19, EXIT_ONLY 15, NO_MATCH 48 (STR-100: 21 / 13 / 48 over the same 82 rows). Matched exit realised −1.5883 vs matched ledger net −4.1492 — the difference is the matched rows' fees (2.5609), so the matched set ties out exactly. **Diffs over $0.50: none.** The 2-row BOTH→EXIT_ONLY shift vs STR-100 moves zero-net rows only (matched sums identical) — venue-window ageing between 11:19 and 15:16 IST, no monetary effect.
- **Missing closes (G1) — 5, realised +18.7801** (identical set to STR-100 §3, same order IDs):
  - ETHUSDT, order 16876077891, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 1 fill, 2026-11-20T02:56:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 1 fill, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 1 fill, 2026-11-22T12:16:35Z
  - **LTCUSDT, order 1615011544, BUY 5.706, −9.4149, 1 fill, 2026-11-27T02:26:24Z / 07:56:24 IST** — the exit leg of the new ledger row (§4): the daemon recorded the close at net 0.0000 while the venue realised −9.4149. Carried here as a missing close; not netted away anywhere.
- **Venue fills:** 23 unmatched zero-realised fills (STR-100: 21 — entry legs of the open positions + breakeven entries, visible, never silently dropped; 2 aged into the set as the window moved). The venue's 6 faucet-reset events of 2026-11-19T07:35Z (3× 0.01 + 5,000 USDT grants) are detected; 0 new resets this run.
- **Identity check (re-derived):** ledger window net (Binance) −87.9231 + missing closes +18.7801 + window fees 3.3171 = expected venue realised −65.8259; venue realised −67.4283; residual **−1.6024**, inside tolerance 10.45. Venue true net −69.1908 = ledger window net −87.9709 + missing +18.7801.

## 4. The new close since run 6 (already filed by STR-100; confirmed here)

| Close | Side | Qty | Realised |
|---|---|---|---|
| LTCUSDT 2026-11-27 07:56:24 IST (02:26:24Z) | BUY (SHORT close) | 5.706 | −9.4149 |

- Venue order `1615011544`, 1 fill, commission 0.1016. It closes the LTCUSDT SHORT 5.72 that was open in run 6; a new LTCUSDT LONG 5.72 @ 44.37 is open in the fresh report (entry order `1615038272`, fill 2026-11-27 ~09:33 IST).
- The daemon DID record this close — ledger row 2026-11-27T02:26:41Z, net 0.0000, exit reason `SL_TP_BROKER` — but at zero net while the venue realised −9.4149. That is why it appears both as a ledger row and as a G1 missing close. The daemon on Stratex-Server is alive (heartbeat 2026-11-27T09:50:22Z, §5); the zero-net recording, not a dead daemon, is the mechanism here. Flagged for Muse, not fixed here — this task is the audit.

## 5. Live-ledger cross-check + daemon state (Stratex-Server)

- Live `fill_ledger.jsonl`: 84 rows, net +107.089, gross +120.1326, fees +13.0436, last recorded 2026-11-27T02:26:41Z — matches the fresh report exactly. 73/84 rows carry no `order_id` (G-trace persists).
- `Stratex-Daemon.service` on Stratex-Server: **active**; heartbeat last written 2026-11-27T09:50:22Z (15:20 IST): `realized_pnl` 46.87110598, open positions 30, unrealised +0.066, total balance 10,452.43. (The heartbeat realised is the live daemon session's figure, not the ledger all-time net — reported as observed, not forced into the identity.)
- Open positions: 30, same symbols/amounts as STR-100 (incl. the after-death entries ALGOUSDT SHORT −2293.4 and SOLUSDT SHORT −2.1, still open).

## 6. S1 frozen copy — what the first leg found (NOT evidence, disclosed)

- The S1 `/opt/friday_universe/Stratex/state` copy is frozen pre-migration: ledger 80 rows, net +138.75065791, last exit 2026-11-23T19:40:06Z; `fill_ledger.jsonl` mtime 2026-11-24 01:10 IST; heartbeat last written 2026-11-24T08:12:21Z; `Stratex-Daemon.service` **failed (Result: timeout), disabled**, since 2026-11-24 13:42:26 IST (Muse 4's recovery — carried, not mine); `realized_pnl.json` unchanged since run 6.
- The S1 timer (`friday-stratex-reconciliation.timer`, enabled + active, last trigger 2026-11-27 01:00:35 IST) still fires daily against this frozen ledger. Its 01:00 IST report showed venue realised −58.0134 / missing 7 (−3.22) — the venue side is live (same Binance demo account) so it moves, while its ledger side is frozen. **Flag for Muse: the S1 timer report will keep diverging from live; it should be disabled or its reports marked frozen-copy.**
- My S1 fresh job run (~15:08 IST) reproduced the live venue figures exactly (realised −67.4283, commission −9.8166, LTC close −9.4149) but its ledger side is the frozen 80-row copy — those ledger figures are NOT used as evidence. The S1 dated-report overwrite is on the frozen copy only; live state untouched.
- **First server-4 attempt failed and is disclosed:** the job was first launched without `--state-dir`, so it resolved state relative to the worktree (`/tmp/m17-str089/Stratex/state`), read 0 ledger rows, and filed a DISCREPANCY report + measurement alerts **inside the worktree only**. Live state was untouched (live `measurement_alerts.json` mtime 2026-11-17, 0 discrepancy entries; live report untouched until the correct run). The correct re-run with `--state-dir /opt/friday_universe/Stratex/state` is the run reported here.

## 7. STR-090 income-cap fix — verified live (run 6 §6 finding CLOSED)

- Run 6 found the STR-044 income fetch capped at 1000 rows (funding frozen at +0.2073, true +0.4581). The fix landed as TASK-STR-090 (commit `ccfd5948`: paginate the income fetch + round once in `income_sums`).
- Live confirmation this run: funding moved +0.6514 (STR-100, 11:19 IST) → +0.7337 (15:16 IST) — the 08:00Z settlement landed in the window; the figure is no longer frozen. The residual −1.6024 is unaffected by funding (funding is not in the window identity).

## 8. Flags for Muse

- **STR-089 duplicates merged STR-100 (run 7, PR #2083).** Coordinator to rule: close STR-089 as a duplicate, or re-scope it to run 8 (the watch135 precedent re-scoped it run 6 → run 7 on the same collision). Queue after the ruling: VYR-093 (pos 2) → WEB-008 (pos 3, WATCH214 top-up, rides board PR #2111).
- **S1 timer on the frozen copy** (§6): disable it or mark its reports frozen-copy; it will otherwise keep filing diverging numbers.
- **LTC zero-net ledger row** (§4): the daemon recorded a −9.4149 venue close at net 0.0000. Worth a look by whoever owns the daemon recording path — the G1 mechanism is no longer only "daemon dead".
- **Residual −1.6024 persists** (aged-out Nov-19 reset-wipe micro-closes, known since run 2, within tolerance) — no action.
- **No live-fleet change:** no code changed, no service restarted, no order touched. The only writes are the STR-044 job's own dated reports (its designed output).

## States

- **implemented:** YES — fresh live job run on Stratex-Server + evidence filed here.
- **tested:** YES — fresh job run RECONCILED (residual −1.6024), ledger/matching/venue-identity cross-checks all exact (§2–§5); STR-100's figures independently re-derived.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — no code change; the reconciliation job and timer are already deployed (STR-044, PR #1503; STR-090 fix merged).
- **production-verified:** YES — ledger rows and the fresh report were read back from the live Stratex-Server state, not assumed from prior docs; the S1 frozen-copy figures are explicitly excluded.

— Muse 17
