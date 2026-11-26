# TASK-VYR-072-FIX-01 — Implementation (repo-side): doubled captions in a framed render's .ass

- Task: TASK-VYR-072-FIX-01 — "Held render framed--bh5VGbrbLI-5970f1 carries doubled captions (multiple_caption_tracks:2): repair or re-render the caption track to a single track and re-run held-render QA to pass."
- Owner: Muse 14. Branch: `muse14/task-vyr-072-fix-01` (base main `b74efa00`).
- Filed from: the TASK-VYR-072 live leg, finding Q1 (docs/collaboration/TASK-VYR-072-LIVE-LEG.md section 4b, work PR #1891). Claimed by Muse 14 as the double-scope pair (hub #1483 comment 7175223802, ~03:03 IST 2026-11-26).
- Repo-side only. No live re-render, no vision sampler run, no server move, no new credential. The live leg (repair/re-render on VyralX-Server + re-run held-render QA + vision sampler) is gated on coordinator clearance — see "What remains".

## 1. The defect (Q1, as measured live)

The held render `framed--bh5VGbrbLI-5970f1.mp4` (job 802, video `-bh5VGbrbLI`, PETS, "Dog Watches Man Press Buttons", Nov 18) has a sibling `.ass` with 20 dialogue events, 0 malformed, 20 speech events, 0 hook events. `ass_caption_track_count` = **2**; `caption_track_gate` → `(False, "multiple_caption_tracks:2")`. Overlapping pairs verified first-hand on the server:

- 0.0–1.0 "CRAP, PRESS THE BLUE BUTTON." over 0.0–3.34 "WATCH WHAT HAPPENS WHEN HE POINTS AT THAT BUTTON."
- 0.0–3.34 "WATCH WHAT HAPPENS…" over 1.0–2.0 "OH NO!" and over 2.0–3.56 "WHAT YOU GOT BEEF WITH"
- 25.28–27.28 "OH NO!" over 25.34–29.23 "HE SMILES AS THE DOG STAYS STILL BESIDE THE TWO BUTTONS."

Precise scope (as filed): the defect is in the render's subtitle track; frame-visible confirmation via the vision sampler was not run, so the claim is "subtitle track carries doubled captions", not "frames show doubled captions". This is a defect in a pre-existing Nov 18 held render, not in any of IG2-VYR-01..05.

## 2. Root cause (scoped precisely — the first-pass theory was right, with a date)

The two long cues are the framed edit's **hook** (0.0–3.34s, at the render start) and **payoff** (25.34–29.23s, ending at the render end, 29.23s). The short cues are the source video's own speech (Whisper timings). The doubling is the hook/payoff lines overlapping the source speech **in the same style and screen zone**.

- **Historical cause:** the render predates TASK-VYR-022 by ~1 day. VYR-022 ("framing caption band", commit `ca864e89`, 2026-11-19; merged PR #1053, `b51330d2`) introduced the AntonFraming top band (Alignment 8, opaque box) plus the `_duplicates_framing_line` dedup in `framed_cues`. Before it, `_write_ass` wrote EVERY cue in AntonBold — verified by reading the pre-VYR-022 function (`git show ca864e89^:VyralX/app/services/viral_remix.py`): no framing style, no overlap check. The Nov 18 render (file dated Nov 18 23:46, per TASK-DB-003) was authored by that code.
- **Current forward path (already fixed for new renders):** `framed_cues` marks hook/payoff with `"framing": True` (top band) and drops source speech cues duplicating a framing line; `render_framed` is called in production only from `produce_framed_short` with `framed_cues` output. Verified: a Q1-shaped input through `framed_cues` + `_write_ass` now counts exactly one speech track (test `test_framed_cues_plus_write_ass_produces_single_track`).
- **Remaining gap (this fix):** `_write_ass` — the single writer all four renderers share (`render_scene_timed`, `render_with_commentary`, `render_with_original_audio`, `render_framed`) — had NO overlap validation. It would silently emit a doubled `.ass` for any overlapping same-style input. The other `.ass` writer, `captions.write_ass`, DOES raise on overlap. So the defect class was still producible through `_write_ass`.
- **Not the cause:** this is NOT the 823/841/861 class (source footage's own burned-in captions — those renders tile cleanly in the `.ass` while the vision gate finds extra tracks). Here the doubling is IN the `.ass` itself. The QA gate (`held_render_qa.ass_caption_track_count`) and the `.ass` parser were NOT changed — per the board acceptance, the defect is not fixed by editing the gate or the parser; the caption track itself is repaired.

## 3. What changed

### 3a. `VyralX/app/services/viral_remix.py` — `_write_ass` is now fail-closed

- New constant `_ASS_SAME_BAND_OVERLAP_TOLERANCE_S = 0.1`.
- Per-style validation, after centisecond rounding (the timestamps libass actually sees — the same semantics as `captions.write_ass`): a cue must span >= 1 centisecond; cues in one style must be ordered by start; two cues in the SAME style overlapping by more than 0.1s raise `ValueError` naming the style, the times, and the cue text. Cross-style overlap (AntonFraming vs AntonBold) is allowed — different bands by design (TASK-VYR-022), pinned by the existing tests.
- **Why a 0.1s tolerance, not zero:** `_row_cue` extends every caption row by 0.06s, so consecutive rows from fast speech legitimately micro-overlap. Verified empirically: `_cues_from_words` on fast-speech word timings (0.02s gaps) produces rows overlapping by 0.04s. A zero-tolerance check would break the normal commentary path. The tolerance (0.06s extension + centisecond rounding + margin) keeps that deliberate behaviour; the Q1 overlaps (1.0–3.89s) are an order of magnitude above it.

### 3b. `VyralX/app/services/viral_framing.py` — new `repair_doubled_ass`

Re-authors a doubled framed-render `.ass` to a single speech track, for the live leg to apply to the existing render without a full re-render:

- Parses the `.ass` (`held_render_qa.parse_ass_dialogue`; refuses malformed files).
- Takes the hook and/or payoff text from the job record (at least one required). Events matching a framing line (via the existing `_duplicates_framing_line` token logic — case/punctuation-insensitive) are re-styled to AntonFraming; when several events match one line, the longest is the framing line and the rest are dropped as speech duplicates (the job-801 shape).
- Re-writes through the production writer (`viral_remix._write_ass`) — so the writer's own per-style validation is the first proof — to a NEW path (the source is never overwritten).
- Re-parses the result and requires `ass_caption_track_count(speech) == 1` (the QA's strict measure) — otherwise raises instead of claiming success.
- Returns a report (events in/out, re-styled framing events, dropped duplicates, final track count).
- Fails closed: no framing text, no matching event, or a remaining speech-vs-speech overlap all raise `ValueError`.

### 3c. Test fixtures updated to the current production cue shape

- `VyralX/tests/test_viral_framing.py` (`_capture_render`) and `VyralX/tests/test_vyr032_doubled_caption.py` (`_capture_framed`): the fixtures passed an unflagged hook overlapping the speech cue in AntonBold — exactly the Q1 defect shape, from before VYR-022. They now pass the current production shape (hook flagged `"framing": True`, sorted by start). `render_framed` is called in production only from `produce_framed_short` with `framed_cues` output, so no production caller passes the old shape.

### 3d. CI collection (REL-068)

- `.github/workflows/friday-universe-ci.yml`: the VyralX tier-1 list now also collects `tests/test_vyr072_fix01_doubled_caption.py` (new), `tests/test_vyr032_doubled_caption.py`, and `tests/test_viral_framing.py` (both edited) — the VYR-059 precedent. The new test file is hermetic (no ffmpeg, no vision, no network); the two edited files already ran cleanly in the lock venv locally.

## 4. Tests

- Baseline (before the fix, on main `b74efa00`, venv from `VyralX/requirements.lock` + pytest 9.2.0, Python 3.12.3): **146 passed, 0 failed** across `test_viral_framing.py`, `test_vyr032_doubled_caption.py`, `test_vyr044_held_render_qa.py`, `test_vyr045_caption_dedup.py`, `test_ass_captions.py`.
- New file `VyralX/tests/test_vyr072_fix01_doubled_caption.py` (9 tests): Q1 reproduction (the reconstructed doubled `.ass` counts 2); `_write_ass` rejects the Q1 cue list and raises on out-of-order / zero-length; cross-style overlap and tiling + row-extension micro-overlap still write; repair restores a single track (8 events in, 8 out, 2 framing re-styled, 0 dropped, count 1, source untouched); repair drops a speech duplicate of the payoff (job-801 shape); repair fails closed (no framing text / no match / remaining speech-vs-speech overlap); forward path (`framed_cues` + `_write_ass`) produces a single track. **9 passed, 0 failed.**
- After the fix, the same six files: **155 passed, 0 failed** (146 baseline + 9 new), exit 0. The first run after the writer fix caught 4 failures in the two `_capture_framed`/`_capture_render` fixtures (the legacy cue shape) — fixed by updating the fixtures to the current production shape (3c), not by weakening the validation.
- Full VyralX sweep: [pending — run in progress at doc time; update before merge if it reports anything in the touched files].
- The Q1 `.ass` in the tests is a reconstruction: the 6 overlap events are verbatim from the live-leg evidence; the 2 middle events are representative tiling fill, labelled as such in the test file (the live leg lists 20 speech events; only the overlap events are needed to reproduce the doubling).

## 5. Five states (owner standard: merged code is NOT implemented)

| State | Value |
| --- | --- |
| Implemented | YES — repo-side: writer fail-closed + repair utility + tests |
| Tested | YES — 155/155 in the relevant suite (9 new FIX-01 tests) |
| Merged | NO — this work PR is the merge vehicle |
| Deployed | NO — no live change; the live leg is gated (below) |
| Production-verified | NO — the render has not been repaired/re-rendered live and QA has not been re-run on it |

## 6. What remains (the live leg — gated, needs coordinator clearance)

1. On VyralX-Server, repair the render's caption track: run `repair_doubled_ass` on `renders/framed--bh5VGbrbLI-5970f1.ass` with the job-802 hook/payoff texts from the job record (hook "Watch what happens when he points at that button.", payoff "He smiles as the dog stays still beside the two buttons." — as quoted in the live-leg evidence), writing to a new `.ass`, and replace the render's `.ass` with the repaired one — OR re-render the excerpt with the current (fixed) code path. Either satisfies "repair or re-render".
2. Re-run `run_held_render_qa` on the render: the caption_track gate must pass (`single_caption_track`), and the `.ass` corroboration must count 1.
3. Frame-visible confirmation via the vision sampler (the live leg measured the track from the `.ass` only) — part of the fix verification per the board acceptance.
4. File the live evidence in a follow-up doc and flip FIX-01 to MERGED in that work PR (the REL-087 rule: a work PR must not flip its own task to MERGED citing itself).

The live leg needs coordinator clearance (live re-render/repair + vision sampler on VyralX-Server), like the VYR-072 live leg did (WATCH113). It does NOT need a server move or a service restart. The owner stop order on server MOVES still stands and is not touched by this leg.

## 7. Notes

- The QA gate and the `.ass` parser were not modified (board acceptance criterion 3). The gate already catches the defect — that is how Q1 was found.
- The watermark finding (Q2, held renders carry no provenance watermark) is a separate, pool-wide item for the coordinator's decision — not part of this fix.
- The 0.1s writer tolerance and the QA's strict any-overlap count disagree on micro-overlaps (<=0.1s): the writer allows them (deliberate row extension), the QA counts them as 2. The repair validation uses the QA's strict count, so a repaired `.ass` is held to the strict standard. A new render with a micro-overlap would pass the writer but be flagged by the `.ass` corroboration column — that is the pre-existing behaviour of the QA column, not something this fix introduces.
- Scratch venv used for the runs: `~/workspace/venvs/muse14-fix01` (built from `VyralX/requirements.lock` + pytest/pytest-asyncio; `/tmp` is a 512M tmpfs and could not hold the install).

— Muse 14
