# TASK-STR-074 CHECKPOINT 2 — live probes (production-verify wave 1: IG2-STR-09..13)

Worker: Muse 11. Claim: branch `muse11/task-str-074-production-verify-wave1`
@ 21f59056 (CP1). This CP2 follows the CP1 plan verbatim; the TP4
live-leg spec adoption ruling is still owed (spec NOT re-read, not
adopted — divergence: none from CP1; TP4 spec pending ruling).

Probe runs: 2026-11-27 ~18:19–18:49 IST, first-hand by Muse 11.
Method: STR-070/STR-073 precedent — bridge run_shell on Server 2 ->
ssh (S2 Oracle key `Oracle-Cloud-x-AWS-Key`) to Stratex-Server
13.211.78.20. Read-only probes, except /tmp scratch files (probe
scripts, probe results, tax CSV/summary, calendar store, empty/bad
test ledgers, FRED CSV) — all created, verified, deleted afterwards
(`ls /tmp/str074_*`: no such file). No daemon start/stop, no trades /
orders, no config or code changes, no failure injection, no moves.

## Live environment at probe time

- Stratex-Server up 3d 8:38, load 0.70. Checkout `main` @ 3db55adf
  (behind main f0d575f1 — same commit STR-073 noted; the exercised
  files are byte-identical to main, see below, so this run's evidence
  is unaffected). Venv python with requests 2.34.2.
- stratex-daemon inactive / dead / Result success / NRestarts 0;
  :8003/health 503 — documented baseline for a stopped daemon, not a
  new failure. (S1 :8003 curl returns 000 — nothing listens on S1:8003;
  the daemon lives on Stratex-Server.)
- Ledgers present: `/opt/friday_universe/Stratex/testnet_trade_ledger.jsonl`
  (197 lines) and `paper_trade_ledger.jsonl` (3 lines).

## Byte-identity: all five modules are current main code

md5 on Stratex-Server == md5 of main f0d575f1 for every file:

| File | md5 |
|---|---|
| `Stratex/reporting/tax_ledger_export.py` | 979bd091ff0ab360a604a12dcdbf6621 |
| `Stratex/market_data_fallback.py` | de02e2f41fecbcbd72d9cd72e585f6aa |
| `Stratex/research/economic_calendar.py` | 3b1b19c8d73e9a20e8e12e96cc1decaa |
| `Stratex/rigorous_backtest/ig/bayesian_uncertainty.py` | 33c680aa49808c10482b0fdb0b006605 |
| `Stratex/rigorous_backtest/ig/RESULTS_BOX_THEORY.md` | b4104bd2c1526ac308c8979e48fc99cc |

## Per-item verdicts

### IG2-STR-09 — Tax-ready trade-ledger export — VERIFIED LIVE

Live task: run the export CLI in the server checkout against the live
testnet ledger (`python -m reporting.tax_ledger_export --ledger
…/testnet_trade_ledger.jsonl --out /tmp/str074_tax.csv --summary
/tmp/str074_tax_summary.json`).

Result: CLI rc=0. 197 trades exported, CSV holds 197 data rows, the
summary JSON is byte-equal to the in-memory summary. Summary totals:
trades 197, total_fees 10.79956616, total_realised_pnl -65.09342417
(Binance 124 trades / +22.82963119; MULTI_VENUE_RECONCILIATION 73
trades / -87.92305536). Reconciliation against the ledger's own
figures, computed independently in the probe: realised P&L matches
exactly; fees match to 1e-8 (10.79956616 vs 10.79956615 — float
summation-order rounding, not a defect; the summary has no
total_gross_pnl key, so no gross total is published to reconcile).
Failure cases (as coded): empty ledger -> 0 rows, no crash; malformed
file (one bad-JSON line, one empty-symbol row, one non-numeric
quantity) -> bad line skipped, empty-symbol row skipped, non-numeric
quantity coerced to 0, valid rows kept (2 rows, realised 0.8), no
crash. Observation (cosmetic, not a verdict-changer): `by_year`
buckets the 73 reconciliation rows under year "1795" — their
timestamps are epoch seconds, and the bucketing reads the string
prefix as a year.

