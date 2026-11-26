# TASK-VYR-083 — Format-template registry additions

Worker: Muse 5. Claim: hub #1483 comment 7156341324, 2026-11-25 ~13:25 IST.
Branch: `muse5/task-vyr-083-format-registry`, from main `36e2e2c9`,
fast-forwarded to main `c554c54f` before the work PR opened (branch
had 0 commits on top of old main at the fast-forward — plain ref move).
Base for all verification below: main `c554c54f` unless stated. Work
PR #1818 (head `72bc3f7f` at open).

## Acceptance

> Register all three in VyralX's format-template registry with
> production specs. VyralX's standing rules apply to every pilot:
> short excerpts only, her English narration, subtitles always on,
> BGM, unlisted review-first. Done = three registry entries + one
> pilot render in one of the formats passing machine QA.

## What was already on main (verified first-hand, not assumed)

- The registry leg's shape was DONE by TASK-IG-VYR-09 (merged):
  `VyralX/app/data/format_templates.json` carried 8 templates, and
  `VyralX/app/services/format_templates.py` loads + validates them
  (required fields, structure shares summing to 1.0, lanes inside
  the owner's three, name + source_strategy screened against the
  compliance gate's excluded tokens). The IG-VYR-09 suite (9 tests)
  pins the expected set of 8 ids.
- The three sources are board-cited only: vyralx package V-02 (item
  Dag2UFvTD2C — the build-in-public Day-1 series format) and watches
  Df17y3toZBu (AI 3D cartoon comedy short) and DfHutKDSsEM (the
  trail-transition editing technique). A repo code search for
  Dag2UFvTD2C returns 0 hits — the source package/watch records are
  not in the repo. Provenance is carried as `ig_sources` on each
  entry, as the existing entries do.

## What changed (4 files + this doc + board flip)

1. `VyralX/app/data/format_templates.json` (+3 templates, registry
   8 -> 11; `registry_version` stays `ig-vyr09-1`, as the
   `what_if_narrated_story` addition did before it):
   - `build_in_public_day1` — ig_sources `Dag2UFvTD2C`; lanes
     `tech_ai`; target `[30, 60]`; beats day_hook 0.15,
     build_progress 0.45, setback_lesson 0.25, next_step_close
     0.15. Hard rules carry the standing pilot rules verbatim
     (short excerpts only, English narration in FRIDAY's voice,
     subtitles always on, BGM, unlisted review-first).
   - `ai_3d_cartoon_comedy_short` — ig_sources `Df17y3toZBu`;
     lanes all three; target `[30, 60]`; beats gag_hook 0.15,
     setup 0.25, escalation 0.35, punchline 0.15, tag_close 0.10.
     Hard rules mandate ORIGINAL characters owned by the channel
     and forbid game / anime / film / third-party characters.
   - `trail_transition_technique` — ig_sources `DfHutKDSsEM`;
     lanes all three; target `[5, 15]` (a transition segment, on
     the `flyover_segment` precedent); beats outgoing_scene 0.30,
     trail_build 0.30, transition_moment 0.15, incoming_settle
     0.25. Hard rules: the transition must never obscure narration
     or subtitles; the trail is generated in the edit, never copied
     from a reference video's artwork.
   - No excluded token (`anime`, `gameplay`, `sports`,
     `bollywood`, `movie`, `compilation`, `reupload`) appears in
     any new name or source_strategy — the gate screen passes by
     construction; the tokens appear only inside `hard_rules` as
     prohibitions, which the screen does not cover (same pattern as
     `original_character_series`).
2. `VyralX/tests/test_ig_vyr09_format_tooling.py`:
   `EXPECTED_TEMPLATES` 8 -> 11 ids.
3. `VyralX/tests/test_vyr083_format_registry.py` (new, 5 tests).
4. `.github/workflows/owner-workflows.yml`: the new test file added
   to the VyralX pytest list in the contracts job (REL-068
   collection guard — a PR test file must run in PR CI).

## Tests (pytest, local run, no server execution)

- New suite `test_vyr083_format_registry.py`: **5/5 pass**.
- Neighbours re-run in the same process:
  `test_ig_vyr09_format_tooling.py` 9/9,
  `test_vyr062_stick_figure_series.py` 8/8,
  `test_ig_vyr04_series_automation.py` 8/8 — **30/30 pass total**.
  (Fresh clone of main `c554c54f`; venv with pytest 9.2.0, Pillow
  13.0.0, httpx, pydantic, pydantic-settings — the neighbour suites
  need the last three for collection via `remix_flow`/`app.config`.)
- Clean-main check: the new suite against the pristine registry
  gives **5 failed / 0 passed** (`load_templates` raises
  `ValueError` on the unknown ids) — the tests pin what this task
  adds, by design.
- Lint: `ruff check --select F821` (the rule CI enforces for
  VyralX) clean on both touched Python files.

## Live leg

NOT RUN — gated, not refused. Done needs one pilot render in one
of the formats passing machine QA; the pilot render is gated:
VyralX-Server is down (S2 `VyralX/` tree deleted, cookies and
exclusion ledgers gone) and the owner stop order (~16:42 IST
2026-11-24) is still in force. No live step taken, no run_shell
grant for VYR-083. Verifier re-tests live when the gate lifts.

## Board flips (in this PR)

- TASK-VYR-083 AVAILABLE -> IN_REVIEW (owner muse_5, branch
  `muse5/task-vyr-083-format-registry`, pr 1818).
- TASK-VYR-051 is already MERGED on main (coordinator board PR
  watch085; merge `01e49d30`) — verified first-hand this run; no
  flip rides here.

## Pushed file SHAs (read back from the branch)

- `VyralX/app/data/format_templates.json`: blob `ad8c8e19`
  (commit `4b7c3e9c` — first of the four code commits)
- `VyralX/tests/test_ig_vyr09_format_tooling.py`: blob `c5b95241`
- `VyralX/tests/test_vyr083_format_registry.py`: blob `330e5011`
- `.github/workflows/owner-workflows.yml`: blob `809007a3`
- This doc: blob recorded in the hub status post after push (a file
  cannot carry its own blob sha).

— Muse 5
