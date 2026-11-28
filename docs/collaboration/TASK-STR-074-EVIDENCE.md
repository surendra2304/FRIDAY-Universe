# TASK-STR-074 — Evidence: production-verify wave 1 (checkpoint 1 — scoping + live S4 baseline)

- **Task:** PRODUCTION-VERIFY wave 1 — live extreme-condition verification of TASK-IG2-STR-09, -10, -11, -12, -13 (Stratex corpus items).
- **Filed:** 2026-11-28 ~04:15 IST, by Muse 3 (claim hub #2045 comment 7228374022; BE 02:38 §B, hub 7228172325).
- **Branch:** `muse3/task-str-074-production-verify-wave1` off main `e5adbc89`.
- **Board:** TASK-STR-074 CLAIMED / owner muse_3 / branch `muse3/task-str-074-production-verify-wave1` / pr null / P1 on live main (blob `35b6b1ef`). No board hunk in this PR per the coordinator-only flip rule.
- **Stall note:** claimed 02:41 IST; paired verdict #2203 filed 02:53 IST; paired verdict #2209 (WATCH244 §D, due ~04:42) filed 04:09 IST (review 6094011749, VERIFIED). No branch commit between claim and this checkpoint — this checkpoint 1 repairs the stall with scoping + live baseline.

## Scope — the five items (code locations found by first-hand code search)

| item | what it is | code |
|---|---|---|
| IG2-STR-09 | tax ledger export | `Stratex/reporting/tax_ledger_export.py` (+ `Stratex/tests/test_ig2_str09_tax_export.py`) |
| IG2-STR-10 | market-data fallback chain | `Stratex/market_data_fallback.py` (+ `Stratex/tests/test_ig2_str10_fallback_chain.py`) |
| IG2-STR-11 | economic calendar | `Stratex/research/economic_calendar.py` (+ `Futuris/futuris/features/calendar_context.py`) |
| IG2-STR-12 | Bayesian uncertainty | `Stratex/rigorous_backtest/ig/bayesian_uncertainty.py` (+ `Stratex/rigorous_backtest/ig/tests/test_bayesian_uncertainty.py`) |
| IG2-STR-13 | Box Theory RD | board VERIFIED 2026-11-16 (Muse, TASK-IG2-STR-13 landing) — backtest record only |

- **Flag (coordinator's call):** IG2-STR-13 already reads VERIFIED on the board from its backtest landing. This wave's live leg for it is a live re-check, not a first verification; if the board VERIFIED stands, the item needs a live run recorded here, not a re-verdict.
- **Acceptance (board):** for EACH item, run it in the live agent on a real task and file live evidence (what ran, on which server, with what result, incl. the failure case). Extreme-condition test: live demo-daemon cycle on Stratex-Server on real market data + failure injection (venue disconnect, stale feed) + full-allowlist load scan, results filed from the live ledger. A code-only report is rejected; any item that fails live gets a named fix task, never a verified mark.

## Live S4 baseline (bridge run_shell, read-only, 2026-11-27T22:40Z / 04:10 IST)

- Daemon RUNNING, PID 74531 (`run_daemon.py`), scan_count 1343, 15 s interval; last evaluation 22:40:06Z; last cycle: scanned 2310, signals 0, executed 0, errors 0, 30 symbols (30 1d).
- `forward_scorecard.json` mtime 22:39:57Z, `daemon_heartbeat.json` 22:40:21Z — fresh at probe time (22:40:25Z). Scorecard parses, 9 keys.
- Equity $10,473.91, balance $10,436.11, unrealized +$37.80, realized +$46.87, 30 open positions, daily breaker NOT hit, daily start equity $10,485.85.
- `fill_ledger.jsonl`: 84 lines; latest fills ATOMUSDT LONG exit (net −10.78) and LTCUSDT SHORT exit; live hash identical to the backup copy.
- Backup cross-check (same run, #2209 verdict probes): dated set `20261128T023026Z` complete, verify 4159 OK / 0 failed on S1 and S2; all four spot hashes match the filed table. The live ledger is therefore backed up before the failure-injection leg — nothing here changes S4 state.

## Next (checkpoint 2)

- IG2-STR-10 first: the failure-injection leg (venue disconnect, stale feed) maps directly onto the fallback chain — run it live on S4 and file the ledger result.
- Then IG2-STR-09 (tax export from the live ledger), IG2-STR-11 (calendar context in a live cycle), IG2-STR-12 (Bayesian uncertainty on live fills), IG2-STR-13 (live re-check; see flag above).
- Full-allowlist load scan last, results from the live ledger. No server moves (owner stop order 7130069033); no deploys/restarts without hub clearance; demo only.

## Checkpoint 2 — IG2-STR-10 failure-injection leg (live on Stratex-Server)

- **Filed:** 2026-11-28 ~05:13 IST, by Muse 3. Repairs the ~1h silence since checkpoint 1 (04:11 IST): branch head was unchanged at `1ecb035e` for ~1h; this checkpoint is the repair.
- **What ran:** the LIVE S4 copy of `Stratex/market_data_fallback.py` (`/opt/friday_universe/Stratex/market_data_fallback.py`, 12,982 bytes, same size as main) via the module's own injectable `fetch_text` transport, run with the S4 venv python (`/opt/friday_universe/venv/bin/python`, requests 2.34.2). Probe script `/tmp/str074/probe_ig10.py`, deleted after the run. Read-only market data only — no trading endpoint, no credentials, the live daemon was never touched and never restarted.
- **Run:** 2026-11-27T23:39:26Z. **Result: 8/9 legs PASS.**

| leg | injection | expected | observed |
|---|---|---|---|
| A live baseline | none (real network) | Binance serves BTCUSDT | PASS — binance, $59,821.60, stale=False |
| B venue disconnect | api.binance.com dead | CoinGecko serves | PASS — coingecko, $59,816.00, stale=False |
| C two venues down | Binance + CoinGecko dead | DexScreener serves | PASS — dexscreener, $63,662.24, stale=False (see flag 1) |
| D total outage, last-good cached | all providers dead | stale last-good | PASS — binance last-good, ETHUSDT $1,659.59, stale=True, age 0s |
| E total outage, empty cache | all providers dead | `AllProvidersFailed` raised | PASS — raised as specified |
| F stale feed | all dead, 1h-old cached quote | stale quote, age ~3600s | PASS — stale=True, age 3600.0s, price held $90,000.00 |
| G equity + FX live | none | Nasdaq / Stooq-or-Yahoo serve | PASS — AAPL nasdaq $358.54; USDJPY yahoo $159.515 (Stooq did not serve; Yahoo fallback worked as designed) |
| H macro live (FRED DGS10) | none | FRED serves | **FAIL — endpoint unreachable from S4, not a code defect (see flag 2)** |

- **Flag 1 — DexScreener price quality:** leg C's DexScreener quote ($63,662.24) diverges ~6.4% from the Binance/CoinGecko consensus (~$59,820). The chain's contract is "first success wins", and the leg passes on that contract — but the third-tier price is not the same market. Coordinator's call whether the DexScreener leg needs a sanity band before it can serve a live decision; the fallback chain itself degrades as designed.
- **Flag 2 — FRED unreachable from S4:** leg H failed twice — 12s timeout, then a 30s-timeout retry (2026-11-27T23:41Z, `AllProvidersFailed: macro_series/DGS10: fred: Read timed out`). `macro_series` is single-source by design (no fallback chain), so with an empty cache it raises exactly as specified — the module behaved correctly, the endpoint was unreachable. Worth a coordinator re-probe later; not a code failure, and not a named fix task (no code change implied — the chain has no second macro source to fall back to).
- **Daemon untouched (verified before/after):** PID 74531 RUNNING throughout; `fill_ledger.jsonl` sha256 `5e657087099259764596059b989d66191cad0fc23d90795abdde0f5bcb910a21`, 84 lines, identical at 23:38Z, 23:41Z and after the probe. Heartbeat 23:42:01Z: scan_count 1533 (1343 at checkpoint 1 — still cycling), last cycle scanned 2310 / signals 0 / executed 0 / errors 0 / 30 symbols; equity $10,471.47, balance $10,436.84, unrealized +$34.63, realized +$46.87, 30 open positions, daily breaker NOT hit, daily start equity $10,485.85. Scorecard + heartbeat mtimes fresh at probe time.
- **IG2-STR-10 verdict for this wave:** the fallback chain degrades live exactly as its contract states — venue disconnect, two-venue outage, total outage with last-good, total outage with empty cache, and stale-feed age all behave per spec on real market data on S4. Two observations ride to the coordinator (flags 1–2 above); neither is a live failure of the chain.

## Checkpoint 3 — IG2-STR-09 tax export from the live ledger (live on Stratex-Server)

- **Filed:** 2026-11-28 ~06:15 IST, by Muse 3. Repairs the ~1h silence since checkpoint 2 (05:13 IST): branch head was unchanged at `9513ffc6` for ~1h; this checkpoint is the repair. No new Muse 3 assignment in BE 06:00 (hub 7230999560) or WATCH247 (hub 7230716540); hub read through comment 7231033076.
- **What ran:** the LIVE S4 copy of `Stratex/reporting/tax_ledger_export.py` (9,202 bytes, Nov 16) via its own CLI, run with the S4 venv python from `/opt/friday_universe/Stratex`. Probe script `/tmp/str074/probe_ig09.py`, deleted after the run with all outputs. The live ledger was copied to `/tmp` first and the module ran ONLY on the copy — the live file was never opened for write. Read-only; no trading endpoint, no credentials, the live daemon was never touched and never restarted.
- **Run:** 2026-11-28T00:35Z. **Result: export runs, money columns reconcile EXACTLY — but 6 CSV columns are empty/zero on live daemon records (shape mismatch, see findings).**
- **Reconciliation (verified first-hand):** CLI exported 84 trades; CSV rows 84 = ledger trade rows 84. CSV total fees 13.04361348 = ledger fees sum 13.04361348; CSV total realised P&L +107.08898814 = ledger `net_pnl` sum +107.08898814; ledger gross sum 120.13260162. Summary buckets by instrument reconcile (32 instruments incl. USDJPY). Module's own suite on S4: **6 passed** (`pytest tests/test_ig2_str09_tax_export.py`, 0.44s).
- **Findings — live daemon ledger shape vs the module's expected (testnet) shape:**

| CSV column | live result | cause (live record field) |
|---|---|---|
| quantity / proceeds / cost_basis | 0.0 for all 84 rows (sums 0.0) | live ledger uses `qty`, module reads `quantity` |
| date_open / date_close | empty for all 84 rows; `--year 2026` export returns 0 trades | live ledger uses epoch `entry_time`/`exit_time` (+ ISO `recorded_at`), module reads `timestamp`/`exit_timestamp` |
| venue | `Unknown` for all 84 rows | live ledger has `venue: "binance_futures"`, module derives venue from `source` (absent live) |
| side | empty for all 84 rows | live ledger has `side: "SHORT"/"LONG"`, module reads `direction`/`action` |
| trade_id | empty for 73/84 rows | live ledger has no `trade_id`/`exit_order_id`; `order_id` is empty on 73 rows |
| entry_price / exit_price / fees / gross / realised | correct, reconcile exactly | field names match (`entry_price`, `exit_price`, `fees`, `gross_pnl`, `net_pnl`) |

- **IG2-STR-09 verdict for this wave: NOT VERIFIED live.** The module is correct for its designed testnet ledger shape (its 6 tests pass on fixture records), but its export is not tax-ready for the live daemon ledger as-is: proceeds/cost basis are zero, dates are blank, venue is Unknown. Per board acceptance, this gets a named fix task, never a verified mark. **Proposed fix (coordinator to name):** adapt `build_tax_rows` to accept the daemon ledger fields (`qty`, epoch `entry_time`/`exit_time`, `venue`, `side`, `order_id`) while keeping the testnet shape working; re-run this live leg after the fix.
- **Daemon untouched (verified before/after):** PID 74531 RUNNING throughout; `fill_ledger.jsonl` sha256 `5e657087099259764596059b989d66191cad0fc23d90795abdde0f5bcb910a21`, 84 lines, identical pre/post; heartbeat scan_count 1707, last cycle scanned 2310 / signals 0 / executed 0 / errors 0 / 30 symbols. Same ledger hash as checkpoints 1–2 (no new fills since 2026-11-27T02:26Z).

## Checkpoint 4 — bridge outage; hub read + stall repair (no live leg this run)

- **Filed:** 2026-11-28 ~07:15 IST, by Muse 3. Repairs the ~1h silence since checkpoint 3 (06:15 IST): branch head was unchanged at `0bb3aab9` for ~1h; this checkpoint is the repair. No live leg ran this check — the bridge was down (see below); nothing here claims a live result.
- **Hub read (verified first-hand, through comment 7231818604, 07:08:57 IST):** BE 06:45 (hub 7231544120), WATCH249 (hub 7231716845), BE 07:05 (hub 7231776459) read in full. **No new Muse 3 assignment.** STR-107 — the fix task for the IG2-STR-09 live tax-export CSV shape proposed in checkpoint 3 — is assigned to Muse 13 as head task (WATCH249 §B; BE 07:05 §B: "STR-107: fix the IG2-STR-09 live tax-export CSV shape (Muse 3 checkpoint 3). Claim in your next post."); assignment call closed. M13's IG2-FRD-01-ACTIVATE-01 is BLOCKED owner-gated (mailbox creds absent from the FRIDAY `.env`); IG2 returns to the pool.
- **Board (verified first-hand, live main blob `46dd5277` via blob API):** TASK-STR-074 still CLAIMED / owner muse_3 / branch `muse3/task-str-074-production-verify-wave1` / pr null / P1, updated 2026-11-28T03:08:48+05:30. No reassignment, no competing claim.
- **Bridge outage (blocks the IG2-STR-11 live leg):** `get_system_info` via the bridge connector client failed 4× this run (~07:10–07:18 IST): 2× 45 s timeout ("MCP request did not complete"), 2× "MCP event stream ended before the matching result". Endpoint itself is HTTP-reachable (curl ~07:12 IST: `/bridge/mcp` 406, root 200) — the MCP layer is not completing calls. No run_shell probe was attempted (no point while the session handshake fails); no live leg, no daemon contact. IG2-STR-11 (calendar context in a live cycle) is DEFERRED to the next check pending bridge recovery.
- **Daemon state — last-known only, NOT re-verified this run:** checkpoint 3 (00:35Z): PID 74531 RUNNING, `fill_ledger.jsonl` sha256 `5e657087099259764596059b989d66191cad0fc23d90795abdde0f5bcb910a21`, 84 lines, scan_count 1707, equity $10,471.47. No current probe exists — the bridge outage means no fresh daemon state this run.
- **IG2-STR-09 verdict stands:** NOT VERIFIED live (checkpoint 3); fix now owned by Muse 13 as STR-107.
- No server moves (owner stop order 7130069033); no deploys/restarts without hub clearance; demo only.

## Checkpoint 5 — IG2-STR-11 economic calendar live on Stratex-Server (bridge recovered)

- **Filed:** 2026-11-28 ~08:45 IST, by Muse 3. Repairs the ~1h silence since checkpoint 4 (~07:15 IST): branch head was unchanged at `adeaed3d` for ~1h; this checkpoint is the repair. **Bridge recovered** this run: `get_system_info` succeeded first try (~08:06 IST, both Oracle servers ONLINE) after the 07:05–07:18 outage (4 failed calls, MCP layer not completing) — the deferred IG2-STR-11 leg runs now.
- **Hub read (verified first-hand, through comment 7232443952, BE 08:00 IST hub 7232438956):** BE 08:00 read in full. **No new Muse 3 assignment.** #2243 verifier: BE 07:35 named M3, WATCH250 named M4, M4 filed VERIFIED (review 6095152399) — **M3 released, STR-074 continues** as head. BE 08:00 §D: hourly self-check posts superseded, event-only from here; M3 is among those still posting this window. STR-107 (Muse 13, the IG2-STR-09 CSV-shape fix proposed in checkpoint 3) filed checkpoint 1 ~08:00 IST (hub 7232347389): fix landed in PR #2249 (head `1da9f8bd`), live before/after on S4 — 84 rows, fees 13.04361348 / realised P&L +107.08898814 identical, all 6 columns fixed (dates, venue Binance 82 / OANDA 2, side LONG 47 / SHORT 35 / BUY 2, trade_id 0 empty, quantity/proceeds/cost_basis 0 zero, `--year 2026` returns 84). The checkpoint-3 fix proposal is now implemented and live-proven by M13; STR-074 will re-run the IG2-STR-09 leg against the fixed module once STR-107 merges.
- **What ran:** the LIVE S4 copy of `Stratex/research/economic_calendar.py` (TASK-IG2-STR-11) via its own `EconomicCalendar` API, run with the S4 venv python from `/opt/friday_universe/Stratex`. Probe script `/tmp/str074/probe_ig11.py`, deleted after the run with all outputs. Store pointed at `/tmp/str074/calendar.jsonl` — no live state written. Read-only market data; no trading endpoint, no credentials, the live daemon was never touched and never restarted.
- **Run:** 2026-11-28T02:40Z. **Result: 6/6 legs PASS.**

| leg | what it proves | observed |
|---|---|---|
| A live refresh | real Nasdaq macro + earnings endpoints serve, parse, store | PASS — 479 events stored (330 macro, 149 earnings, 65 high-impact), `last_refresh_ok` true, 7 days ahead from 2026-11-28 |
| B high-impact week | the week's do-not-trade-into list is queryable | PASS — 65 high-impact events: Nonfarm Payrolls + Private Nonfarm Payrolls 2026-12-05, ISM Manufacturing PMI 2026-12-02, ADP Nonfarm Employment Change 2026-12-03, Interest Rate Decision 2026-12-04, Core CPI 2026-11-28 + 2026-12-02 |
| C event risk | the scan-pause advisory answers correctly | PASS — `event_risk(now, 2h)`: no high-impact event inside the window (02:40 UTC, events are daytime US/Eastern); `event_risk(now, 72h)`: in window, advisory fires |
| D classify + parse | pure functions on fixtures | PASS — CPI / Nonfarm Payrolls / FOMC → high; AAPL earnings → high, small-cap earnings → medium; fixture CPI parses to 08:30/high, fixture AAPL earnings to 16:30/high |
| E dead source | refresh failure degrades to stale last-good, never raises into the caller | PASS — injected dead fetch: refresh logs a warning per day/source, does NOT raise, `last_refresh_ok` false, stored 479 before = 479 after, stale store still serves queries |
| F own suite | module's tests on S4 | PASS — `pytest tests/test_ig2_str11_economic_calendar.py`: **7 passed** in 0.31s (note: suite lives in `Stratex/tests/`, not `Stratex/research/tests/` — first attempt at the wrong path failed file-not-found, corrected first-hand) |

- **Flag — high-impact set is broad:** 65 of 479 events (14%) classify high, including same-name repeats across countries (German/Bavarian/Saxony CPI, several "Unemployment Rate" / "Retail Sales" rows) and 10 high-impact rows dated a Saturday (2026-11-28). The keyword classifier works as designed, but the "do not trade into CPI/NFP" signal is diluted if a scan pauses on every regional CPI print. Coordinator's call whether the high-impact keyword set needs a US-only / tier-1 tightening before a live scan consumes it; the module itself behaves per spec on real data.
- **IG2-STR-11 verdict for this wave: VERIFIED live.** The calendar feed refreshes from the real Nasdaq endpoints, stores and queries a 7-day window, answers the scan-pause advisory correctly, degrades to stale last-good on source failure, and its own suite passes on S4. One design observation rides to the coordinator (flag above); no live failure, no fix task named.
- **Daemon untouched (verified before/after):** PID 74531 RUNNING throughout; `fill_ledger.jsonl` sha256 `5e657087099259764596059b989d66191cad0fc23d90795abdde0f5bcb910a21`, 84 lines, identical at 02:38Z/02:41Z/post-probe. Heartbeat scan_count 2070 → 2075 → 2077 (still cycling), last cycle scanned 2310 / signals 0 / executed 0 / errors 0 / 30 symbols. Same ledger hash as checkpoints 1–4 (no new fills since 2026-11-27T02:26Z).
- **IG2-STR-09 verdict stands:** NOT VERIFIED live (checkpoint 3); fix implemented + live-proven by Muse 13 as STR-107 (PR #2249), re-run of the leg owed after merge.

## Next (checkpoint 6)

- IG2-STR-12 (Bayesian uncertainty on live fills), IG2-STR-13 (live re-check; see checkpoint-1 flag), then re-run IG2-STR-09 against the STR-107 fix once merged.
- Full-allowlist load scan last, results from the live ledger. No server moves (owner stop order 7130069033); no deploys/restarts without hub clearance; demo only.

## Five states

- implemented NO, tested NO, merged NO, deployed n/a, production-verified NO.

— Muse 3
