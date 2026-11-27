# TASK-STR-074 CHECKPOINT 1 — scoping (production-verify wave 1: IG2-STR-09..13)

Worker: Muse 11. Claim: branch `muse11/task-str-074-production-verify-wave1`
@ eb7f81d0 (claim-time main = merge of board PR #2106, 2026-11-27 14:48:53 IST).
Board record on main 3db9f11a (11,286 lines, line 8246): status AVAILABLE /
owner muse_11 / branch null / pr null, updated 2026-11-27T12:11:00+05:30 —
the CLAIMED flip rides in the work PR per the follow-up directive §4;
the branch-side claim was verified by ls-remote (eb7f81d0).

Acceptance (verbatim from the board record):
- PRODUCTION-VERIFY (owner standard 2026-11-24: merged code is NOT
  implemented): live extreme-condition verification of TASK-IG2-STR-09,
  TASK-IG2-STR-10, TASK-IG2-STR-11, TASK-IG2-STR-12, TASK-IG2-STR-13.
- Extreme-condition test: live demo-daemon cycle on Stratex-Server on real
  market data + failure injection (venue disconnect, stale feed) +
  full-allowlist load scan; results filed from the live ledger.
- For EACH item: run it in the live agent on a real task, file the live
  evidence (what ran, on which server, with what result, incl. the failure
  case). A code-only report is rejected — the task closes only on live
  evidence per item.
- Any item that fails live gets a named fix task filed from this record;
  do not mark a failing item verified.

## The five items (board records + merges verified first-hand)

| Item | Title | Board status | PR / merge |
|---|---|---|---|
| IG2-STR-09 | Tax-ready trade-ledger export | MERGED (archive board) | #688 / 978799db |
| IG2-STR-10 | Free market-data fallback chain | MERGED (archive board) | #691 / 8eef510e |
| IG2-STR-11 | Economic/earnings calendar feed for Stratex research | MERGED (archive board) | #697 / f20a84c8 |
| IG2-STR-12 | MCMC/Bayesian strategy-uncertainty modelling for Stratex RD | MERGED (archive board) | #725 / caa4c4c2 |
| IG2-STR-13 | Box Theory RD candidate — declared backtest RUN: FAIL, family CLOSED | VERIFIED (live board, 2026-11-16) | #729 / fe403867 |

Files (all merged 2026-11-16, present on main 3db9f11a):
- STR-09: `Stratex/reporting/tax_ledger_export.py` (223 lines) +
  `Stratex/tests/test_ig2_str09_tax_export.py`. Reads the canonical fill
  ledger (`testnet_trade_ledger.jsonl` / `live_trade_ledger.jsonl`) and emits
  a per-trade CSV + summary JSON. Per-trade realised-P&L export, NOT a
  FIFO/LIFO engine, not tax advice. CLI: `python -m
  reporting.tax_ledger_export --ledger … --out … --summary …`.
- STR-10: `Stratex/market_data_fallback.py` (303 lines) +
  `Stratex/tests/test_ig2_str10_fallback_chain.py`. Free public endpoints,
  ordered chains (crypto: Binance -> CoinGecko -> DexScreener; equity:
  Nasdaq -> Stooq -> Yahoo; fx: Stooq -> Yahoo; macro: FRED CSV).
  First success wins, cached as last-good; all providers down returns
  last-good with `stale=True`; every result names its provider. Transport
  injectable (`fetch_text`). Read-only market data, no credentials.
- STR-11: `Stratex/research/economic_calendar.py` (310 lines) +
  `Stratex/tests/test_ig2_str11_economic_calendar.py`. Macro + earnings
  from Nasdaq public calendar endpoints, stored as JSONL, deduped on
  (date, name, type); failed refresh keeps serving last stored events
  (`last_refresh_ok` flag); deterministic impact table (CPI/NFP/FOMC/GDP
  HIGH); `event_risk(now, hours)` is advisory only, never touches the
  execution engine.
- STR-12: `Stratex/rigorous_backtest/ig/bayesian_uncertainty.py` (301 lines)
  + `Stratex/rigorous_backtest/ig/tests/test_bayesian_uncertainty.py`.
  Stdlib-only Metropolis-Hastings MCMC over R-multiples, two chains, fixed
  seed, deterministic; reports P(true expectancy > 0) and P(true PF clears
  the bar) as gate evidence. RESEARCH-ONLY: places no orders, promotes
  nothing by itself.
- STR-13: results in `Stratex/rigorous_backtest/ig/RESULTS_BOX_THEORY.md` +
  `box_theory_results.json` + `box_theory_provenance.json`. Declared run
  2026-11-16: FAIL (crypto30 @ 15m pooled walk-forward OOS 16,842 trades,
  expectancy -0.218%/trade, PF 0.805, Bonferroni p = 1.0 at floor N = 3,885).
  Family CLOSED; nothing promoted, nothing registered for forward testing,
  nothing trades. Global trial counter 3,891 after this run.

## Prior work on this task (TP4)

Claim of record: Muse TP4, branch `musetp4/task-str-074-production-verify-wave1`
@ 2eee6607 — CP1 (1c3481a9, "read-only prep, live clearance requested") and
a live-leg spec (2eee6607, "Tier A/B legs per item, clearance requested",
`docs/collaboration/TASK-STR-074-LIVE-LEG-SPEC.md`, 84 lines). The claim
lapsed/released (board: "verified AVAILABLE / owner null on main 64e97ece",
then queued pos 3 for muse_11). The spec file itself was NOT re-read in
this run: the branch fetch tripped an execution-risk check, so no content
from that branch was opened, checked out, or run. Whether TP4's Tier A/B
leg design is adopted or superseded is a coordinator/Muse ruling owed
before CP2; this CP1 scopes from the board records + the STR-070 precedent
below, which is the same method TP4's CP1 used.

## Precedent: TASK-STR-070 (Muse 5, PR #1688, IN_REVIEW)

Per-item live exercise on Stratex-Server via bridge run_shell (S2 -> ssh):
byte-identity check of each module vs main, run in the server's deployed
checkout on live market data, read-only except one disclosed /tmp scratch
file (created, verified, deleted). Verdict PARTIAL: 5/5 items exercised
live, but failure injection NOT RUN (coordinator ruling owed; owner stop
order freezes server moves) and full-allowlist load scan NOT RUN (no
allowlist applies to those research utilities). The programme doc
PRODUCTION-VERIFICATION-PROGRAMME.md is NOT in the repo — re-confirmed
absent from main 3db9f11a (repo-tree search); acceptance is taken from the
STR-074 board record itself.

## Live environment at CP1 time (16:13–16:20 IST, first-hand)

- S1 + S2 ONLINE (bridge get_system_info). S2 checkout branch
  `musetp13/task-frd-046-storage-repair-sequences` @ 83d53187 — NOT main;
  byte-identity checks must target the Stratex-Server checkout, not S2.
- FRIDAY /health 200: direct EC2 15.134.130.145:10000 (overall healthy,
  observed 16:17:37 IST, Python 3.10.22) and duckdns route 200.
- Memora S1 :8002 PID 1448930, elapsed ~12h54m — NO seventh restart (sixth
  ~03:24 IST stands). Log 201 lines: 0x401, 199x200, 168 /health 200s.
  Sentinel :8008 PID 1449170; Forge :8006 PID 1531569 (solo restart
  ~05:58 IST); Cortex :8009 untouched.
- S1 disk 51% (49G/97G, 48G avail) — up from 48% (47G, 51G avail) at
  15:13 IST, ~2G growth in the hour; flag, not a blocker. S1 mem 66 MB
  free / 265 MB avail.
- S2 disk 91% (44G/49G, 4.9G avail) — the hourly swing continues (96% at
  12:13, 90% at 13:13/14:13). S2 mem 97 MB free / 290 MB avail.
  Caddy active/running (recovery holds). VyralX.service masked
  (symlink -> /dev/null, Nov 26 19:36), NRestarts=123 — the counter
  discrepancy (123 vs 0 across runs) persists; the masked state itself is
  confirmed first-hand, loop dead.
- Stratex-Server 13.211.78.20 (ssh from S2 with Oracle-Cloud-x-AWS-Key):
  stratex-daemon inactive / SubState dead / Result success / NRestarts 0;
  :8003/health 503. The 503 is the documented baseline for a stopped
  daemon (repo AGENTS.md: Stratex returns 503 with no loaded strategy or
  live heartbeat) — not a new failure.

## CP2 plan (per-item live probes, Stratex-Server, read-only)

Common: byte-identity check of each module file on Stratex-Server vs main
3db9f11a before running; run in the server's deployed checkout; /tmp
scratch only, deleted after; no daemon start/stop, no trades/orders, no
config or code changes, no failure injection.
- STR-09: run the export CLI against the live ledger on the server; verify
  CSV rows + summary totals reconcile to the ledger's own figures; failure
  case = ledger with zero closed trades / malformed row handling (as coded).
- STR-10: exercise the live chains (crypto_price BTCUSDT, equity, fx) from
  the server; record which provider served each number. Failure case: the
  stale path (all providers down -> last-good with `stale=True`) is
  unit-testable only — a live provider outage cannot be induced read-only;
  record the live provider actually served instead.
- STR-11: live calendar refresh from the Nasdaq endpoints; verify JSONL
  store, dedup, and `event_risk` advisory for a live window. Failure case:
  a failed refresh keeps serving last stored events — observable only if
  Nasdaq fails during the probe; otherwise record the live refresh.
- STR-12: run the MCMC on the live forward-fill R-multiples (paper
  ledger) with the fixed seed; verify deterministic output and the
  P(expectancy > 0) / P(PF clears bar) evidence pack from real fills.
- STR-13: record-check ONLY — confirm RESULTS_BOX_THEORY.md + JSONs on
  main, confirm no promotion / forward registration / trades since the
  2026-11-16 FAIL verdict; no live run (nothing trades).

## Blockers (all pre-existing; no M11 action)

1. Demo-daemon cycle leg: daemon dead (see above); restart is a server
   move, frozen; clearance owed (coordinator/owner). The per-item probes
   do NOT need the daemon (standalone research utilities, same as STR-070)
   — but the acceptance's "live demo-daemon cycle" leg cannot be satisfied
   while it is down.
2. Failure injection (venue disconnect, stale feed): NOT RUN — held per
   STR-070 precedent + owner stop order; coordinator ruling owed.
3. Full-allowlist load scan: no allowlist applies to these five utilities
   (caller-supplied data, no venue allowlist); the daemon's own scan is a
   separate live leg — same disposition as STR-070, ruling owed.
4. Hub #1483 frozen at 2,500 comments (verified 16:1x IST; open, updated
   2026-11-27T00:44:02Z) — no status post possible; CP1 is branch-recorded,
   announcement pending the successor hub (coordinator's call).
5. TP4 live-leg spec adoption: ruling owed (see Prior work). Do not start
   CP2 probes until Muse rules the spec adopted or superseded — or run CP2
   on this CP1's plan and note the divergence.

## Run state

- Usage 61% fresh (reset Nov 29 18:00 IST); additional tokens 0% — above
  50%, no wrap-up trigger.
- Crons verified: muse11-hourly-self-check enabled (interval 1h, this run);
  muse11-weekly-reset enabled (Sun 18:10); muse11-work-request absent
  (removed — correct mid-task).
- Queue: STR-074 (head, claimed) -> IG-FRD-003-FIX-01 -> SEN-022.
- Next: CP2 live probes per the plan above (after the TP4-spec ruling or
  on this plan with the divergence noted); rebase this branch onto current
  main before the work PR; board flip to CLAIMED rides in the work PR.

— Muse 11, 2026-11-27 ~16:25 IST
