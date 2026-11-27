# TASK-SEN-028 — Checkpoint 1: scoping + adoption (Muse 20)

**Filed:** 2026-11-27 ~20:10 IST, Muse 20 work-request run (claim).
**Task:** Sentinel: 7-step digital-footprint cleanup as an owner checklist tool.
**Board (live main `8e5238a1`, WORK_BOARD.yaml read first-hand this run):**
AVAILABLE / owner null / branch `musetp11/task-sen-028-seven-step-cleanup`
(stale pointer) / pr null / P2. Next action: claim via hub + branch push.
**Assignment:** Burn Enforcer CORRECTION 2 §D (hub #2045 comment 7220831110):
M20 → TASK-SEN-028; claim + first checkpoint in the next post.
**Branch:** `muse20/task-sen-028` @ `8e5238a1` (claim base). This commit is the
first work commit on the branch.

## Acceptance (board, verbatim)

- Sentinel can walk the owner through the 7 steps with per-step status:
  HIBP check (reuses TASK-IG2-INT-06), JustDeleteMe, email aliases,
  Google My Activity cleanup, YourDigitalRights.org, ExifTool metadata
  stripping, EFF Cover Your Tracks.

## Adoption — M19 checkpoint 2 + TP11 checkpoint 1 (verified first-hand)

M19 built the CLI and then released the task; TP11 scoped the adoption and
then missed the checkpoint-2 deadline. The work is adopted, not rebuilt:

- M19 branch `muse19/task-sen-028` @ `6687c056` (head: "TASK-SEN-028
  checkpoint 2: CLI walkthrough skeleton + status store + tests (18/18 pass;
  HIBP reuse verified)", 2026-11-26T00:01:58Z). Compare vs live main
  `8e5238a1`: ahead 5 — exactly these files:
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
- TP11 branch `musetp11/task-sen-028-seven-step-cleanup` @ `77b2e0f1`:
  checkpoint-1 doc only (ahead 1). Checkpoint 2 missed the ~17:00 IST hard
  deadline → re-slotted to pool per WATCH218; TP11 takes TASK-SEN-035.
  TP11's checkpoint-1 scoping is adopted here; this filing supersedes it
  as the checkpoint of record for the M20 claim.
- Muse 2's SEN-028 pull self-corrected (branch deleted, re-GET 404) — no
  collision; SEN-028 is M20's per BE CORRECTION 2 §D.

## Base checks re-verified on main `8e5238a1` this run (first-hand, API)

- `IntelX/intelx/osint/breach_check.py` — 200, blob `08b5a63e` (matches
  M19's citation exactly). HIBP reuse target present.
- `Sentinel/sentinel/apps/cli/main.py` — 200, blob `a76b2b96` (matches
  M19's citation exactly). The 2-line wiring applies cleanly.
- `Sentinel/sentinel/apps/cli/footprint_cleanup.py` — 404 on main.
  Adoption owed (checkpoint 2).
- `Sentinel/tests/test_sen028_footprint_cleanup.py` — 404 on main.
- `docs/collaboration/TASK-SEN-028-CHECKPOINT-1.md` /
  `TASK-SEN-028-CHECKPOINT-2.md` / `TASK-SEN-028-GROUNDING.md` — all 404
  on main (live only on the prior workers' branches).

## Scope of checkpoint 2 (next)

Bring M19's 5 files onto current main on this branch, re-run the 18 tests
first-hand, re-verify `sentinel footprint status` lists all 7 steps pending.
Then the single work PR with the tool, tests, and board flip at completion
(owner rule: no PR with this checkpoint; board flip rides in the work PR).

## Out of scope / held (nothing attempted)

- Live walkthrough with the owner (all 7 steps, owner-initiated, in the
  owner's own sessions) — waits on clearance under the owner stop order;
  live legs HELD per WATCH176 grant dispute (repo-only first).
- No password is ever taken on the command line without an explicit owner
  decision. No server move, no restart, no owner data touched, no
  credentials stored.

— Muse 20
