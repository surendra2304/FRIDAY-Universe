# TASK-VYR-062 — Stick-figure template usable by the faceless-series automation

Worker: Muse 5. Claim: hub #1483 comment 7147880361, 2026-11-25 ~05:20 IST.
Branch: `muse5/task-vyr-062-stick-figure-template`, from main `07c526bf`,
rebased onto main `8415199b` then `6fbc9b3b` before the work PR opened (branch
had 0 commits on top of old main at the first rebase — ref fast-forward;
the second rebase replayed the 3 pushed commits onto `6fbc9b3b` via the
git-data API, same blobs and messages, after #1751 and #1752 merged).
Base for all verification below: main `6fbc9b3b` unless stated. The three
code files verified are byte-identical on `f6d1e665`, `8415199b` and
`6fbc9b3b` (`series_automation.py` blob `7545597d` on all three).

## Acceptance

> Stick-figure style is a validated registry template usable by the
> faceless-series automation (TASK-IG-VYR-04).

## What was already on main (verified first-hand, not assumed)

- The registry leg was DONE by TASK-IG3-VYR-02 (merged before this task):
  `VyralX/app/data/format_templates.json` carries `stick_figure_explainer`
  (7 templates total), and `VyralX/app/services/stick_figure.py` renders it.
  Re-verified this run against main `6fbc9b3b`: `get_template(...)` returns it,
  `validate_template(...) == []`, lanes are all three owner lanes
  (`tech_ai`, `history`, `space_science`), structure shares sum to 1.0
  (0.12 + 0.23 + 0.4 + 0.15 + 0.1), target `[30, 60]`, beats
  `hook_pose, setup, build_up, aha_pose, recap_line`, IG source `DemH26soPPx`.
  The IG-VYR-09 suite (9 tests) already pins this template in the registry's
  expected set.
- The gap was the second half of the acceptance: `VyralX/app/services/
  series_automation.py` (TASK-IG-VYR-04, MERGED) had NO reference to any
  template — `grep template|format_templates|stick` over the file returned
  nothing. A series could not name a style, and no brief was ever planned
  against a registered format. That is what this task implements.

## What changed (3 files + this doc + board flip)

1. `VyralX/app/services/series_automation.py` (+61/-14, `SERIES_VERSION`
   `ig-vyr04-1` → `ig-vyr04-2`, stdlib-only preserved — `format_templates`
   imports only json/pathlib plus the compliance gate):
   - `validate_series` accepts an optional `template_id`: it must resolve
     via `format_templates.get_template` (unknown id → problem
     `unknown format template: ...`) and the template must serve the series
     lane (else problem `template ... does not serve lane ...`). The resolved
     template is returned as `template` in the result (None when absent or
     invalid). All prior validation is unchanged.
   - `plan_episodes` with a valid `template_id` plans each brief against the
     template: the outline follows the template beats (`beat: note`), the
     brief carries `template_id` + the instantiated `format_plan`
     (`format_templates.instantiate` at the template range midpoint — 45.0 s
     for `[30, 60]` — contiguous beats, `within_template_range` true,
     `status` pending_review, hard rules included), and `format_name`
     defaults to the template name when the spec names none (an explicit
     `format_name` still wins). Without `template_id` the brief shape is
     byte-identical to before (regression-guarded by test).
   - `daily_queue` / `enqueue_briefs` untouched; templated briefs flow
     through them unchanged. Nothing renders, uploads, or publishes.
2. `VyralX/tests/test_vyr062_stick_figure_series.py` (new, 8 tests).
3. `.github/workflows/owner-workflows.yml`: the new test file added to the
   VyralX pytest list in the contracts job (REL-068 collection guard — a PR
   test file must run in PR CI; the IG-VYR-04/09/IG3-VYR-02 suites are not
   collected by any workflow and run locally only, as before).

## Tests (pytest, local run, no server execution)

- New suite `test_vyr062_stick_figure_series.py`: **8/8 pass**.
- Neighbours re-run in the same process: `test_ig_vyr04_series_automation.py`
  8/8, `test_ig3_vyr02_stick_figure.py` 7/7 — **23/23 pass total**.
- Clean-main check: the new suite against unmodified `series_automation.py`
  gives 6 failed / 2 passed — the 2 passing are the registry-leg test and
  the no-template regression guard, which pin what already exists by design.
- Lint: `ruff check --select F821` (the rule CI enforces for VyralX) clean
  on both touched files. (Default-rules UP035/RUF007 nits match pre-existing
  style — `typing.Iterable` import and `zip(beats, beats[1:])` — already
  present in the module and in the IG-VYR-09/IG3-VYR-02 suites; not changed.)

## Live leg

NOT RUN — gated, not refused. The change is planning-library code (no render,
no publish, no server call); a live leg would be a VyralX-Server probe of the
series automation against a real series, which is gated by the owner stop
order (~16:42 IST 2026-11-24, still in force; no lift through the latest
coordinator watch 7148827655). No live step taken, no run_shell grant for
VYR-062. Verifier re-tests live when the gate lifts.

## Board flips (in this PR)

- TASK-VYR-071 IN_REVIEW → MERGED (work PR #1738 merged 05:01 IST, merge
  `07c526bf`; M9 verifier PASS 7147333628 + coordinator full-diff review
  watch 7147595568). Carried here per the claim post (rule 4).
- TASK-VYR-062 AVAILABLE → IN_REVIEW (owner muse_5, branch
  `muse5/task-vyr-062-stick-figure-template`, pr 1756).

## Pushed file SHAs (read back from the branch)

- `VyralX/app/services/series_automation.py`: blob `ba7928ef`
  (commit `a90c8fea` after the rebase onto main `6fbc9b3b`)
- `VyralX/tests/test_vyr062_stick_figure_series.py`: blob `26a986ce`
  (commit `6cc8bc1b`)
- `.github/workflows/owner-workflows.yml`: blob `2ac29a3f`
  (commit `519d6903`)
- This doc: blob recorded in the hub status post after push (a file cannot
  carry its own blob sha).

— Muse 5
