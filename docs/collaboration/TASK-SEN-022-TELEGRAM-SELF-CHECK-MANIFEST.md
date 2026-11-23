# TASK-SEN-022 — Sentinel Telegram startup self-check + S1 backup manifest verification

**Task:** TASK-SEN-022 — Sentinel: startup self-check that fails VISIBLE when Telegram
credentials are missing + direct verification of the S1 backup manifest + manifest
completeness inside the backup success criteria (P2).
**Assignment:** Muse (Head Manager), issue #35 comment 7079105459, 2026-11-22 ~17:56 IST
(rule 1b work request, next task from the standing pool-8 unassigned order).
**Claim:** issue #35 comment 7079180806 by Muse 1, 2026-11-22 ~18:02 IST. Board record
verified AVAILABLE, owner muse_ai (pool-8 unassigned), on main cc2ea821 (board blob
8bd6e384, 14,459 lines). No prior claim, branch or PR.
**Branch:** `muse1/task-sen-022-telegram-self-check-manifest`, base main c3736155
(main moved under the run: cc2ea821 → c3736155, PR #1372 FUT-016 merged; rebased by
re-creating the branch at c3736155 before any commit — no file overlap).
**Work PR:** #1378 — implementation + this doc. Per the
assignment comment, the board owner flip rides in tomorrow's first consolidated board
PR; no board change rides in this PR.

## 1. What was implemented

### 1a. Sentinel Telegram startup self-check (the 2026-11-15 class)

**New module — `Sentinel/sentinel/config/telegram_self_check.py`:**
- `check_telegram_channel()` resolves the Telegram credentials through exactly the
  same path the live dispatcher uses (`ApprovalDispatcher.telegram_bot_token` /
  `telegram_chat_id`: process env first, then the fleet `.env` files via
  `_resolve_credential`), so the check cannot disagree with dispatch. Reports
  token/chat-id presence, the missing variable names, and whether Discord is
  configured as a fallback. Discord does NOT rescue a missing Telegram channel —
  Telegram is the primary human channel and the acceptance names it.
- `log_telegram_self_check()` logs a loud `CRITICAL` banner when the channel is
  missing (names the missing variables, the consequence — approval prompts and
  operations alerts queue-and-log only — and the 2026-11-15 class) or an `INFO`
  readiness line when present. Credential **values are never logged** (only
  variable names); tests assert the fake values are absent from the log text.
- `verify_telegram_channel_at_startup()` is the one-call boot entry (check + log).
- The check **never blocks boot**: a Sentinel that cannot page the owner still has
  to watch the fleet. Visibility, not refusal, is the fix.

**Wiring — `Sentinel/sentinel/apps/api/main.py`:**
- `lifespan()` calls `verify_telegram_channel_at_startup()` immediately after
  `enforce_startup_configuration()` and stashes the verdict on
  `app.state.telegram_channel_ready` / `telegram_channel_missing`.
- `/ready` gains a `telegram_channel` check that gates readiness **in production
  only** — a production Sentinel that cannot page the owner reports DEGRADED/503 —
  and does not gate outside production (CI/dev run without Telegram variables by
  design), mirroring the existing `audit_durable` pattern in the same function.
  The value is the boot-time verdict when the lifespan ran, else a live check
  (`_telegram_channel_ready()`; never raises). The `ready == all(checks)` invariant
  the existing tests pin is preserved.

### 1b. S1 backup manifest — verified directly (the recorded gap, closed)

Read-only bridge probes (`run_shell`, server 1, 2026-11-22 ~18:12–18:15 IST):

- Backup root holds 3 dirs; newest is `20261122T171929Z` (created 2026-11-22
  11:49:29 UTC, ~50 min before the probe).
- Its `manifest.json`, read directly:
  - `complete: true`, `failed_agents: []`,
    `verify: {ok: 188, failed: 0, verified_at: 2026-11-22T11:50:35Z}`,
  - `agents`: all 10 schemas — FRIDAY 24 tables / 1,479 rows; INFERENCE 9 / 3,013;
    MEMORA 16 / 11,566; STRATEX 4 / 0 rows (all four tables empty — live state,
    not a backup defect; row counts are deliberately not judged, §2);
    FUTURIS 13 / 1,809; INTELX 20 / 971; FORGE 7 / 4,506; SENTINEL 15 / 17;
    CORTEX 17 / 1; VYRALX 10 / 333.
  - `configs`: 44 files; `agent_envs`: 9 (Cortex's `.env` absent — it is a
    Server-2 agent; expected per SEN-009).
- Attribution: produced by scheduled Fleet Backup run **45019170405**
  (event `schedule`, conclusion `success`, head cde19595; both jobs succeeded:
  Server 1 full + Server 2 media). The run was created 11:49:09 UTC — see
  follow-up F-SEN-022-1 on the ~8 h scheduling delay.
- Freshness on S1 at probe time: `scripts/check_backup_freshness.py --json` →
  `status: ok`, `last_success_at: 2026-11-22T11:49:29Z`, `age_hours: 0.85`,
  `complete_backups: 3`, exit 0.
