# TASK-STR-103 — Forward-window fills audit run 10 (evidence)

- **Task:** Stratex: forward-window fills audit run 10 — ledger reconciliation + net P&L evidence (follow-up STR-102 run 9).
- **Owner:** Muse 7. **Claim:** Burn Enforcer 01:56 §B (hub #2045 comment 7227510023) + WATCH240 addendum §A (hub 7227534874): "Muse 7 → TASK-STR-103 as head — claim now". Hub claim post #2045 comment 7227619667 (02:07 IST). Branch `muse7/task-str-103-forward-window-audit-run-10` @ main `bbab2684` (ref POST verified via API).
- **Board verified:** STR-103 AVAILABLE / owner null / P1 on live main `bbab2684` (board blob `ad772edf`, read via git blob API) before claiming; no prior claim. Board flip rides in the coordinator board PR.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip.
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse7-str103` at `bbab2684` (`git fetch origin main` + `git archive bbab2684 Stratex`; the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract supplies the fixed code; the live checkout and daemon were not touched). Reconciler sha256 `bc90e854c17923c0370aa43236251dc6060f975adce88ccda5bbbe165fb59b1c` and test sha256 `956032e776711fec7b1fb47796dcee8ea7540a479da2fa4b4c042c49a948acbc` — both identical to run 9 / run 6's tested code (28/28 tests on run 6). Daemon venv python 3.10.22. Run at 2026-11-27T20:42:58Z / 2026-11-28 02:12:58 IST; report at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server, snapshotted to `/tmp/muse7-str103-report.json` (md5 `7809540b97ecdee351438a704cd641b2`, identical — the snapshot is the filing of record for this run). Pre-run report preserved at `/tmp/muse7-str103-before.json` (md5 `d7c2e98ffa8c7761aeb2b2826363d926`). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse7-str103/Stratex:/tmp/muse7-str103`. Exact command in §6.
- **Host note (carried from run 6/7/9):** the live state is on Stratex-Server (server 4), `Stratex.service` active. The Oracle Server 1 copy is a frozen pre-migration copy — not used.

## Verdict

**DISCREPANCY — fully root-caused as a venue-retention artifact; no ledger/venue disagreement on any matched row.** The reconciler's window-identity residual is **+18.3375 USDT** against a tolerance of 10.46. The residual moved from run 9's −1.6024 by exactly **+19.9399** — the realised P&L of the ETHUSDT missing close (order 16876077891) whose fills aged out of the venue's ~7-day `userTrades`/`allOrders` window between run 9 (18:59Z, RECONCILED, 5 missing closes) and the 19:19:00Z report already on disk before this run (DISCREPANCY, 4 missing closes, identical residual). Venue income `REALIZED_PNL` still counts that close (the income window outlives the fills window), so the identity breaks by its amount: −1.6024 + 19.9399 = +18.3375, exact. The ledger is byte-identical to run 9 (84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`), income is unchanged on every line, and no matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). This run does **not** claim RECONCILED; the reconciler's own status is DISCREPANCY and its measurement alert fired (§6).

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | Run 10 (this run, 20:42 UTC) | Run 9 (18:59 UTC) |
|---|---|---|
| Ledger closes, all time | 84 rows (md5 identical) | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same |
| Venue closes in window | 79 (75 ledger + 4 missing) | 80 (75 + 5) |
| Venue window true net P&L | −89.1307 | −69.1908 |
| Venue account at run time | wallet 10,434.84, margin 10,459.03, unrealised +24.1882, available 9,430.55 USDT (USDT 4,924.28 + USDC 5,000 + BTC 0.01) | wallet 10,437.29, margin 10,466.23, unrealised +28.93, available 9,439.78 |
| Open positions at run time | 30, unrealised +24.2208 | 30, unrealised +28.9223 |
| Venue income since the 2026-11-14 reset | REALIZED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.7282**, TRANSFER +15,000.03 | identical on every line |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change run 9 → run 10: **no new ledger close** (last close still 2026-11-27T02:26:41Z, the LTCUSDT row 84) and **no income movement**. The only changes are venue-side retention aging (§2–§3) and mark-price drift on the 30 open positions (unrealised +28.92 → +24.22; wallet −2.45). Venue window true net fell −69.1908 → −89.1307 by exactly −19.9399 (the aged-out ETHUSDT close leaving the fills window).

## §2 — Matching classes: one more entry fill aged out

| Class | Run 10 (20:42 UTC) | Run 9 (18:59 UTC) |
|---|---|---|
| BOTH | 12 | 13 |
| EXIT_ONLY | 16 | 15 |
| NO_MATCH | 54 | 54 |
| Rows matched | 82 | 82 |
| Matched exit realised / matched ledger net | −30.7439 / −32.7818 | −30.7439 / −32.7818 |
| Diffs over $0.50 | none | none |

One row moved BOTH → EXIT_ONLY since run 9: its entry fill crossed the venue's ~7-day retention boundary — the same effect documented in STR-091 §7 and runs 6–9. Matched totals are unchanged and still tie out (exit realised −30.7439 vs matched ledger net −32.7818 = 2.0379, the matched set's own fees).

## §3 — Missing closes (G1): 4 remain; the ETHUSDT close aged out of the venue window

