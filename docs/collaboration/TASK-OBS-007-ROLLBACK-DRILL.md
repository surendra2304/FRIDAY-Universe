# TASK-OBS-007 — Rollback drill re-run (TASK-OBS-002 follow-up)

**Task:** Re-run the rollback drill for TASK-OBS-002 (MASTER_PLAN §6 STALE-UNVERIFIED follow-up).
**Owner:** Muse 4 · **Date:** Sun 2026-11-22, ~10:30–10:40 IST · **Base:** main `60886ff6` (board blob `808514b0`)
**Claim:** issue #35 comment 7074476190 · **Board claim PR:** #1317 (board-only, superseded by the implementation PR)
**Drill form:** SAFE — throwaway git fixture only. No live production service was rolled back, restarted, or touched. No Fleet Rollback workflow run was triggered (that path needs hub clearance and a real incident window).

## What was drilled

`scripts/rollback_deploy.sh` (TASK-OBS-002, merged 2026-11-10) as it stands on main `60886ff6`, plus its guard suite `tests/test_rollback_deploy.py` and the one-click workflow `.github/workflows/rollback-deploy.yml`. All four OBS-002 artifacts were read from main; the script and tests were copied verbatim into a scratch fixture for the drill.

## Phase A — Guard suite re-run (8/8 pass)

`pytest tests/test_rollback_deploy.py -v` (pytest 9.2.0) against main's script and tests, verbatim:

- `test_rejects_non_commit_target` — PASS
- `test_rejects_target_equal_to_current_head` — PASS
- `test_rejects_forward_rollback` — PASS
- `test_rejects_sideways_rollback` — PASS
- `test_accepts_true_ancestor_and_resets` — PASS
- `test_dry_run_changes_nothing` — PASS
- `test_unconfirmed_interactive_mode_aborts` — PASS
- `test_affected_service_detection_from_changed_folders` — PASS

**Result: 8 passed in 2.05s.** The rollback-only guard (target must be an ancestor of the deployed HEAD) still holds on current main.

## Phase B — End-to-end rollback on a throwaway fixture

Fixture repo `/tmp` (discarded after the drill): commit A "known-good deploy" (`FRIDAY/app.py` = "FRIDAY v1 (good)") → commit B "bad deploy" (`FRIDAY/app.py` = "FRIDAY v2 BROKEN", plus `Stratex/engine.py`). Deployed HEAD = B (`d8bc2484…`), known-good target = A (`7f359fc2…`).

| Step | Command | Result |
|---|---|---|
| 1. Dry-run | `rollback_deploy.sh <A> --dry-run` | Exit 0. Printed `DRY-RUN rollback B -> A`, diffstat (2 files), `would restart: <none>`. HEAD stayed at B; `FRIDAY/app.py` still the broken v2. Nothing changed. |
| 2a. Guard: non-commit | `… 0000…0000 --yes` | Exit 1, `ROLLBACK-ABORT: target '0000…' is not a commit object`. HEAD unchanged. |
| 2b. Guard: target == HEAD | `… <B> --yes` | Exit 1, `ROLLBACK-ABORT: target … is already the deployed HEAD`. HEAD unchanged. |
| 2c. Guard: forward | Detached at A, `… <B> --yes` | Exit 1, `ROLLBACK-ABORT: target … is NOT an ancestor of deployed …`. HEAD unchanged (back on main at B after). |
| 3. Real rollback | `rollback_deploy.sh <A> --yes` | Exit 0, `ROLLBACK DONE`. HEAD == A (`7f359fc2…`); `FRIDAY/app.py` restored to "FRIDAY v1 (good)"; `Stratex/engine.py` gone; `git status` clean. **Rollback restores the prior state — proven, not just dry-run.** |

## Phase C — `--json` receipt path

| Step | Result |
|---|---|
| 4. Happy path | Second bad deploy D → `rollback_deploy.sh <A> --yes --json`: exit 0, receipt written to `/var/lib/friday-universe/rollback-receipts/rollback-20261122T050212Z.json` with `{"rolled_back_at": "2026-11-22T05:02:12Z", "from": "b396ea8e…", "to": "7f359fc2…", "restarted": "", "health": ""}`. |
| 5. Receipt dir blocked | Third bad deploy E → receipts path blocked by a regular file where the directory must be → `mkdir: cannot create directory '/var/lib/friday-universe': Not a directory`, **exit 1 — but only AFTER `git reset --hard` had already succeeded**: HEAD == A and `FRIDAY/app.py` == v1, with no `ROLLBACK DONE` printed. See G1. (Blocker file removed afterwards; sandbox receipts dir cleaned up.) |

## Live-server check (read-only, bridge)

- Both Oracle servers ONLINE (bridge `get_system_info`, 2026-11-22 ~10:33 IST).
- `scripts/rollback_deploy.sh` on Server 1 and Server 2 is **byte-identical to main `60886ff6`** (5,274 bytes each, diff clean).
- `.github/workflows/rollback-deploy.yml` on Server 1 is **byte-identical to main** (3,076 bytes).
- Note: the bridge `read_file` tool resolves relative paths against the workspace — absolute `/opt/friday_universe/…` paths return "File not found"; relative paths work. One server-2 read also dropped once with an HTTP `IncompleteRead` (transport flake, retry succeeded). Neither affects the drill result.

## Gaps filed

- **G1 — Receipt-write failure masks a successful rollback.** `scripts/rollback_deploy.sh`: the `--json` block runs `mkdir -p "$RECEIPTS_DIR"` under `set -euo pipefail` *after* `git reset --hard` has already succeeded, so an uncreatable receipts directory exits 1 with no `ROLLBACK DONE`. Proven in Phase C step 5. Impact: the Fleet Rollback workflow runs `--yes --json`, so it would report failure even though the rollback took effect — an operator re-running it would then hit "already the deployed HEAD". Fix: make the receipt write best-effort (e.g. `mkdir -p … || echo "warning: receipt not written" >&2`) so a post-reset bookkeeping failure cannot report a successful rollback as failed. Severity: low (on the real servers the script runs under `sudo`, so the directory is normally creatable) — robustness only.
- **G2 — Post-rollback health probe never fails the workflow.** `.github/workflows/rollback-deploy.yml`, "Post-rollback fleet health" step: unhealthy agents only produce `::warning::`; the step (and job) still exits 0. A rollback that leaves agents unhealthy shows green. Fix: `exit 1` when `bad` is non-empty (or keep the warning and fail the step), so the job log cannot be misread as a clean rollback.

## Honest limits of this drill

- The **systemctl restart + HTTP health-check loop was not exercised**: the fixture has no systemd units, so affected-service detection yielded `would restart: <none>` in every step. The guard suite shares this limitation by design (it asserts the folder-diff logic, not the restart loop). A full production-path proof needs a real deploy plus a typed Fleet Rollback workflow run — that requires hub clearance and a real incident window, and is out of scope for this safe-form drill.
- The drill ran against main's script copied to a scratch fixture, not against a live server checkout; the byte-identical check above is what ties the drilled code to the deployed code.

## Acceptance verdict

- ✅ Drill executed and recorded; rollback restores the prior state (Phase B step 3) and the dry-run proves each step (Phase B step 1).
- ✅ Gaps filed with file/line: G1 `scripts/rollback_deploy.sh` (`--json` receipt block, after `git reset --hard`), G2 `.github/workflows/rollback-deploy.yml` (post-rollback health step).
- ✅ No live production service rolled back or restarted without hub clearance — nothing live was touched at all.

**Status: implemented + tested (drill evidence above). Awaiting Muse's review/merge. Only Muse merges.**

— Muse 4
