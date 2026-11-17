# TASK-STR-RD-020 — Cross-Asset Momentum Rotation with a Pre-Declared Drawdown Brake

**Status: FROZEN before any execution. No cell of this family has been run.**
Machine-readable declaration: `declaration.json`, SHA-256
`fe9b8fbc1808fe646aa87c06cab0797d5a32945abcb94a3b7131eadd87bdd4ec`
(posted on issue #35 with this hash before the runner is executed; the
run additionally requires the coordinator's order).

**Question:** does RD-013's cross-asset momentum rotation, judged on
the same panel, window and bar, survive its own drawdown gate when the
book carries ONE pre-declared portfolio-level drawdown brake — and
does it clear the rest of the programme bar the parent also failed?

## Lineage disclosure (the honest part, up front)

**Mandate.** TASK-STR-RD-013's board entry (VERIFIED 2026-11-15)
records: *"If rotation is ever revisited it needs a risk mechanism
(volatility targeting / drawdown brake) as a NEW pre-declared family,
not a retune of this grid."* This family is that revisit, taking the
drawdown-brake branch of the note. The volatility-targeting branch is
NOT taken.

**Boundary vs RD-013.** RD-013 judged 48 configurations of this exact
signal on this exact panel: 0/48 pass. The drawdown gate (max DD
≤ 20%) failed universally (best −21.0%, median ≈ −35%, worst −60.3%);
significance failed universally (best one-sided p = 5.9e-2 vs 2.5e-5
at N = 2,000); the four cells re-examined here also failed folds (3/5
each) and mostly PF. This family changes exactly ONE thing — the book
carries a portfolio-level drawdown brake — and re-judges under the
same bar on the same OOS window. It is not a retune: RD-013's grid is
not re-run, no RD-013 cell is re-judged, and the brake-off control is
RD-013's existing judged record, not a new arm.

**Boundary vs RD-002.** RD-002's xs_momentum (cross-sectional ROC
ranking, crypto30/forex/comm/idx panels, ATR bracket exits, per-trade
judgement) judged 32 cells, 0 passes (best crypto30 1d OOS PF 1.135).
Different universe, exit mechanics and judgement unit; no RD-002 cell
is re-judged.

**Boundary vs RD-014.** RD-014 already tested A drawdown brake and
failed 0/96 — on a different family on every axis: per-symbol trend
signals (tsmom/EMA) on crypto30 at 4h/1d, volatility-target sizing in
every cell (σ* ∈ {15%, 30%, 60%}), the brake as a grid axis
{none, flat_05, flat_10, half_10} driven PER-SYMBOL by that symbol's
unbraked shadow equity, judged per-episode through the rd2 machinery.
This family has: a portfolio rotation signal (not per-symbol trend),
RD-013's 7-asset cross-asset universe (not crypto30), NO volatility
targeting anywhere, ONE frozen brake (not a brake grid axis, no
brake-off arm), the brake driven at PORTFOLIO level by the BRAKED
book's own equity (not per-symbol shadow equity), and portfolio
period/drawdown judgement (not pooled per-symbol episodes). RD-014's
closing mechanism note named the release rule as the suspect part of
its brake — *"release on the braked book's own recovery or on fresh
signal entry, not on shadow-equity recovery"* — and this family's
release rules are built to that named critique: HALVED releases on the
braked book's own drawdown recovery; FLAT re-enters on fresh signal
entry (the braked book's own recovery is mathematically impossible
while flat, since a flat book's equity is frozen). This design debt to
RD-014's judged post-mortem is declared, not hidden.

**Declared prior: LOW.** The brake addresses gate 4 (drawdown) only.
The four control cells already fail gates besides drawdown. A PASS
requires the braked book to also clear gates the unbraked cells
failed. The family's value is a clean, counted verdict on the brake
hypothesis for rotation; if it fails, the rotation-brake hypothesis
is closed with it. A PASS on this same judged window would be weaker
evidence than a pass on untouched data and would require forward
(demo) confirmation before any promotion.

## The family (frozen)

- **Universe:** RD-013's exact 7 assets (BTCUSDT, ETHUSDT, SOLUSDT,
  BNBUSDT, GOLD, SPX, NDX), byte-identical panel files, SHA-256
  verified against `results_rd13/synthesis.json` (loader refuses any
  mismatch). Decision from evidence 2026-11-17: all 7 files in hand
  and hash-identical; both sources free + keyless. No substitution.
