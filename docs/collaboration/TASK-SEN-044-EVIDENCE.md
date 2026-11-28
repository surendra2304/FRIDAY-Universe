# TASK-SEN-044 — Sentinel approval-path live proof, re-proof run 2

**Task:** Sentinel: approval-path live proof re-proof run 2 — one low-risk action auto-approved and one high-risk action prompting on Telegram, each exactly once, with evidence.
**Owner:** Muse 13 · **Branch:** `muse13/task-sen-044-approval-path-live-proof`
**Claim:** hub #2045 comment 7236433092, 2026-11-28 ~13:42 IST (WATCH263 §C assignment, adopted by Burn Enforcer ~13:45 IST, hub #2045 comments 7236357595 / 7236383505). Board on main `6b1c91cb` verified first-hand: NO SEN-044 record yet — the draft rides WATCH264's board PR. No board hunk in this PR — board flips are coordinator-only.
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008. Service start: 2026-11-28 12:04:56 IST, Main PID 2493397, NRestarts 0, single worker (`Sentinel.service` active, unchanged across the run — no restart during the legs; see "No-execution corroboration"). Note: the service start predates this run by ~1.7 h (it was already running at claim time); what restarted it at 12:04:56 IST was not established in this run. SEN-043's baseline was 02:47:41 IST, PID 2201682 — a restart happened between the runs.
**Prior runs:** Run 2 SEN-036 (Muse 10, work PR #1971 MERGED 0434f6df); run 3 SEN-037 (Muse 4, work PR #2065); SEN-038 (Muse TP10, work PR #2074 MERGED 83d53187); SEN-040 (Muse 14, evidence PR #2176 MERGED); SEN-042 (Muse 14, evidence PR #2247 MERGED 93ccfd72); SEN-043 (Muse 14, evidence PR #2283, M5 VERIFIED) — same legs, same procedure; this run repeats it against the current deploy. Run-2 evidence: `docs/collaboration/TASK-SEN-036-APPROVAL-PATH-LIVE-PROOF-RUN-2.md`; run-3 evidence: `docs/collaboration/TASK-SEN-037-EVIDENCE.md`; SEN-038 evidence: `docs/collaboration/TASK-SEN-038-EVIDENCE.md`; SEN-040 evidence: `docs/collaboration/TASK-SEN-040-EVIDENCE.md`; SEN-042 evidence: `docs/collaboration/TASK-SEN-042-EVIDENCE.md`; SEN-043 evidence: `docs/collaboration/TASK-SEN-043-EVIDENCE.md`.
**Method note:** this run follows the SEN-043 method exactly (same two actions, same caller MUSE_13, same checks). The only method differences are stated where they occur below.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`, `apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical (md5) to the surveyed code — the code below is the code that ran:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

Same four md5s as SEN-024, SEN-036, SEN-037, SEN-038, SEN-040, SEN-042 and SEN-043 surveyed — the approval path is unchanged since run 1. Server 1 git HEAD at pre-flight was `527b073d9d2b67100066ab71b852504fae210f9f` (STR-115 merge; the claim branch was cut from main `6b1c91cb`, which S1 had not checked out — a checkout lag, not a deploy; the four approval-path files above prove the approval path itself is unchanged). Untracked files on S1 (`FRIDAY/.frd002_scratch/`, `FRIDAY/scripts/telegram_webhook_watchdog.py`, `FRIDAY/state/`, `Stratex/daily_loss_breaker_state.json`, `Stratex/forward_daily_reports/`, `Stratex/loss_streak_breaker_state.json`, `Stratex/scripts/telegram_webhook_watchdog.py`, `Stratex/self_experiments_data/`, `VyralX/light_result_r1.txt`, `VyralX/light_result_r2.txt`, `backtest_results/`, `venv312/`, `.backups/`) are recorded as observed, no action taken.

## Clearance for the live legs (why the legs were run, not held)

- **Standing clearance 7200564540** (coordinator ruling, hub #1483, 2026-11-27 ~00:05 IST; WATCH181 §2c + WATCH182 §2d) covers own-task live verification; only server moves, live money and destructive deletes still need a ruling. The Telegram prompt leg is none of those — it is a notification, not an execution (see "No executor on this path").
- **Owner stop order** (2026-11-24) freezes server moves only. The legs change no server state beyond the two approval-path test actions themselves: no deploy, no restart, no file written, no service stopped or started.
- **WATCH263 §C** (coordinator, hub #2045 comment 7236357595, 2026-11-28 ~13:35 IST) assigned SEN-044 to Muse 13, adopted by the Burn Enforcer ~13:45 IST (hub 7236383505). Leg 1 `list sentinel pending approval requests`, LOW, expect AUTO_APPROVE/read_only; leg 2 `change sentinel approval policy threshold in production`, HIGH, expect OWNER_PROMPT/sentinel_policy_change. Leg 2 is a request record only — no policy is changed, no command runs, no file is written, no service is restarted.
- Legs were run exactly once each by this run in a single no-retry batch (a retry after a dropped response could have double-fired a leg). See "Duplicate legs by an unattributed second actor" — an identical pair was submitted ~21–23 s earlier by someone else; this run's legs are separately identified by their own request ids throughout.

## How the approval path works (repo source)

Same as SEN-021 / SEN-024 / SEN-036 / SEN-037 / SEN-038 / SEN-040 / SEN-042 / SEN-043 (verified unchanged in the surveyed files):

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`. `classify_approval` returns `AUTO_APPROVE` only when ALL hold: caller risk claim is low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern (live-money, owner-data deletion, credential change, Sentinel-policy change); and the action positively matches the low-risk class — read-only leading verb with no write verb later, internal housekeeping, or caller-attested reversible. Anything else is `OWNER_PROMPT`; the policy never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`. `submit_approval` classifies first. Auto-approve: writes an `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only then marks the request APPROVED; if the ledger write fails it falls back to the owner prompt. Owner prompt: `_dispatch_notifications` sends the Telegram message via `_send_telegram` and records the request PENDING with approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`: `POST /api/v1/approvals/request` calls `submit_approval` and returns the pending record. `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit POST from the confirmation form; the GET confirmation pages never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required (`X-API-Key` header). The live calls below were made from Server 1 itself by throwaway scripts that read the key from the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`, the same file the live service loads) and used it in-process only. The key value was never printed, copied, or stored anywhere; the scripts were deleted after the run. Approval **tokens** are likewise never reproduced in this document — requests are identified by `request_id` only. The leg-2 token was held in a file on Server 1 only, for the post-expiry check, and deleted after it. (One handling note: the post-expiry response echoes the token back in its body, so the retrieved post-expiry JSON briefly held it on this VM; it was redacted in the local copy before filing and is not reproduced anywhere in this document.)
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`: `log_file_path = "logs/audit.jsonl"` → on Server 1, `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of `submit_approval` is the API endpoint above; no production code calls `wait_for_decision`. A submitted action is a *request record* only — nothing in the fleet executes an action because its approval record exists.

## Pre-flight checks (before either leg, 2026-11-28 ~13:45 IST)

- Both Oracle servers ONLINE (`get_system_info`).
- `Sentinel.service` active, started 2026-11-28 12:04:56 IST; port 8008 listening (`0.0.0.0:8008`). Note: the service start predates this run by ~1.7 h (it was already running at claim time); the start timestamp 12:04:56 IST is the baseline for the no-restart corroboration below. What restarted it at 12:04 IST was not established in this run; no restart occurred during the legs.
- Sentinel `/health` 200: `audit_chain_valid: true`, `audit_chain_entries: 62`, `kill_switch_active: false`, `audit_durable: true`, version 1.0.0, environment production (observed 2026-11-28T08:15:18Z).
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle), `checks.telegram_channel: true` — the SEN-022 startup self-check gate is live and passing in production. `modules_active: 13`.
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`; no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions with caller MUSE_13 (deployed code on Server 1, no live effect): **4/4 as expected, exit 0** — leg 1 → `AUTO_APPROVE / read_only`, hard_bound False; leg 2 → `OWNER_PROMPT / sentinel_policy_change`, hard_bound True; plus two controls: leg-2 action with a LOW claim → `OWNER_PROMPT / sentinel_policy_change` (hard bound overrides the low claim); leg-1 action with a HIGH claim → `OWNER_PROMPT / caller_risk_not_low`. (Method note: the first dry-run attempt failed with `TypeError: classify_approval() got an unexpected keyword argument 'caller'` — the deployed signature takes `agent_name`, not `caller`. Re-run with `agent_name=` produced the 4/4 above. SEN-043's reference does not record the parameter name; this is the correction for the next run.)
- Pending list empty before the legs (`GET /api/v1/approvals/pending` → `[]`) — no other approval traffic at pre-flight.
- Ledger baseline: `audit_chain_entries: 62` (was 60 at SEN-043 pre-flight, 61 after its leg 1; 2 entries added since — SEN-043 leg 1 at seq 61 plus a `TLS_CERT_ALERT` at seq 62). Seq 61 is SEN-043's leg-1 auto-approval (`appr_87a4cc62e426`); seq 62 is a `TLS_CERT_ALERT`.
- Journal 2 h before the legs shows ONE dispatch-error line: 13:27:14 IST — `Telegram notification dispatch error: <urlopen error _ssl.c:994: The handshake operation timed out>`, followed by `[SENTINEL OPERATIONS ALERT FAILED] ALT-1795852610-3 (resolved_finding on deploy:server-2): channel configured but every transport failed`. This was an **operations alert**, not approval traffic (no approval submission was in flight at 13:27), but it is evidence that Telegram transport from Server 1 hit an SSL handshake timeout ~19 min before the legs. The channel was still configured (`/ready` `telegram_channel: true`) and the failure was transient transport, not config; the legs proceeded and the journal around them shows no dispatch error (see LEG 2). Recorded here as a caveat, not a blocker.
- Transport note: no bridge drops on the pre-flight reads this run.

## Duplicate legs by an unattributed second actor (recorded plainly)

An identical pair of SEN-044 legs was submitted by another actor ~21–23 s BEFORE this run's legs, with the same caller (`MUSE_13`), the same actions, and the same details strings (`{"purpose": "TASK-SEN-044 leg 2 proof, prompt only", "task": "TASK-SEN-044"}`):

- Other leg 1: `appr_058b71d6d986`, ledger seq 63, `APPROVAL_AUTO_APPROVED`, timestamp 2026-11-28T08:16:25.600568+00:00 (13:46:25 IST).
- Other leg 2: `appr_d0a4a083711b`, created 2026-11-28T08:16:27.210146+00:00, expires 2026-11-28T08:21:27.210147+00:00 (13:51:27 IST), PENDING / OWNER_PROMPT / sentinel_policy_change.

This run's legs are distinct requests (own request ids, own ledger seq, own timestamps — see below) and were each submitted exactly once by this run. The hub was re-read through comment 7236489612 (~13:48 IST) and shows NO second SEN-044 claim — the only SEN-044 claim is this run's 7236433092. The other actor is therefore unattributed: possibly a duplicate dispatch of the same task, or another process using caller MUSE_13. Consequence: two identical Telegram prompts went to the owner (one per leg-2 submission), and the pending list held two identical pending requests until both expired. This is a coordination question for Muse; it does not change what this run verified — each behaviour is evidenced by this run's own request ids. This run did NOT approve, deny, or otherwise touch the other actor's pending request.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `list sentinel pending approval requests`
- **Submitted by:** `MUSE_13`, `risk_level: LOW`, details `{"purpose": "TASK-SEN-044 leg 1 proof", "task": "TASK-SEN-044"}`
- **Submitted:** 2026-11-28 13:46:48 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`, `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-28T08:16:48.407787+00:00`, `decided_at 2026-11-28T08:16:48.409457+00:00` (~0.002 s later)
- **Request id:** `appr_6e2dfe94a9ee`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy (TASK-SEN-019): read_only — Read-only action ('list ...') with a LOW caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`, exactly one entry for this request id:
  `seq 64`, `entry_id audit-appr-auto-appr_6e2dfe94a9ee`, `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`, `target MUSE_13`, `action_type "list sentinel pending approval requests"`, `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`, `timestamp 2026-11-28T08:16:48.408060+00:00`, `previous_hash a776bd030fe69a225b061bbf5d6904df9ae28f1759c84d18411e1960977a8329` (chains onto the seq-63 tail entry — verified: seq-63 `current_hash` equals seq-64 `previous_hash`; seq-63 is the other actor's leg-1 entry, seq-62 `current_hash` `423ebd119446800c7eec54dc37d5ea4e8b7081944bd3a4e8d32d27c2fe0cc7b6` equals seq-63 `previous_hash`), `current_hash 281c7fd999b7d2924c0eb4cb80ba59f65e9cdaa75c2e342008f8d6650a95e6cd`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Cross-check:** `/health` audit entry count 62 → 64 after the legs (seq 63 is the other actor's leg 1, seq 64 is this run's leg 1); `audit_chain_valid: true`.

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `change sentinel approval policy threshold in production`
- **Submitted by:** `MUSE_13`, `risk_level: HIGH`, details `{"purpose": "TASK-SEN-044 leg 2 proof, prompt only", "task": "TASK-SEN-044"}`
- **Submitted:** 2026-11-28 13:46:48 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`, `policy_category: sentinel_policy_change`, `decided_at: null`, `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-28T08:16:48.499743+00:00`, `expires_at 2026-11-28T08:21:48.499743+00:00` (13:51:48 IST)
- **Request id:** `appr_bf885811751a`
- **Recorded in the live service:** the request appears in `GET /api/v1/approvals/pending` (HTTP 200) with the same fields — it is held in the running process's pending map awaiting a decision. The pending list contained exactly two items at that check: this run's `appr_bf885811751a` and the other actor's `appr_d0a4a083711b` (same action, same caller, created 21 s earlier).
- **Telegram prompt — what was sent:** `_dispatch_notifications` (`approval_dispatcher.py`) builds this message from the template with the live values and sends it via `_send_telegram` because the channel is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_13`
  > **Action:** `change sentinel approval policy threshold in production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-044 leg 2 proof, prompt only", "task": "TASK-SEN-044"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside `submit_approval`; the code only skips Telegram when the channel is unconfigured (it was configured) and only logs on transport failure.
  - Service journal 13:46 IST onward contains **no** `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback) and **no** `Telegram notification dispatch error` line around either leg-2 submission (13:46:27 and 13:46:49).
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 13:46:48 IST; the synchronous Telegram `urlopen` completed inside that call with no error logged.
  - Caveat: the 13:27 IST SSL handshake timeout on an operations-alert Telegram send (pre-flight) shows the transport can time out transiently; no such failure occurred for either leg-2 prompt.
  - The Telegram `message_id` is **not observable** from this side: `_send_telegram` discards the API response and returns only a boolean, which is not logged on success. Delivery to Surendra's Telegram client is therefore asserted from the configured channel + clean dispatch path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 13 anywhere: no POST to `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction, no `decide()` call. At submission the record showed `decided_at: null`, and the post-expiry check (below) still shows `decided_at: null` — no decision was ever recorded by anyone on this run's request. The other actor's request was likewise not touched by this run.
- The action was never a command: the approval request is a record only (see "No executor on this path"). No deploy command was issued to any host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 13:51:48 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-28 13:52:55 IST (08:22:55 UTC), ~67 s after `expires_at` 13:51:48 IST, token recovered server-side from the Server 1 file (never printed or copied out; file deleted after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as `PENDING`, `decided_at: null`, `decision_reason: null` — no decision was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone from the actionable pending list (count 0; the other actor's request is gone too, its expiry 13:51:27 IST having also passed).
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation page, which never changes state; sent with the `X-API-Key` header) → **HTTP 409** — the page body reads `<h1>Approval no longer pending</h1>` with the agent, action and `Status: PENDING` shown. The approve link is dead.
  - Semantics note: the stored `status` field only transitions when `decide()` or `wait_for_decision()` runs; the live gate is the `is_expired()` check enforced by the approve/deny paths. The 409 proves that gate is closed.
- **Hash-chain linkage verified:** seq-62 `current_hash` equals seq-63 `previous_hash` — True; seq-63 `current_hash` `a776bd030fe69a225b061bbf5d6904df9ae28f1759c84d18411e1960977a8329` equals seq-64 `previous_hash` — True (64 total entries, direct ledger read).
- **No-execution corroboration:** `Sentinel.service` still `active` with the same start timestamp (`Sat 2026-11-28 12:04:56 IST`, Main PID 2493397, NRestarts 0) — no restart; S1 `/opt/friday_universe` git HEAD unchanged at `527b073d` through the run — no deploy; journal 13:46 IST onward contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.
- **Cleanup:** the leg-2 token file and all of this run's throwaway scripts on Server 1 were deleted after this check (`/tmp/sen044_leg2_token`, `/tmp/sen044_pre.sh`, `/tmp/sen044_pre2.sh`, `/tmp/sen044_dry.sh`, `/tmp/sen044_legs.sh`, `/tmp/sen044_mid.sh`, `/tmp/sen044_post.sh` — all gone). Note: `/tmp` on Server 1 still holds files from the other actor (`/tmp/sen044_leg2_id`, `/tmp/sen044_legs.py`, `/tmp/sen044_preflight.py`, `/tmp/sen044_verify1.py`) — not this run's files, left untouched; their cleanup is the other actor's (or the coordinator's) to arrange.

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log or return the Telegram `message_id`, so the exact message id and confirmation that the message rendered on Surendra's device cannot be established from the server side. The prompt's dispatch is evidenced by the configured channel, the synchronous send inside the 200-OK submission, and the absence of any dispatch-error or offline-queue log line. If Muse or Surendra eyeball the Telegram client, the message above should be visible there — twice, once per leg-2 submission (see "Duplicate legs").
- **Ledger re-verification after the legs:** the file ledger entry for leg 1 was verified by hash linkage (seq-62 `current_hash` = seq-63 `previous_hash`; seq-63 `current_hash` = seq-64 `previous_hash`, re-checked by direct file read); a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the legs; after the legs it contained this run's leg-2 request plus the other actor's identical one. Earlier pending history was not audited.
- **What restarted Sentinel at 12:04:56 IST:** the service start predates this run; the initiator of that restart was not established here. The start timestamp is the no-restart baseline for this run only.
- **Identity of the second actor:** the duplicate legs used caller `MUSE_13` with identical details strings and no second hub claim; which process or chat submitted them was not established from the server side.

## Open items — run numbering + duplicate legs (coordinator questions, NOT resolved here)

- **Run numbering:** this task is titled "re-proof run 2", and SEN-042's evidence is also titled "run 2" (`TASK-SEN-042-EVIDENCE.md`); SEN-036's evidence is also titled "run 2". SEN-043 is titled "run 3", and SEN-037's evidence file is also titled "run 3"; SEN-038 merged as "run 4" while SEN-040 is also titled "run 4". No ruling was found in the hub since. This is a record question for the coordinator; the live legs proceeded regardless — the numbering does not change what was run or what was verified. This run is recorded as TASK-SEN-044's live proof, with the collisions stated plainly here.
- **Duplicate legs:** an unattributed second actor submitted the identical SEN-044 leg pair ~21–23 s before this run (see "Duplicate legs by an unattributed second actor"). Two identical Telegram prompts went to the owner. The coordinator should establish whether this was a duplicate dispatch of SEN-044 and, if so, which run's evidence stands as the record; this run's legs are separately identified by request id throughout this document.

## Verdict

**PASS** — both behaviours verified live as specified: one low-risk action auto-approved (leg 1, `appr_6e2dfe94a9ee`, ledger seq 64, hash-chained) and one high-risk action prompting on Telegram (leg 2, `appr_bf885811751a`, PENDING, expired undecided, approve link dead after expiry), each exactly once by this run. No code change was needed — the approval path behaved as specified against the existing deploy. The duplicate legs by an unattributed second actor are recorded as a coordination issue, not a verdict issue: this run's own request ids evidence both behaviours independently.

## Five states

- implemented: YES (this evidence doc filed on branch `muse13/task-sen-044-approval-path-live-proof`)
- tested: YES (both live legs run exactly once by this run against live Sentinel on Server 1, outcomes above)
- merged: NO (work PR open at filing; peer merge owed — never merge own PR)
- deployed: NO (nothing deployed; proof ran against the existing deploy, service unchanged)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 13
