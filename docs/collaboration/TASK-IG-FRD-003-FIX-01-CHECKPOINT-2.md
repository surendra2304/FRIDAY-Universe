# TASK-IG-FRD-003-FIX-01 — CHECKPOINT 2: Greenhouse API path implemented + tested

- **Task:** TASK-IG-FRD-003-FIX-01 — fix job-hunt extractor for current Greenhouse markup (IG-FRD-003 follow-up).
- **Branch:** `musetp7/task-ig-frd-003-fix-01-greenhouse-extractor` @ remote `ae8cab1c` (checkpoint 1; base main `02ed2f98`).
- **Board:** CLAIMED/muse_tp7 on live main `55a11a60` (verified first-hand this run; blob `46dd5277`, 12,468 lines).
- **Status:** fix implemented, suite green. Work PR opened (see §4).

## 1. What changed

`FRIDAY/src/friday/workflows/job_hunt.py` (+68/-5) — the checkpoint-1 design, as filed:

- `run_scan` detects Greenhouse job URLs (`job-boards.greenhouse.io/{board}/jobs/{id}`
  and the `boards.greenhouse.io` variant) and fetches the official public Job Board API
  single-job endpoint (`boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}`, no auth
  for reads) through the existing fetcher instead of the HTML page. No new transport.
- New `extract_listings_from_greenhouse_json` maps the API job object onto the existing
  listing schema: `title`, `company` ← `company_name`, `url` ← `absolute_url`,
  `location` ← `location.name`, `description` ← `content` double-unescaped then
  tag-stripped, `posted_days_ago` ← `first_published`. Stable id `gh-{job id}`.
  A payload with no usable job object returns an honest `[]`.
- Honesty preserved: a Greenhouse URL whose API call returns non-JSON is recorded
  `fetch_failed` with the error; a valid API error payload is `no_postings_found`.
  The LD-JSON path is byte-untouched for all other hosts. No send/apply path added —
  the module's no-send structural test still passes.

`FRIDAY/tests/test_ig_frd_003_job_hunt.py` (+115) — 6 new hermetic tests (fake
fetcher), fixture shaped on the real live GitLab API response from checkpoint 1:

- API URL construction; JSON → listing field mapping (incl. `posted_days_ago == 9`
  on a pinned clock); double-encoded content decodes to plain text
  (`"Hello & goodbye"`, no tags); non-job payloads are honest empty; `run_scan`
  fetches the API endpoint (never the HTML page) and shortlists the GitLab posting;
  API non-JSON → `fetch_failed`.
- Stale-fixture fix: `test_extract_listings_from_json_ld` now pins `now_epoch` to
  the fixture `datePosted` + 1 day and asserts `posted_days_ago == 1` — the recency
  assertion tests the formula, not the calendar, so it cannot rot again in 10 days.

## 2. Test run (this sandbox, this run)

- `FRIDAY/tests/test_ig_frd_003_job_hunt.py`: **17 collected, 17 PASS** (was 11
  collected / 10 PASS / 1 FAIL on the stale-date fixture at checkpoint 1).
- Run: `PYTHONPATH=/home/hatch/.local/lib/python3.12/site-packages:src python3 -m
  pytest tests/test_ig_frd_003_job_hunt.py -v` (pytest 9.2.0, installed to
  `~/.local` at checkpoint 1; the plain `python3 -m pytest` path has no pytest and
  the `~/.local/bin/pytest` shim misses its user site-packages — use the
  PYTHONPATH form above).
- Sandbox note (unchanged): `friday.tools` live import still trips the fail-closed
  Oracle `DATABASE_URL` gate — environment, not code (same as FRD-059 / checkpoint 1).

## 3. Base / rebase note

- A rebase of checkpoint 1 onto live main `55a11a60` was attempted this run
  (local `5e4be99a`, clean) but the git-data push helper refuses non-fast-forward
  ref updates (422) and the branch ref stays at `ae8cab1c` — correctly, no force
  used. The branch was reset to the remote head (tree verified identical to the
  pre-rebase checkpoint-1 tree) and checkpoint 2 was built on top of it.
- No rebase is needed for a clean merge: `git log 02ed2f98..origin/main` shows
  **zero** main changes to either touched file since the branch base, so the work
  PR diff is exactly these two files. Mergeability is verified on the PR (§4).
- Orphaned remote commit `ce87360e` (created by the refused rebase push attempt,
  same tree/message as checkpoint 1, parent `55a11a60`) is unreferenced and
  harmless; no ref points at it.

## 4. Work PR

- PR opened this run (number + head recorded in the run log; see hub-status
  2026-11-28-0701). Files: this checkpoint doc, `job_hunt.py`, the test file.
  No board hunk. CI finding carried (not fixed here):
  `test_ig_frd_003_job_hunt.py` is uncollected by any PR-triggered workflow —
  same class as FRD-049 REL-068 / FRG-026 / FRD-059; ruling ask carried per
  WATCH226 §D6 (coordinator takes the owner-workflows edit).

## 5. Next

- Paired-verifier verdict on the work PR, then merge. Live leg HELD per owner stop
  order — no live FRIDAY-Server move this run; the live re-probe against the
  FRD-051 GitLab/Canonical postings rides the work PR after merge + deploy ruling.
