# TASK-STR-075 — Checkpoint 1: repo-side mapping (2026-11-24 ~23:15 IST)

Claim: hub #1483 comment 7138192201 (Muse 6, ~22:08 IST), central-pool pull model
(owner directive 7136890552). Branch `muse6/task-str-075-prod-verify`, base main
`6e3fe04`. Board flip AVAILABLE → CLAIMED rides in this PR.

## Method

Read each of the five IG2-STR board records on main `6e3fe04` and verified the
named merged artefact exists on that main (`git cat-file -e`). No live moves:
owner stop order still in force; no bridge / Stratex-Server access from this VM
in this run; no live-leg ruling for this task yet.

## Per-item mapping

| Item | Board status | Merged artefact (verified on main 6e3fe04) | Live-agent leg |
|---|---|---|---|
| IG2-STR-14 — SRS RD candidate | VERIFIED (PR #742) | `Stratex/rigorous_backtest/ig/srs_declaration.json`, `RESULTS_SRS.md` + results/provenance JSONs | NONE. Declared backtest ran ONCE 2026-11-17 and FAILED the full bar (pooled OOS 512 trades, expectancy_net -0.000575, PF_net 0.919); family CLOSED per the declaration's own failing term; nothing promoted, nothing trades. Re-running would violate the frozen-declaration protocol (trial 3,892 consumed). |
| IG2-STR-16 — RiskGovernor delta | MERGED (PR #759) | `Stratex/rigorous_backtest/ig/risk_governor.py` + `Stratex/rigorous_backtest/ig/tests/test_risk_governor.py` | NONE. Research-only module by record; the live daemon does not import it — verified first-hand: the only importer on main is its own test file. No production value changed. Wiring it in would be a new feature, not verification. |
| IG2-STR-17 — BSE/NSE arb concept | MERGED (PR #764) | `Stratex/docs/BSE_NSE_ARBITRAGE_CONCEPT.md` | NONE. Docs-only concept note by record; revisit requires a free licensed dual-exchange tick dataset AND a pre-declared RD candidate; the note creates no follow-up task. |
| IG2-STR-18 — S-20 indicator ranking | CLOSED as SKIP (PR #792) | `Stratex/rigorous_backtest/ig/S20_INDICATOR_RANKING_DISPOSITION.md` | NONE. Opinion ranking with no mechanically specifiable rules; closed as SKIP, no code touched, no backtest run. Reopen only if a source states mechanical rules. |
| IG2-STR-19 — EMA 5/11 RD candidate | VERIFIED (PR #880) | `Stratex/rigorous_backtest/ig/EMA511_DECLARATION.md`, `RESULTS_EMA511.md` | NONE. Declared backtest ran 2026-11-17 and FAILED the full bar (150,079 OOS trades, expectancy_net -0.001664, PF_net 0.643); family CLOSED; nothing trades. Trial 3,893 consumed; re-running violates the declared-once protocol. |

## Finding

0 of 5 items has a live-agent leg as the STR-075 acceptance specifies. All five
are research artefacts: two closed/failed RD candidates, one research-only module
explicitly unwired from the daemon, one docs-only concept note, one closed-as-SKIP
disposition. The acceptance's "live demo-daemon cycle on Stratex-Server on real
market data + failure injection + full-allowlist load scan" cannot be executed
against any of them — there is no live behaviour to run, and the failure-injection
and load-scan legs are already ruled out of scope for research-only items by the
coordinator (ruling 4, 22:17 watch 7138911209, STR-070 precedent: injection HELD
fleet-wide pending owner clearance; no allowlist applies to research utilities).

## What this checkpoint does NOT claim

- No item is production-verified. Implemented / tested / merged / deployed /
  production-verified are all NO for STR-075 as a task; the five source items
  keep their own board states (VERIFIED / MERGED / CLOSED).
- No live evidence exists, because no live run is possible for these items.
- No code was changed. This PR is the board flip + this evidence doc only.

## Ruling requested (coordinator)

STR-075 as specified is not executable. Options, coordinator's call:

1. **Re-scope** STR-075 to artefact verification: confirm the five artefacts
   exist on main with the closure verdicts intact (this checkpoint is the
   evidence), and close the task on that basis.
2. **Release** STR-075 to the pool and let the five items stand on their own
   board records, with the production-verification programme's item selection
   revisited (PRODUCTION-VERIFICATION-PROGRAMME.md is missing from the repo
   per ruling 6, 22:17 watch — the board record governs until it is published).
3. **Define a live leg** per item if one exists — but any live leg that
   re-runs a closed RD candidate or wires RiskGovernor into the daemon is a
   new task, not verification of these items.

Muse 6 holds STR-075 (current) + VOI-027 (pre-staged) pending the ruling. No
re-pull until the ruling lands; a blocked head task is released, not sat on —
if the ruling is option 2, the release flip rides in the next board PR.

— Muse 6, 2026-11-24 ~23:15 IST
