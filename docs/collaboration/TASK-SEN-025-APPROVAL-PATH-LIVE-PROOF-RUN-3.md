# TASK-SEN-025 — Sentinel approval-path live proof run 3 + backup manifest verification run 2

**Task:** Sentinel: approval-path live proof run 3 + backup manifest
verification run 2 — one low-risk auto-approval + one high-risk Telegram
prompt, each exactly once, with evidence; and the backup manifest verified
against live state.
**Owner:** Muse 13 · **Branch:**
`muse13/task-sen-025-approval-path-live-proof-run-3`
**Claim:** hub #1483 comment 7120832047, 2026-11-24 ~08:40 IST, under the
blocked-head rule (VOI-030 + VOI-035 both CLAIMED and blocked on a
calm-window voice call); assigned as queue position 3 after VOI-030 →
VOI-035 by coordinator watch ~07:53 IST (board PR watch010).
**Claim PR:** #1617, merged 2026-11-24 09:07:33 IST (merge ab5651a5), CI
9/9 green (7 success, 2 skipped, 0 failures). Work PR filed after the
merge, per standing workflow.
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via
`https://friday-universe.duckdns.org/sentinel` (Caddy). Service start:
2026-11-24 08:29:17 IST, MainPID 3425193, `Sentinel.service` active.
(Note: the service restarted at 08:29:17 IST, before this run; the cause
was not established this run. The deployed code matches S1 HEAD, so the
restart is consistent with the current deploy.)
**Run-2 reference:** TASK-SEN-024 (Muse 13, 2026-11-24) — same legs, same
procedure; this run repeats it against the current deploy.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`,
`apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical
(md5) to this repo at S1 HEAD `27f181e4` — the code surveyed below is the
code that ran (identical md5s to SEN-024; no commits touched these files
between `45b8fbba` and `27f181e4`):
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

## How the approval path works (repo source, at 27f181e4)

Same as SEN-024 (verified unchanged in the surveyed files):

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`.
  `classify_approval` returns `AUTO_APPROVE` only when ALL hold: caller risk
  claim is low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern
  (live-money, owner-data deletion, credential change, Sentinel-policy
  change); and the action positively matches the low-risk class — read-only
  leading verb with no write verb later, internal housekeeping, or
  caller-attested reversible. Anything else is `OWNER_PROMPT`; the policy
  never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`.
  `submit_approval` classifies first. Auto-approve: writes an
  `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only
  then marks the request APPROVED; if the ledger write fails it falls back
  to the owner prompt. Owner prompt: `_dispatch_notifications` sends the
  Telegram message via `_send_telegram` and records the request PENDING with
  approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`:
  `POST /api/v1/approvals/request` calls `submit_approval` and returns the
  pending record. `GET /api/v1/approvals/pending`,
  `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit
  POST from the confirmation form; the GET confirmation pages never change
  state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals
  endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required
  (`X-API-Key` header). The live calls below were made from Server 1 itself
  by throwaway scripts that read the key from the systemd `EnvironmentFile`
  (`/opt/friday_universe/Sentinel/.env`, the same file the live service
  loads) and used it in-process only. The key value was never printed,
  copied, or stored anywhere; the scripts were deleted after the run.
  Approval **tokens** (bearer approve/deny credentials) are likewise never
  reproduced in this document — requests are identified by `request_id`
  only. The leg-2 token was held in a file on Server 1 only, for the
  post-expiry check, and deleted after it.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`:
  `log_file_path = "logs/audit.jsonl"` → on Server 1,
  `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of
  `submit_approval` is the API endpoint above; no production code calls
  `wait_for_decision`. A submitted action is a *request record* only —
  nothing in the fleet executes an action because its approval record
  exists.

## Pre-flight checks (before either leg)

- Both Oracle servers ONLINE (`get_system_info`, 2026-11-24 ~08:44 IST).
- Sentinel `/health` 200: `audit_chain_valid: true`,
  `audit_chain_entries: 28`, `kill_switch_active: false`,
  `audit_durable: true` (2026-11-24 08:44 IST). Seq 28 is a
  `TLS_CERT_ALERT` (sentinel_tls_daemon, 08:30:08 IST, after the 08:29
  service restart) — not approval traffic.
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle),
  `telegram_channel: true` — the SEN-022 startup self-check gate is live
  and passing in production (2026-11-24 08:44 IST).
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`;
  no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions (repo code at 27f181e4,
  no live effect): leg 1 → `AUTO_APPROVE / read_only`; leg 2 →
  `OWNER_PROMPT / caller_risk_not_low`.
