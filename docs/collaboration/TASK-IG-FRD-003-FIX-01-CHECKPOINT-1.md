# TASK-IG-FRD-003-FIX-01 — CHECKPOINT 1: Greenhouse probe + fix design

- **Task:** TASK-IG-FRD-003-FIX-01 — fix job-hunt extractor for current Greenhouse markup (IG-FRD-003 follow-up).
- **Branch:** `musetp7/task-ig-frd-003-fix-01-greenhouse-extractor` @ main `02ed2f98` (checked out this run, clean).
- **Board:** CLAIMED/muse_tp7 on live main `fac8c0eb` (verified first-hand this run; flip landed via board PR #2230, WATCH247).
- **Status:** research / evidence complete. No code changed in this checkpoint.

## 1. The defect (re-confirmed from the record)

- `FRIDAY/src/friday/workflows/job_hunt.py::extract_listings` parses ONLY
  `application/ld+json` `JobPosting` blocks. A page with none yields an honest `[]`.
- FRD-051 live probe (record `docs/collaboration/TASK-FRD-051-PRODUCTION-VERIFY.md`,
  M17, PR #2044): probe profile with 2 live Greenhouse postings
  (GitLab job `8623389002`, Canonical job `2413329`) + 1 dead URL → scan `0/0`,
  dead URL honestly `fetch_failed` 404. The live GitLab posting page (116,902 B,
  real SRE posting) carries **0 LD-JSON blocks**; board indexes carry 0 too.
- Acceptance: the extractor finds real postings on live Greenhouse pages
  (JS-rendered shell, no `application/ld+json` JobPosting) or honestly reports
  the host as unsupported. Live-proof route: live FRIDAY on FRIDAY-Server;
  file the scan evidence on the GitLab/Canonical postings from the FRD-051 probe.

## 2. Live probe this run (2026-11-28 ~06:30 IST, read-only)

Both FRD-051 postings are still live:

- GitLab — `https://job-boards.greenhouse.io/gitlab/jobs/8623389002`
  "Site Reliability Engineer, Infrastructure Platforms — AMER (Intermediate to
  Senior Staff)". Page crawled <1 min before the read; full job description is
  present in the served HTML (server-rendered content, not JS-only). No LD-JSON
  JobPosting on the page — the FRD-051 finding stands.
- Canonical — job `2413329`, "Software Engineer (Python/Linux/Packaging)",
  still live on the Canonical board.

Greenhouse publishes an official public Job Board API (docs:
`https://docs.greenhouse.io/job-board` — no auth for reads; key only to
submit an application, which this workflow never does):

- `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}`

Verified live first-hand for BOTH probe jobs (crawled 2026-11-28 00:36 UTC):

- GitLab `8623389002` → `title` "Site Reliability Engineer, Infrastructure
  Platforms — AMER (Intermediate to Senior Staff)", `company_name` "GitLab",
  `location.name` "Remote, Canada; Remote, US",
  `absolute_url` "https://job-boards.greenhouse.io/gitlab/jobs/8623389002",
  `first_published` "2026-07-10T22:45:49-04:00",
  `updated_at` "2026-11-06T15:25:07-05:00", `id` 8623389002.
- Canonical `2413329` → `title` "Software Engineer (Python/Linux/Packaging)",
  `company_name` "Canonical", `location.name` "Home Based - Americas",
  `first_published` "2020-11-16T12:44:29-05:00",
  `updated_at` "2026-08-05T18:23:33-04:00", plus `departments` / `offices`.
- Both return `content`: the full job description as **double-entity-encoded
  HTML** (the documented quirk — `&lt;` encoded as `&amp;lt;`, etc.), so the
  fix must unescape twice, then strip tags, before scoring.
- Single-job retrieve returns `content` by default; the list endpoint
  (`.../boards/{token}/jobs`) needs `?content=true` for descriptions.

## 3. Fix design (for checkpoint 2 / work PR)

- In `run_scan`, detect Greenhouse job URLs
  (`job-boards.greenhouse.io/{board}/jobs/{id}` and `boards.greenhouse.io`
  variant): fetch the Job Board API single-job endpoint instead of the HTML
  page, using the existing fetcher (it takes a URL, returns text — the API
  returns JSON text, no new transport needed).
- New `extract_listings` path: parse the Greenhouse job JSON and map it onto
  the existing listing schema — `title`, `company` ← `company_name`,
  `url` ← `absolute_url`, `location` ← `location.name`,
  `description` ← double-unescaped, tag-stripped `content`,
  `posted_days_ago` ← `first_published`. Keep the LD-JSON path untouched for
  all other hosts.
- Honesty: a Greenhouse URL whose API call fails is recorded `fetch_failed`
  with the error (same as today); a non-Greenhouse page with no LD-JSON stays
  `no_postings_found`. No invented listings, ever. No send/apply path added —
  the module's no-send structural test must keep passing.
- Tests (hermetic, fake fetcher, in `FRIDAY/tests/test_ig_frd_003_job_hunt.py`):
  Greenhouse JSON fixture → 1 listing with the mapped fields; double-encoded
  content decodes to plain text; LD-JSON path unchanged; API failure →
  `fetch_failed`. Also refresh the stale `datePosted` fixture (see §4).

## 4. Baseline test run (this sandbox, this run)

- `FRIDAY/tests/test_ig_frd_003_job_hunt.py`: **11 collected, 10 PASS, 1 FAIL**.
- The failure is the known stale-date fixture, not the implementation:
  `test_extract_listings_from_json_ld` asserts `posted_days_ago <= 10` for
  fixture `datePosted` 2026-11-10; today 2026-11-28 gives 18. Same failure
  seen on the FRD-059 run (then 17 days). Implementation correct.
- Sandbox note: pytest + the FRIDAY dep subset (pydantic, sqlalchemy,
  oracledb, etc.) were installed to `~/.local` this run to make the suite
  runnable here; `friday.tools` live import still trips the fail-closed
  Oracle `DATABASE_URL` gate — environment, not code (same as FRD-059).
- CI finding carried (not fixed here): `test_ig_frd_003_job_hunt.py` is
  uncollected by any PR-triggered workflow — same class as FRD-049 REL-068 /
  FRG-026 / FRD-059. Ruling ask carried per WATCH226 §D6 (coordinator takes
  the owner-workflows edit).

## 5. Next

- Checkpoint 2: implement the Greenhouse path + tests, run the suite, file the
  work PR. Live leg HELD per owner stop order — no live FRIDAY-Server move
  this run; the live re-probe against the FRD-051 postings rides the work PR
  after merge + deploy ruling.
