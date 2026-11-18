# Stratex Self-Experiments — design (TASK-STR-EXP-001)

Owner's order, 2026-11-18: *"make Stratex experiment by itself."*
This is the Stratex slice of the Self-Upgrade Programme — the shared
mechanism in `~/workspace/self-upgrade/DESIGN.md` (every agent learns
from its own work and upgrades itself; no agent depends on Muse or
any outside party), applied to the agent whose discovery programme
was already closest to this shape. It mirrors Forge's idle loop
(TASK-FRG-017, PR #971), including the lesson of its review condition
C2: the host-load gate ships from the start, not in a follow-up.

## What the loop does

`Stratex/self_experiments/` is an autonomous research loop that keeps
extending the admitted strategy bench (the near-miss re-audit,
`~/workspace/str-nearmiss/REPORT.md`: 128 second-tier rows of ~3,899
recorded trials) without any outside party. One cycle:

1. **Gates** (re-checked every cycle, in order): kill switch
   `STRATEX_SELF_EXPERIMENTS` must be exactly `on` — default OFF,
   stricter than FRG-017 because this loop can admit entries to a
   trading lane; host-load gate (1-minute load average below 0.7 ×
   CPU count); an injectable work probe (the production wiring
   supplies the daemon-activity probe at activation); daily cap of 4
   experiments; 600 s per-experiment time box; one at a time.
2. **Propose** from the closed catalogue (below), deterministically,
   skipping anything already declared.
3. **Declare**: the proposal — hypothesis, variant, members, data
   window — is written to the append-only experiment ledger with the
   sha256 of its canonical form BEFORE anything runs. The run path
   re-verifies the declaration and recomputes the hash: work that was
   never declared, or whose content differs from its declaration, is
   refused. Pre-declaration is enforced by the record format, not by
   convention.
4. **Run** on the provenance-verified stream store (below). Every
   judged evaluation increments the persistent global trial counter
   FIRST; the post-increment value is that trial's Bonferroni
   denominator.
5. **Judge** under the frozen bars (`judge.py`, constants in
   `bounds.py` — the bars are code in this PR, not data the loop can
   reach):
   - **PROVEN** (full bar, unchanged): expectancy > 0, PF ≥ 1.2,
     ≥ 200 OOS trades, ≥ 4/5 positive folds, one-sided p < 0.05 / N,
     pooled holdout expectancy > 0 (every member must carry holdout
     data, else PROVEN is unreachable — fail-closed).
   - **FORWARD_TEST** (the owner's second tier, 2026-11-18):
     expectancy > 0, PF ≥ 1.05, ≥ 200 OOS trades.
   - Otherwise **FAIL**: recorded closed, never admitted.
6. **Admit** (passers): an entry in exactly the FWD-003 registry
   shape is written to the loop's admissions registry (see below).
7. **Lesson**: a procedural-type memory through
   `mesh.memory_fabric` (owner STRATEX) into Stratex's private
   section for every verdict; a FAIL lesson is ALSO written to the
   universal section — the owner's standing rule R, so one agent's
   mistake teaches all ten. Lessons are mirrored in a local ledger
   first; failed deliveries stay pending and are retried.

## The closed catalogue

Declared in `catalogue.py` as code. Slice 1 implements ONE family
end-to-end — **combinations of already-admitted streams** (members
must share panel and timeframe; the combination is the equal-standing
union of the members' judged OOS trade streams, pooled exactly):

- `combination_pair`, `combination_triple` — all pairs/triples in a
  panel/timeframe group.
- `combination_cluster_champions` — the champion (highest recorded
  PF) of each declared mechanism cluster (trend / breakout /
  reversion / volatility / pattern), combined — the owner's
  2026-11-18 amendment that combinations go beyond 2–3 members.
- `combination_greedy_forward` — greedy forward selection up to 10
  members; EVERY candidate evaluation inside the search is a counted
  trial with its own ledger record; only the final set is judged for
  admission.

Declared but NOT implemented in slice 1 (catalogue entries with
`implemented=False`; the loop never proposes them):
`parameter_variant` (new parameter variants within pre-declared
grids) and `exit_sizing_gate_variant` (exit/sizing/regime-gate
variants of live streams) — both need the harness re-runner over
stored market data and are named follow-up slices.

Combination semantics, stated plainly: pooling trade lists judges the
union book's trade quality. It is NOT the Stage-C daily-book
accounting (the audit itself warns that accounting is not the live
sleeve's sizing). Capital contention between members trading the same
symbol is arbitrated live by the lane's frozen heat caps, not by this
judgement.

## Data — the provenance-verified stream store

The loop judges only stored research data it can trace
(`store.py`). A store holds one JSON per stream: OOS per-trade net
returns grouped by fold, holdout aggregates, the recorded pooled
metrics, and a provenance block (source record file + sha256). The
manifest carries every stream file's sha256; loading verifies all of
them and refuses the store on any mismatch.

Stores are built by `self_experiments/export_stream_store.py` from
the RD-002 backup row files. Fold assignment is by entry time in
[oos_start, oos_end) — the harness's convention, verified empirically:
the exporter ASSERTS, for every stream, that the derived per-fold
trades/wins reproduce the recorded `per_fold` exactly, per-fold
expectancy/PF within 1e-6, the derived holdout (OOS-era trades on the
recorded untouched-symbol subset) reproduces the recorded untouched
trades/expectancy, and the recomputed t-stat/p reproduce the recorded
`trade_stats` within 1e-3/1e-5. A stream that fails reconciliation
never enters a store.

This PR ships a test fixture store of 6 real crypto30 1d streams
(the live lane's bollinger p50_sd2.0 and shock k1.0, plus tier rows
vol_adaptive ema12_26_nogate, donchian n55_b26, ts_momentum roc72,
stoch_reversion k14_raw), exported with those assertions passing and
figures matching the audit exactly. The production store build is a
coordinator-run exporter invocation over the full backup at
activation time.

## The trial counter

Persistent JSON in the loop's data directory, seeded at **3,899** —
the programme counter at RD-020 (sources: `rd020-record/STATE.md`,
"Programme trial counter now 3,899"; the near-miss REPORT headline).
The seed and its source are recorded in the counter file; a file
below the seed raises (no silent resets). Concurrent crew rounds
(RD-021, RD-025) advance the programme counter outside the loop; at
activation the coordinator reconciles this counter upward to the
recorded programme value if it has moved.

## Admissions — the registry path, and its honest limit

An admitted combination is written to the loop's admissions registry
(data-directory JSON) in the FWD-003 entry shape: `status
FORWARD_TEST`, `forward_protocol: True`, `forward_lane
"FORWARD_TEST"`, `lane_assets` = the judged universe (read from
`config_strategy` — the loop reads config, never writes it),
`risk_per_trade_pct 0.001`, `max_heat_pct 0.02` (the frozen FWD-006
lane terms, stamped from `bounds.py` constants), and a reason string
carrying the judged figures, the declaration id, and the trial
number. `admissions.merged_registry(base, admissions)` is the view
the daemon side consumes; it never overwrites a governed entry (a
collision raises), and `revoke()` removes an admission — every
admission is reversible. The tests classify an admission through the
daemon's own `strategies.strategy_registry.governance_status_for`
and get `FORWARD_TEST`.

The honest limit, also stamped on every admission
(`"execution": "PENDING_ENSEMBLE_MODULE"`): no executable ensemble
module exists yet, so the daemon's governance fail-closes an admitted
combination and it cannot place an order until the slice-2 ensemble
module lands. This is exactly FRG-017's posture — the loop maintains
the registry; production adoption is a separate gated step. A PROVEN
verdict is recorded as proven-eligible; promotion to VALIDATED
travels the Universe change path (Forge builds, Sentinel gates,
Cortex schedules), never the loop's own call.

## Hard bounds (test-asserted)

- **Risk parameters are read-only to the loop.** The package contains
  no write path to `config_strategy.py`,
  `measurement/forward_guard.py`, or any risk file; its writes are
  confined to its own data directory. Admission risk fields are
  frozen constants, not inputs. Defence in depth: a guard
  (`bounds.assert_no_risk_touch`) refuses any proposal or
  caller-supplied admission payload that names a risk field
  (risk/sizing/stop/heat/leverage/kill/…) — the tests drive synthetic
  risk-touch payloads at both the declaration and admission paths
  and both refuse.
- **Demo venues only**: admissions are FORWARD_TEST lane entries;
  the lane itself is demo-only fail-closed in
  `strategies/strategy_registry.py`.
- **Guardrails are not self-editable**: the catalogue, the bars, the
  caps and the kill switch live in code and environment — none in
  the loop's data directory.
- **Everything logged, everything reversible**: append-only ledger;
  admissions revoke; lessons are memories, not mutations.

## Activation (coordinator step, NOT in this PR)

`run_forever()` and `start_if_enabled()` ship in the package,
deliberately NOT hooked into `run_daemon.py`. Activation, later, by
the coordinator: build the production stream store with the
exporter, reconcile the trial counter, set
`STRATEX_SELF_EXPERIMENTS=on`, wire the driver with the
daemon-activity probe, deploy, and watch the first cycles. Slice 2
(the ensemble module) is what turns admitted combinations into
executable lane members.

## First light (fixture data, in tests)

On the shipped fixture the loop's first cycle judges the
cluster-champion ensemble — vol_adaptive ema12_26_nogate + shock
k1.0 + stoch_reversion k14_raw: pooled PF 1.2643 over 1,719 OOS
trades, 4/5 positive folds, p ≈ 1.2e-05 against the Bonferroni
threshold 1.28e-05 at N=3,900, holdout expectancy +2.9% — a PROVEN
verdict on the pooled record, recorded as proven-eligible and
admitted to the lane registry with execution pending the ensemble
module. That is the pooled-trade judgement doing its job on recorded
data; live forward evidence remains the settler for anything that
actually trades.
