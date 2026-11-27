# TASK-WEB-004 — PRODUCTION-VERIFY (groundwork draft) — 2026-11-27 ~23:42 IST — Muse 2

Claim: hub #2045 comment 7225226784 (23:41 IST 2026-11-27).
Branch: `muse2/task-web-004-production-verify`, from main `0f465767`.
Task: PRODUCTION-VERIFY website corpus items IG-WEB-01, IG-WEB-02,
IG-WEB-03, IG-WEB-05, IG-WEB-06 — live browser verification (wave 2, P1).

## Verdict: NOT YET RUN — groundwork only

This file is the pre-run record: item definitions verified first-hand on
main `0f465767`, the production URLs, and the exact live-check plan per
item. **No live browser leg has run yet.** The live legs run next through
the live-browser route; results, screenshots and the verdict table land
here as a follow-up commit on this branch. Nothing in this draft counts
as verification. A code-only report is rejected by the acceptance — the
task closes only on live evidence per item.

## Live target and method (planned)

Live target: the public production site `https://friday-universe.duckdns.org`
(public ingress per repo `AGENTS.md`; Caddy on Oracle Server 2
reverse-proxies the FRIDAY service on FRIDAY-Server `:10000`).

- Home `/` renders the Ultron stage unconditionally (owner's WEB-003
  pick, 2026-11-17) — it is NOT the surface for these five items.
