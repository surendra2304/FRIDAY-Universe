# TASK-SEN-028 — Checkpoint 1: scoping + adoption of M19 checkpoint 2

**Filed:** 2026-11-27 ~13:20 IST, Muse TP11 hourly self-check (stall repair).
**Task:** Sentinel: 7-step digital-footprint cleanup as an owner checklist tool.
**Board (live main `25ce04a3`, WORK_BOARD.yaml blob `67e6c9e8`, verified first-hand
this run):** CLAIMED / muse_tp11 / branch
`musetp11/task-sen-028-seven-step-cleanup` / pr null / P2.
**Branch:** cut from main `8477b554` (claim base, 2026-11-27 ~10:08 IST, hub
#2045 comment 7209970585). This commit is the first work commit on the branch.
**Why now:** WATCH210 §3 ruling (hub #2045 comment 7212533780, stands per
WATCH210-CORR): checkpoint 1 due 13:30 IST; the re-slot rides the next board
PR unless checkpoint 1 lands first. This filing meets that condition.

## Acceptance (board, verbatim)

- Sentinel can walk the owner through the 7 steps with per-step status:
  HIBP check (reuses TASK-IG2-INT-06), JustDeleteMe, email aliases,
  Google My Activity cleanup, YourDigitalRights.org, ExifTool metadata
  stripping, EFF Cover Your Tracks.

## Adoption — M19 checkpoint 2 (verified first-hand this run)

M19 built the CLI and then released the task (hub: M19 released SEN-028,
claimed SEN-039). The work is adopted, not rebuilt:

- M19 branch `muse19/task-sen-028` @ `6687c056` (head commit: "TASK-SEN-028
  checkpoint 2: CLI walkthrough skeleton + status store + tests (18/18 pass;
  HIBP reuse verified)", 2026-11-26T00:01:58Z). Compare vs live main
  `25ce04a3`: ahead 5, behind 581 — the diff is exactly these 5 files:
  - `Sentinel/sentinel/apps/cli/footprint_cleanup.py` (+315) — 7-step
    walkthrough, step registry in board order, JSON per-step status store
    (`pending | done | skipped | blocked | unavailable`, evidence +
    timestamp, owner-local `~/.sentinel/footprint-cleanup.json`, never in
    the repo), HIBP reuse seam, ExifTool helpers, `footprint` Typer
    sub-app (`status`, `step`, `mark`, `reset`, `hibp`).
  - `Sentinel/sentinel/apps/cli/main.py` (+2) — import + `add_typer`.
  - `Sentinel/tests/test_sen028_footprint_cleanup.py` (+191) — 18 hermetic
    tests (no network, no server, no owner data).
  - `docs/collaboration/TASK-SEN-028-CHECKPOINT-2.md` (+60).
  - `docs/collaboration/TASK-SEN-028-GROUNDING.md` (+83).
- M19's filed claims (cited, not re-claimed here): 18/18 tests pass;
  `sentinel footprint status` lists all 7 steps `pending`; HIBP reuse
  verified against the real `breach_check.py`. Re-verification on this
  branch is checkpoint 2's job.
- Grounding adopted: greenfield absence proof (no footprint tool on main);
  HIBP reuse target real and free-only; CLI-first host recommendation
  (owner-operated, no deploy, fits the stop order); API route / dashboard
  page later, after the CLI leg is proven.

## Base checks re-verified on THIS branch this run (first-hand, API)

- `IntelX/intelx/osint/breach_check.py` — 200, blob `08b5a63e` (matches
  M19's citation exactly). HIBP reuse target present.
- `Sentinel/sentinel/apps/cli/main.py` — 200, blob `a76b2b96` (matches
  M19's citation exactly). The 2-line wiring applies cleanly.
- `Sentinel/sentinel/apps/cli/footprint_cleanup.py` — 404 on this branch.
  Adoption owed (checkpoint 2).
- `docs/collaboration/TASK-SEN-028-CHECKPOINT-1.md` — 404 on this branch
  before this filing. Filed by this commit.

## Scope of checkpoint 2 (next)

Bring M19's 5 files onto this branch (onto current main), re-run the 18
tests first-hand, re-verify `sentinel footprint status` lists all 7 steps
pending. Then the single work PR with the tool, tests, and board flip at
completion (owner rule 1: no PR with this checkpoint; owner rule 4: board
flip rides in the work PR).

## Out of scope / blocked (nothing attempted)

- Live walkthrough with the owner (all 7 steps, owner-initiated, in the
  owner's own sessions) — waits on clearance under the owner stop order.
- Password-breach step wiring into the CLI — helper exists in M19's module
  and is tested; no password is ever taken on the command line without an
  explicit owner decision.
- No server move, no restart, no owner data touched, no credentials stored.

— Muse TP11
