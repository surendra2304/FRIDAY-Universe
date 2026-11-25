# TASK-STR-051-FIX-01 — Checkpoint 2: live-leg verdict (G1, 35 closes)

Muse 18 — 2026-11-25. Live leg run under the coordinator grant (hub #1483 comment 7151724843,
watch072 follow-up; scope confirmed standing in watch073 7151960206): read-only bridge
`run_shell` server 1 (Oracle Server 1), cwd `/opt/friday_universe`, on exactly three files.
No writes, no other servers, no credential reads. No live move (owner stop order stands).

## Sources — pulled first-hand, byte-exact (sha256 verified against the live files)

| File (S1 `/opt/friday_universe`) | Bytes | Lines | md5 | sha256 | mtime |
|---|---|---|---|---|---|
| `Stratex/state/fill_ledger.jsonl` | 38,809 | 80 | `5a8d43a3ef9f32c111280a615d6ceb35` | `2b6fd0fb2c5c926a9c14f8fc39ef549e29ab4ad8d0a4b6908a7996b7833f3493` | Nov 24 01:10 |
| `Stratex/state/reconciliation/daily_2026-11-23.json` | 45,641 | 1,791 + closing `}` (no trailing newline) | `9a11563a666988f19ba293a80e1ffd43` | `4449965642a0793cc693dbdc3677787cb859786acd6e4b1695d93ee20decb602` | Nov 23 19:38 |
| `Stratex/state/reconciliation/daily_2026-11-24.json` | 46,274 | 1,818 + closing `}` (no trailing newline) | `f54994b87973088006492f3a6ba6d25c` | `b66f38d33f6727f41673cef58c1e5567daa0d78a866660b85d8b1edac030de1c` | Nov 24 16:23 |

The S1 ledger is the file M13 pulled (hub 7146269836): same 80 lines / 38,809 bytes / md5
`5a8d43a3…` — identity confirmed before reading. It is NOT the Stratex-Server ledger read
for STR-053 (82 lines / 39,796 bytes, different file). Pull method: chunked `sed -n` ranges
via the granted `run_shell`; each assembled file re-hashed locally until the sha256 matched.
Two pull artefacts are recorded honestly: the 11-23 file needed its un-newline-terminated
final `}` fetched separately (the `wc -l` count hides it), and a probe marker line briefly
appended to the local copy was truncated back out before hashing — the hashes above are of
the final local copies and match the live files exactly.

## Method

Offline matcher `Stratex/scripts/g1_reconcile.py` (checkpoint 1, 11/11 tests pass locally): each
`missing_closes.orders` entry joins to a ledger row on symbol + side (SELL close = LONG-row
exit, BUY close = SHORT-row exit) + qty within max(0.001, 1%) + ledger `exit_time` within
5 minutes of the close first/last fill time; price leg via implied exit
(entry ± realized/qty vs row `exit_price`, 0.5% / 0.5 USDT floor). Verdicts: MATCHED /
MATCHED_PRICE_MISMATCH / AMBIGUOUS / GENUINE_GAP. Ledger `exit_time` is seconds; close fill
times are milliseconds — the matcher converts (×1000) before comparing; this was verified
by reading the code and by an independent spot check below.

## Verdict — 2026-11-24: all 35 closes GENUINE_GAP

- **35 / 35 GENUINE_GAP, 0 MATCHED, 0 MATCHED_PRICE_MISMATCH, 0 AMBIGUOUS.**
- Reported `missing_closes.realized_pnl` **+15.9305 USDT**; sum of the 35 filed orders **+15.9305 USDT** — arithmetic_ok=True.
- **Zero candidates, zero qty-level time-misses:** no close has any ledger row passing symbol+side+qty at any time distance. For 11 of the 35 closes there is no same-symbol+side ledger row at all; for the other 24 a same-symbol+side row exists but with a different qty and/or a far-apart time.
- **Fill-day concentration: 30 of 35 fills are 2026-11-19** (the reset day), 1 on 11-20, 2 on 11-21, 1 on 11-22, 1 on 11-24. G1 is overwhelmingly a Nov-19-reset artefact: the venue closes from the reset day never got ledger rows.
- **Per-symbol:** SUIUSDT +30.4595 (2 closes), ETHUSDT +19.9010 (2), then 26 closes of dust (-0.0055 to -0.1700 each), ALGOUSDT -10.7046 (2), VETUSDT -10.9567 (2), SANDUSDT -11.3637 (2). Total +15.9305.
- **The books still balance:** the 11-24 report `window_identity` is RECONCILED, residual -0.0001 — venue realized -37.2558 = ledger window net -56.2614 + missing closes +15.9305 + window fees 3.0752 (rounding). The +15.93 USDT is real venue P&L with no ledger row: a ledger-completeness gap, not unaccounted money.
- **G-trace stands:** 69 of 80 ledger rows carry no `order_id` (report `gaps` agrees); row-to-venue traceability rests on price/qty/time matching.

### 35-close verdict table (2026-11-24 report, `missing_closes.orders`, in filed order)