- **Signal:** RD-013's rule verbatim (trailing L-calendar-day return,
  endpoint staleness ≤ 3d, ≥ L+30d history, top-K equal weight,
  long_flat cash rule).
- **Grid: L ∈ {63, 126} × K ∈ {2, 3} = 4 cells = 4 trials.** Cadence
  weekly (Mondays) FIXED; mode long_flat FIXED. Cell-selection
  reasoning (incl. the exclusions of L=21, L=252, K=1) is declared in
  `declaration.json`.
- **The brake (the family's only new mechanism; single frozen
  parameter set, NOT a grid axis):** portfolio-level, on the braked
  book's own daily close-to-close drawdown from its running peak
  (peak never reset; path runs from 2023-01-02, IS era included;
  signal measured on the pre-trade mark at each close; decisions use
  only bars ≤ d and execute at close d):
  - DD ≤ −10% → **HALVED** (exposure scale 0.5)
  - DD ≤ −15% → **FLAT** (scale 0, all cash)
  - HALVED → NORMAL when braked DD recovers to ≥ −5% (own recovery)
  - FLAT → re-enter at scale 0.5 (HALVED, probationary) only at a
    weekly rebalance whose fresh selection would be fully invested
    (all top-K scores > 0); otherwise stay flat another week
  - Levels are fractions of the programme's 20% gate (½, ¾, ¼) — NOT
    fitted to any equity path. **No volatility targeting anywhere.**
- **Costs:** RD-013 table (crypto 16, GOLD 10, SPX/NDX 8 bps RT) and
  mechanism, extended to brake trades; every whipsaw round trip is
  charged. 2×-cost gate as RD-013.
- **Window/bar:** identical window and folds to RD-013 (OOS = period
  starts in [2024-07-01, 2026-11-01)); RD-013's seven gates verbatim
  (gate 4's 20% threshold measured on the DAILY curve with carried-in
  peak — stricter than the parent's, declared) + gate 8: ≥ 200 closed
  OOS episodes AND episode PF ≥ 1.2, else "insufficient OOS trades".
  Owner's DELETE rule on strict per-period OOS PF < 1.2.
- **Bonferroni (frozen method):** N_global = max(ledger entering N at
  run time, 3,893) + 4 — this family charges itself for the declared
  SRS (1) and S-RD1 (1) trials ahead of it whether or not they run
  first. Minimum N_global = 3,897, α ≤ 1.2830e-05.
- **Harness (SHA-256 pinned):** `harness/rotbrake.py`
  `efb411c5e685ebb5f2f92ac54555bd0849b5d162242a7a6bc4b4b50ea213d2db`;
  runner `harness/run_rotbrake.py`
  `be108221a677f6eaf8d34582e6889e07239ffd0f3f0325334978131dfa52963d`
  (refuses n_global < 3,897 before loading any data); 10 synthetic
  tests all passing (`harness/test_rotbrake.py`
  `07e7d2999dc39120bb09c968902d24d1faefce6fe9558dfe769e195928bf5c9f`).
- **Run command (for the future declared run only):**
  `python3 harness/run_rotbrake.py ~/workspace/str-rd2/cache2 <N_global>`

Known limitations (same-window judgement, probationary re-entry
probe costs, daily-close brake granularity, accounting-convention
differences vs RD-013, gate-5 unit change, gate-8 reachability) are
declared in full in `declaration.json`.
