# TASK-STR-085 — CHECKPOINT 1: DUPLICATE — S-24 already declared, run and CLOSED under TASK-IG-STR-06

**Task:** TASK-STR-085 (Stratex: SK System confluence — Fib zone plus broken structure entry), P3.
**Claim of record:** hub #1483 comment 7155770973 (2026-11-25 ~12:52 IST); branch `muse20/task-str-085` @ `be3f303e`.
**Checkpoint:** 1 — scoping / duplication finding. No backtest run, no new code.

## Finding (plain)

TASK-STR-085 is a duplicate of completed, verified work. Its source — stratex package S-24, item `DYeU6nSBl9K`, the SK-System Fib/BOS confluence model — is the same family TASK-IG-STR-06 already declared, ran and closed. The supervisor already ruled on exactly this: S-24 is the same family/source, "so no separate S-24 test exists or is added" (`Stratex/rigorous_backtest/ig/CONFLUENCE_RESULTS.md`, corpus scope note). Re-running it would duplicate 4 trials and violate the declaration's own closing term ("Failing it closes the family").

## Evidence (all first-hand from main `be3f303e`, 2026-11-25 ~12:55 IST)

1. **Same source item.** STR-085 board record: "Source: stratex package S-24 (item DYeU6nSBl9K)". IG-STR-06 board record defect field: "IG corpus item DYeU6nSBl9K (SK-System Fib/BOS confluence model) had no RD registration". Same item, same model.
2. **Declaration frozen before any run.** `Stratex/rigorous_backtest/ig/declaration.json`, sha256 `43c025e1ce4dffd16d21d7cbd1218dc11006bdc85c77a933d66785cbdc280300`, declared 2026-11-15 (commit `7ffcf10179`, "TASK-IG-STR-06: RD candidate family: Fib/BOS confluence (pre-declared)"). It freezes stop (leg origin), targets (1.272R / 1.618R), entry (BOS confirmation close), invalidation, instruments (crypto30 + forex_cross41 panels, 1h/4h), and the frozen bar — the "missing rules" STR-085's acceptance asks to be frozen before any run. Sizing is returns-basis per the programme bar (expectancy/PF on per-trade returns), so it cannot change the verdict.
3. **Declared run executed, verdict DELETE.** `Stratex/rigorous_backtest/ig/CONFLUENCE_RESULTS.md` + `confluence_results.json`, landed 2026-11-16 (commit `7230ae6fcb`, "TASK-IG-STR-06: land the declared-run results — fib_bos_confluence FAIL 0/4 cells, family CLOSED"). ZERO of 4 cells pass the programme bar; trials +4 (3,885 → 3,889, Bonferroni α = 1.2857e-05, best p = 0.230). Per-cell pooled OOS: crypto30 1h — 18,466 trades, expectancy −0.1641%, PF 0.818, folds 0/5; crypto30 4h — 3,923 trades, expectancy +0.0694%, PF 1.041, folds 3/5 (closest cell; 2×-cost shadow expectancy −0.0900%); forex_cross41 1h — 14,047 trades, expectancy −0.1105%, PF 0.318; forex_cross41 4h — 3,868 trades, expectancy −0.0994%, PF 0.572. Results posted to issue #35 comment 6924993040.
4. **Board status VERIFIED.** TASK-IG-STR-06 on main: status VERIFIED, owner muse_ai, PR #466; next_action "Done — research complete, zero passers: the fib_bos_confluence family is CLOSED per the declaration's own terms; NOTHING from this family is wired into any forward lane".
5. **STR-085 filed after closure.** STR-085 board record created 2026-11-25 (updated 03:10 IST), nine days after the family closed, in the coordinator's Instagram adoption re-audit batch 3 under the owner's "DEFAULT = IMPLEMENT" correction — filed without noticing IG-STR-06 already covered S-24.

## What this means for STR-085

- The done-condition ("the declared run completed with an honest verdict under the frozen bar") is already satisfied by IG-STR-06's work; the verdict was DELETE (family closed).
- No new run is authorised by this record: a re-run would be a duplicate trial, and a variant would need a NEW pre-declaration naming what differs, at the then-current trial floor (3,891 as of 2026-11-16) — STR-085 names no variant.
- No code, no tests, no backtest in this checkpoint. Nothing was executed locally; no bridge grant sought — there is nothing to execute.

## Ruling requested from Muse

- Rule STR-085 VOID as a duplicate of TASK-IG-STR-06 (already done + closed), with the board flip AVAILABLE → CLOSED (reason: duplicate of IG-STR-06, family tested + closed 2026-11-16) riding in the closing work PR — or name the distinct delta if one exists.
- Re-slot Muse 20: my queue after STR-085 is empty (STR-084 moved to Muse 8 in watch083). Per the blocked-head rule the head is released here; the work-request cycle is re-armed to pull the next pool task, Stratex + VyralX first.

## Five states

- implemented: NO (no new implementation — the family implementation already exists under IG-STR-06)
- tested: NO (no new run — the declared run already happened, 2026-11-16)
- merged: NO
- deployed: NO (no live leg; demo-only research family, closed)
- production-verified: NO (n/a — closed family, nothing trades)

## Usage

10% of free weekly limit (verified 2026-11-25 ~12:52 IST); reset Dec 1, 11:00 AM IST. Not exhausted.

— Muse 20, 2026-11-25 ~13:00 IST
