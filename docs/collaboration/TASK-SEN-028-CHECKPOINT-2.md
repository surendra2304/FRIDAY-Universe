# TASK-SEN-028 — Checkpoint 2: CLI walkthrough skeleton + status store + tests

**Filed:** 2026-11-26 ~05:2x IST, Muse 19 hourly self-check.
**Branch:** `muse19/task-sen-028` (checkpoint 1 grounding: commit `b1fbcc66`).
**Board (main `25cfe733`):** AVAILABLE / owner muse_19 / branch null / pr null.
Board flip AVAILABLE → CLAIMED rides in the single work PR (owner rule 4).
No PR with this checkpoint (owner rule 1).

## What was built (repo-side, no server move, no live run)

- `Sentinel/sentinel/apps/cli/footprint_cleanup.py` — the 7-step
  walkthrough: step registry (ids/titles/kinds in board order), JSON
  per-step status store (`pending | done | skipped | blocked |
  unavailable`, evidence + timestamp, owner-local
  `~/.sentinel/footprint-cleanup.json`, never in the repo), HIBP reuse
  seam, ExifTool helpers, and the `footprint` Typer sub-app
  (`status`, `step`, `mark`, `reset`, `hibp`).
- `Sentinel/sentinel/apps/cli/main.py` — 2-line wiring: import +
  `app.add_typer(footprint_app, name="footprint")`. Base blob
  `a76b2b96` verified identical on the branch and on current main, so
  the edit applies cleanly.
- `Sentinel/tests/test_sen028_footprint_cleanup.py` — 18 hermetic tests
  (no network, no server, no owner data).

## HIBP reuse — verified first-hand against the real module

Read `IntelX/intelx/osint/breach_check.py` (blob `08b5a63e`) this run:
`check_email_breaches(email, fetch=None, api_key=None)` is async and
returns `EmailBreachResult(status, checked, breaches, reason)`; without
a key it returns `unavailable` with the reason stated, never "no
breaches". `check_password_breach(password, fetch=None)` is the free
k-anonymity range check. The footprint module calls both through a
lazy import with an injectable test seam; when the module cannot be
imported from Sentinel the step reports `unavailable` with the reason.

## Verification (this run, first-hand)

- 18/18 tests pass (`pytest`, typer 0.29.2 / pytest 9.2.0 in a
  throwaway venv; the VM has no typer/pytest installed).
- `sentinel footprint status` and `sentinel footprint step hibp` run
  clean through a mounted root Typer app (same `add_typer` pattern as
  `main.py`); all 7 steps list with `pending` status.
- New files + edited `main.py` all `py_compile` clean; no line over
  100 chars (repo ruff limit).

## What is left

- Live walkthrough with the owner (all 7 steps, owner-initiated, in
  the owner's own sessions) — waits on clearance under the owner stop
  order; nothing attempted.
- Password-breach step wiring into the CLI (helper exists and is
  tested; no password is ever taken on the command line without an
  explicit owner decision).
- API route / dashboard page for the walkthrough — later, after the
  CLI leg is proven.
- Single work PR at completion: grounding + this checkpoint + live
  walkthrough evidence + board flip. DB-009's backup write stays
  frozen; REL-094 stays parked.

— Muse 19
