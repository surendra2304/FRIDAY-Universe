# TASK-IG2-FRD-01-ACTIVATE-01 — live recon: mailbox credentials absent, owner-gated

- **Task:** TASK-IG2-FRD-01-ACTIVATE-01 — "activate the IG2-FRD-01 mailbox and re-probe triage + drafts live"
- **Claimed:** 2026-11-28 ~06:00 IST (hub #2045, comment 7230963708), per WATCH246 correction §2 / BE 05:35 §C (FRD-068 deploy first — done).
- **Branch:** `muse13/task-ig2-frd-01-activate-01` @ `fac8c0eb27a5` (verified on origin; no PR yet — recon only).
- **Board:** CLAIMED/muse_13 on live main `98215372` (blob `cbc16f50`, 504 tasks, 0 dups; updated 06:42:00 IST via board PR #2234).
- **Acceptance:** mailbox credentials (`FRIDAY_EMAIL_ADDRESS` / `FRIDAY_EMAIL_APP_PASSWORD`) in FRIDAY `.env` on FRIDAY-Server via the credentials-file flow (never pasted in chat or the repo); `triage_inbox` + `inbox_drafts` re-probed live with real results filed.

## Recon 1 — credential presence in the FRIDAY .env (bridge run_shell, server 3, read-only)

- FRIDAY service `WorkingDirectory=/opt/friday_universe/FRIDAY`; two `.env` files exist:
  - `/opt/friday_universe/FRIDAY/.env` (4,625 bytes, Nov 24 07:17) — the service's env file.
  - `/opt/friday_universe/.env` (517 bytes, Nov 17 12:20).
- Presence counts only (no values ever printed or read):
  - `FRIDAY_EMAIL_ADDRESS` lines: **0** in both files.
  - `FRIDAY_EMAIL_APP_PASSWORD` lines: **0** in both files.
  - Any `*EMAIL*` key names: **none** in either file (aliases `EMAIL_ADDRESS` / `EMAIL_APP_PASSWORD` from `config.py:110-111` also absent).

## Recon 2 — what the code does when unset (repo, main base f15516b0)

- `FRIDAY/src/friday/proactive/agentic_inbox.py:205` — returns `[], "not_configured: FRIDAY_EMAIL_ADDRESS / FRIDAY_EMAIL_APP_PASSWORD are unset"`.
- `FRIDAY/src/friday/tools/builtin/agentic_inbox_tools.py:105` — inbox_drafts: "No mailbox is configured (FRIDAY_EMAIL_ADDRESS unset), so there is no draft queue."
- `FRIDAY/src/friday/tools/builtin/gmail_tools.py:96` — "No mail was read: FRIDAY_EMAIL_ADDRESS and FRIDAY_EMAIL_APP_PASSWORD are not [set]..."

## Recon 3 — live loopback re-probe (bridge run_shell, server 3; `POST http://127.0.0.1:10000/api/chat`, no credential)

- **Turn 1** — 01:13:04–01:13:57 UTC (06:43–06:44 IST). HTTP 200, 77.2 s wall, `task_state` COMPLETED, gemini-3.6-flash, routed `DIRECT_REASONING`, 1 iteration. Reply verbatim: "Sure thing, Boss. Right now I don't have access to your inbox data, so I can't pull the latest messages or any pending drafts. If you'd like, we can try again later or adjust the permissions so I can retrieve that information for you. Just let me know how you'd like to proceed!" `proactive_notice`: memory 99.0% of the 200 MB service limit (197.9 MB used).
- **Turn 2** — ~01:15 UTC (06:45 IST). HTTP 200, 76.7 s wall, `task_state` COMPLETED, routed `DIRECT_REASONING`. Asked explicitly to run `triage_inbox` then `inbox_drafts` and report exactly what each returned. Reply verbatim: "I'm sorry, Boss, but I can't run the `triage_inbox` or `inbox_drafts` tools at the moment, so I'm unable to fetch your mailbox status or any draft messages right now. Let me know if you'd like to try again later or adjust anything else!"
- Service state at probe time: FRIDAY.service active, MainPID 129597, NRestarts 3 — OOM kills continue (FRD-064, TP1's task); the brain did not dispatch to either inbox tool in either turn.

## Verdict

**BLOCKED — owner-gated.** The mailbox credentials are not in the FRIDAY `.env` on FRIDAY-Server, in either file or under any alias, and the live brain confirms it has no inbox access (two loopback turns, both COMPLETED, neither dispatched to the inbox tools). No credentials were requested, pasted, or read anywhere in chat or the repo. The credential leg needs the owner to place `FRIDAY_EMAIL_ADDRESS` / `FRIDAY_EMAIL_APP_PASSWORD` in the FRIDAY `.env` via the credentials-file flow; the triage + drafts live re-probe runs immediately after they land. Task stays CLAIMED/muse_13 pending the credential leg or the coordinator's re-slot; the next queue item (IG2-FRD-02-ACTIVATE-01) is likewise owner-gated (gateway unconfigured).

— Muse 13
