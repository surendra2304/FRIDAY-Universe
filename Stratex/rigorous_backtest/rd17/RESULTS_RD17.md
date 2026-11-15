# RESULTS — TASK-STR-RD-017: funding-carry forward PAPER SIMULATION

**Status: the instrument is built, tested, and RUNNING; the forward clock
has started. There is no result yet, and there cannot be one before
2027-05-15 at the earliest (see §5). Any P&L figure from the proof window
below is NOISE — stated plainly, per the tasking and the declaration.**

## 1. What this is

RD-009 (hash-frozen backtest, completed 2026-11-15) found exactly one
structure with a real signal: positive funding carry, `always_pos`
(long spot / short perp, always-on) — 150 episodes, expectancy +1.273%,
PF 2.960, surviving 2× costs and Bonferroni, failing only the ≥200-episode
check that an always-on book structurally cannot satisfy. RD-009 §7
specified a forward test instead of a promotion. This task builds and
starts that forward test: a paper book on **live Binance mainnet public
data** (demo-fapi cannot host spot+perp), full accounting, immutable
hash-chained ledger, pre-declared evaluation bar.

## 2. Declaration and claim (frozen before the first data point)

- Declaration: `declaration.json` (this directory), SHA-256
  `9769000a50979a602bcaf58721b66489492082d77befa1742c14127a445317d7`.
- Claim: issue #35 comment **6893763575**, created **2026-11-15T11:40:16Z**
  (GitHub's timestamp, independently re-fetched and verified by this crew:
  the comment contains the declaration hash and states no ledger row,
  entry or mark existed yet). The sim's first data point (SIM_START) is
  later than the claim. 
- **Timestamp wart, disclosed:** the declaration's internal
  `declared_at_utc` field reads `2026-11-15T11:58:00Z`, which does not
  match GitHub's 11:40:16Z claim timestamp (a clock-source discrepancy in
  the authoring step). The substantive freeze guarantee — hash public
  before any data point — is verified; the internal field is not relied
  on and is left as-is because the file is hash-frozen.
- The sim adds **ZERO** backtest trials to the programme floor (forward
  measurement, declared in `trial_accounting`).

Book (declaration governs): RD-009's crypto30 set unchanged; 1,000 USDT
one-leg notional × 30 symbols; cross-margin portfolio account, perp margin
cash 1.0× notional (effective 1× — RD-009's liquidation evidence rules out
3× isolated); flat declared MMR 1.0%; RD-009's 1× cost model verbatim
(0.19% entry / 0.19% exit of one-leg notional) plus a parallel 2×-cost
shadow in every MARK; funding booked from the exchange's published
settlement prints only, cashflow = q × mark-at-print × rate.

Evaluation bar: RD-009 §7's pass standard, with the episode unit honestly
replaced by the SYMBOL-SEGMENT (declared adaptation, not smuggled):
≥6 months AND ≥2 confirmed regime turns; forward net yield ≥ +1.29%/yr on
one-leg notional sustained; segment expectancy > 0; segment PF ≥ 1.2;
breadth ≥ 50%; 2×-cost expectancy > 0; zero unresolved kill trips.
The ≥200-episode and Bonferroni checks are declared inapplicable to a
≤30-segment always-on book.

## 3. Implementation

`Stratex/rigorous_backtest/rd17/` (layout follows the rd9/rd16 precedent):

- `carry_paper_sim.py` — engine. Book state is rebuilt by replaying the
  ledger, so restarts are safe and funding prints dedupe by
  (symbol, fundingTime). Poll cycle: fetch bundle → archive gzipped raw
  bundle (SHA-256 recorded in the ledger rows) → SIM_START/ENTRY on first
  poll → FUNDING rows per settled print → MARK every poll → liquidation
  check (equity ≤ maintenance margin) → MARGIN_REVIEW at 25% adverse
  excursion → SYMBOL_DROP on a >5%-of-notional 30d funding flip →
  KILL_STOP on negative rolling-90d net → daily REGIME_SNAPSHOT + turn
  confirmation.
- `server_fetch.py` — one-shot public-data fetcher (stdlib only, no keys):
  premiumIndex marks, spot tickers, settled funding prints, and
  mark-at-print from ONE batched markPriceKlines range call per symbol.
- `bridge_fetch.py` — proof transport only: executes the identical
  fetcher on FRIDAY Server 1 through the MCP bridge, because the Muse
  sandbox's egress proxy receives Binance's geo-restriction response for
  futures endpoints (verified by this crew; spot via
  data-api.binance.vision works from the sandbox, perp/funding do not).
  Bundles are tagged `bridge-s1`; a server deployment uses
  `--transport rest` and tags `rest`.
- `test_carry_paper_sim.py` — 9 offline tests, all passing: T3
  frozen-price funding identity, funding sign convention (short receives
  positive rates), entry-cost math vs the declaration, ledger hash-chain
  verification + replay, symbol-drop trigger (and no-drop on a small
  flip), regime-turn confirmation on a fabricated series, flip-back NOT
  confirmed, and the first-poll since regression (below).
