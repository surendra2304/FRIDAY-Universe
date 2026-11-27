# TASK-SEN-038 — Checkpoint 2 (SEN-036 precedent read; probe + legs pending coordination)

- Worker: Muse TP10
- Filed: 2026-11-27 ~09:23 IST, hourly self-check run
- Branch: `musetp10/task-sen-038` (checkpoint 1 `1dbc72f0` @ base main `5fd32fdf`; main now `091bc349`, branch ahead 1 / behind 10, docs-only, no PR yet)
- Board (main blob `f572e413`): TASK-SEN-038 CLAIMED / muse_tp10 / branch null / pr null (branch flip rides in coordinator board PR #2060, open, CI green). Queue: SEN-038 head → VOI-045 (AVAILABLE/muse_tp10). Claim post: hub #2045 comment 7208545276.

## Precedent read (this run, first-hand)

`docs/collaboration/TASK-SEN-036-APPROVAL-PATH-LIVE-PROOF-RUN-2.md` on main (blob `b798343b`, 12,816 bytes) — run 2 by Muse 10, 2026-11-26. SEN-038 (run 4) repeats this procedure against the current deploy. Approval-path source paths verified present on current main: `Sentinel/sentinel/gatekeeper/approval_policy.py` (blob `8c55456c`), `Sentinel/sentinel/gatekeeper/approval_dispatcher.py` (blob `2d8f81ea`), `Sentinel/sentinel/apps/api/main.py` (blob `97f4eddd`). Live byte-identity vs Server 1 is re-verified in the probe step (run 2 recorded md5s: approval_policy `87ca1ed1…`, approval_dispatcher `92468726…`, main.py `b5d932ae…`, middleware `ceffdcf2…` at its branch HEAD `6250d1f2`).

How the path works (per precedent):
- Classifier `approval_policy.py::classify_approval` → `AUTO_APPROVE` only when caller risk claim is low, no hard-bound pattern, and the action positively matches the low-risk class; otherwise `OWNER_PROMPT` (fail-closed, never downgrades a claim).
- Dispatcher `approval_dispatcher.py::submit_approval` → auto-approve writes `APPROVAL_AUTO_APPROVED` to the audit ledger first; owner prompt sends Telegram via `_send_telegram` and records PENDING with approve/deny links.
- HTTP entry: `POST /api/v1/approvals/request` (plus `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{token}/status`); auth: `X-API-Key` header, 32+ char `SENTINEL_API_KEY` (approvals endpoints not exempt). Live service: Sentinel on Oracle Server 1, port 8008, `Sentinel.service`.
- Audit ledger: `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- No executor on this path: a submitted action is a request record only; nothing executes because its approval record exists.

Exact leg actions from the precedent (to be confirmed by Muse on hub #2045 before either leg runs — not invented here):
- Leg 1 (low-risk): action `check sentinel health status`, `risk_level: LOW` → run 2 result: APPROVED, `AUTO_APPROVE / read_only`, one ledger entry, `/health` count +1.
- Leg 2 (high-risk, prompt only): action `deploy sentinel configuration change to production`, `risk_level: HIGH` → run 2 result: PENDING, `OWNER_PROMPT / caller_risk_not_low`, Telegram prompt dispatched, expires in 5 minutes, no decision, no execution; post-expiry approve GET → HTTP 409.

Pre-flight (per precedent): both Oracle servers ONLINE; Sentinel `/health` 200 (`audit_chain_valid: true`, `kill_switch_active: false`); `/ready` 200 (`telegram_channel: true`); classifier dry-run on the exact planned actions; pending list empty. Key handling per precedent: read from Server 1 systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`) in-process only, never printed/copied/stored; approval tokens never reproduced (request_id only); throwaway scripts deleted after the run.

## Status / next

- Step 1 of checkpoint 1 plan (precedent read) DONE this run. Steps 2–4 (read-only bridge probe of live Sentinel on Server 1, then the two action legs, each exactly once) are HELD pending Muse confirmation of the exact leg actions on hub #2045 — server-touching steps are serialized through Muse and the Telegram leg prompts the owner, so neither leg fires without that confirmation. Coordination/blocked post filed this run (see hub).
- Exactly-once discipline: no retries that could double-prompt; if a leg errors ambiguously, stop and report on #2045, do not re-fire.
- Completion route unchanged: file `docs/collaboration/TASK-SEN-038-EVIDENCE.md` with both outcomes; one work PR; paired verification by a different chat; never merge own PR.

## Five states

- implemented: NO
- tested: NO
- merged: NO
- deployed: NO
- production-verified: NO

No live evidence yet — nothing above is a result claim. Usage: 11% of free weekly limit (resets Dec 2 6:34 PM IST).

— Muse TP10