| # | Symbol | Order | Side | Qty | Realized (USDT) | Fills | First fill (UTC) | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | TRXUSDT | 1173153567 | BUY | 61.0 | -0.0055 | 1 | 11-19 07:56 | GENUINE_GAP |
| 2 | MANAUSDT | 241723755 | BUY | 188.0 | -0.0376 | 1 | 11-19 07:56 | GENUINE_GAP |
| 3 | FILUSDT | 357157011 | BUY | 30.1 | -0.0993 | 1 | 11-19 07:56 | GENUINE_GAP |
| 4 | DOTUSDT | 664485237 | BUY | 27.0 | -0.0675 | 1 | 11-19 07:56 | GENUINE_GAP |
| 5 | ETHUSDT | 16874886479 | BUY | 0.016 | -0.0389 | 1 | 11-19 07:56 | GENUINE_GAP |
| 6 | SUIUSDT | 1099990253 | BUY | 13.8 | -0.0414 | 1 | 11-19 07:56 | GENUINE_GAP |
| 7 | BCHUSDT | 2612293141 | BUY | 0.055 | -0.0440 | 1 | 11-19 07:56 | GENUINE_GAP |
| 8 | INJUSDT | 331708071 | BUY | 2.0 | -0.1700 | 2 | 11-19 07:56 | GENUINE_GAP |
| 9 | ETCUSDT | 682043496 | BUY | 2.2 | -0.0286 | 1 | 11-19 07:56 | GENUINE_GAP |
| 10 | LTCUSDT | 1612113572 | BUY | 0.29 | -0.0203 | 1 | 11-19 07:56 | GENUINE_GAP |
| 11 | ATOMUSDT | 642763075 | BUY | 14.28 | -0.0428 | 1 | 11-19 07:56 | GENUINE_GAP |
| 12 | XRPUSDT | 3546043750 | BUY | 13.9 | -0.0528 | 1 | 11-19 07:56 | GENUINE_GAP |
| 13 | LINKUSDT | 1073129051 | BUY | 1.26 | -0.0277 | 1 | 11-19 07:56 | GENUINE_GAP |
| 14 | VETUSDT | 457619917 | BUY | 2123.0 | -0.0361 | 1 | 11-19 07:56 | GENUINE_GAP |
| 15 | NEARUSDT | 662684725 | BUY | 4.0 | -0.0840 | 1 | 11-19 07:56 | GENUINE_GAP |
| 16 | AAVEUSDT | 444082337 | BUY | 0.2 | -0.1000 | 1 | 11-19 07:56 | GENUINE_GAP |
| 17 | BTCUSDT | 28686637814 | BUY | 0.0008 | -0.0820 | 1 | 11-19 07:56 | GENUINE_GAP |
| 18 | SOLUSDT | 4247827494 | BUY | 0.18 | -0.0342 | 1 | 11-19 07:56 | GENUINE_GAP |
| 19 | APTUSDT | 500703285 | BUY | 35.2 | -0.0528 | 1 | 11-19 07:56 | GENUINE_GAP |
| 20 | AVAXUSDT | 559212681 | BUY | 3.0 | -0.0930 | 1 | 11-19 07:56 | GENUINE_GAP |
| 21 | UNIUSDT | 497754303 | BUY | 3.0 | -0.0870 | 1 | 11-19 07:56 | GENUINE_GAP |
| 22 | BNBUSDT | 2682338050 | BUY | 0.03 | -0.0306 | 1 | 11-19 07:56 | GENUINE_GAP |
| 23 | DOGEUSDT | 2392235543 | BUY | 225.0 | -0.0540 | 1 | 11-19 07:56 | GENUINE_GAP |
| 24 | XLMUSDT | 743599548 | BUY | 97.0 | -0.0233 | 1 | 11-19 07:56 | GENUINE_GAP |
| 25 | OPUSDT | 367842932 | BUY | 165.7 | -0.0497 | 1 | 11-19 07:56 | GENUINE_GAP |
| 26 | HBARUSDT | 336905538 | BUY | 230.0 | -0.0391 | 1 | 11-19 07:56 | GENUINE_GAP |
| 27 | ALGOUSDT | 430047109 | BUY | 146.3 | -0.0424 | 1 | 11-19 07:56 | GENUINE_GAP |
| 28 | ADAUSDT | 1340462696 | BUY | 70.0 | -0.0280 | 1 | 11-19 07:56 | GENUINE_GAP |
| 29 | SANDUSDT | 339382246 | BUY | 481.0 | -0.0385 | 1 | 11-19 07:56 | GENUINE_GAP |
| 30 | ARBUSDT | 365776235 | BUY | 128.1 | -0.0512 | 1 | 11-19 07:56 | GENUINE_GAP |
| 31 | ETHUSDT | 16876077891 | BUY | 0.148 | +19.9399 | 2 | 11-20 19:14 | GENUINE_GAP |
| 32 | SUIUSDT | 1100728824 | BUY | 304.4 | +30.5009 | 1 | 11-21 06:16 | GENUINE_GAP |
| 33 | VETUSDT | 458616420 | BUY | 42328.0 | -10.9206 | 1 | 11-21 13:28 | GENUINE_GAP |
| 34 | SANDUSDT | 340506462 | BUY | 5219.0 | -11.3252 | 1 | 11-22 12:16 | GENUINE_GAP |
| 35 | ALGOUSDT | 431920550 | SELL | 2569.2 | -10.6622 | 1 | 11-24 09:11 | GENUINE_GAP |

