# TASK-WEB-004-FIX-02 — Tour crew chip must match the live Fleet sheet count

**Task:** WEB: tour crew chip must match the live Fleet sheet count (WEB-004 IG-WEB-06 FAIL)
**Owner:** Muse 4 · **Branch:** `muse4/task-web-004-fix-02-tour-crew-chip`
**Claim:** hub #2045 comment 7230354795, 2026-11-28 ~05:13 IST, on assignment BE 04:37 §B / BE 05:05 §C / WATCH246 §B (SEN-041 merged, queue empty). Board record on main `ff5806b2`: TASK-WEB-004-FIX-02 CLAIMED / owner muse_4 / P1. Board flips are coordinator-only; no board hunk in this PR.
**Live target:** `https://friday-universe.duckdns.org/halo` as a visitor (public read, no sign-in); live data `GET /api/agents/status`.

## The failure (IG-WEB-06 FAIL)

WEB-004 live browser run 2026-11-27 23:52 – 2026-11-28 00:08 IST (Muse 2, browser task `browser-task:080a7a64-9934-549d-89b0-c25576b3244a`, `docs/collaboration/TASK-WEB-004-PRODUCTION-VERIFY.md`): the Tour sheet crew chip read **"Right now: 0 of 9 are answering" on both fresh opens**, while live fleet data in the same session said **6 of 9 answering** (Fleet sheet "6 of 9 are answering"; home glance showed 9 agents with live statuses). Paired re-verdict PARTIAL (Muse 17, review 6093585761, ~03:13 IST). Per the acceptance rule an unanswered chip must be absent, not a default 0.

## Root cause — two counting rules for one number (PROVEN on live data)

Both sheets call the same `fetchFleet()` → `GET /api/agents/status` and count from the same snapshot. They counted differently:

- **Tour sheet** (`FRIDAY/ui/components/stage/TourSheet.tsx`, main `ff5806b2`): `facts.fleet?.agents.filter((a) => a.status === "online").length` — exact, case-sensitive, lowercase `"online"` only.
- **Fleet sheet** (`FRIDAY/ui/components/stage/FleetSheet.tsx`): `fleet?.agents.filter((a) => toneFor(a.status) === "good").length` — via `toneFor` in `FRIDAY/ui/lib/wire.ts`, which uppercases first and maps ONLINE / REACHABLE / OK / HEALTHY / COMPLETED / DONE / SUCCESS → "good".

Two layers of divergence:

1. **Case.** The backend ships UPPERCASE statuses. `"ONLINE" === "online"` is false, so the Tour rule matched *nothing* — not even the one ONLINE agent.
2. **Rule.** Even case-fixed, `"online"` would count only ONLINE (1 of 9), not REACHABLE (4 of 9) — the Fleet sheet counts REACHABLE as answering.

**Live snapshot, 2026-11-28 05:17:39 IST** — bridge curl from Oracle Server 1, `GET https://friday-universe.duckdns.org/api/agents/status`, HTTP 200 in 11.9 s, 3,198 bytes, `timestamp 2026-11-27T23:47:39Z`, `status_counts {ONLINE: 1, REACHABLE: 4, DEGRADED: 4, UNREACHABLE: 0, OFFLINE: 0}`:

| agent | live status | Tour rule (`=== "online"`) | Fleet rule (`toneFor === "good"`) |
|---|---|---|---|
| Inference | REACHABLE | — | ✓ |
| Memora | ONLINE | — (case) | ✓ |
| Stratex | DEGRADED | — | — |
| IntelX | DEGRADED | — | — |
| Futuris | DEGRADED | — | — |
| Cortex | REACHABLE | — | ✓ |
| Forge | DEGRADED | — | — |
| Sentinel | REACHABLE | — | ✓ |
| VyralX | REACHABLE | — | ✓ |
| **total** | | **0 of 9** | **5 of 9** |

(The WEB-004 run saw 6 of 9; the fleet state moved between runs — 1 ONLINE + 4 REACHABLE now vs 6 answering then. The rules, not the moment, are what diverged: on any snapshot the Tour rule reads 0 while the Fleet rule reads the true good-tone count.)

## The fix

One shared rule, `countAnswering()`, in `FRIDAY/ui/lib/wire.ts` (after `toneFor`); both sheets use it. The duplicated counting rule — the actual defect — is gone; a new status string needs one mapping update in `toneFor`.

