# TASK-VYR-065 — Hard niche avoid-list exclusion guardrail in discovery

**Task:** VyralX: hard niche avoid-list exclusion guardrail in discovery (P1)
**Owner:** Muse 4 — claimed hub #1483 comment 7144438110, 2026-11-25 ~02:35 IST
**Branch:** `muse4/task-vyr-065-niche-avoid-guardrail` (from main `894dbf08`)
**Work PR:** #1733 (https://github.com/surendra2304/FRIDAY-Universe/pull/1733; single work PR per owner order 7143628341 rule 1)
**Board:** `docs/collaboration/WORK_BOARD.yaml` TASK-VYR-065 AVAILABLE → CLAIMED (flip rides in this PR, rule 4)

## Acceptance (board record, source GAP-LIST.md §2, TASK-VYR-AVOID-GUARD, research note vyralx-niche-research-20261115)

Discovery rejects the researched ban-list niches by rule — anime compilations,
cricket/sports highlights, Bollywood edits, movie/TV scene compilations,
celebrity edits, unlicensed viral-clip compilations, borrowed gameplay,
borrowed exam lectures, automated finance advice — with the rejection reason logged.

## What was built (repo-side, verified first-hand this run)

**New module — `VyralX/app/services/niche_guard.py` (stdlib only: `re` + `logging`)**

One rule set shared by both discovery entry points, so the guardrail cannot be
bypassed through the other path:

- `BANNED_NICHES` — 9 rules, each with a stable id, a human label, and the
  phrases that trigger it. Matching is phrase-based on text normalised to
  `[a-z0-9 ]`, so case and punctuation cannot dodge a rule.
- Single words are used only where the word itself names the niche (`anime`,
  `bollywood`, `celebrity`, `gameplay`); ambiguous words match as phrases
  only — bare `cricket` does not match (a cricket-sounds sleep video is
  legitimate), bare `exam` does not, bare `highlights` does not (only
  sport + highlights phrases do).
- `check_candidate(candidate)` — checks title / description / channel text;
  returns `(allowed, reason)`, reason of the form
  `banned niche: <label> (matched '<phrase>')`.
- `check_query(query)` — a query naming a banned niche is rejected outright;
  the search is never issued.
- `filter_candidates(candidates)` — splits into `(kept, rejected)`; rejected
  entries are shallow copies carrying `rejection_reason` (inputs never
  mutated); each rejection is logged (`vyralx.niche_guard`, WARNING) with
  the video id and the reason, so the exclusion is auditable in the run log.

**Wiring — both live discovery paths, one choke point each**

- `VyralX/app/services/discovery.py` — `discover_youtube_videos` now
  pre-checks the query (banned query → `[]`, no API call, no quota spent)
  and filters candidates before returning. Covers all five callers
  (`app/main.py` API route, `autonomous_orchestrator.py`,
  `project_pipeline.py`, `task_dispatch.py`, `viral_repurposer.py`).
- `VyralX/scripts/find_viral_candidates_flat.py` — the supervised-cycle
  discovery path (proven in VYR-055): `run_query` pre-checks the query
  (`rejected_query` recorded, no search issued) and filters the ranked
  fresh pool; output gains `rejected_niche` (count) and
  `rejected_niche_reasons` (`[{id, rejection_reason}]`). The guard is
  loaded by file path (script runs standalone, no app imports); a missing
  guard file fails loudly.
- `VyralX/scripts/find_viral_candidates.py` — the non-flat script gets the
  same treatment (query pre-check + final filter) so the guardrail has no
  bypass, even though that path is currently unusable (yt-dlp per-video
  extraction hangs since 2026-11-24; see the flat script's docstring).

**Deliberately NOT changed:** the operator-configured `channel_avoid_topics`
setting (`VyralX/app/config.py`) is soft editorial guidance for *generation*
(`app/services/content.py`), not a discovery rule; the id-based
`data/rejected_sources.json` ledger (`viral_loop.py`) rejects known video
ids, while this module rejects *niches*, including ids never seen before.

## Tests (all run locally this run, 2026-11-25 ~02:50 IST)

- **New `VyralX/tests/test_vyr065_niche_guard.py` — 52 tests, 52 passed.**
  All 9 niches rejected with the niche named in the reason (18 title cases
  + per-niche label coverage); 4 banned queries rejected; the 10 proven
  discovery queries (6 flat + 4 non-flat) pass; 8 allowed titles pass;
  4 near-misses pass (cricket-sounds, bare highlights, bare exam, football
  drills); case/punctuation insensitivity; filter order/stamping/no-mutation;
  empty/None/missing-field safety; flat-script `run_query` end-to-end over a
  stub yt-dlp (banned row dropped despite the highest views, reason recorded;
  banned query returns `fresh: []` with `rejected_query`); static pin that
  `discovery.py` imports and calls the guard; guard module is stdlib-only.
- **Existing `VyralX/tests/test_vyr055_discovery_helpers.py` — 30 tests, 30 passed**
  (no regression in the flat-script helpers; `run_query` shape additions are
  additive keys only).
- **Existing `VyralX/tests/test_services_coverage.py::test_discovery_youtube_videos` — 1 passed**
  (mocked API results flow through the new filter untouched, order preserved).
- **Total: 82 passed + 1 passed, 0 failed.** `python -m py_compile` clean on
  all four touched files. `ruff check` clean on all five touched files.
- **Regression — no false positives on proven-good material:** guardrail run
  over all 17 merged pool items (`TASK-VYR-053/054/055-refresh-3/057-POOL.json`)
  and all 10 discovery queries: **0 rejections**.
- **CI wiring:** the new test is added to the VyralX contracts list in
  `.github/workflows/owner-workflows.yml` (same list as `test_vyr074_mapping.py`),
  so the REL-068 collection guard passes — a PR test must run in PR CI.

## Live leg — BLOCKED, with reason (not attempted)

The live proof is a real discovery run on VyralX-Server showing banned-niche
rejections in the live log. It is **not run** in this PR:

1. The owner stop order is still in force (no lift through watch058, hub
   7144369853, run scheduled 01:57 IST).
2. The VyralX-Server route itself is proven live by watch058's first-hand
   probe (`VyralX.service` active, local port 8010 answers HTTP 200) — the
   server is not the blocker; the stop order is the only gate.
3. No run_shell grant for VYR-065; no live step taken.

Per owner order 7143628341 rule 1 this is the task's SINGLE work PR, opened
genuinely BLOCKED on the live leg with the repo-side evidence above. The
paired verifier (named by Muse when this PR opens) re-tests live
independently when the gate lifts; the flat-script output fields
(`rejected_niche`, `rejected_niche_reasons`) are the exact evidence the
live run will produce.

## Honest limits

- The guardrail is a keyword-rule layer, not a classifier: a banned video
  whose title/description/channel never names its niche will pass. That
  residual risk is a live re-test item, not something this PR claims to close.
- The live leg, the verifier verdict, and any fix task for items that fail
  live are still owed after the gate lifts.

## States

- implemented: YES (repo-side; guardrail + wiring + tests + evidence + board flip)
- tested: YES (83 tests green locally; CI pending on this PR)
- merged: NO (awaiting Muse)
- deployed: N/A (repo code; no deploy leg for this task)
- production-verified: NO — live leg BLOCKED (owner stop order); verifier re-test owed

— Muse 4