- Pending list empty before the legs (`GET /api/v1/approvals/pending` →
  `[]`, HTTP 200, 2026-11-24 08:46 IST) — no other approval traffic.
  (One first attempt at this read timed out client-side at 30 s; retried
  with a 120 s timeout and succeeded — the same slow-under-load behaviour
  SEN-024 observed. The service never stopped.)
- **Load note (observed, not a blocker):** none this run — `/health`,
  `/ready`, and all approval calls answered in seconds.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel health status`
- **Submitted by:** `MUSE_13`, `risk_level: LOW`,
  details `{"purpose": "TASK-SEN-025 leg 1 proof", "task": "TASK-SEN-025"}`
- **Submitted:** 2026-11-24 08:47:09 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`,
  `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-24T03:17:09.712882+00:00`,
  `decided_at 2026-11-24T03:17:09.732880+00:00` (~0.02 s later)
- **Request id:** `appr_5988b5ba8538`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy
  (TASK-SEN-019): read_only — Read-only action ('check ...') with a LOW
  caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`,
  exactly one entry for this request id:
  `seq 29`, `entry_id audit-appr-auto-appr_5988b5ba8538`,
  `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`,
  `target MUSE_13`, `action_type "check sentinel health status"`,
  `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`,
  `timestamp 2026-11-24T03:17:09.727745+00:00`,
  `previous_hash 937ca1ab8b8a772051c57af19347fc6b6ccb96a0c916182620272739142036e0`
  (chains onto the seq-28 tail entry, a `TLS_CERT_ALERT`),
  `current_hash 066b47ee7ed80cc508393c281a9ef4598bd5ac8843124e9df9e45af79d2fac6f`.
  Hash linkage verified: seq 29 `previous_hash` == seq 28 `current_hash`
  (`937ca1ab8b8a7720…`). Details: `policy_category read_only`,
  `risk_level LOW`.
- **Service journal:** `Nov 24 08:47:09 … Approval appr_5988b5ba8538
  (check sentinel health status by MUSE_13) AUTO-APPROVED [read_only]`
- **Cross-check:** `/health` entry count 28 → 29 after the leg
  (`audit_chain_valid: true`).

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `deploy sentinel configuration change to production`
- **Submitted by:** `MUSE_13`, `risk_level: HIGH`,
  details `{"purpose": "TASK-SEN-025 leg 2 proof, prompt only",
  "task": "TASK-SEN-025"}`
- **Submitted:** 2026-11-24 08:48:24 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`,
  `policy_category: caller_risk_not_low`, `decided_at: null`,
  `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-24T03:18:20.223776+00:00`,
  `expires_at 2026-11-24T03:23:20.223777+00:00` (08:53:20 IST)
- **Request id:** `appr_284a976be909`
- **Recorded in the live service:** the request appears in
  `GET /api/v1/approvals/pending` (HTTP 200) with the same fields —
  it is held in the running process's pending map awaiting a decision.
  The pending list contained exactly this one item (checked 08:49:09 IST).
- **Telegram prompt — what was sent:** `_dispatch_notifications`
  (`approval_dispatcher.py`) builds this message from the template with
  the live values and sends it via `_send_telegram` because the channel
  is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_13`
  > **Action:** `deploy sentinel configuration change to production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-025 leg 2 proof, prompt only", "task": "TASK-SEN-025"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside
    `submit_approval`; the code only skips Telegram when the channel is
    unconfigured (it was configured) and only logs on transport failure.
  - Service journal 08:47:00–08:52:00 IST contains **no**
    `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback)
    and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 08:48:24 IST;
    the synchronous Telegram `urlopen` completed inside that call with no
    error logged.
  - The Telegram `message_id` is **not observable** from this side:
    `_send_telegram` discards the API response and returns only a boolean,
    which is not logged on success. Delivery to Surendra's Telegram client
    is therefore asserted from the configured channel + clean dispatch
    path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 13 anywhere: no POST to
  `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction,
  no `decide()` call. At submission the record showed `decided_at: null`.
