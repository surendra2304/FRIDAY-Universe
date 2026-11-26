# TASK-WEB-005 — PRODUCTION-VERIFY — 2026-11-26 ~23:41–23:52 IST — Muse TP1

Claim: hub #1483 comment 7200140397 (board assignment watch099, verified
AVAILABLE / owner muse_tp1 on main df4e261b).
Branch: musetp1/task-web-005-production-verify, from main df4e261b.
Task: PRODUCTION-VERIFY website corpus items IG-WEB-08, IG2-WEB-01,
IG2-WEB-02, IG2-WEB-03 (live extreme-condition verification, wave 2, P1).

## Verdict: 1 of 4 verified live

| Item | Verdict | One line |
|---|---|---|
| IG-WEB-08 Editorial sheet | NOT VERIFIED | The sheet's only host, the Halo stage, is not mounted on any live route — ThemeRoot renders the Ultron stage unconditionally (owner's WEB-003 pick, 2026-11-17) |
| IG2-WEB-01 diagram-design adoption | VERIFIED (tooling scope) | Adopted file set present in the live fleet checkout on Oracle Server 2 and exercised end-to-end on a real task this run (diagram produced under the skill's rules + §9 taste gate) |
| IG2-WEB-02 RankBoard sheet | NOT VERIFIED | Same cause as IG-WEB-08: RankSheet mounts only inside the unreachable Halo stage; the live page shows one aggregate "Mean latency" figure, no per-agent ranked rows |
| IG2-WEB-03 Orb sheet | NOT VERIFIED | Same cause: OrbSheet mounts only inside the unreachable Halo stage; the live Ultron stage's own orb is the WEB-003 stage orb, not this item's component |

Failure case (acceptance: a failure case per item): for the three sheet
items the live system supplies the failure itself — the summon path does
not exist in the served build, so no deliberate outage was staged. For
IG2-WEB-01 the failure case is in the skill run below (remove test).

## Live target and method

Live target: the public production site https://friday-universe.duckdns.org
(public ingress per bridge get_system_info; Caddy on Oracle Server 2
reverse-proxies the FRIDAY service on FRIDAY-Server :10000). Sheet legs ran
in a real browser as a visitor, no sign-in, nothing restarted, deployed or
changed (browser run 23:41–23:43 IST, screenshots 1919x998). Fleet legs ran
read-only through the bridge (run_shell, servers 2 and 3).

Scope limits, stated plainly:

- Viewport: the browser tooling provides no resize/emulation or network
  throttling, so observations are desktop 1919x998 and the slow-network
  leg was NOT run; it is owed on re-verification. The decisive failure
  (no summon path in the served build) is viewport-independent.
- The Orb sheet's voice-phase behaviour could not be exercised: the
  sheet cannot be opened at all (see root cause).

## Root cause (verified first-hand, code + live)

The three sheets exist on main and are mounted in exactly one place:
FRIDAY/ui/components/stage/Stage.tsx (the Halo stage) renders
EditorialSheet (sheet === "editorial"), RankSheet and OrbSheet
(sheet === "orb", driven by the stage voice phase), summoned through a
veil opened by the "Everything else" summon pill, the FRIDAY wordmark,
or Cmd/Ctrl-K.

The live home route never reaches that stage:

- FRIDAY/ui/app/page.tsx renders ThemeRoot.
- FRIDAY/ui/components/ThemeRoot.tsx (TASK-WEB-003, amended 2026-11-17)
  renders UltronStage UNCONDITIONALLY. Its header comment records the
  owner's 2026-11-17 pick: ULTRON is the only theme; Halo was "kept
  aside in workspace storage — not kept selectable in the live site";
  the theme switch was removed.
- The served export confirms it: FRIDAY/ui/out/index.html on main is
  the Ultron stage markup (class "ultron-stage", "ULTRON COMMAND ·
  TASK-WEB-003", no summon pill, no veil). The FRIDAY-Server checkout
  (git 5b245ffd, 2026-11-24) serves the same export via
  friday.api.server (uvicorn :10000, started 2026-11-26 16:02 UTC);
  its out/ tree is the Ultron build.
- /start is a separate route rendering GlassStartPage (TASK-IG2-WEB-07's
  item, not one of these four) — not a path to the sheets.

So this is not a code bug and not a deploy staleness issue: an owner
product decision in WEB-003 (2026-11-17) superseded the surface the
three IG sheet items were built for, and no route has mounted the Halo
stage since. The items cannot be verified live until that conflict is
ruled on (FIX-01 below).

## Live legs — what the browser actually saw (23:41–23:43 IST)

Base stage (Ultron) renders with live data: heading "FRIDAY",
"ULTRON COMMAND · TASK-WEB-003"; SYSTEM DIAGNOSTICS with real figures
(CPU LOAD 2%, MEMORY 41%, "Agents awake 6/9"); CORE MODULES with per-unit
states (Inference REACHABLE, Memora ONLINE, Stratex DEGRADED, IntelX
DEGRADED, Futuris DEGRADED, Cortex REACHABLE, Forge REACHABLE, Sentinel
REACHABLE, VyralX REACHABLE); FLEET LINK "Agents online 6/9",
"Mean latency 1782 ms" then "1332 MS", "Last fleet check 23:41:33" /
"23:42:42". The stage orb shows "TAP TO TALK" / "STANDING BY".

Summon attempts, all failed: Ctrl+K, Cmd+K, Ctrl+K after focusing the
page, reload + Cmd+K again — no veil, no overlay, no sheet list ever
appeared. Full-page scroll and element inspection: no summon pill, no
"Everything else" button; text search of the loaded page for "summon",
"veil", "Editorial", "Rank" returned no matches. The only stage buttons
are VOICE / TEXT / QUIET, the orb / "Start the line", WAKE WORD OFF /
START THE LINE / WRITE INSTEAD, and the message composer.

Natural failure observed on the same page (honest degradation, worth
recording): immediately after a reload the fleet panels showed
"Agents online 0/—", "Mean latency —", "Telemetry unreachable — no
figures shown rather than invented ones", "Fleet unreachable — module
states unknown, not guessed", recovering to live values within ~20 s
with no action taken. The app shows nothing rather than invented
figures — the sheets' data discipline exists in the stage that IS live.

### IG-WEB-08 — NOT VERIFIED (Editorial sheet)

No masthead, spec sidebar, spotlight or tilted roster could be rendered:
the EditorialSheet mounts only in the unreachable Halo stage. The base
page's own FLEET LINK panel is not Editorial evidence and is not counted
as such. Code position on main verified first-hand: EditorialSheet.tsx,
Stage.tsx, globals.css all present; the item's DEPLOYED board status
refers to the 2026-11-15 combined-export landing, which predates the
WEB-003 theme decision that unmounted its host.

### IG2-WEB-01 — VERIFIED (tooling scope)

This item adopted a skill file-set into website/docs tooling; it has no
website surface, so its live path is the fleet itself.

- Presence in the live fleet checkout, verified this run via bridge
  run_shell on Oracle Server 2 (host friday-universe-vnic-2):
  /opt/friday_universe/FRIDAY/ui/diagram-design/ contains LICENSE,
  README.md, SKILL.md and examples/friday-fleet-architecture.html —
  the full adopted set from PR #686.
- End-to-end use on a real task, this run: I used the adopted SKILL.md
  to draw the TASK-WEB-005 verification-flow diagram
  (docs/collaboration/TASK-WEB-005-DIAGRAM-DESIGN-USE.html in this PR):
  semantic pattern chosen first (flow/process), 8 nodes / 7 arrows
  (budget ≤9 / ≤12), accent on exactly 1 element (the live site under
  test), arrows drawn before nodes, orthogonal connectors only, node
  geometry on the 4px grid, hairline borders, no shadows, legend
  present. §9 taste gate run: remove test — the "Five states" node was
  nearly merged into "Peer verification"; kept separate because the
  five-state report is a distinct owner-mandated output, recorded here
  as the gate's ledger entry. Failure case: my first layout draft put
  the accent on two nodes (task + live site); the gate's signal check
  (accent ≤2, editorial not a flag) cut it to the live site only.

### IG2-WEB-02 — NOT VERIFIED (RankBoard)

The RankBoard (RankSheet) is fed by measured fleet latencies from
/api/agents/status and mounts only in the unreachable Halo stage. On
the live page there is no ranked list, no per-agent latency rows, and
no count of excluded/unmeasured agents — only the aggregate
"Mean latency 1332 MS" in FLEET LINK. Code position on main verified:
lib/ranking.ts, lib/fleetRank.ts, components/stage/RankSheet.tsx
present; mounting PR #757 landed the sheet inside the Halo stage that
WEB-003 later unmounted.

### IG2-WEB-03 — NOT VERIFIED (Orb sheet)

OrbSheet (driven by the stage's real voice phase, Halo remains the
face) mounts only in the unreachable Halo stage. The live Ultron stage
has its own orange wireframe orb with "STANDING BY" / "TAP TO TALK" —
that is UltronStage's orb (TASK-WEB-003), not this item's OrbSheet, and
is not counted as evidence for it. No phase-following behaviour could
be exercised.

## Fix task named from this record (coordinator to file/board)

- **WEB-005-FIX-01 — Halo stage and its summoned sheets are unreachable
  in production since TASK-WEB-003.** ThemeRoot renders UltronStage
  unconditionally (owner pick 2026-11-17: Halo "kept aside in workspace
  storage — not kept selectable in the live site"). IG-WEB-08,
  IG2-WEB-02 and IG2-WEB-03 (and every other Stage.tsx sheet: Fleet,
  Galaxy, Chronicle, City, Life, Pulse, Showcase, Tour) have no live
  route. This needs an owner/coordinator ruling, not a code fix:
  either (a) mount the Halo stage at its own route (e.g. /halo) so the
  sheets are reachable without displacing the Ultron home the owner
  picked, or (b) formally retire the sheet items so the board stops
  carrying them as DEPLOYED/MERGED work awaiting verification.
  Evidence: this doc, root cause section.

## Five states

- implemented: PARTIAL (all four items' code/tooling on main; three
  sheets' live surface unmounted by the WEB-003 decision)
- tested: YES for this verification run (live browser + bridge legs
  above; slow-network and mobile-viewport legs NOT run — tooling
  limits, owed on re-verification)
- merged: NO (work PR filed this run)
- deployed: PARTIAL (Ultron stage live; Halo stage not deployed on any
  route; diagram-design set present in the live fleet checkout)
- production-verified: PARTIAL — IG2-WEB-01 verified in its tooling
  scope; IG-WEB-08, IG2-WEB-02, IG2-WEB-03 NOT verified, FIX-01 named

— Muse TP1
