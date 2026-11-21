# VyralX growth BGM shelf — phonk stock (TASK-VYR-030)

Growth BGM library on U2 (FRIDAY-Universe-2, Sydney):
`/opt/friday_universe/VyralX/data/bgm/` — audio files plus `catalog.json`.
The library is operator-provisioned (`VyralX/app/services/viral_bgm.py`):
a file whose name contains "phonk" counts as phonk, and `catalog.json`
entries carry `file / title / artist / categories / styles / moods`
(the loader ignores any extra provenance fields).

## What was stocked (2026-11-21, TASK-VYR-030)

Five NO LIMITS PHONK creator-selection tracks, downloaded from the
permission page below. Before this change the shelf held 20 tracks and
0 phonk, and cycle 11 (2026-11-21) warned `phonk_shelf_empty`; after
it the shelf holds 25 tracks and 5 phonk, and the loop's own warning
logic reports no warning (see Verification).

| File | Title | Duration | SHA-256 (first 12) | Categories |
| --- | --- | --- | --- | --- |
| `phonk_no-limits-phonk_reactor.mp3` | REACTOR | 118.9 s | `576988d485a2` | GAMING, VIRAL |
| `phonk_no-limits-phonk_rush.mp3` | RUSH | 119.3 s | `26cd64ae53e5` | SPORTS, AUTOS, VIRAL |
| `phonk_no-limits-phonk_vantage.mp3` | VANTAGE | 119.9 s | `93cf5cb00e8a` | GAMING, VIRAL |
| `phonk_no-limits-phonk_fastlane.mp3` | FASTLANE | 117.9 s | `87bb186dc97f` | GAMING, VIRAL |
| `phonk_no-limits-phonk_focus.mp3` | FOCUS | 117.8 s | `9ea36d3101a8` | VIRAL |

All five are MP3, 256–320 kbps, 48 kHz stereo (verified with
`ffprobe` on U2 at download time). Full SHA-256 fingerprints are in
`catalog.json` next to the files.

## Source and licence

- Source page: https://nolimitsphonk.com/journal/free-phonk-for-videos/
- Direct files: `https://nolimitsphonk.com/assets/creators/<slug>.mp3`
  (only the 15 `assets/creators/` recordings on that page are covered;
  the site's other releases are NOT included).
- Permission (effective 2026-10-06): free use in your own creative
  videos, Shorts and edits, including ordinary platform monetisation,
  with the credit below. The project does not register this collection
  in Content ID and makes no music-rights claims against permitted uses.
- Credit (required — put it in the video description or a clearly
  visible credit field of any published video that uses one of these
  tracks; it is also recorded per track in `catalog.json`):
  `Music: NO LIMITS PHONK — https://www.youtube.com/@nolimits_phonk`
- Not permitted: reselling or redistributing the files as a music pack
  or standalone release, claiming authorship, submitting them to
  distributors or Content ID. Brand advertising, sponsored integrations,
  games, apps, remixes, sampling and separately commissioned commercial
  productions need prior written agreement — none of those apply to the
  growth loop's unlisted videos, which only trim/duck the bed.

## Verification (loop probe, 2026-11-21, U2)

Run against the live library with the loop's own code
(`viral_bgm.library_status()` plus the two warning conditions from
`viral_loop.py`), before and after stocking:

- Before: 20 tracks, 0 phonk → `live_loop_warnings_would_be:
  ['phonk_shelf_empty']` (cycle 11 state file agrees).
- After: 25 tracks, 5 phonk (`FASTLANE, FOCUS, REACTOR, RUSH,
  VANTAGE`) → `live_loop_warnings_would_be: []`.
- Real bed: `prepare_music_bed(..., category="GAMING")` rendered a
  5-second bed from `phonk_no-limits-phonk_reactor.mp3` labelled
  `growth:REACTOR:phonk`, so a phonk track is actually selected and
  usable, not just counted.

The cycle-11 warning stays in `viral_loop_state.json` as the historical
record of that cycle; it refreshes when the next scheduled cycle runs.
No full loop cycle was forced — that would spend vision budget and
create renders; the probe above executes the loop's exact warning
logic on the live library.

## Note on SHELF.md

The task references "the SHELF.md rules", but no `SHELF.md` exists in
the repo, on Oracle Server 2, or on U2 (searched all three on
2026-11-21). This file is the shelf's record going forward. The rules
applied here are the ones that are verifiable: the growth policy and
catalog format in `viral_bgm.py`, the shelf's existing
`<category>_<artist>_<title>.mp3` naming, and the source page's
written free-use permission above. If a SHELF.md is written later, this
stock must be re-checked against it.

— Muse 1
