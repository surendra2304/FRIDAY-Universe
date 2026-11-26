# TASK-DB-011 — scoping checkpoint (Muse TP10, 2026-11-26)

Claimed 2026-11-26 ~13:25 IST (hub #1483 claim post, same run) as queue head
after coordinator WATCH147 (hub 7185752260) re-slotted TASK-FRD-046 to the
pool. Branch `musetp10/task-db-011` cut from main `8ee4a98d`. Queue:
DB-011 (now) → INF-043 → VOI-045. Five states all NO: implemented NO /
tested NO / merged NO / deployed NO / production-verified NO. Scoping only;
no code changed, no server touched.

## Acceptance (board, main 8ee4a98d, board blob df05f01b)

"Back up the Forge workspaces on Oracle Server 1 (server 1): Forge/workspaces/
(27M). Prove with a dated backup + a read-back check. (Coordinator may close
as not-needed if workspaces are regenerable output; the audit flags the gap,
this task settles it.)"

Board record verified first-hand this run: DB-011 AVAILABLE / muse_tp10 / P2 /
blockers [] / branch null / pr null (CLAIMED flip rides the work PR). Filed by
Muse 13 in TASK-DB-003; assigned to muse_tp10 by coordinator watch113.

## Verified first-hand this run (repo-side only)

- Source audit `docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md`
  (blob `333b75ee`, 20,343 bytes, at main `8ee4a98d`): single dated sweep
  2026-11-25 05:43–06:06 IST via the bridge, read-only. Forge row (line 42):
  S1, `Forge.service` active, `/opt/friday_universe/Forge/` with
  `workspaces/` 27M and `app/` 7.2M; ADB FORGE schema (7 tables, 4,506 rows
  @ 2026-11-22) covered by the 2026-11-22 fleet backup; workspaces **NO FILE
  BACKUP** → follow-up DB-011 (line 93). All sizes are audit-sourced
  (2026-11-25 sweep), not re-measured live this run.
- No DB-011 branch, PR, or competing claim existed before this claim
  (matching-refs scan: only orphaned musetp10 branches; open-PR scan: 42
  open, 0 musetp10 heads; hub tail read through WATCH147 + corrections).
- FRD-046 predecessor state accepted: branch `musetp10/task-frd-046` @
  `c60d09f0` (checkpoint only, 10:27 IST), 1 ahead / 86 behind main
  `8ee4a98d`, no work PR. Orphaned branch left in place, untouched.

## Open question this task must settle first

Regenerability: are the contents of `/opt/friday_universe/Forge/workspaces/`
regenerable build output (→ coordinator may close DB-011 as not-needed) or
irreplaceable working state (→ dated backup + read-back check owed)?

- Repo-side step (unblocked): read the Forge sources/docs for how workspaces
  are created, consumed, and whether they can be rebuilt from git + ADB.
- Live step (S1 listing/sizes, then any backup): **GATED** — owner stop order
  on live legs (WATCH141) stands; bridge server-touching ops are serialized
  through Muse and coordinated on #1483 first. No Server 1 touch without
  coordinator clearance; exact read-only commands will be proposed on the hub
  before any live step, per precedent.

## Plan

1. Repo-side: settle the regenerability question from Forge sources; design
   the dated-backup + read-back procedure with exact commands.
2. Live leg only on coordinator clearance: dated backup of
   `/opt/friday_universe/Forge/workspaces/` + read-back check, evidence filed.
   If the coordinator rules the workspaces regenerable, file that ruling as
   the settlement instead — no backup theatre.
3. One work PR (board flip rides it); rebase onto current main at PR step.
   Never claim production-verified without live evidence.

— Muse TP10
