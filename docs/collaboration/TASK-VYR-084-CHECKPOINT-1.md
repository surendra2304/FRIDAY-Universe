# TASK-VYR-084 — CHECKPOINT 1 — scoping: source lists not in the repo

- **Task:** VyralX: record the 100-faceless-ideas list and the space-movies list into channel_strategy.json
- **Worker:** Muse TP6. Claim of record hub 7164711567 (2026-11-25 ~19:34 IST).
- **Branch:** `musetp6/task-vyr-084-named-lists` @ main 3b8c0307 (no commits yet — scoping only).
- **Board:** TASK-VYR-084 AVAILABLE / owner muse_tp6 (queue pos 3, watch088); sources per the board record: vyralx package V-04 (item `DeUpDUwDID-`, a 100-item faceless channel-ideas list with per-niche RPM figures) and the V-07 round-8 addendum (item `DfaN9_fEVNy`, a space-movies listicle, on-lane reference for the Space & Science lane).

## Scoping — first-hand, main 5c901138 (2026-11-25 ~20:45 IST)

All searches below are repo-wide `git grep` / `git log` against the explicit main sha (not a stale ref — this clone's `origin/main` is a single-branch ref stuck at b9a4c8cfc; the explicit sha was used throughout).

- `DfaN9_fEVNy`: **zero hits outside the board's own VYR-084 record.** No space-movies list content — no titles, no items — anywhere in the repo.
- `DeUpDUwDID-`: only three places — `VyralX/app/data/channel_strategy.json` (`faceless_idea_examples`), `VyralX/tests/test_ig3_vyr01_named_lists.py` (assertions), and the board record. The full 100-item list is **not exposed in the repo**; only the 8 named ideas + RPM range $3–15 are recorded.
- V-04 / V-07 package files: **none in the repo.** The packages exist only as references — the board record, `VyralX/docs/CHANNEL_STRATEGY.md:62`, and the test file's docstring (which says the re-watch diff covered "package entries V-04/V-06/V-07").
- "round-8" / "addendum": no content anywhere except the board record.
- Workspace-wide grep on this VM: `DfaN9_fEVNy` appears only in `WORK_BOARD.yaml` snapshots; `DeUpDUwDID-` only in board snapshots + `channel_strategy.json` + the test file. No IG corpus package store on this VM.
- `VyralX/app/data/channel_strategy.json` on main 5c901138: keys are `browser_toolkit_reference`, `creator_tools_reference`, `faceless_idea_examples`, `free_generator_shortlist`, `free_route_alternatives`, `lanes`, `listicle_tool_patterns`, `niche_selection_criteria`, `note`, `playbook_version`, `series_seeds`, `teaching_channel_watchlist`. No space-movies key exists.

## Finding

**VYR-084 cannot complete from repo sources alone.** The two lists' full contents live in the IG corpus packages V-04 / V-07, which are not in the repo and not locatable from it.

- **V-04 leg:** the content the corpus exposes (8 named ideas + RPM $3–15) is **already recorded** under `faceless_idea_examples` (TASK-VYR-063, commit 40e6ae2c2, 2026-11-16; verified first-hand on main 5c901138 this run — see hub status). Either the full 100 must be supplied, or this leg is already satisfied.
- **V-07 leg:** nothing is recorded and nothing is available in the repo. The space-movies listicle items must be supplied.

## Asked of the coordinator (Muse)

1. Supply the V-07 round-8 addendum item `DfaN9_fEVNy` contents (the space-movies listicle items as named in the corpus), or point to where the V-07 package is readable.
2. Rule on V-04: is the full 100-item list available to supply, or does the already-recorded 8 named ideas + RPM range satisfy the V-04 leg of VYR-084?

## Proposed record shape (once supplied)

- New key `space_movies_reference` in `channel_strategy.json`: `status` `reference_only_unverified`, `ig_sources` `["DfaN9_fEVNy"]`, items exactly as named in the listicle, note carrying the unverified / creator-claim language (same pattern as the VYR-063 sections; RPM figures, if any, flagged UNVERIFIED — planning hints, never revenue facts).
- Extend `VyralX/tests/test_ig3_vyr01_named_lists.py` with exact-name assertions for the new section (same pattern as the VYR-063 tests).
- Update `VyralX/docs/CHANNEL_STRATEGY.md` to list the new section.
- Board flip rides in the work PR per rule 4.

## Next

Awaiting the coordinator's supply / ruling (items 1–2 above). Then: implement the JSON + test + docs changes, run the VyralX tests first-hand, and open the work PR. No repo code was changed in this checkpoint.

— Muse TP6
