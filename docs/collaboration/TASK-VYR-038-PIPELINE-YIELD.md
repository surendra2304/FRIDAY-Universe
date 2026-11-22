# TASK-VYR-038 — VyralX pipeline yield: evidence (work in progress)

- Task: `TASK-VYR-038` — render-fit profile on the excerpt cut + 20-track BGM
  shelf confirmation on U2 + real-track gate field per job + headline emoji
  glyph fix.
- Branch: `muse5/task-vyr-038-pipeline-yield`, base main `a9c94dfa`
  (2026-11-23 ~03:14 IST). Claim: hub comment 7084681956 (~01:15 IST).
- Loop stays OFF, uploader stays paused, renders held unlisted.

## 1. Excerpt cut — render-fit profile (code + deploy verified; cycle proof owed)

- The excerpt cut already uses the render-fit profile in code (TASK-VYR-023):
  `VyralX/app/services/viral_framing.py::_cut_excerpt` calls
  `_excerpt_command` — 720x1280 box, fps cap 30, ultrafast/crf23,
  threads 2, aspect preserved, never upscaled, never cropped. Pinned by
  `tests/test_viral_framing.py`. No code change was needed for this leg.
- Deployed state verified 2026-11-23 ~03:20 IST: the U2 checkout
  (`03378ba4`, clean) contains `_excerpt_command` (file fetched at that
  SHA, 4 matches for `_EXCERPT_WIDTH|_excerpt_command`), so the deployed
  code already carries the fix.
- Still owed: the supervised-cycle proof that the cycle-1 timeout class
  is gone. That needs a supervised cycle, which needs Muse's order —
  the loop stays OFF until he orders one.

## 2. U2 BGM shelf — stocked (probe 2026-11-23 ~03:20 IST, read-only)

- Via bridge `run_shell` on S2 → `ssh ubuntu@16.176.9.247`, read-only.
- `/opt/friday_universe/VyralX/data/bgm/` exists: **25 audio files**,
  `catalog.json` present with **5 catalogued tracks, 0 orphans**.
  `bgm_library/` (monetisation) does not exist — expected, policy is growth.
- Catalogued (all phonk): REACTOR, RUSH, VANTAGE, FASTLANE, FOCUS
  (`phonk_no-limits-phonk_*.mp3`, categories GAMING/VIRAL/SPORTS/AUTOS).
- Bare files (usable via `load_catalog`, title = file stem, no category
  affinity): comedy_kazumi-totaka_mii-channel-theme,
  comedy_kevin-macleod_carefree, comedy_kevin-macleod_monkeys-spinning-monkeys,
  comedy_kreepa_oh-no, howto_dua-lipa_levitating,
  howto_pharrell-williams_happy, howto_silent-partner_spring-in-my-step,
  money_lisa_money, motivation_imagine-dragons_believer,
  pets_american-authors_best-day-of-my-life, pets_bensound_ukulele,
  pets_kevin-macleod_life-of-riley, phonk_no-limits-phonk_reactor,
  phonk_no-limits-phonk_rush, phonk_no-limits-phonk_vantage,
  phonk_no-limits-phonk_fastlane, phonk_no-limits-phonk_focus,
  space_ludovico-einaudi_experience, sports_interworld_metamorphosis,
  sports_moondeity_neon-blade, sports_survivor_eye-of-the-tiger,
  viral_glass-animals_heat-waves, viral_imagine-dragons_enemy,
  viral_masked-wolf_astronaut-in-the-ocean, viral_oneheart_snowfall.
  (25 files: the 5 catalogued phonk + 20 bare.)
- Raw probe output: `/tmp/vyr038_bgm_shelf.txt` on the run host.

## 3. Real-track gate field per job (implemented + tested)

- `VyralX/app/services/viral_bgm.py::is_real_track_label(label)` — True
  only for `growth:<title>` / `monetisation:<title>` labels, False for
  `synth_fallback` and empty. One function owns the check; the produce
  paths never string-match the label.
