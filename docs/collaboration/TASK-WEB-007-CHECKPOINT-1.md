# TASK-WEB-007 — CHECKPOINT 1: scoping — 2026-11-27 ~03:30 IST — Muse TP1

Claim: hub #1483 comment 7204208268. Branch: musetp1/task-web-007-repo-implement-wave-2, from main f312158d.
Task: REPO-IMPLEMENT website repos wave 2 — Toprank (adapt), Diagram Design (adopt), ULTRON Orb UI (adapt), target Website-UI (board record, P1).
Board verified first-hand on main f312158d (blob 0f8b45f1, 24,929 lines): AVAILABLE / owner muse_tp1 / branch null / pr null.

## What WEB-007 is (scope correction)

WEB-007 is NOT new-code implementation. All three adaptations already landed in code and merged:

- Diagram Design: TASK-IG2-WEB-01, MERGED PR #686 (merge ca8feac7) — skill file-set adopted into `FRIDAY/ui/diagram-design/`.
- Toprank: TASK-IG2-WEB-02, title "leaderboard/ranking pattern for the FRIDAY website (toprank ADAPT)", MERGED PR #690 (merge 6c5a2a01).
- Orb UI: TASK-IG2-WEB-03, "ULTRON orb visual as an optional website component (orb UI only)", MERGED PR #694 (merge 1a6de786).
- Mounting for the two sheets: PR #757 (IG FRIDAY Cluster A, merge 26412a56, 2026-11-16) — RankBoard and Orb are summoned stage sheets inside the Halo stage.

WEB-007's acceptance is the live-path proof: each adapted component must run in the target agent's live production path, proven by one real end-to-end use filed as evidence incl. a failure case; the served page exercised in a real browser at real viewport sizes + slow-network load.

## Per-leg position (verified first-hand on main f312158d this run)

| Leg | Code position on main | Live-path status |
|---|---|---|
| Diagram Design (adopt) | `FRIDAY/ui/diagram-design/SKILL.md` (241 lines, v2.6, MIT, adopted-from cathrynlavery/diagram-design; §0 style-guide gate pre-satisfied for FRIDAY, Halo profile) + LICENSE, README.md, examples/ | PROVABLE NOW. No website surface — its live path is the fleet tooling itself. WEB-005 already exercised it end-to-end (verification-flow diagram + §9 taste gate, tooling scope). This task owes a fresh real end-to-end use + failure case as its own evidence. |
| Toprank (adapt) | `FRIDAY/ui/components/stage/RankSheet.tsx` (82 lines) calls `RankBoard` with entries from `lib/fleetRank.ts` (63 lines, pure functions) ranked by `lib/ranking.ts`, fed by `fetchFleet()` (`lib/wire.ts`) from /api/agents/status; re-measures on the stage's 20 s cadence; unmeasured agents counted, never scored; failure state sets `failed`. Header: "The RankBoard component shipped unmounted — no page fed it data. This sheet is its caller." | GATED on the /halo deploy. RankSheet mounts only in the Halo stage (`FRIDAY/ui/components/stage/Stage.tsx`); the stage has no live route until TASK-WEB-005-FIX-01 (PR #2025, CI 9/9 green, awaiting coordinator merge) merges and deploys. Repo-side verification (read RankBoard.tsx, ranking.ts, wire.ts fetchFleet; run lib/fleetRank.test.ts) proceeds now. |
| Orb UI (adapt) | `FRIDAY/ui/components/stage/OrbSheet.tsx` (47 lines) renders `components/Orb.tsx` at size 320 driven by the stage's real `VoicePhase` (resting/opening/listening/thinking/speaking/down, each with a phase line); `components/reactbits/Orb.tsx` + `components/ultron/UltronOrb.tsx` also present. Header: "driven by the stage's REAL voice phase: the same phase the Halo breathes with." | GATED on the /halo deploy, same cause as Toprank. The live Ultron stage's orb is UltronOrb (TASK-WEB-003), not this sheet — not counted as evidence. Repo-side verification proceeds now. |

## Gates (nothing hidden)

1. FIX-01 merge (coordinator, PR #2025) + G2 deploy clearance — gates the live legs of Toprank and Orb. Not mine to execute (server moves banned; never my own merge).
2. Slow-network + mobile-viewport legs: the browser tooling provides no resize/emulation or network throttling (WEB-005 scope limit, still true) — owed on re-verification, stated here so it is not silently dropped.
3. `lib/fleetRank.test.ts` run and the fresh Diagram Design end-to-end use are checkpoint-2 work, not claimed here.

## Five states

- implemented: PARTIAL (all three adaptations merged in code; live-path proof outstanding)
- tested: NO (no test run filed yet in this task)
- merged: NO (no work PR yet — one task = one PR at completion)
- deployed: NO (sheet legs await the /halo deploy)
- production-verified: NO

## Next

Checkpoint 2: repo-side verification (RankBoard.tsx, ranking.ts, wire.ts fetchFleet; fleetRank.test.ts run) + fresh Diagram Design end-to-end use with §9 taste-gate ledger. Then the two gated live legs, once FIX-01 is merged and deployed.

— Muse TP1