- `FRIDAY/ui/lib/wire.ts` (+12/−0): `export function countAnswering(agents: FleetAgent[]): number { return agents.filter((a) => toneFor(a.status) === "good").length; }`
- `FRIDAY/ui/components/stage/TourSheet.tsx` (+6/−1): import `countAnswering`; `const answering = facts.fleet ? countAnswering(facts.fleet.agents) : undefined;` — the chip is still absent while the fetch is unresolved (the `typeof answering === "number"` guard is unchanged) and shows the true count once resolved. Never a default 0.
- `FRIDAY/ui/components/stage/FleetSheet.tsx` (+6/−1): `const answering = countAnswering(fleet?.agents ?? []);` — byte-identical logic to its old inline filter (the `?? 0` default is preserved: `countAnswering([])` is 0).
- `FRIDAY/ui/lib/wire.test.ts` (+39/−0): regression test on the live snapshot above + tone-class cases.

Diff total: 4 files, +63/−2. No board hunk, no workflow edits, no fleet config changes.

## Test-first record

- Baseline: `node lib/wire.test.ts` on main `ff5806b2` → "wire.test.ts: all expectations passed", exit 0 (Node v24.22.1, native type stripping; the file's own header documents this runner).
- Failing test first: added the `countAnswering` test block → `SyntaxError: The requested module './wire.ts' does not provide an export named 'countAnswering'`, exit 1.
- Fix applied → `node lib/wire.test.ts` → "wire.test.ts: all expectations passed", exit 0.
- Rule check on the live snapshot (node one-liner, same 9 statuses): old Tour rule 0 of 9 | Fleet rule 5 of 9 | fixed helper 5 of 9.
- Note: `wire.test.ts` is NOT run by CI (the CI workflow runs the Python agent suites; the UI has no test job — `package.json` has dev/build/start/lint only). The wire test is run locally first-hand; the PR's CI is the standard repo suite. A `next build` typecheck was not run here (needs node_modules + full Next install); the change is type-correct by inspection (`countAnswering` takes `FleetAgent[]`; both call sites pass `FleetAgent[]`).

## Live probe record

- Endpoint snapshot (above): live, first-hand, 05:17:39 IST, HTTP 200. The chip's data source, read directly.
- Visual chip check: NOT run in this task — the fix is not deployed (see below); the halo page serves a built export rebuilt at deploy, and the chip is client-rendered (a text fetch returns only the empty-state shell, no chip). The visual re-probe (chip vs Fleet sheet in the same browser session) is OWED after deploy.
- The WEB-004 live observation (chip 0 vs sheet 6, same session, 23:52–00:08 IST) is the pre-fix live record; the endpoint snapshot is the post-diagnosis live record.

## Deploy state

- **Deployed: NO.** The fix lives only in this PR. The halo page serves the built `out/` export on FRIDAY-Server, rebuilt at deploy; this PR does not deploy. Deploy rides the Fleet CD / coordinator clearance — not done here, not claimed.
- **Production-verified: NO.** The chip-match acceptance can only be proven live after deploy, by a browser re-probe (chip vs Fleet sheet in the same session). That leg is owed; paired verification of this PR is also owed.

## Same-bug-class notes (NOT in this PR — follow-ups)

- `FRIDAY/ui/components/stage/CitySheet.tsx:187` — `onlineCount` uses the same exact `=== "online"` match and renders `{onlineCount ?? 0} of {fleet.agents.length} districts are lit tonight` — the same false-0 pattern on live data. Follow-up fix task.
- `FRIDAY/ui/components/stage/EditorialSheet.tsx:82,89,140,176,243` — `=== "online"` for the featured-agent pick and the "online" filter; different behaviour (selection, not a count chip) — assess separately.
- `FRIDAY/ui/components/stage/ShowcaseSheet.tsx:102` and `FRIDAY/ui/components/kit/ShowcaseRows.tsx:248` — same exact match but both fall back to the full list when nothing matches, so they degrade gracefully (no false 0). No change needed.
- `FRIDAY/ui/components/ultron/UltronStage.tsx:174` and `FRIDAY/ui/components/stage/Stage.tsx:351` already use `toneFor(...) === "good"` — correct, unchanged.

## Five states

- implemented: YES (fix + shared helper + regression test)
- tested: YES (wire.test.ts first-hand, failing-first; live endpoint snapshot)
- merged: NO (PR open)
- deployed: NO (awaiting deploy — Fleet CD / coordinator clearance)
- production-verified: NO (visual chip-match re-probe owed post-deploy; paired verification owed)

— Muse 4
