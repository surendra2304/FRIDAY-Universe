# TASK-WEB-007 — CHECKPOINT 2: repo-side verification + Diagram Design end-to-end use — 2026-11-27 ~04:10 IST — Muse TP1

Claim: hub #1483 comment 7204208268. Branch: musetp1/task-web-007-repo-implement-wave-2 (head 8322b538, checkpoint 1). Base verified first-hand this run: main `56ebae7d` (merge PR #2025, WEB-005-FIX-01).

## 1. Repo-side verification — Toprank + Orb (all read first-hand on main 56ebae7d)

| Check | Result |
|---|---|
| `lib/fleetRank.ts` — pure mapping, unmeasured counted never scored (missing / NaN / infinite / negative → `unmeasured`, 0 ms is a real measurement) | PASS by read |
| `lib/ranking.ts` — competition ranking, ties share rank, movement = previousRank − rank, input not mutated | PASS by read |
| `lib/wire.ts` `fetchFleet()` = `requestJson("/api/agents/status")` — endpoint exists in production per wire.ts header | PASS by read |
| `components/RankBoard.tsx` — ranks via `rankEntries`, explicit empty state ("No measured entries yet"), movement column, pageSize 10 | PASS by read |
| `components/stage/RankSheet.tsx` — fetchFleet → fleetRankEntries → rankEntries "asc", 20 s re-measure, failure sets `failed`, unmeasured counted out loud | PASS by read |
| `components/stage/OrbSheet.tsx` — renders `Orb` size 320 driven by the stage's real `VoicePhase`, one phase line per phase | PASS by read |
| `components/stage/Stage.tsx` — RankSheet (line 33) + OrbSheet (line 34) dynamic-imported; rendered only as `{sheet === "rank" && <RankSheet />}` (410) and `{sheet === "orb" && <OrbSheet phase={stagePhase} />}` (411) — both sheets mount ONLY inside the Halo stage | PASS by read |
| `/halo` route (`FRIDAY/ui/app/halo/page.tsx`) mounts `<Stage />`; Caddy `/halo` handle rewrites to `/friday/halo/` — both in main via FIX-01 (#2025, merged 03:22 IST) | PASS by read — code merged, live leg still deploy-gated (see §3) |

## 2. Tests run — plain node v24.22.1, scratch worktree of origin/main 56ebae7d

```
node lib/fleetRank.test.ts  → all expectations passed
node lib/ranking.test.ts    → all expectations passed
node lib/wire.test.ts       → all expectations passed
```

(No test runner configured in FRIDAY/ui; the test files run with plain node per their headers. The `MODULE_TYPELESS_PACKAGE_JSON` warnings are benign — exit 0 on all three.)

## 3. Diagram Design end-to-end use (fresh, this task's own evidence)

- **Plan stated before drawing (§3):** visual type Architecture, minimal-dark preset, 6 nodes / 5 arrows / 2 accent elements / 1 callout. A table would not show the gate sitting between merged code and both sheet legs, or the tooling leg bypassing it — the diagram earns its keep.
- **Artifact:** `docs/collaboration/TASK-WEB-007-LIVE-PATH-DIAGRAM.html` — self-contained HTML, inline SVG, no JavaScript, no external images. Nodes: main 56ebae7d → /halo deploy (GATED, G2 clearance owed) → live /halo → Toprank + Orb legs; Diagram Design leg bypasses the gate (this diagram is its proof).
- **§9 taste-gate ledger (run before output):** type fit yes; remove test — no node/arrow/label removable (each leg, the gate and the route are distinct ideas); accent on exactly 2 nodes (deploy gate, Diagram Design); legend covers every type used and nothing extra; budget 6/9 nodes, 5/12 arrows, 2/2 accents, 1/2 callouts; SVG has `role="img"` + `aria-labelledby` to `<title>` (first child) + `<desc>`; arrows drawn before boxes; §6 rules 1–6 hold — orthogonal elbows rounded r=8, labels ≤7 chars all caps on paper masks, parallel routes offset 24px, no shared strokes, no crossings, no transit behind any non-endpoint box, masks clear of nodes; 4px grid clean; typography Space Grotesk names / mono sublabels only.
- **Machine check of the SVG (this run):** parses as XML; 6 node boxes, 0 overlapping pairs; 5 label masks, 0 overlapping nodes; max label length 7; 5 arrow paths; title first child; all node origins/sizes on the 4px grid.
- **FAILURE CASE (recorded, not hidden):** the skill says to load the upstream Architecture type reference before drawing — the fetch of `https://raw.githubusercontent.com/cathrynlavery/diagram-design/main/references/type-architecture.md` returned **HTTP 404**. Recovery: proceeded from the in-folder worked example `examples/friday-fleet-architecture.html`, which §10 prescribes as the starting point for an Architecture diagram (the upstream per-type library is not vendored; Architecture is the example's own type). The 404 is the failure; the example is the recovery; the diagram still passed the §9 gate above.

## 4. Gates (unchanged from checkpoint 1, one moved)

1. ~~FIX-01 merge~~ — DONE: PR #2025 merged by coordinator (WATCH186), main `56ebae7d`. The merge leg is closed; what remains is the **deploy** (G2 clearance, coordinator-side execution — server moves banned for me).
2. Live legs of Toprank + Orb stay GATED on that deploy. Nothing to execute from this side.
3. Slow-network + mobile-viewport legs: still owed on re-verification (browser tooling provides no resize/emulation or network throttling — WEB-005 scope limit, still true).

## 5. Five states

- implemented: PARTIAL (all three adaptations merged in code; repo-side verification done; live-path proof outstanding for the two sheet legs)
- tested: PARTIAL (three lib test files pass on main 56ebae7d; no live test yet)
- merged: NO (no work PR yet — one task = one PR at completion)
- deployed: NO (sheet legs await the /halo deploy)
- production-verified: NO

## Next

Checkpoint 3 (or the work PR, when the deploy lands): live legs — Toprank + Orb summoned on the live /halo route in a real browser at real viewports + slow-network, with failure cases; then one work PR with the live evidence + board flip inside it.

— Muse TP1
