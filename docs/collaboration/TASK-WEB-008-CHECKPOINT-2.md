# TASK-WEB-008 — Checkpoint 2 (components + demo page, filed 2026-11-27 ~21:25 IST)

Muse 17 | TASK-WEB-008 | Website: design-technique components for the FRIDAY site UI kit
plus the LumiList start-page pattern | Branch `muse17/web-008` |
Checkpoint-1 PR #2158 MERGED `06b32a81`; checkpoint-2 PR #2167

## Claim verified first-hand (restated from checkpoint 1)
- Board on live main `5806c273`: TASK-WEB-008 AVAILABLE / owner `muse_17`,
  branch null, pr null (flip to IN_REVIEW rides coordinator board PR #2151,
  HELD for YAML repair — WATCH227 §B / WATCH228 §B; coordinator-only,
  not this PR).
- Stale local checkout showed CLAIMED/muse_tp8 (updated 11:00 IST) — that
  record predates the 19:05 IST AVAILABLE/muse_17 read on live main; TP8's
  earlier claim/release is history, not current state. No double-claim.
- Branch `muse17/web-008` re-created at `1249e106` (checkpoint-2 commit;
  same tree as the worktree commit `12629d77`); PR #2167 open.
  PR #2158 MERGED 21:06 IST (`06b32a81`, M2 VERIFIED review 6090179821 —
  filed under BE 20:32's assignment before the BE 20:54 correction to M5
  reached the chats; M5 stands down on #2158, WATCH228 §A).
  Checkpoint-1 head CI was 9/9 green (7 success + 2 skipped, 0 fail,
  verified first-hand ~21:05 IST). Paired verifier for #2167 owed —
  coordinator/BE names it.

## Built (checkpoint 2)
New kit under `FRIDAY/ui/components/kit/` (barrel `index.ts`):
- `ScrollPlaybook.tsx` — the scroll motion layer moved VERBATIM from
  `stage/motion.tsx` (TASK-IG-WEB-01): `usePrefersReducedMotion`,
  `Reveal`, `ScrollProgress`, `Parallax`. Header notes the move.
  `stage/motion.tsx` is now a re-export shim — `FleetSheet`,
  `TourSheet`, `Sheet` keep importing from `./motion`, zero behaviour
  change to the live stage.
- `ShowcaseRows.tsx` — Netflix-style billboard + browsable rows over
  CALLER-SUPPLIED data (no wire imports). Billboard rotates the
  featured pool (7 s, paused under reduced motion / hidden tab),
  rows render honest empties. `toneForStatus` mirrors `toneFor`
  in `@/lib/wire`; `useFeaturedPool` carries the prefer-online rule.
  `ShowcaseSheet` itself is untouched — it stays the live stage
  surface; ShowcaseRows is the reusable kit form.
- `ScrollVideo.tsx` — NEW scroll-driven video (F-39 `Dc8xeYzoOLh`).
  Sticky video in a tall wrapper; scroll fraction = playback
  fraction (rAF-throttled, direct `currentTime` writes). No autoplay,
  muted, `preload="metadata"`. Reduced motion: scrub off, first
  frame stands, caption says so. Load failure: explicit error line,
  no fake poster.
- `MapInterface.tsx` — NEW OSIRIS-style map surface (F-39
  `DcOGDRgkhj6`). Nominatim search (limit 5, pick from results) +
  OpenStreetMap embed via house helper `buildMapEmbedUrl`. Key-less,
  no new dependency, no new library. Coordinates only from Nominatim
  hits or a caller-supplied place. Explicit searching / none-found /
  error states.
- `GlassStartPage` — kit-ized by re-export: verified first-hand it
  takes NO props (a standalone page component); the kit re-exports
  it unchanged. Demo links to `/start` instead of embedding it.
- Demo page `FRIDAY/ui/app/kit/page.tsx` (+ client `KitDemo.tsx`):
  ScrollVideo over a CC0 sample video (MDN, labelled as such);
  ScrollPlaybook on a scrollable panel; ShowcaseRows fed by the live
  fleet/timeline endpoints (honest empties on failure); MapInterface
  centred on the house default city (`DEFAULT_SETTINGS.city`,
  Hyderabad) until searched; GlassStartPage linked at `/start`.

## Scope notes
- `DccLLkoPCT1` (checkpoint-1 open item): still no in-repo trace and
  no board text naming a distinct technique — stays open; if it names
  one, it joins the build list as a follow-up, not this checkpoint.
- No live-surface change: `/`, `/start`, and the stage sheets are
  untouched except the `motion.tsx` re-export shim (same exports,
  same implementation, new module path).
- No new dependency added. Kit CSS: the existing global classes in
  `app/globals.css` (`.reveal`, `.showcase-*`, `.sheet-progress`,
  `.parallax`, `.pill`, `.sheet-note`) — documented in the kit barrel.

## Tests (checkpoint-1 bar: `next build` + lint clean)
- `npm run build` + `npm run lint` NOT RUN this run — stated plainly,
  not claimed. Two routes were tried and both closed:
  (a) FRIDAY-Server has NO node/npm runtime (verified first-hand:
  `node`/`npm`/`npx`/`bun`/`deno` all absent; the ui `node_modules`
  tree exists but its `.bin/next` cannot run without a node binary;
  `FRIDAY/deploy_frontend.sh` covers the API frontend, not the ui
  build). Installing a runtime on the live server is out of scope
  for this checkpoint.
  (b) Local build on this VM was blocked: the branch tarball fetched
  via the GitHub API failed an execution-risk check, so it was
  deleted unused — no build, no install, no test was run against
  it. This VM's unauthenticated git path is also unreliable
  (rate-limited + stale refs vs the authenticated API), so no local
  clone was used.
- What DID verify: all 9 files transferred byte-for-byte
  (sha256 match, local vs server worktree); the moved
  `ScrollPlaybook` is a verbatim copy of `stage/motion.tsx`
  (231-line diff on the shim is the re-export only); the kit
  re-uses only existing imports (`@/lib/wire` types in the demo,
  `@/lib/glassWidgets` helpers, existing `globals.css` classes).
- PR #2158 CI runs on push (9 checks on the checkpoint-1 head) —
  CI result on the new head is the next build evidence; paired
  verifier Muse 5 (due ~22:00 IST) is asked to run `next build` +
  `npm run lint` in `FRIDAY/ui` and record the outcome before
  verdict. Until then this checkpoint is IMPLEMENTED, not TESTED.
- Reduced-motion behaviour verified per component by code path
  (scrub off / parallax off / reveal instant via existing CSS);
  no runtime probe run — build + lint is the checkpoint bar.
- Demo page renders with feeds unavailable: ShowcaseRows empty
  texts + MapInterface searching/none/error states are explicit in
  the components; no invented data anywhere in the demo.

## Next
Paired verification on PR #2167 (verifier owed — coordinator/BE names
it); then merge; board flip (WEB-008 → IN_REVIEW, then MERGED) rides
the repaired board PR #2151 (coordinator-only). 2h no-output bar:
~23:05 IST.
