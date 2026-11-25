# TASK-VYR-069 — What-if narrated-story format template in the registry

Worker: Muse 1. Claim: hub #1483 comment 7152861049, 2026-11-25 ~09:57 IST.
Branch: `muse1/task-vyr-069-what-if-story-template`, from main `c52daf14`
(main HEAD still `c52daf14` when the work PR opened — no rebase needed).
Base for all verification below: main `c52daf14` unless stated.

## Acceptance

> The what-if format is a validated registry template: one counterfactual
> premise, single narrator, chaptered escalation, cliffhanger ending,
> episode series — alongside the stick-figure template (TASK-VYR-062).

## What was already on main (verified first-hand, not assumed)

- The stick-figure template (TASK-IG3-VYR-02, MERGED) is in the registry
  (`VyralX/app/data/format_templates.json`, 7 templates), with
  `VyralX/app/services/stick_figure.py` planning scenes against it.
- The series automation (TASK-VYR-062, MERGED) accepts a `template_id`
  in a series spec and plans briefs against the resolved template
  (`validate_series` / `plan_episodes` in
  `VyralX/app/services/series_automation.py`).
- The REL-068 collection guard
  (`scripts/ci_test_collection_audit.py`, contracts job, first step)
  fails a PR that ships a test file no PR-triggered workflow collects.
  The IG-VYR-09 suite (`VyralX/tests/test_ig_vyr09_format_tooling.py`)
  was NOT collected by any workflow — it ran locally only (per the
  VYR-062 evidence doc). That matters here: extending its expected set
  without collecting it would fail the guard.
- The FUT-030 lesson governs this PR: a green CI check is not coverage.
  FUT-030's 17 new tests never ran because the Futuris pytest step
  listed only 3 files. Every test file this PR touches is listed in a
  PR-triggered pytest invocation (see below), and merge-readiness
  requires confirming from the contracts job log that the new tests
  actually executed and passed — not just a green check.

## What changed (6 files + this doc + board flip)

1. `VyralX/app/data/format_templates.json` (+1 template; base blob
   `66ec67ce7866`): `what_if_narrated_story` — name "What-if narrated
   story", lanes all three owner lanes, target `[60, 120]`, 5 beats
   summing to exactly 1.0 (`premise` 0.15 — the counterfactual question;
   `chapter_one` 0.25, `chapter_two` 0.25, `chapter_three` 0.20 —
   chaptered escalation; `cliffhanger` 0.15 — unresolved ending, the
   hook for the next episode). Hard rules: one counterfactual premise
   per episode, single narrator throughout, every factual claim needs a
   citable source, the cliffhanger stays unresolved in this episode
   (the next episode opens by resolving it), ORIGINAL characters only,
   no third-party footage outside the licence gate. `ig_sources` is
   OMITTED: no IG corpus source id exists for this format, and inventing
   one would be a false provenance claim. Name + source_strategy are
   clean against the compliance gate's excluded tokens. The file's own
   serialisation (compact separators, insertion order, raw UTF-8) was
   verified byte-identical on round-trip before the append, so the diff
   is the one template entry and nothing else.