- `README.md` — the runbook (daemon + cron forms, state files, restart
  behaviour, evaluation procedure).

**First-poll failure, disclosed:** the sim's very first live poll
(2026-11-15T11:58:46Z) failed — recorded in the ledger as seq 1, type
ERROR. Cause: the engine requested funding history from epoch (since=0)
for the not-yet-open book; the fetcher pulled 100 prints per symbol and
the run exceeded the bridge's 120s server-side cap and was killed. No
market data was booked and the book had not opened. Fix: first-poll
since = poll time (pre-entry prints are never bookable under the
declaration; the next poll re-fetches from entry_ts), plus the batched
kline fetch above. A regression test pins the behaviour. The book opened
on the retry — SIM_START is the clock start, not the failed attempt.

**Regime-turn detector interpretation, disclosed:** F14 (trailing-14d mean
settled funding, daily snapshot) decays gradually through an exact 0.0
snapshot when a regime flips; sign(0) is no regime, so the detector
compares against the last established (non-zero) sign at or before 14
snapshots earlier. The declared rule — new sign persists 14 consecutive
snapshots — is unchanged. A synthetic test caught the naive version
silently never firing; the fixed detector confirms a sustained flip and
ignores a flip-back.

## 4. Proof run (sandbox, bridge transport)

State directory: `~/workspace/rd-017/state/` (ledger.jsonl + bundles/).
Daemon: `carry_paper_sim.py daemon --transport bridge --interval 900
--claim-comment 6893763575`, started 2026-11-15T12:00:34Z (after the fix;
first attempt 11:51:11Z produced only the ERROR row above).

Live evidence from the running instance (report run 2026-11-15T12:02Z):

- Ledger: 33 rows — seq 1 ERROR (the disclosed first-poll failure),
  seq 2 **SIM_START at 2026-11-15T12:01:56Z** carrying
  `declaration_sha256 = 9769000a…` (matches the frozen declaration) and
  `claim_comment = 6893763575`, seqs 3–32 the 30 ENTRY rows, seq 33 the
  first MARK. Hash chain verifies on load.
- First MARK (at entry prices): equity **59,943.00** (= 30,000 spot +
  30,000 perp margin cash − 57 entry costs), **net_1x = −57.00** —
  exactly 30 × 1.90 entry cost, to the cent — **net_2x = −114.00** (the
  2×-cost shadow), margin ratio 199.9 (MM = 1% × 30,000 = 300).
- T2 decomposition identity: diff 0.0 for all 30 symbols at the first
  MARK (segment PnL −1.90 = entry cost; basis and funding still zero).
- T1 funding identity: vacuous so far (no settlement inside the run yet).

The funding settlement cadence is 8h (00:00 / 08:00 / 16:00 UTC). The book
opened after the 08:00Z settlement, so the first settlement inside the run
is **2026-11-15T16:00:00Z — PENDING at ship time**; the daemon (900s
polls) books it automatically as 30 FUNDING rows, and T1 then becomes a
real check. The daemon keeps running after this report ships; the
coordinator can read the ledger at any time with
`python3 carry_paper_sim.py report --state-dir ~/workspace/rd-017/state`,
and the first-settlement capture is a one-command verification.

## 5. Honest limits

- **Proof-window P&L is noise.** Entry costs are 57 USDT (0.19% × 30,000);
  at the current regime (~+1.29%/yr on one-leg notional) the book expects
  roughly +1 USDT/day of funding. Hours of marks say nothing about the
  strategy; they prove the accounting, not the edge.
- **Earliest honest evaluation: 2027-05-15** (SIM_START + 6 months), and
  only if ≥2 regime turns have confirmed by then; if turns lag, the
  judgement waits for them. A **regime turn** means: a held symbol's
  trailing-14d mean settled funding (F14) changes sign versus its last
  established sign and the new sign persists 14 consecutive daily
  snapshots.
- The sandbox-bridge instance is a proof vantage, not the durable home:
  the runbook's server deployment (`--transport rest`, 300s cadence) is
  the intended long-running form. Migrating = copy the state directory;
  restarting fresh would restart the 6-month clock.
- Current funding regime is thin/mixed (at the pre-start probe:
  BTC last rate +9.36e-06, ETH −2.533e-05, SOL −9.93e-05 per 8h) —
  consistent with RD-009's W5 picture of ≈+1.29%/yr, i.e. even a perfect
  forward run is measuring a small effect that needs the full window.

## 6. Five states

- Implemented: YES (engine, fetcher, both transports, tests, runbook).
- Tested: YES — 9/9 offline tests; live end-to-end poll proven (book
  opened on live data at 12:01:56Z, accounting identities exact at
  entry; first settlement capture pending per §4 — the daemon is
  running and books it automatically).
- Merged: NO — PR open, awaiting coordinator merge per protocol.
- Deployed: NO server deployment; the sandbox proof instance is running
  (state dir above). Server deployment is a coordinator step under the
  README runbook.
- Production-verified: N/A by design — this is a research paper book; it
  touches no production system, daemon, or config.