## Q1 — 2026-11-23 vs 2026-11-24 (side-by-side, from the same run)

| | 2026-11-23 | 2026-11-24 | Delta |
|---|---|---|---|
| Report status | RECONCILED | RECONCILED | — |
| Ledger rows | 78 | 80 | +2 |
| Ledger net (all rows) | +160.6847 | +138.7507 | -21.9340 |
| Window ledger net | -34.3752 | -56.3092 | -21.9340 |
| Closes on venue | 103 | 106 | +3 |
| Venue true net | -7.7825 | -40.3787 | — |
| Identity residual | -0.0001 | -0.0001 | — |
| Daily-job matching | NO_MATCH 39 / BOTH 37 | NO_MATCH 39 / BOTH 39 | — |
| Missing closes | 34 | 35 | +1 |
| Missing realized | +26.5927 | +15.9305 | -10.6622 |
| Matcher verdicts | 34 GENUINE_GAP | 35 GENUINE_GAP | — |

The 11-24 set is the 11-23 set plus exactly one close: **ALGOUSDT SELL 2569.2, -10.6622 USDT,
order 431920550, filled 11-24** — the only 11-24-dated fill in the set, and the whole delta
(26.5927 - 10.6622 = 15.9305). The daily job re-files the same 34 unresolved closes each
day; the backlog is not growing except by that one close. The 11-23 per-symbol picture is
identical to 11-24 (SUI +30.4595, ETH +19.9010, SAND -11.3637, VET -10.9567) except ALGO,
which was -0.0424 on 11-23 (1 close) and -10.7046 on 11-24 (2 closes).

## Independent spot checks (not the matcher)

- **TRXUSDT BUY 61.0, fill 11-19 07:56 UTC, order 1173153567:** the only TRXUSDT SHORT ledger row is qty 521.0, exit 11-19 07:36, net 0.0, no order_id — same morning, 20 min apart, but qty differs 8.5×. Not a match; confirms the matcher is not missing a qty match.
- **SUIUSDT BUY 304.4, +30.5009, fill 11-21 06:16, order 1100728824** (the largest single close): ledger SUI rows are LONG 60.9 (11-19 07:36), LONG 300.5 (11-20 02:32, net -10.6613), SHORT 80.0 (11-21 13:08). The 300.5 row is the wrong side (a BUY close exits a SHORT) and ~28 h away; the SHORT row is the wrong qty (80.0 vs 304.4) and ~7 h away. Not a match.
- **Time-unit check:** ledger `exit_time` is epoch seconds with a fractional part (e.g. 1794658249.801); close fill times are epoch milliseconds (e.g. 1795074998291). The matcher multiplies the ledger time by 1000 before comparing — verified in the code (`exit_ms = int(... * 1000)`) and by the spot checks above, where times were compared in UTC directly. A units error would have shown as systematic ~1000× offsets; the spot checks show genuine qty/side absences instead.

## Notes / limits (stated, not hidden)

- The report `gaps` text per-symbol figures (SUI +30.50, ETH +19.94, SAND -11.33, VET -10.92, ALGO -10.66) differ from the filed orders by up to ~0.05 USDT per symbol, in both directions; realized+commission does not explain the difference either. The order-level sums reconcile exactly to the reported totals (+15.9305 / +26.5927), so this is a presentation difference in the daily job's gaps text, not a P&L hole. Flagged for the daily-job owner (STR-044), not fixed here.
- No per-fill prices or VWAP exist in the filed reports, so the price leg is the aggregate implied-exit check only; no close reached that leg (zero candidates). A live venue read would be needed to re-verify VWAP per order — not granted, not attempted.
- The daily job's own matching classes (NO_MATCH 39 / BOTH 39 on 11-24) count a different population than `missing_closes` (35); the 4-order difference is the daily job's internal accounting (venue fills vs filed missing orders) and was not chased — the matcher verdict above is on the filed `missing_closes.orders` exactly as the task states.
- Ledger rows whose exit time is a Nov-19 reset fallback (e.g. 11-19 07:36, net 0.0) match nothing by design; they surface in the table only via their absence — no row was forced to fit.
- No re-run of the daemon was attempted: a re-run writes reports, outside the read-only grant. The verdict is a read-only recomputation from the pulled rows.

## What this closes

G1 is reconciled as **genuine gaps, all 35 (+15.93 USDT)**: the S1 ledger has no row for any of
them, the venue P&L identity still balances, and the gap is concentrated on the Nov-19 reset.
The fix is the verdict + the reusable matcher (`g1_reconcile.py`, checkpoint 1) + this record;
back-filling the 35 rows into the ledger would be a write and is NOT done here — it needs a
separate write-scoped decision by the coordinator. Machine-readable verdicts:
`docs/collaboration/TASK-STR-051-FIX-01-RESULT.json` (this run, exit 0).

— Muse 18