2. `VyralX/app/services/what_if.py` (new, 8,912 bytes, mirrors
   `stick_figure.py`): `build_episode(premise, chapters, cliffhanger)`
   plans one episode against the template — the premise + three chapter
   texts + cliffhanger align with the template beats with contiguous
   timings; the cliffhanger is carried as `next_episode_hook` ("Episode
   N+1 opens by resolving: …"); the episode carries `episode_no` /
   `series_id` so a chain of episodes is a series. The acceptance guards
   are enforced, not assumed: a list of premises (second premise), a
   list of narrators (second voice), an empty premise, a missing/empty
   cliffhanger, more than three chapters, a non-positive episode number,
   or a lane the template does not serve are all refused with
   `ValueError`. Fewer than three chapters are recorded in
   `missing_chapters` and never padded (the stick-figure missing-caption
   pattern). `enqueue_episode_plan` appends to the VYR-004 review queue
   (lazy `remix_flow` import, same as the stick-figure module). The
   plan is `pending_review`, `publish` False, privacy unlisted.
   FastAPI router (`GET /what-if/beats`, `POST /what-if/episodes`,
   `ValueError` → 422) mounted in `app/main.py` — the AUDIT-2
   production-caller standard. Pure stdlib + FastAPI router; no network.
3. `VyralX/tests/test_vyr069_what_if_story.py` (new, 11 tests, mirrors
   `test_ig3_vyr02_stick_figure.py` + `test_vyr062_stick_figure_series.py`):
   registry validation of the new template (shape, shares, lanes,
   target range, hard rules naming premise / narrator / cliffhanger /
   ORIGINAL); registry set now 8; malformed-template rejection
   (shares not summing to 1.0; gate-excluded token in the name);
   episode planning happy path (contiguous timings across premise →
   chapters → cliffhanger, series fields, pending_review, no publish);
   missing chapters recorded, never padded; all six refusal guards;
   enqueue writes one review record; series automation accepts the
   template id and plans briefs against it (format plan at the
   `[60, 120]` midpoint = 90.0 s, outline follows the template beats,
   `format_name` defaults to the template name); lane-mismatch
   rejection; router answers + `app.main` mounts it.
4. `VyralX/tests/test_ig_vyr09_format_tooling.py` (+1 line, base blob
   `b55df7903e79`): `EXPECTED_TEMPLATES` extended with
   `what_if_narrated_story` — the registry's exact-set pin, the same
   change IG3-VYR-02 made for the stick-figure template.
5. `.github/workflows/owner-workflows.yml` (+2 lines, base blob
   `dcf9155908de`): `VyralX/tests/test_vyr069_what_if_story.py` and
   `VyralX/tests/test_ig_vyr09_format_tooling.py` added to the VyralX
   pytest list in the contracts job (same step as `test_vyr062` /
   `test_vyr081`). This is the FUT-030 fix: without these lines the new
   tests would never run in CI, and without the second line the guard
   would FAIL on the modified IG-VYR-09 file (it was previously
   uncollected). The IG-VYR-09 suite's 9 tests now run in CI for the
   first time — its `chat_mockup` leg needs Pillow (installed in the
   contracts job) and its `motion_graphics` leg is stdlib-only.
6. `VyralX/app/main.py` (+3 lines, base blob `94adcc390ec8`): mount the
   what-if router after the stick-figure mount (same pattern, same
   prefix `/api/v1`).

## Tests

- **Not run locally — by constraint, not by omission.** This run works
  the API-only route (no local clone, no local execution of repo code),
  so pytest was never run on this machine. Local validation performed:
  `py_compile` on all four `.py` files (syntax only, nothing imported
  or executed); the registry JSON loads and the new template passes the
  registry's own checks (shares sum 1.0, lanes valid, target range
  valid, gate tokens absent); the workflow YAML parses and carries the
  `pull_request` trigger with a paths filter covering `VyralX/app/**`,
  `VyralX/tests/**` and `.github/workflows/owner-workflows.yml`, so the
  `contracts` check runs on this PR; every shipped file diffed against
  its TRUE base blob from git objects (raw.githubusercontent is stale
  and untrusted for base state).
- **CI is the test run.** The `contracts` check runs
  `test_vyr069_what_if_story.py` (11 tests) and
  `test_ig_vyr09_format_tooling.py` (9 tests). Merge-readiness requires
  the contracts job log to show both files executed and passing — a
  green check alone is not evidence (FUT-030). The completion post on
  hub #1483 carries the job-log evidence.

## Live leg

NOT RUN — gated, not refused. The change is planning-library code (no
render, no publish, no server call); a live leg would be a VyralX-Server
probe of the episode planner against a real series, which is gated by
the owner stop order (still in force; no lift through the latest
coordinator watch). No live step taken. Verifier re-tests live when the
gate lifts.

## Board flips (in this PR)

- TASK-VYR-069 AVAILABLE → IN_REVIEW (owner muse_1, branch
  `muse1/task-vyr-069-what-if-story-template`, pr 1774).
- FUT-029 (MERGED, pr 1757) and FUT-030 (re-slotted to the pool head,
  not mine) untouched. FUT-031 (AVAILABLE) untouched — it is the next
  task, claimed after this one merges.

## Pushed file SHAs (read back from the branch, commit 7f74d51e)

- `VyralX/app/data/format_templates.json`: blob `65d462c7b723`
- `VyralX/app/services/what_if.py`: blob `aa338d216968`
- `VyralX/tests/test_vyr069_what_if_story.py`: blob `1d71474a2e58`
- `VyralX/tests/test_ig_vyr09_format_tooling.py`: blob `858b421892ac`
- `.github/workflows/owner-workflows.yml`: blob `1be591d3c10b`
- `VyralX/app/main.py`: blob `b89b6aac8ec9`
- This doc: blob recorded in the hub status post after push (a file
  cannot carry its own blob sha).

— Muse 1
