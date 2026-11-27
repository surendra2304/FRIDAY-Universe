# TASK-SEN-028 — Checkpoint 2: M19 CLI adopted + re-verified 18/18 (Muse 20)

**Filed:** 2026-11-27 ~22:38 IST, Muse 20 hourly self-check (stall repair —
checkpoint 2 was ~25 min past the ~22:10 IST 2h bar when this run started).
**Branch:** `muse20/task-sen-028` (claim base `8e5238a1` + checkpoint 1
`7398a99d`). No PR with this checkpoint (owner rule 1).
**Task:** Sentinel: 7-step digital-footprint cleanup as an owner checklist
tool.

## Adoption — M19's work, brought onto this branch verbatim

From `muse19/task-sen-028` @ `6687c056` (head: "TASK-SEN-028 checkpoint 2:
CLI walkthrough skeleton + status store + tests (18/18 pass; HIBP reuse
verified)", 2026-11-26T00:01:58Z):

- `Sentinel/sentinel/apps/cli/footprint_cleanup.py` (+315, blob
  `c759f9b7`) — 7-step walkthrough, step registry in board order, JSON
  per-step status store (`pending | done | skipped | blocked |
  unavailable`, evidence + timestamp, owner-local
  `~/.sentinel/footprint-cleanup.json`, never in the repo), HIBP reuse
  seam, ExifTool helpers, `footprint` Typer sub-app (`status`, `step`,
  `mark`, `reset`, `hibp`).
- `Sentinel/sentinel/apps/cli/main.py` (+2) — import + `app.add_typer(
  footprint_app, name="footprint")` onto base blob `a76b2b96`.
- `Sentinel/tests/test_sen028_footprint_cleanup.py` (+191, blob
  `b460ef34`) — 18 hermetic tests (no network, no server, no owner data).
- `docs/collaboration/TASK-SEN-028-GROUNDING.md` (+83, blob `73feeec3`).
- M19's checkpoint-2 doc (blob `7141e01e`, +60) is the adopted evidence
  base: cited here, lives on `muse19/task-sen-028`. **This doc
  supersedes it as the checkpoint of record for the M20 claim** (same
  precedent as checkpoint 1 vs TP11's scoping).

## Re-verification — first-hand this run

- **18/18 tests pass** (`pytest`, typer 0.29.2 / pytest 9.2.0 in a
  throwaway venv; the VM has no typer/pytest installed). Same versions
  M19 used; run in scratch from the adopted files, no repo state touched.
- **`sentinel footprint status` lists all 7 steps `pending`** (mounted
  root Typer app, same `add_typer` pattern as `main.py`; HOME pointed at
  an empty scratch dir; exit 0). `sentinel footprint step hibp` runs
  clean (exit 0, no key pasted, step reports unavailable without one,
  never clean).
- **Base checks on current main `330de772`:** `main.py` still blob
  `a76b2b96` — zero drift since M19's citation, the +2 applies cleanly
  (diff verified: exactly 2 added lines). All 4 adopted files 404 on
  main (recursive tree, 9,142 paths: zero `footprint` / `SEN-028` hits).
- **Board on main `330de772`** (blob `f51d3528`, 1.5 MB): SEN-028 still
  **AVAILABLE / owner null / branch null / pr null / P2**. The CLAIMED
  flip is **not** in this commit and **not** in the work PR — board flips
  are coordinator-only (ruling 7200564540 §3; STR-065 board-strip
  precedent). Flip owed via coordinator board PR.
- `py_compile` clean on all 3 py files. No new line over 100 chars: the
  2 added `main.py` lines are short; `main.py`'s 54 pre-existing long
  lines are untouched (base and adopted counts identical).
- HIBP reuse: **not** re-run live (no key; live legs HELD per WATCH176
  grant dispute). The injectable checker seam + no-key / no-import
  `unavailable` paths are covered by the 18 tests; M19's first-hand
  read of `breach_check.py` (blob `08b5a63e`) is adopted, not re-claimed.

## Five states

implemented NO (repo-side tool only, no live walkthrough) / tested YES
(18/18 first-hand, repo-side) / merged NO / deployed NO /
production-verified NO (live legs HELD per WATCH176).

## What is left

- Single work PR at completion: tool + tests + grounding + this
  checkpoint. No board hunk in it (see above).
- Live walkthrough with the owner (all 7 steps, owner-initiated, in the
  owner's own sessions) — waits on clearance under the owner stop order;
  nothing attempted.
- Password-breach step wiring into the CLI (helper exists and is tested;
  no password is ever taken on the command line without an explicit
  owner decision).
- API route / dashboard page for the walkthrough — later, after the CLI
  leg is proven.

— Muse 20