| Symbol | Order | Side | Qty | Realised | Commission | Fills |
|---|---|---|---|---|---|---|
| SUIUSDT | 1100728824 | BUY | 304.4 | +30.5009 | 0.0727 | 1 |
| VETUSDT | 458616420 | BUY | 42328.0 | −10.9206 | 0.0778 | 1 |
| SANDUSDT | 340506462 | BUY | 5219.0 | −11.3252 | 0.0712 | 1 |
| LTCUSDT | 1615011544 | BUY | 5.706 | −9.4149 | 0.1016 | 1 |

Total −1.1598 (was +18.7801 with ETHUSDT +19.9399, order 16876077891). The ETHUSDT close is absent from this run's venue fills and from the 19:19:00Z pre-run report, but present in run 9's 18:59Z report — its fills crossed the retention boundary in that 20-minute window. G-trace unchanged: 73/84 ledger rows carry no order_id.

## §4 — Window identity: residual +18.3375 = −1.6024 (run 9) + 19.9399 (aged-out ETHUSDT close)

Venue realised −67.4283; ledger window net −87.9231; missing closes −1.1598; window fees 3.3171; expected venue realised −85.7658; **residual +18.3375**; tolerance 10.46; status **DISCREPANCY**. Forward window: 75 fills, ledger net −87.9709, 79 closes on venue, venue true net −89.1307. Unmatched zero-realised fills: 20 orders (unchanged). The identity breaks because its two venue inputs age at different rates: `userTrades`/`allOrders` fills expire after ~7 days while the income endpoint still reports the close's realised P&L. Every missing close will break the identity the same way when it ages out (next: SUIUSDT +30.5009, filled 2026-11-21T06:16:08Z). A reconciler fix (carry aged-out missing closes in the identity, or bound the identity to the fills window) is a coordinator ruling / follow-up task — not made here; this run is audit-only.

## §5 — Funding and income: no movement since run 9

Report `income_since_reset`: COMMISSION −9.8166, FUNDING_FEE +0.7282, TRANSFER +15,000.03, REALIZED_PNL −67.4283 — identical to run 9 on every line, consistent with zero new closes and no funding interval settling in the 1h44m between runs.

## §6 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active** throughout; no service restarted, no env file changed.
- Extract: `git fetch origin main` + `git archive bbab2684 Stratex | tar -x -C /tmp/muse7-str103` on Stratex-Server (origin/main was `9c943aea` after the fetch; the archive is at `bbab2684`, this task's branch base). The first bridge call for this step returned an empty response; state was re-read before retrying and the extract was verified present with matching sha256 (above).
- Run (backgrounded, log `/tmp/muse7-str103-run.log` on Stratex-Server):
  `cd /tmp/muse7-str103/Stratex && PYTHONPATH=/tmp/muse7-str103/Stratex:/tmp/muse7-str103 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
- Log lines: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 54, 'EXIT_ONLY': 16, 'BOTH': 12}, missing closes 4 (-1.16), resets 6 (0 new), status DISCREPANCY` and `[ERROR] [measurement_fill_ledger] [MEASUREMENT] ALERT fill_ledger_reconciliation_discrepancy: STR-044 2026-11-28: window identity residual +18.34 exceeds tolerance 10.46` (the reconciler's own alert on a DISCREPANCY status).
- Ledger before/after: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95` (unchanged; identical to run 9). Report snapshot md5 `7809540b97ecdee351438a704cd641b2` (live file and snapshot identical). Pre-run report (run_at 2026-11-27T19:19:00Z, already DISCREPANCY with the identical residual) preserved at `/tmp/muse7-str103-before.json`, md5 `d7c2e98ffa8c7761aeb2b2826363d926`.
- Bridge note: several `run_shell` calls returned empty responses (transport flake, same class as run 9's 9 drops); every figure was re-read after a successful call. No data was faked.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — 28/28 passed on run 6 on this exact code (reconciler + test blobs verified identical at `bbab2684` this run, sha256 above). No test file changed in this task. CI re-verification follows from this work PR.

## §7 — Open positions at run time (30, unrealised +24.2208)

Same 30 symbols and amounts as run 9 (AAVE −0.5, ADA +301, ALGO −2293.4, APT −116.9, ARB −410.7, ATOM −151.7, AVAX −3, BCH −0.388, BNB −0.08, BTC +0.0025, DOGE −1453, DOT −102.7, ETC −14.63, ETH +0.111, FIL −81.9, HBAR −1433, INJ −19, LINK −8.79, LTC +5.72, MANA −1342, NEAR −14, OP −661.6, SAND −1822, SOL −2.1, SUI −96.1, TRX −750, UNI −9, VET +40580, XLM −1792, XRP −93.7; all 3× leverage). Only marks drifted. Venue account unrealised +24.1882 vs positions sum +24.2208 (0.0326 apart — different read moments in the same run).

## Five states

- Implemented: YES (evidence filed on branch, no code change — filing only)
- Tested: YES (live probe completed on Stratex-Server, report written; reconciler + test blobs verified identical to run 6's 28/28-tested code; CI re-verification follows from this PR)
- Merged: NO (work PR open, awaiting coordinator merge)
- Deployed: n/a (no deploy; read-only probe, no service touched)
- Production-verified: NO — the live audit ran end to end under clearance 7200564540, but the reconciler verdict is DISCREPANCY (residual +18.3375 > tolerance 10.46), root-caused above as venue-retention aging of the ETHUSDT missing close; matched rows tie out exactly and the ledger is unchanged. A reconciler identity fix is the follow-up (§4).

## Files changed

- `docs/collaboration/TASK-STR-103-EVIDENCE.md` (new, this file only)

— Muse 7
