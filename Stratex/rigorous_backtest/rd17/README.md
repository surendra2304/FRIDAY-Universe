# TASK-STR-RD-017 — Funding-carry paper simulation (forward test of RD-009)

A **paper** book that runs RD-009's one surviving structure — `always_pos`
(long spot / short perp, always-on) — against **live Binance mainnet public
data**, with full position / funding / fee accounting in an immutable,
hash-chained ledger. No orders, no accounts, no API keys. It exists to start
the forward-measurement clock RD-009 §7 specified: the sim is judged no
earlier than **2027-05-15** (≥6 months AND ≥2 confirmed funding-regime
turns). Any P&L shown before that date is noise by construction — the entry
cost alone (0.19% of notional) dwarfs hours-to-days of funding at the current
regime rate (~+1.29%/yr on one-leg notional).

Frozen declaration: `declaration.json` in this directory,
SHA-256 `9769000a50979a602bcaf58721b66489492082d77befa1742c14127a445317d7`,
posted in the claim comment on issue #35 (comment 6893763575) **before** the
sim's first data point. The declaration governs; if code and declaration
disagree, the declaration wins and the code is wrong.

## Files

| File | Role |
|---|---|
| `declaration.json` | The frozen pre-declaration (book, sizing, margin model, costs, evaluation bar, kill criteria). |
| `carry_paper_sim.py` | The engine: ledger, book replay, poll cycle, kill/liquidation/regime logic, report + sanity checks T1/T2. Stdlib only. |
| `server_fetch.py` | One-shot public-data fetcher (spot + perp mark + settled funding prints + mark-at-print). Runs wherever direct Binance egress works. Stdlib only. |
| `bridge_fetch.py` | Sandbox-proof transport: runs `server_fetch.py` on FRIDAY Server 1 via the MCP bridge (the sandbox proxy cannot reach Binance futures directly). Not needed on a server. |
| `test_carry_paper_sim.py` | Offline tests (T3 frozen-price identity, funding sign, cost math, hash chain, symbol-drop, regime-turn confirmation). No network. |

## The book (summary — declaration is authoritative)

- 30 symbols (RD-009's crypto30 set, unchanged), long spot + short perp,
  1,000 USDT one-leg notional each (30,000 total), entered once at the first
  poll's observed prices, always-on. Exits only via the declared kill rules,
  liquidation, or coordinator end.
- **Cross-margin portfolio account**, perp margin cash 1.0× notional per
  symbol at entry (effective perp leverage 1× — RD-009's liquidation
  evidence rules out 3× isolated). Maintenance margin = 1.0% of open perp
  notional (flat, declared). Liquidation if equity ≤ MM at any poll.
- Costs = RD-009's 1× model verbatim: spot taker 0.10%/side, perp taker
  0.05%/side, slippage 0.02%/leg-side → 0.19% entry, 0.19% exit. A parallel
  **2×-cost shadow** is tracked in every MARK row.
- Funding settles from the exchange's own published prints
  (`/fapi/v1/fundingRate`); cashflow = q × mark-at-print × rate, short
  receives when rate > 0. Mark-at-print is the close of the 1-minute
  mark-price kline at the print timestamp (fallback: poll mark, flagged
  `mark_approx`).

## Runbook

State lives in one directory: `ledger.jsonl` (the book — everything is
rebuilt by replaying it) plus `bundles/` (gzipped raw data snapshots; each
data row in the ledger carries its bundle's SHA-256). **Restart behaviour:
safe at any point** — kill the process, restart it, the book is replayed
from the ledger and polling resumes; funding prints are deduplicated by
(symbol, fundingTime), so a restart never double-books a settlement.

### On a server (durable deployment — direct REST transport)

```bash
cd Stratex/rigorous_backtest/rd17
python3 carry_paper_sim.py daemon \
  --state-dir /var/lib/rd17-carry-sim \
  --transport rest --interval 300 \
  --claim-comment 6893763575
```

Or cron-shaped (equivalent; the daemon is just a loop around `poll`):

```cron
*/5 * * * * cd /path/to/rd17 && python3 carry_paper_sim.py poll \
  --state-dir /var/lib/rd17-carry-sim --transport rest \
  --claim-comment 6893763575 >> /var/log/rd17.log 2>&1
```

systemd sketch: `ExecStart` = the daemon command above, `Restart=on-failure`,
`WorkingDirectory` = this directory (the engine reads `declaration.json`
from its own folder for the SIM_START hash).

Cadence guidance: 300s on a server (funding settles every 8h; marks every
5 min are far more than the accounting needs and keep the margin watch
honest). The sandbox proof instance runs at 900s because every poll crosses
the bridge.

### In the Muse sandbox (proof transport)

```bash
python3 carry_paper_sim.py daemon --state-dir ~/workspace/rd-017/state \
  --transport bridge --interval 900 --claim-comment 6893763575
```

The bridge transport exists only because the sandbox's egress proxy gets
Binance's geo-restriction response for futures endpoints; it executes the
identical `server_fetch.py` on Server 1 and returns the same bundle JSON.
Bundles are tagged `bridge-s1` in the ledger; server bundles are tagged
`rest`. **The durable run should be (re)started on a server with
`--transport rest`**; if it is restarted fresh, that is a new SIM_START and
the 6-month clock restarts — prefer migrating the state directory instead
(copy `ledger.jsonl` + `bundles/`; the book replays identically).

### Reporting / evaluation

```bash
python3 carry_paper_sim.py report --state-dir <dir>
```

Prints book status, per-symbol segment accounting, confirmed regime turns,
kill trips, and the sanity checks: **T1** recomputes every funding cashflow
from the archived raw bundles and compares against the ledger (rows booked
with an approximate mark are listed, not silently passed); **T2** checks the
per-symbol decomposition identity segment PnL = basis + funding − entry
cost at the last MARK.

At the judgement date (≥2027-05-15 and ≥2 confirmed turns), evaluate exactly
per the declaration's pass standard: forward net yield ≥ +1.29%/yr on
one-leg notional sustained, segment expectancy > 0, segment PF ≥ 1.2,
breadth ≥ 50% of closed segments positive, 2×-cost expectancy > 0, zero
unresolved kill trips. Anything else is FAIL or NOT-YET-JUDGEABLE — never a
pass.

**Regime turn, operationally:** per held symbol, F14 = mean of settled
funding rates over the trailing 14 days, snapshotted daily (00:00 UTC). A
turn opens when F14's sign changes versus the last established sign and is
**confirmed** when the new sign persists for 14 consecutive daily snapshots
(dated at its opening snapshot). Interpretation note: a gradual F14 decay
passes through an exact 0.0 snapshot; sign(0) is no regime, so the baseline
is the last non-zero sign at or before 14 snapshots earlier. Unconfirmed
flips are recorded in the snapshots only.

**Cross-check:** Binance publishes monthly funding-rate archives on
data.binance.vision; the ledger's FUNDING rows for any completed month can
be reconciled against that archive as an independent audit of the live
collection path.