- These five items live in the Halo stage
  (`FRIDAY/ui/components/stage/Stage.tsx`), which mounts at the
  standalone route **`/halo`** (`FRIDAY/ui/app/halo/page.tsx`,
  TASK-WEB-005-FIX-01, PR #2025, merge `56ebae7d`, 2026-11-27 ~03:22 IST).
  Bare-domain URL: `https://friday-universe.duckdns.org/halo`
  (Caddy `handle /halo*` in `deploy/Caddyfile` rewrites to
  `/friday/halo/`); alternate: `/friday/halo/`.
- Live legs run in a real browser as a visitor, no sign-in, nothing
  restarted, deployed or changed. Viewports: desktop 1919x998 (the
  viewport of the WEB-005/WEB-006 runs) and mobile ~390x844. Slow-network
  load: attempted if the browser tooling offers throttling; the WEB-005
  and WEB-006 runs recorded that it does not — if it still does not,
  that leg stays owed on re-verification and is stated plainly, not
  faked.

## Pre-run signal — /halo appears to serve (UNVERIFIED, text fetch only)

At 23:45 IST 2026-11-27 a plain text fetch (not a browser run) of
`https://friday-universe.duckdns.org/halo` returned the title
"FRIDAY — Halo" — exactly the halo route's metadata title — while `/`
returned "FRIDAY" with Ultron copy ("ULTRON LINK QUIET"). The /halo
body text was thin (the stage is client-rendered; only the Conversation
empty state surfaced: "Nothing here yet. Start the line and speak…").
This SUGGESTS the FIX-01 deploy (pull + rebuild of `out/` on
FRIDAY-Server, Caddy `/halo` handle port — see
`TASK-WEB-005-FIX-01-EVIDENCE.md` §5) may have landed since 03:22 IST,
but it proves nothing about what renders: no summon pill, veil, or
sheet was observed in the fetch. Note the committed export on main
`0f465767` still has NO `FRIDAY/ui/out/halo/` directory (FIX-01
deliberately did not refresh `out/`; it is rebuilt at deploy), so the
live run's FIRST check is: GET `/halo` → 200 with Halo stage markup
(`class="stage"`, wordmark FRIDAY, summon pill "Everything else"). If
/halo 404s or serves the Ultron shell, the live legs are DEPLOY-GATED
exactly as WEB-007 checkpoint 2 recorded ("sheet legs await the /halo
deploy") — stop there, file the gate as the finding, do not invent
results.

Prior context that shapes the run: WEB-005 (TP1, 2026-11-26) found
IG-WEB-08 / IG2-WEB-02 / IG2-WEB-03 NOT VERIFIED because the Halo stage
had no live route at all; FIX-01 was the named fix and is now merged.
WEB-007 checkpoint 2 (TP1, 2026-11-27) records the /halo route + gateway
record as PASS-by-read with the live leg still deploy-gated. This task
is the first live attempt at the five sheets since that mount landed.

## Item definitions (verified first-hand on main `0f465767`)

All five items are `DEPLOYED` on the board (2026-11-15/17 combined-export
landings, fleet S1 == S2 == main == `64ca017a` per the 2026-11-17
verification) and all mount ONLY inside `Stage.tsx` — no other route
renders them. Summon path for every sheet: open `/halo`, open the veil
(Cmd/Ctrl-K, the "Everything else" summon pill, or the FRIDAY wordmark),
pick the sheet's label below. The stage, conversation and any live call
never unmount when a sheet opens.

### IG-WEB-01 — scroll-driven motion layer (TASK-IG-WEB-01, PR #482 merged `e712c5fd`)

- Code: `FRIDAY/ui/components/stage/motion.tsx` — `Reveal` /
  `ScrollProgress` / `Parallax` / `usePrefersReducedMotion` on
  IntersectionObserver + rAF + CSS transform/opacity, zero new
  dependencies; `FRIDAY/ui/components/stage/Sheet.tsx`,
  `FleetSheet.tsx`, `FRIDAY/ui/app/globals.css`.
- User-visible: every summoned sheet shows a scroll-progress hairline
  that fills as you scroll; Fleet cards reveal staggered; with
  `prefers-reduced-motion` on, everything is instant/static.
- Live check: open `/halo` → summon Fleet ("Look at the fleet") →
  scroll inside the sheet: hairline fills with scroll position;
  Fleet cards appear staggered, not all at once. Then enable reduced
  motion and reload: no animation, content fully visible immediately.
- Pass: hairline tracks scroll; staggered reveal visible; reduced
  motion renders static content. Fail: hairline absent or static;
  cards pop in all at once; reduced motion still animates.
- Failure case: reduced-motion run IS the failure case (the layer must
  degrade, not break); also scroll to the sheet bottom and back — the
  hairline must track both directions.

### IG-WEB-02 — Life-in-weeks sheet (TASK-IG-WEB-02, landed `cfcfb84c`)

- Code: `FRIDAY/ui/components/stage/LifeSheet.tsx`,
  `Stage.tsx`, `globals.css`. Data: browser `localStorage` ONLY
  (keys for birth date + milestone marks); zero network calls.
- User-visible: summoned via the veil as "See your life in weeks" —
  a 52×90 dot grid (every week of a 90-year life) + year-in-days view;
  set a birth date, mark a week, reload — the mark persists.
- Live check: open `/halo` → veil → "See your life in weeks" → grid
  renders (52 columns × 90 rows of dots); enter a birth date; mark a
  week; reload `/halo` and re-summon — the mark is still there.
- Pass: grid renders; mark persists across reload; no network calls
  from the sheet (it must not phone home). Fail: grid missing/partial;
  mark lost on reload; sheet makes network requests.
- Failure case: clear `localStorage` for the site and reload — the
  sheet must render its empty state (no birth date, no marks), not
  crash and not invent a birth date.

### IG-WEB-03 — Memory Galaxy sheet (TASK-IG-WEB-03, landed `9e098171`)

- Code: `FRIDAY/ui/components/stage/GalaxySheet.tsx`,
  `Stage.tsx`, `FRIDAY/ui/lib/wire.ts`, `globals.css`. Data: real
  memories from `GET /api/memory/browser` (tier colours, score sizes);
  never sample data. Threads labelled in-layer as category/layout
  neighbours; no fabricated graph edges or connection counts.
- User-visible: summoned via the veil as "Wander the memory galaxy" —
  FRIDAY's memories as a starfield.
- Live check: open `/halo` → veil → "Wander the memory galaxy" →
  stars render; spot-check that star count/labels correspond to real
  memories (compare against the endpoint if reachable); no invented
  edges/counts shown.
- Pass: starfield renders from real endpoint data (or an honest empty
  state if the endpoint does not answer — per the board acceptance,
  "Endpoint unreachable renders an honest empty state"). Fail: sample/
  placeholder stars; fabricated connections; a crash or spinner that
  never resolves when the endpoint is down.
- Failure case: the endpoint-down path IS the failure case — if
  `/api/memory/browser` does not answer live, the sheet must show the
  honest empty state, not fake stars. (Board next-action from 2026-11-15
  already flags: "if it shows 'didn't answer', align the
  /api/memory/browser gate with the sibling UI endpoints as a
  follow-up".)

### IG-WEB-05 — Showcase sheet (TASK-IG-WEB-05, landed `b08b084c`)

- Code: `FRIDAY/ui/components/stage/ShowcaseSheet.tsx`,
  `Stage.tsx`, `globals.css`. Data: live fleet data via
  `fetchFleet()` / `fetchLive()` / `fetchTimeline()` in `lib/wire.ts`
  (`/api/agents/status`, `/api/agents/live`, `/api/tasks/timeline`).
- User-visible: summoned via the veil as "Browse the showcase" —
  Netflix-style billboard (only agents the fleet endpoint reports)
  + crew / ledger / rooms rows over real fleet/timeline data (or an
  honest empty note); cards summon the real Fleet/Chronicle/Pulse
  layers via `onSummon`; rotation pauses on hidden tab and under
  reduced motion.
- Live check: open `/halo` → veil → "Browse the showcase" → billboard
  shows a real fleet agent; rows render real data or an honest empty
  note; click a card → the corresponding layer opens (not a dead link);
  wait and watch the billboard rotate; switch tab away and back —
  rotation must have paused while hidden.
- Pass: billboard + rows from live data (or honest empty notes);
  cards navigate to real layers; rotation pauses hidden/reduced-motion.
  Fail: billboard features an agent the fleet does NOT report; rows
  show invented figures; cards dead-end; rotation keeps running hidden.
- Failure case: hide the tab for ~30 s and return (rotation must not
  have advanced as if continuously visible); enable reduced motion —
  rotation must stop.

### IG-WEB-06 — Guided Tour sheet (TASK-IG-WEB-06, landed `94bb776c`)

- Code: `FRIDAY/ui/components/stage/TourSheet.tsx`,
  `Stage.tsx`, `globals.css`. Data: live fact chips ONLY from
  answered endpoints (`fetchFleet()`, `fetchLive()`,
  `fetchTelemetry()`, `fetchAutonomy()`); no invented figures. Uses
  the local `Reveal` in `TourSheet.tsx` (board notes a follow-up to
  swap it for `motion.tsx` after PR #482 — not this task's scope).
- User-visible: summoned via the veil as "Take the guided tour" —
  cinematic serif hero + five-chapter scroll narrative (voice, crew,
  ledger, machine, watch) with live fact chips and `onSummon` CTAs;
  the voice-first home is unchanged.
- Live check: open `/halo` → veil → "Take the guided tour" → hero
  renders; scroll through all five chapters; each fact chip shows a
  real number from a live endpoint (or is absent — "no chip is better
  than an invented one"); click a chapter CTA → the named layer opens.
- Pass: all five chapters render; every shown figure traces to a live
  endpoint; CTAs navigate. Fail: a chip shows a figure no endpoint
  returned; a chapter missing; a CTA dead-ends.
- Failure case: if any endpoint is unreachable live (e.g. a DEGRADED
  agent per the Ultron fleet panel), its chip must be ABSENT, not a
  guessed number — record which endpoints answered and which did not.

## Results (to be filled by the live run)

| Item | Verdict | One line |
|---|---|---|
| IG-WEB-01 motion layer | NOT RUN | — |
| IG-WEB-02 life-in-weeks | NOT RUN | — |
| IG-WEB-03 memory galaxy | NOT RUN | — |
| IG-WEB-05 showcase | NOT RUN | — |
| IG-WEB-06 guided tour | NOT RUN | — |

Live legs (fill in): browser runs, viewports, slow-network leg,
per-item observations, screenshots, failure-case outcomes.

## Fix tasks named from this record (if any item fails live)

- None yet — to be filed from the live results. Any item that fails
  live gets a named fix task filed from this record; a failing item is
  never marked verified.

## Five states (TASK-WEB-004, groundwork only)

- implemented: YES (all five items' code merged on main; Halo mount
  merged via FIX-01 PR #2025)
- tested: NO (no live leg run yet — this draft is groundwork only)
- merged: NO (work PR not opened yet)
- deployed: UNVERIFIED (the /halo deploy state is the live run's
  first check; text-fetch signal only, see above)
- production-verified: NO (0 of 5 — pending the live browser run)

— Muse 2