### IG2-STR-10 — Free market-data fallback chain — PARTIAL (3/4 legs live)

Live task: `FallbackChain(cache_path=None)` on the server; one live
quote per chain + the FRED macro leg.

Result:
- crypto BTCUSDT via **binance** $61,452.01, stale=False.
- equity AAPL via **nasdaq** $358.4049, stale=False.
- fx EURUSD via **yahoo** 1.0969, stale=False — Stooq (first in the
  fx chain) failed and the chain fell over to Yahoo, i.e. the
  fallback itself working live.
- macro DGS10 via FRED: **NOT VERIFIED — live failure.** The module
  (`default_fetch_text`, requests, UA
  `FRIDAY-Stratex-Research/1.0 (+free public data)`) raised
  `AllProvidersFailed` on read timeout, 3 consecutive attempts at the
  12 s timeout, plus once more at 30 s. The endpoint is healthy from
  the same server: `curl` fetches
  `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10` in
  0.318 s (HTTP 200, 269,519 B, latest row 2026-11-24 4.91).
  Discriminating test, same client, same server: requests + browser
  UA stalls (20 s timeout); requests + `curl/8.5.0` UA returns 200 in
  0.2 s. FRED's edge stalls this server's requests client unless the
  UA looks like curl. The stale path (all providers down -> last-good
  with `stale=True`) is unit-testable only and was not exercised live;
  with `cache_path=None` there is no last-good to serve.

Fix task owed from this record: **TASK-IG2-STR-10-FIX-01 — FRED macro
leg stalls from Stratex-Server.** The requests-based fetch with the
module UA never completes against FRED while curl succeeds in 0.3 s;
give the FRED fetch a curl-compatible client/UA (or an alternate macro
source) and re-probe live. Do NOT mark IG2-STR-10 verified until the
macro leg returns a live value.

### IG2-STR-11 — Economic/earnings calendar feed — VERIFIED LIVE

Live task: `EconomicCalendar(store_path=/tmp/str074_cal.jsonl)`,
live refresh from the Nasdaq endpoints, dedup + `event_risk` advisory.

Result: refresh returned 484 events stored, `last_refresh_ok=True`
(sources ok); `upcoming(7)` 484 events; `high_impact_events(7)` 66;
a second refresh stored 484 again (0 new, dedup holds — the store
does not grow on re-refresh). `event_risk()` for the live window:
`in_risk_window: false`, window 2.0 h, advisory "No high-impact
event inside the window.", `last_refresh_ok: true`. The failed-refresh
failure case (keep serving last stored events) was not observable —
no source failed during the probe; it stays unit-testable only.

### IG2-STR-12 — MCMC/Bayesian strategy-uncertainty modelling — NOT VERIFIED (live data cannot supply R)

Live task (CP1 plan): run the MCMC on the live forward-fill
R-multiples (paper ledger) with the fixed seed; verify deterministic
output and the P(expectancy > 0) / P(PF clears bar) evidence pack.

