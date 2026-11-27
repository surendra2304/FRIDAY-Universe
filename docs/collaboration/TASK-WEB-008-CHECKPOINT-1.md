# TASK-WEB-008 — Checkpoint 1 (scope + inventory, filed 2026-11-27 ~20:20 IST)

Muse 17 | TASK-WEB-008 | Website: design-technique components for the FRIDAY site UI kit
plus the LumiList start-page pattern | Branch `muse17/web-008` @ `fae3ee05` (claim base)

## Claim verified first-hand
- Board on live main `8e5238a1`: TASK-WEB-008 AVAILABLE / owner `muse_17`, branch null,
  pr null (flip to CLAIMED rides coordinator board PR #2151, open, mergeable).
- Branch `muse17/web-008` verified via get-ref: `fae3ee05ff7f6972690d3bed1f01b3ba2c50b82d`.
- Claim posted hub #2045 comment 7219676811 (19:05 IST, read back).
- Usage at filing: 41% of free weekly limit, reset Nov 30 10:28 PM IST — no wrap-up.

## Source check — F-39 / F-04 item IDs not in the repo
- `git grep` at HEAD (live main, FRIDAY-Server): NO hits for `Dc8xeYzoOLh`,
  `LumiList`, or `F-39` in any tracked file. The F-39/F-04 source package
  (Instagram adoption re-audit corroboration set) is not in the repo; the
  board acceptance text itself names the techniques, so the build scopes
  from that text plus the in-situ implementations below.
- Naming gap (not a blocker): the glass start page in-repo cites GNTD
  (shortcode `DX7B57RM491`, crew-13), while the board cites F-04 item
  `DWG2zqlk7NO` (LumiList). Same pattern family (glass new-tab dashboard);
  confirm the mapping with the coordinator if it matters — no work waits on it.

## Inventory — verified first-hand (FRIDAY/ui, live main)
| # | Technique (board acceptance) | State in repo |
|---|---|---|
| 1 | Scroll-driven video (`Dc8xeYzoOLh`) | ABSENT — no video/scroll component tracked under `FRIDAY/ui`. Build new. |
| 2 | GSAP-style scroll animation (`DcBGh30yOLW`) | PRESENT in situ — `stage/motion.tsx` house playbook (scroll reveal, progress, pin + scrub, parallax ≤ 3 layers, IO-based, reduced-motion hard rule) + `gsap@3.15.1` / `@gsap/react@2.1.2` installed. Needs extraction into a reusable kit component. |
| 3 | OSIRIS-style map interface (`DcOGDRgkhj6`) | ABSENT as a component — only map-search/embed URL helpers inside `GlassStartPage` (`lib/glassWidgets.ts`). Build new. |
| 4 | Netflix-style portfolio layout (`Dc1I-6SSLxV`) | PRESENT in situ — `stage/ShowcaseSheet.tsx` (TASK-IG-WEB-05, cites `DePJT2NJvz_`: billboard + browsable rows over the real fleet/timeline). Needs extraction into a reusable kit component. |
| 5 | LumiList start-page pattern (`DWG2zqlk7NO`, F-04) | PRESENT in situ — `components/GlassStartPage.tsx` (557 lines, TASK-IG2-WEB-07, GNTD pattern) mounted at `/start` (`app/start/page.tsx`, 45 lines). Already a component; kit-ize + demo only. |
| 6 | Remaining F-39 items (`DccLLkoPCT1`, `DePJT2NJvz_`) | `DePJT2NJvz_` is the ShowcaseSheet source (see #4). `DccLLkoPCT1` has no in-repo trace — carry as an open item; if it names a distinct technique, it joins the build list at checkpoint 2. |

Existing kit shape (top level `FRIDAY/ui/components/`): `ControlGate.tsx`,
`GlassStartPage.tsx`, `Orb.tsx`, `RankBoard.tsx`, `ThemeRoot.tsx`, `VoiceCall.tsx`,
plus `reactbits/` (Counter, Magnet, Orb, ShinyText, SplitText, SpotlightCard),
`stage/` (sheets + motion), `ultron/`.

## Build plan (checkpoint 2)
1. NEW kit components: `ScrollVideo` (scroll-driven video, IO + reduced-motion
   fallback to static poster) and `MapInterface` (OSIRIS-style map surface,
   key-less OSM/Nominatim feeds only — same no-invention rule as GlassStartPage).
2. Kit extractions: `ScrollPlaybook` from `stage/motion.tsx` (no behaviour change
   to the live stage) and `ShowcaseRows` from `stage/ShowcaseSheet.tsx`
   (billboard + rows over caller-supplied data, not the fleet endpoint).
3. Kit-ize `GlassStartPage` (already a component; confirm its public props
   read as a kit component) and add a demo page exercising each component.
4. Scope limit (board): components + demo page only — which design the live
   site adopts stays the owner's pick. No live-surface change.
5. Tests: `next build` + lint clean; reduced-motion behaviour verified per
   component; demo page renders with feeds unavailable (explicit states, no
   invented data).

## Transport note
- Bridge (friday-universe.duckdns.org/bridge/mcp) answered 6 run_shell /
  get_system_info calls this run, then initialize failed twice in a row
  (`init_http=000`, no session, ~20:15 IST). Checkpoint 1 filed via the
  GitHub API instead. Bridge health to re-check next run; no live leg is
  owed for checkpoint 1 (repo-only).

## Next
Checkpoint 2: implement `ScrollVideo` + `MapInterface`, extract
`ScrollPlaybook` + `ShowcaseRows`, demo page; then work PR update + paired
verification. 2h no-output bar: ~21:05 IST.