- The action was never a command: the approval request is a record only
  (see "No executor on this path"). No deploy command was issued to any
  host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 08:53:20 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-24 08:53:58 IST, after `expires_at` 08:53:20 IST,
  token recovered server-side from the Server 1 file (never printed or
  copied out; file deleted after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as
    `PENDING`, `decided_at: null`, `decision_reason: null` — no decision
    was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone
    from the actionable pending list.
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation
    page, which never changes state) → **HTTP 409 "Approval no longer
    pending"** — the approve link is dead.
  - Semantics note: the stored `status` field only transitions when
    `decide()` or `wait_for_decision()` runs; the live gate is the
    `is_expired()` check enforced by the approve/deny paths. The 409
    proves that gate is closed.
- **Honesty note on the first expiry attempt:** an earlier check ran at
  08:52:09 IST — 71 seconds *before* `expires_at` — and is not a
  post-expiry check (status PENDING, still listed, as expected
  pre-expiry). It also showed the approve confirmation page returns
  **HTTP 401 without an API key**; the valid 409 above was obtained with
  the key on all three calls. Only the 08:53:58 IST check counts as the
  post-expiry proof.
- **No-execution corroboration:** `Sentinel.service` still `active` with
  the same start timestamp (`Tue 2026-11-24 08:29:17 IST`) — no restart;
  S1 `/opt/friday_universe` git HEAD unchanged at `27f181e4` — no deploy;
  journal 08:47–08:52 IST contains zero `Telegram notification dispatch
  error` / `[SENTINEL APPROVAL QUEUED]` lines.
- **Cleanup:** the leg-2 token file and all throwaway scripts on Server 1
  were deleted after this check (verified: no `/tmp/sen025_*` remains).

## BACKUP MANIFEST VERIFICATION — run 2

Run 2 re-verifies the same newest backup against current live state,
using the REL-089 drill scripts (integrity + scratch load + Phase A +
field-by-field content compare; read-only vs live, `SELECT` only; the one
load went to a throwaway SQLite DB in `/tmp`, deleted afterwards).

### Backup used (still the latest)

| | |
|---|---|
| Backup dir (Server 1) | `/var/backups/friday-universe/20261122T171929Z` |
| Created (UTC) | 2026-11-22T11:49:29Z |
| Produced by | Scheduled Fleet Backup run 45019170405 (event `schedule`, success) |
| Manifest | `complete: true`, `failed_agents: []`, `verify: {ok: 188, failed: 0}` |
| Freshness at verification | `status: ok`, `age_hours: 39.52`, `complete_backups: 3`, exit 0 (checked 2026-11-24 08:50 IST / 03:20:30Z) |
| Newer backup? | No — still the newest on S1 (dirs: `20261116T062553Z`, `20261118T173701Z`, `20261122T171929Z`); the next scheduled run is Sun Nov 29 03:30 UTC |
| SENTINEL in manifest | 15 tables, 17 rows (AUDIT_LOGS 4, EVENTS 12, SCOPES 1, 12 tables 0 rows) |

### Results — identical shape to REL-089, drift grown

| Check | Result |
|---|---|
| Backup tool's own `--verify` | 188 files OK, 0 failed — "backup complete", exit 0 |
| Per-file integrity (15 files) | 15/15 SHA-256 match; 15/15 line counts == manifest `row_count` |
| Scratch load (SQLite) | 17/17 rows; counts equal to manifest for every table (incl. 12 empty tables at 0) |
| Restored columns vs live schema | Equal for all 3 tables with rows; live columns recorded for the 12 empty tables |
| Phase A (verify-only) | 14 match, 1 differ — `SENTINEL_EVENTS` 12 → 29 (+17, was +13 at REL-089; live writes since backup, expected drift); 0 missing, 0 extra |
| Scalar columns vs live | Identical for all 17 rows (entry/event/scope ids, hashes, signatures, timestamps, decisions) |

### Content: the same 21 values are still lost in the backup

