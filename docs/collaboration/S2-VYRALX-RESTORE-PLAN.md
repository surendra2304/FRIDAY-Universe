# S2 VyralX restore plan — DRAFT (decision owed)

- Status: **DRAFT for coordinator/owner decision. No server action taken.**
- Filed by: Muse 5, 2026-11-25 ~12:30 IST, in the TASK-VYR-077 work branch
  (`muse5/task-vyr-077-repo-implement-wave1`), per coordinator watch082
  FLEET ALERT and watch083 ("restore-plan task draft + restore decision
  carried to next run").
- Owner stop order (2026-11-24 ~16:42 IST) freezes server moves. A restore
  IS a server move: **nothing below executes without explicit owner
  clearance via Muse.** This doc is the plan, not the execution.

## What happened — first-hand facts

- Found 2026-11-25 ~11:25 IST (Muse 5, read-only S2 `run_shell` probes
  during the TASK-VYR-051 discovery pass; evidence
  `docs/collaboration/TASK-VYR-051-CANDIDATE-POOL.md`):
  - `/opt/friday_universe` @ `09603dff` (merge #1651), detached HEAD.
  - Working tree **1,801 files deleted** (unstaged `D`), including the
    entire `VyralX/` (418 files in the index) and `Cortex/` trees.
    16 untracked files present.
  - `VyralX.service`: inactive / dead (`Result=success` — stopped cleanly
    at some point); `/health` + `/ready` on port 8010: connection failed
    (000).
  - Gone from disk: the discovery script, the YouTube cookie jar
    (`VyralX/data/youtube_cookies.txt`, present 2026-11-23 19:59 per the
    VYR-055 doc), the exclusion ledgers (`rejected_sources.json` 51 ids,
    `published_shorts_manifest.json` 11, `viral_loop_manifest.jsonl` 11),
    the niche guard.
  - `CREDENTIALS.md.bak-20261125-preupdate` exists at the repo root —
    something touched the S2 checkout on 2026-11-25. Cause of the deletion
    is **unknown**.
  - Still present: `yt-dlp` venv 2026.10.21. Flat-playlist search works
    without cookies; per-video metadata fetch fails (`Sign in to confirm
    you're not a bot` — no cookie jar to pass). The yt-dlp n-challenge /
    SABR-only wall documented in VYR-055 stands.
- Corroborated by Muse 17 (watch083): **1,817 files deleted**, VyralX/ +
  Cortex/ gone, detached HEAD `09603dff`. (Count differs from 1,801 — the
  tree may have changed between probes; re-count at restore time.)

## What is blocked until the restore

- VyralX-Server is DOWN: no discovery, no renders, no machine-QA gates,
  no metrics sync. TASK-VYR-051's pool (12 candidates, PR #1780 merged
  11:54 IST) cannot run its media gates or a supervised cycle.
- TASK-VYR-052 (Muse 16) executes on the VYR-051 pool — gated.
- TASK-VYR-077 (Muse 5, claimed 2026-11-25 ~12:30 IST) requires a live
  end-to-end cycle on VyralX-Server — its live leg is gated; repo leg
  proceeds first.

## Proposed restore — steps in order, each gated

1. **Owner decision (via Muse).** Authorize the restore as a server move
   under the stop order. Questions for the owner: (a) restore the tracked
   tree only, or full service restore incl. fresh YouTube session?
   (b) accept the ledger-rebuild residual risk below?
2. **Snapshot first (before touching anything).** Tar the current S2 working
   tree including untracked files and `CREDENTIALS.md.bak-20261125-preupdate`
   to `/tmp` (or operator-chosen backup path). Preserve the evidence of
   what happened; do not destroy the scene.
3. **Find the cause (read-only).** `git status`, `git log`, `git reflog`,
   systemd journal for `VyralX.service`, shell history on S2. Record what
   deleted the tree before restoring, so it does not recur. Do NOT restore
   blind — a restore that re-runs the same trigger deletes the tree again.
4. **Verify `.git` integrity.** If the object store is damaged, re-clone
   from the public repo instead of trusting a partial restore.
5. **Restore tracked files.** `git restore .` (or `git checkout -- .`) from
   HEAD `09603dff`. Verify: `git status` clean; `VyralX/` and `Cortex/`
   present; file counts match the index (VyralX 418 files).
6. **Rebuild what git cannot restore (gitignored, S2-only).**
   - Fresh YouTube cookie session: new login / cookie export by the
     operator. Secrets never go in the repo; the jar lives only on S2.
   - Rebuild the exclusion ledgers from the pool JSONs on main (VYR-053 /
     054 / 055 / 055-REFRESH-3 / 057 + VYR-051 pool). **Residual risk:**
     ids that existed only in the lost ledgers cannot be recovered and a
     re-discovery could re-pick a rejected/published source. Record the
     rebuild provenance; the supervised cycle re-checks each candidate
     against the rebuilt ledgers.
7. **Restart + verify.** Start `VyralX.service`; `/health` + `/ready` must
   return 200 on port 8010. Then a per-video `yt-dlp` metadata fetch on a
   known candidate (proves the download path is back).
8. **Re-verify the yt-dlp / SABR wall.** If per-video fetch still fails
   with fresh cookies, the PO-token provider decision is a coordinator
   call — do not install anything without clearance (owner freeze).
9. **Prove the cycle.** One supervised-cycle dry run on the VYR-051 pool:
   loop stays OFF, uploader paused, renders held unlisted. Machine QA
   gates (licence, caption-track count, BGM, watermark, loudness) must run
   end-to-end. File the run as evidence.

## Acceptance (restore is done when)

- `VyralX.service` active; `/health` + `/ready` 200 on 8010.
- Discovery + per-video fetch + machine QA gates runnable end-to-end on
  the VYR-051 pool.
- Ledgers rebuilt with provenance recorded; residual-risk note filed.
- Cause of the deletion recorded (or recorded as unknown with the
  evidence preserved).

## Open questions (for the coordinator / owner)

- Authorize the restore now, or hold until the stop order lifts?
- Who exports the fresh YouTube session (operator step — needs a login)?
- Accept the ledger-rebuild residual risk, or require a full re-audit of
  the pool against channel history first?