Result: the live data cannot supply credible per-trade R-multiples.
- Paper ledger: 3 closed trades (need >= 10, >= 5 per side per the
  module's own `MIN_TRADES`/`MIN_PER_SIDE` guard) and NO `r_multiple`
  field (keys: direction, entry/exit price/time, quantity, gross/net
  pnl, fees, funding, margin_released, signal, strategy, status).
- Testnet ledger: `r_multiple` exists, but ONLY on the 73
  MULTI_VENUE_RECONCILIATION rows — never on the 124 Binance fills.
  Those 73 values are not credible per-trade R: range -19,268.63 to
  +71,580.43, 31 exact zeros; sampled rows are zero-pnl placeholders
  (`gross_pnl 0.0, net_pnl 0.0, r_multiple 0.0, trades 0`,
  exit_reason SL_TP_BROKER). The MCMC was run on them to see what it
  does: deterministic (two runs identical, 8,000 draws retained) but
  the posterior is meaningless — observed expectancy 913.0479 R,
  expectancy median -1743 R, CI90 [-3.8e39, 5e8], PF median 0.2662;
  gate `supports_promotion: false` (P(expectancy>0) 0.3743, P(PF>=1.2)
  0.3599). Determinism is confirmed live; a meaningful posterior is
  not — the gate refuses for the wrong reason (absurd input, not a
  weak strategy). The 124 Binance fills carry no risk field either, so
  no R is derivable from any live ledger as stored.
  `forward_reconciliation.jsonl` (284 lines) carries only
  reconciled_at/status/detail — no R.

Fix task owed from this record: **TASK-IG2-STR-12-FIX-01 — forward
fills must record per-trade risk.** Record the risk (or R) on each
closed fill in the forward/paper ledger so R-multiples exist, and
re-probe the MCMC once >= 10 closed fills with credible R exist.
Do NOT mark IG2-STR-12 verified until then.

### IG2-STR-13 — Box Theory RD candidate — VERIFIED (record-check only, as planned)

No live run (nothing trades). Record check: RESULTS_BOX_THEORY.md +
`box_theory_results.json` + `box_theory_provenance.json` are
byte-identical to main f0d575f1 (md5s above / fc15c3c7… /
b87ca41a…). Results JSON: task TASK-IG2-STR-13, trial_floor 3885,
T1 pooled OOS PF 0.805696 — the declared 2026-11-16 FAIL verdict
stands (16,842 OOS trades, expectancy -0.218%/trade, PF 0.805,
Bonferroni p = 1.0, family CLOSED). Server-side: 0 "box" mentions in
`/opt/friday_universe/Stratex/forward_signal_log.jsonl` (no box
signals/trades). Repo-wide: `box_theory` mentions outside
`rigorous_backtest/ig/` are other families' declarations
(grid_mm TASK-STR-RD-023, xsrev TASK-STR-RD-019) citing the shared
panel/provenance and the global trial counter only — no promotion, no
forward registration of Box Theory, nothing trades. Family CLOSED
stands.

## Task-level verdict: PARTIAL — 3/5 verified live

- VERIFIED LIVE: STR-09 (export + reconciliation + failure cases),
  STR-11 (live refresh, dedup, event_risk), STR-13 (record-check).
- PARTIAL: STR-10 (3/4 legs live; macro leg fails live — fix task
  TASK-IG2-STR-10-FIX-01 named above).
- NOT VERIFIED: STR-12 (no credible live R-multiples — fix task
  TASK-IG2-STR-12-FIX-01 named above).
- Acceptance legs NOT RUN (unchanged from CP1): live demo-daemon
  cycle (daemon down; restart is a server move, frozen; clearance
  owed); failure injection (venue disconnect, stale feed — held per
  STR-070 precedent + owner stop order; coordinator ruling owed);
  full-allowlist load scan (no allowlist applies to these five
  utilities; the daemon's own scan is a separate live leg — same
  disposition as STR-070, ruling owed).

STR-074 goes IN_REVIEW on this evidence once the work PR lands;
closure is Muse's call. STR-10 and STR-12 stay unverified until
their fix tasks land and are re-probed live.

## Run state

- Usage 62% fresh (reset Nov 29 6:00 PM IST); additional tokens 0% —
  above 50%, no wrap-up trigger.
- Queue: STR-074 (head, claimed, CP2 filed) -> IG-FRD-003-FIX-01 ->
  SEN-022.
- Next: rebase this branch onto current main (2882aac6) before the
  work PR; board flip to CLAIMED rides in the work PR (one task = one
  PR when done/blocked, per owner rule).
- TP4 live-leg spec adoption ruling still owed (not re-read; CP2 ran
  on the CP1 plan, no divergence from it).

— Muse 11, 2026-11-27 ~18:50 IST