- Both produce paths record `"bgm_real_track"` in the RenderJob
  `options_json` and in the returned result dict, next to `bgm_source`:
  `viral_framing.produce_framed_short` (framed) and
  `viral_remix.produce_viral_short` (commentary).
- Tests: `tests/test_viral_bgm.py` (label gate cases + label assertions
  in the prepare test), `tests/test_viral_framing.py`
  (`test_produce_framed_short_records_bgm_real_track` — full produce
  run with stubs, real-track True and synth_fallback False, in both
  the result and the persisted options).

## 4. Headline emoji glyph fix (implemented + tested; render proof owed)

- Defect (coordinator watch 7075907547, VYR-032 PASS): "an emoji in the
  static top headline renders as a hollow box glyph".
- Root cause, verified: the static top headline is the framed
  hook/payoff burned by `viral_remix._write_ass` in the `AntonFraming`
  top-band style (`_ASS_FRAMING_STYLE`: `Style: AntonFraming,Anton,...`),
  and the thumbnail headline is drawn by
  `thumbnail_designer.generate_genre_thumbnail` with Montserrat-Black /
  Anton. Neither font carries emoji glyphs, and the U2 render host has
  **no emoji font at all** (`fc-list`: 8 fonts total, 0 emoji, Anton
  absent) — so any emoji reaching those surfaces must tofu.
- Fix: emoji never reach a rasterised surface. `strip_emoji` in
  `app/services/viral_quality.py` (ranges mirror the packaging emoji
  counter, widened to the whole `\U0001F000-\U0001FAFF` block plus
  variation selectors, ZWJ and the keycap combiner), applied at three
  points: `sanitize_spoken_text` (hook/payoff, before TTS and the
  burn-in), `_write_ass` (the burn-in boundary, covers any cue source
  including transcript cues), and the thumbnail headline in
  `generate_genre_thumbnail` (before measuring/drawing).
- The YouTube title/description keep their emoji — `_clean_title` does
  not strip them, and they render natively on YouTube. The produce test
  asserts the narration loses the emoji while the title keeps it.
- Alternative considered and not taken: installing an emoji font asset
  on U2 (e.g. `fonts-noto-color-emoji`) so the glyph renders in colour.
  Rejected for this leg because libass colour-emoji rendering on the
  host is unverified — it needs a test render to prove, which needs a
  supervised cycle. If Muse wants the asset route instead, that is a
  host-provisioning decision, not a code change; the strip stays as the
  deterministic guarantee of "no hollow box".
- Tests: `tests/test_vyr014_quality_gates.py`
  (`test_spoken_text_strips_emoji_for_burn_in`, incl. flag and keycap),
  `tests/test_viral_framing.py`
  (`test_write_ass_strips_emoji_from_burned_captions`).
- Still owed: the next render proving no hollow box (supervised cycle).

## Tests run (offline, 2026-11-23 ~03:40 IST)

- 150 passed: `tests/test_viral_bgm.py`, `tests/test_vyr014_quality_gates.py`,
  `tests/test_viral_framing.py`, `tests/test_viral_loop.py`,
  `tests/test_viral_loop_audition.py`, `tests/test_vyr039_remix_music_bed.py`
  (local venv, exact-main tree; pytest 9.2.0).
- Pre-existing failures found during testing, NOT caused by this change:
  `tests/test_vyr009_compliance_gate.py` (2 tests) fails identically on
  pristine main — the test stubs `app.services.viral_remix` in
  `sys.modules` without `_run`/`build_music_bed`, and
  `prepare_music_bed`'s lazy import hits the stub (verified by running
  the same tests against pristine main files).
- `tests/test_ass_captions.py`, `tests/test_backfill_public_metadata.py`,
  `tests/test_growth_wiring.py` need `fastapi`, not installed in the
  local venv; CI covers them.

## Owed before merge-readiness

- Deploy this branch to U2 + a supervised cycle (Muse's order): proves
  leg 1 (no excerpt-cut timeout) and leg 4 (no hollow box in the next
  render), and exercises leg 3 (`bgm_real_track` True on a real job).
- Board flip AVAILABLE → CLAIMED rides in the work PR (this branch).
