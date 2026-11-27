# TASK-FRD-047 — CHECKPOINT 3 — live leg RELEASED with reasons (2026-11-27 ~06:35 IST)

- **Worker:** Muse 10 (live leg reassigned from Muse TP7 by Burn Enforcer 06:05 §B, hub 7206512535)
- **Task:** TASK-FRD-047 (P2, "FRIDAY: Nod-style one-page pre-call brief from Gmail + Calendar")
- **Claim:** hub #1483 comment NOT POSTED — the hub froze at exactly 2,500 comments during this run (GitHub 403: "Commenting is disabled on issues with more than 2500 comments"). No successor hub exists yet. The claim will be posted on the successor hub when Muse opens it; this checkpoint + work PR carry the claim record meanwhile.
- **Branch:** `muse10/task-frd-047-live-leg` (base main `8de8e3ed`)
- **Code under test:** TP7's branch `musetp7/task-frd-047-pre-call-brief` @ `32a86954` (checkpoint 2)
- **Board:** FRD-047 still CLAIMED/muse_tp7 on main `8de8e3ed` (blob `552c9e04`, 25,020 lines) — leg-only assignment, no board change by this worker

## Verdict: LIVE LEG RELEASED — prerequisites missing, verified first-hand

| Check | Result |
|---|---|
| Calendar feed configured | NO — `ICS_URL_SET` False in the live service env |
| Gmail configured | NO — `MAIL_CONFIGURED` False |
| Events found (today + tomorrow) | 0 |
| `maybe_deliver_pre_call_brief` | `None` — no brief composed, by the module's own design (no feed → no event → no brief) |
| News source (Google News RSS) | ERROR — HTTP 429 at probe time (transient) |
| FRIDAY.service (Server 1) | inactive (dead); unit absent on Server 2 |
| Public ingress `/friday/health` | 502 |

## What was run (first-hand, read-only)

- Scratch worktree `/tmp/frd047-leg` of TP7's branch @ `32a86954` on Oracle Server 1; probe ran with the service venv (`/opt/friday_universe/venv/bin/python`, the `ExecStart` interpreter) and the live service env (`FRIDAY/.env` loaded via dotenv). No deploy, no service restart, no mutation; `notifications=None`, so nothing was pushed anywhere.
- Probe output (booleans/counts only): `MAIL_CONFIGURED: False`, `ICS_URL_SET: False`, `ICS_TEXT_IS_NONE: True`, `EVENTS: 0`, `MAYBE_DELIVER: None`, `NEWS_ERROR: True` (Google News RSS 429).
- Config search, exhaustive over the live service's config chain: `FRIDAY/.env` (Server 1), `/etc/friday/dispatch.env` (dispatch bus credentials only), project-root `.env` (Telegram + Alpaca only), service `Environment=` lines (`PORT` only), Server 2 root `.env` (Telegram only). No `FRIDAY_CALENDAR_ICS_URL` / `CALENDAR_ICS_URL` / `calendar_ics_url` and no `FRIDAY_EMAIL_ADDRESS` / `FRIDAY_EMAIL_APP_PASSWORD` (or aliases) anywhere in it.
- Codebase grep confirms those are the only sources: `calendar.py:97`, `gmail_tools.py:77-78,290-291`, `config.py:109-111,367-377`. The morning brief uses the same feed variable (`morning_brief.py:157`), so it has the same gap.
- Grant / stop order: clearance 7200564540 stands; coordinator clarification 7200651240 settles the stop order (it froze moving agents between servers only, never live verification). Neither blocks the leg — the block is missing prerequisites, not permission.

## Release reasons — what must change to re-arm the leg

1. Owner supplies a calendar ICS URL (`FRIDAY_CALENDAR_ICS_URL`) in the service env.
2. Owner supplies Gmail address + app password (`FRIDAY_EMAIL_ADDRESS` / `FRIDAY_EMAIL_APP_PASSWORD`).
3. FRIDAY.service restored — currently dead; public ingress 502. Restart is a coordinator/owner call (FRD-052 OOM-kill investigation is already drafted to the pool; the service was OOM-killed twice more under chat turns per M17).
4. News 429 was transient at probe time; re-probe when the leg re-runs.

## Notes

- TP7's claim question stands: does the FRD-047 claim transfer with the leg, or stay with TP7 (TP7's ask, hub 7206560851)? TP7's rebase + work PR remain owed either way.
- No board hunk in this PR (coordinator-only flips, ruling 7200564540).
- Work-request job `muse10-work-request` removed on this claim (06:13 run); it will need recreating when Muse 10 is free again.
- Scratch worktree `/tmp/frd047-leg` + probe script removed from Server 1 after the run; the shared checkout was never switched (Server 1 still main `bf3c76c9`; Server 2 still on its stale branch, pre-existing).

— Muse 10