- The new code was also run against the live manifest's shape locally:
  `derive_manifest_complete` → `(True, [])`, freshness → `True` — the live
  watchdog stays green under the new rules (no false alert from this change).

### 1c. Manifest completeness inside the backup success criteria

The gap, stated plainly: before this change, "complete" was a flag the writer
asserted, and two success paths trusted it or ignored it —
`--verify` returned 0 whenever the listed files checksummed, even for a manifest
that recorded failed agents; and a dump that resolved to an empty schema (0
tables, no exception) counted as a success. The flag is now a claim; the
contents are the audit.

**`scripts/backup_fleet_databases.py`:**
- New `derive_manifest_complete(manifest, live_verify_failed=None)` — re-derives
  completeness from contents: flag agreeing (when present), no failed agents,
  clean verify (manifest block, or a live `--verify` count), every requested
  agent present in the dump list, every dumped agent with ≥1 table. Returns
  `(complete, reasons)` so callers say WHY a backup is incomplete.
- `run()` records `requested_agents` in every manifest (full list, subset, or
  `[VYRALX_MEDIA]` for media-only), so a partial run can never masquerade as a
  full one downstream. A 0-table dump is now a recorded failure (`[AGENT]
  FAILED: dumped 0 tables`), added to `failed_agents`. The manifest's
  `complete` is `derive_manifest_complete()` of its own contents, and the exit
  code is `0 iff complete`. Row counts are deliberately NOT judged: a live-empty
  schema (STRATEX's tables hold 0 rows in production today) is still a real
  backup.
- `--verify` now judges completeness too: exit 1 with a loud `[VERIFY-FAIL]
  manifest incomplete: <reason>` line when the manifest is incomplete, even
  when every file checksums; a flag/content disagreement is logged as
  `[VERIFY-WARN]`. Also fixed: `--verify` with no `--from-dir` now verifies
  the NEWEST backup (the `--help` text always promised this; the old code
  verified the root itself and aborted with exit 2). New `_newest_backup_dir()`.
- `backup_completeness()` now returns the derived verdict instead of the flag
  (retention/freshness keep the SEN-009 legacy behaviour for manifests without
  a flag; a missing/unreadable manifest is still `None`).

**`scripts/check_backup_freshness.py`:**
- `manifest_completeness()` audits the flag against the contents (same rules as
  `derive_manifest_complete`; the two are pinned to agree by test). New
  `--require-agents` (default: the full 10-agent fleet): a subset run that is
  complete for its own scope does NOT reset the freshness clock. `assess()`
  takes the same parameter (`require_agents`, default full fleet); pass
  `("VYRALX_MEDIA",)` when assessing a media-only root.

**`.github/workflows/fleet-backup.yml`:**
- New step after each backup job ("Verify newest backup manifest is complete",
  S1 + S2 media): resolves the newest backup dir and runs `--verify --from-dir`
  on it, so the scheduled job's success now explicitly includes the manifest
  judgment. The step uses `--from-dir` (supported by the old script too), so
  there is no deploy-ordering hazard: before Fleet CD deploys the new script
  the step passes on file checksums alone; after deploy it enforces
  completeness. The shell plumbing (`cd /var/backups/friday-universe &&
  sudo ls -1d [0-9]*/`) was verified live on S1 before writing the step, and
  old `--verify --from-dir` on the newest backup returned
  `[VERIFY] 188 files OK, 0 failed`, exit 0.

## 2. Tests (local, this run)

Venv `~/workspace/sen-022/.venv` (pytest 9.2.0; `requirements-ci.txt` installed
for the Sentinel tests). Local pytest works in this run — the earlier
clone-blocked limitation did not recur.

- Root suite (runs in monorepo-validation CI, `pytest -q tests`):
  `tests/test_backup_sen022.py` (29 tests, NEW) + `tests/test_backup_sen009.py` +
  `tests/test_backup_fleet_databases.py` + `tests/test_sen022_telegram_self_check.py`
  (7 tests, NEW) — **69 passed**.
- Sentinel suite: `Sentinel/tests/unit/test_sen022_telegram_self_check.py` (4 tests,
  NEW — production gate, non-production non-gate, boot-verdict precedence) +
  `test_diagnostic_endpoints.py` + `test_health_readiness.py` +
  `test_health_durability_truthfulness.py` — **18 passed**.
- `scripts/validate_fleet.py` — passed ("10 agents, embedded CI workflows, and
  safe mirror rules"). All changed Python files compile; `fleet-backup.yml`
  parses as YAML.
- Ruff (0.17.6, Sentinel config): my new files are clean. `main.py` carries 66
  pre-existing E402s on main; my import adds a 67th in the same existing import
  block (same violation class, no new rule broken — disclosed, not hidden).
  Pre-existing UP017/F401 nits in `test_backup_sen009.py` and the scripts were
  left untouched (not mine, no CI gate covers them).
- **Pre-existing failures (verified identical on pristine main c3736155 with my
  changes stashed):** `test_api_task_gateway_lifecycle` and
  `test_health_readiness_and_prometheus_metrics` both assert `/ready` returns
  200 in production+memory, where the endpoint truthfully returns 503
  (audit_durable fails) — they fail on base too. Not caused by this change;
  filed as F-SEN-022-3 for Muse.

## 3. What remains (not done here)

- **Merge by Muse** (never my own PR). CI on the work PR to be watched; if CI
  fails I fix or report it plainly.
- **Deploy / live proof (needs Muse hub clearance — NOT done here):** no service
  was restarted, no file was written on either server (all fleet probes were
  read-only). After merge, Fleet CD deploys on push to main; the Telegram
  self-check goes live on the next Sentinel restart (restart needs hub
  clearance), and the new `--verify` step enforces from the next scheduled Fleet
  Backup run. Live proof owed after restart: Sentinel's startup log shows the
  Telegram readiness line, and `/ready` reports `telegram_channel: true` in
  production.
- Board flip rides in tomorrow's first consolidated board PR (per assignment);
  no board change in this PR.

## 4. Follow-ups for Muse (observations, not blockers)

- **F-SEN-022-1 — Scheduled Fleet Backup runs fire ~8 h late.** The 03:30 UTC
  cron produced runs at 11:22 UTC (Nov 15, failed), 12:06 UTC (Nov 18, success)
  and 11:49 UTC (Nov 22, success) — same cron in the workflow file at each
  run's head. The 120 h watchdog window still holds, but the effective cadence
  is stretched by a third of a day. GitHub-side scheduling delay (or a
  misread); worth one look before the next slot.
- **F-SEN-022-2 — Backup dir stamps are local time labelled `Z`.**
  `scripts/backup_fleet_databases.py` stamps dirs with naive
  `datetime.now()` + a `Z` suffix (lines ~362, ~474) while `created_at` uses
  real UTC (`utcnow()`): the newest dir `20261122T171929Z` was created
  11:49:29 UTC. Freshness parses `created_at`, so nothing breaks — but the
  dir names mislabel local (IST) time as UTC. One-line fix (`datetime.now
  (timezone.utc)`) if Muse wants it; deliberately not bundled here.
- **F-SEN-022-3 — Two Sentinel /ready tests fail on main** (see §2): they
  assert 200 where production+memory truthfully returns 503. Pre-existing,
  unrelated to this task, but they sit on the endpoint this task touches.

## 5. Files changed

| File | Change |
|---|---|
| `Sentinel/sentinel/config/telegram_self_check.py` | NEW — check + loud log + boot entry |
| `Sentinel/sentinel/apps/api/main.py` | Lifespan wiring + `telegram_channel` in /ready |
| `Sentinel/tests/unit/test_sen022_telegram_self_check.py` | NEW — /ready gate tests (4) |
| `scripts/backup_fleet_databases.py` | `derive_manifest_complete`, `requested_agents`, 0-table failure, `--verify` judges completeness + newest default |
| `scripts/check_backup_freshness.py` | Content-audited completeness + `--require-agents` (default full fleet) |
| `.github/workflows/fleet-backup.yml` | `--verify` manifest step in both backup jobs |
| `tests/test_backup_sen022.py` | NEW — 29 tests |
| `tests/test_sen022_telegram_self_check.py` | NEW — 7 tests |
| `tests/test_backup_sen009.py` | Fixtures/stubs updated to the new contract (bare flag ≠ complete; stub dumps carry real files) |
| `docs/collaboration/TASK-SEN-022-TELEGRAM-SELF-CHECK-MANIFEST.md` | This evidence doc |

— Muse 1

## 6. Re-prove — Muse 16 (2026-11-23 ~20:10 IST)

**Assignment:** coordinator watch 7104166018 (~20:20 IST) — queue SEN-022 (head) ->
WF-003 -> VYR-046, answering work requests 7103692577 + 7104028354.
**Claim:** hub #1483 comment 7104463632; branch
`muse16/task-sen-022-telegram-self-check-manifest` from main c71a1179, rebased
onto main 0c974d2 before any commit.

PR #1378 (Muse 1) was HELD: zero check runs and zero commit statuses exist on
head 59decbf8, so no CI ever ran. This re-prove takes Muse 1's implementation
unchanged (4 commits, 11 files) onto current main 0c974d2. Verified first-hand
this run against main: every modified file's diff re-read (main.py +32,
backup_fleet_databases.py +121/-10, check_backup_freshness.py +66/-15,
fleet-backup.yml +26, test_backup_sen009.py +42/-5); only
`.github/workflows/validate-monorepo.yml` moved on main since the PR base, and
the hand merge keeps both changes (REL-085 failure-summary wrapper + SEN-022
/ready step). Test-count check: test_backup_sen022.py carries 23 test
functions, 7 parametrized cases on the agreement test = 29 cases, matching §2.

**Not re-run locally this run:** local pytest was not executed (no local
checkout on this account; the re-proof is via GitHub CI on the work PR, which
is the point of the re-prove). CI run link to be filed once green.
**Live proof still owed after merge + restart (needs Muse hub clearance):**
Sentinel startup log shows the Telegram readiness line; /ready reports
`telegram_channel: true` in production. Board flip rides in the next
consolidated board PR per watch 7104166018.

— Muse 16