| Table | Rows | Lost in backup |
|---|---|---|
| `SENTINEL_AUDIT_LOGS` | 4 | `details`: `""` in backup, full JSON live (same 4 entries as REL-089) |
| `SENTINEL_EVENTS` | 12 restored / 29 live | `payload`: `""` in backup, full JSON live; the 17 extra live rows are post-backup writes |
| `SENTINEL_SCOPES` | 1 | `allowed_targets`, `in_scope_declarations`, `out_of_scope_declarations`, `scope_contract`: all `""` in backup, full JSON arrays/object live |
| 12 empty tables | 0 rows | Nothing to lose; counts match |

The scope row drifted again on one scalar: `expiry` backup
`2036-11-19 07:43:42` vs live `2036-11-21 02:59:36` (was `2036-11-20
15:59:18` at REL-089 — a live re-issue after the backup; drift, not a
defect).

### Verdict on the backup leg

**The manifest still cannot be trusted as a restore proof.** The Nov 22
backup is unchanged (same files, same manifest), and the defect that made
it lossy is still in the code: `scripts/backup_fleet_databases.py:118`
still reads `value.read(LOB_CAP_BYTES)` on S1 HEAD `27f181e4` (no commits
touched the file since `45b8fbba`). The fix is routed, not landed:
**TASK-REL-091** (fix the backup CLOB-loss defect) is AVAILABLE, owner
muse_4, queue STR-HLT-002 (blocked head) → REL-091. Until REL-091 lands,
a fresh backup is taken, and a re-drill shows zero empty CLOBs, every
backup this tool produces will carry the same loss. The manifest's
`complete: true` and `--verify` 188 OK remain blind to content loss
(REL-089 gaps R2–R4 unchanged).

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log
  or return the Telegram `message_id`, so the exact message id and
  confirmation that the message rendered on Surendra's device cannot be
  established from the server side. The prompt's dispatch is evidenced by
  the configured channel, the synchronous send inside the 200-OK
  submission, and the absence of any dispatch-error or offline-queue log
  line. If Muse or Surendra eyeball the Telegram client, the message
  above should be visible there.
- **Ledger re-verification after the legs:** the file ledger entry for
  leg 1 was verified by hash linkage (previous hash = seq-28 tail hash);
  a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the
  legs and contained only the leg-2 request after it; earlier pending
  history was not audited.
- **Backup leg scope:** Sentinel tables only (as in REL-089). The
  fleet-wide empty-CLOB count (14,414 in the Nov 22 backup) was not
  re-audited; that belongs to the REL-091 fix + fresh backup + re-drill.

## Verdict

**TASK-SEN-025 — live proof run 3 PASS; backup manifest verification run 2
CONFIRMS the REL-089 finding (not yet fixed).** Leg 1 auto-approved
(appr_5988b5ba8538, seq 29, chain OK); leg 2 prompted on Telegram
(appr_284a976be909, PENDING, expired un-actioned, approve link 409-dead);
the high-risk action did not execute. The backup manifest verifies
structurally (188 files OK, 15/15 integrity, 17/17 scratch, Phase A 14/1
with expected drift) but the content loss persists: 21 JSON/CLOB values
still `""` in the Nov 22 backup while live holds full JSON; R1 unfixed in
code, fix task REL-091 still AVAILABLE with Muse 4.

## Files changed

| File | Change |
|---|---|
| `docs/collaboration/TASK-SEN-025-APPROVAL-PATH-LIVE-PROOF-RUN-3.md` | This evidence doc (NEW) |
| `docs/collaboration/WORK_BOARD.yaml` | SEN-025 record CLAIMED → IN_REVIEW (work PR, held on claim PR #1617 merging) |

Drill tooling (REL-089 scripts reused verbatim from
`~/workspace/muse13/rel089/`, copied to S1 `/tmp` as `sen025_*` and deleted
after the run) lives in the worker's scratch dir `~/workspace/muse13/rel089/`
and `~/workspace/muse13/sen025/`; the repo deliverable is this doc + the
board record. No live database or config was written to; no service was
restarted; no approval was granted or denied by Muse 13.

— Muse 13, 2026-11-24 ~08:56 IST. Usage: 23% of free weekly limit
(reset Nov 29, 6:09 PM IST).
