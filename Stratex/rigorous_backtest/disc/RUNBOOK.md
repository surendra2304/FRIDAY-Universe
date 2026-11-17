# RUNBOOK — TASK-STR-RD-023 declared run (grid / passive MM)

**DO NOT execute the run until Gate A and Gate B both pass.**
Executing the runner IS the backtest: the declaration allows
exactly ONE run of this frozen cell. This runbook was written at
declaration time (2026-11-17); nothing here has been run against
the panel beyond the loader-level provenance verification.

## The frozen artefacts

| Artefact | SHA-256 |
|---|---|
| declaration/grid_mm_declaration.json | `2b5d807a5b00c893b1dd28af4d23b943a7fb587c15dc9a7e6cf8a5bdd8a7d66c` |
| declaration/GRID_MM_DECLARATION.md | `b8257ccf9e6614ecfcb18e4a2c5fc9cef5f44c828cc06503cc4517bd1ba76255` |
| harness/grid_mm.py | `f77d95a542a337807ebd0a5a6979b5b0cb901e910959a9e35026e090b38b0650` |
| harness/test_grid_mm.py | `c4c3b0d51330f6233b22ae8a825d49c9b7df32ad1fd9017d9b37fef42096af1a` |
| harness/run_grid_mm.py | `b80ca4047e2e15367520c4f02e01516ec07c2d0fc1689b459d3e211e53dcd554` |
| harness/stage_panel.py | `1204459604889f794e822156e32d7040c2b2176218512a0863931ff836eccee1` |

Repo placement (Gate A PR, branch `claude/task-str-rd-023`):
all six files under `Stratex/rigorous_backtest/disc/`, plus the
TASK-STR-RD-023 board entry (prepared and validated in
`~/workspace/str-grid/board-tree/` — VALID, 466 records on the
be50fa74 extract; re-diff against fresh main before shipping).

## Gate A — declaration merged, hash-identical

1. Ship the PR from a FRESH main; supervisor review; merge.
2. In a fresh checkout of the merged main, verify:
   `sha256sum Stratex/rigorous_backtest/disc/grid_mm_declaration.json`
   == `2b5d807a…a7d66c`. Any mismatch = STOP (the merged
   declaration is not the declared one).
3. Verify the harness pins in the same checkout match the table
   above, and run the synthetic tests there:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest Stratex/rigorous_backtest/disc/test_grid_mm.py -q -p no:cacheprovider`
   → 11/11 PASS required. Any failure = STOP.

## Gate B — programme queue clear

The programme runs ONE declared run at a time. Before this run:
the SRS declared run (TASK via PR #883 lineage) must have
concluded, AND the S-RD1 run (TASK-IG2-STR-19) must have
concluded. If either is still pending, STOP — this run waits.

## Panel

Already verified at declaration time (2026-11-17, loader
verify-only mode): BTC/ETH/SOL, 108,192 rows each, zero missing
bars, csv_sha256 == Box Theory provenance — record in
`~/workspace/str-grid/panel_provenance.json`. The runner re-checks
every symbol against that record (`--expected-provenance`) and
aborts on any deviation. On a write-capable host the runner's
first load also populates the cache at `--panel-dir`
(default `~/workspace/str-grid/panel`); the loader re-verifies
cache hashes on every read. To pre-stage the cache:
`python3 Stratex/rigorous_backtest/disc/stage_panel.py`
(default mode; `--repo` defaults to the repository the script
ships in, resolved from its own path, and `--out` defaults to
`~/workspace/str-grid` — writes `~/workspace/str-grid/panel/` +
refreshes `~/workspace/str-grid/panel_provenance.json`. Pass
`--repo`/`--out` explicitly to stage against another tree or
location.)

## Trial floor

Read the programme trial counter from the rd-reconcile ledger AT
RUN TIME and pass it as `--trial-floor` (the runner has no
default, deliberately). At declaration time the counter stood at
3,891 declared; the SRS cell takes it to 3,892 when run and
S-RD1's to 3,893, so the expected floor for this run is 3,894
(α ≈ 1.284e-05) — but state the ledger's actual figure, never
the expectation.

## The one declared run

From the root of the fresh main checkout verified in Gate A:

```
PYTHONPATH=. python3 Stratex/rigorous_backtest/disc/run_grid_mm.py \
    --repo . \
    --out ~/workspace/str-grid/run-output \
    --expected-provenance ~/workspace/str-grid/panel_provenance.json \
    --trial-floor <N from the rd-reconcile ledger at run time>
```

The runner refuses to start if `RESULTS.md` already exists in
`--out` — there is no second run. It writes `results.json` +
`RESULTS.md` there.

## Verdict rules (frozen by the declaration)

- Pooled OOS round trips (programme stack) < 200 → the verdict is
  exactly **"insufficient OOS trades"**.
- PASS requires every component at BOTH cost stacks (programme
  26 bps effective RT and 2× shadow 42 bps RT): expectancy_net > 0,
  PF_net ≥ 1.2, ≥ 200 OOS round trips, ≥ 4/5 positive folds,
  holdout_check, Bonferroni p < 0.05/N. A PASS makes the family a
  forward-test CANDIDATE only (Phase-3 protocol, demo-only).
- Anything else = FAIL; strict OOS PF < 1.2 closes and DELETES
  the family per the owner's standing rule.

## Recording

1. Copy the verdict + headline numbers (per-stack OOS trades,
   expectancy, PF; touch_no_fill total; the trial floor used)
   into `~/workspace/str-grid/STATE.md`.
2. Post the verdict to GitHub issue #35 (check-before-post;
   read back to confirm exactly one copy).
3. Flip the board entry via a fresh-main board PR with the
   verdict evidence; validator VALID before and after.
