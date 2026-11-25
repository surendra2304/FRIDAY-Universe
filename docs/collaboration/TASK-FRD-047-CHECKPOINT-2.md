# TASK-FRD-047 — CHECKPOINT 2 — implementation + tests (2026-11-26 ~01:30 IST)

- **Worker:** Muse TP7
- **Task:** TASK-FRD-047 (P2, "FRIDAY: Nod-style one-page pre-call brief from Gmail + Calendar")
- **Claim:** hub #1483 comment 7169685491, 2026-11-25 ~23:05 IST
- **Branch:** `musetp7/task-frd-047-pre-call-brief`
- **Base:** `fb086e16` (unchanged — no rebase this run; see rebase debt below)
- **Board:** FRD-047 now **CLAIMED / owner muse_tp7** on main `70ce1089` (flip landed; was AVAILABLE at checkpoint 1)

## Verdict: IMPLEMENTATION DONE, repo-side verified — work PR next

| Leg | Status | One line |
|---|---|---|
| Repo survey + design | DONE | Checkpoint 1 |
| Implementation (`pre_call_brief.py` + tests) | DONE | This run, commit `0647cc65`, remote `bce35c3f` |
| Verification (pytest slice + ruff) | DONE | 42 passed, ruff clean (see below) |
| Work PR (board hunk, true branch name) | NOT STARTED | Next step |
| Live leg (real Gmail/Calendar, FRIDAY-Server) | HELD | Owner stop order stands; no live clearance |

## What was implemented (commit 0647cc65, remote bce35c3f)

- **New `FRIDAY/src/friday/proactive/pre_call_brief.py`** (~330 lines), mirroring `morning_brief.py`:
  - `compose_pre_call_brief(event)` — pure composition, never raises: call line (title/time/location/attendees) + recent Gmail threads with the attendees + the client's latest news + an honest "could not check" line per failing source. Hard-capped at 1800 chars (one page).
  - `maybe_deliver_pre_call_brief(notifications)` — finds the next call starting inside a 30-minute lead window (today + tomorrow's feed), dedupes once per call (event title + start), pushes as a `pre_call_brief` notification.
  - Gmail is attendee-scoped: one IMAP TEXT search per attendee (max 2), subjects only. Unconfigured mailbox omits the section — the tool is never called unconfigured, because its unconfigured path opens the Gmail web UI and its IMAP-failure path opens a browser tab; neither belongs in a greeting hook.
  - News is keyword-filtered: `get_news` is category-only, so business + general headlines are filtered against attendee names + significant title words. No match says so honestly; unrelated headlines are never passed off as the client's news.
  - Read-only by construction: the brief never sends, pays, or deletes; follow-ups go through FRIDAY's existing confirmation flow.
- **`FRIDAY/src/friday/tools/builtin/calendar.py`** — `_parse_ics_content` gains additive `attendees` (ICS `ATTENDEE` CN or mailbox local-part), `start_dt`, `end_dt` keys. `GetTodaysEventsTool` output is unchanged (the keys are ignored by its formatter).
- **Greeting hooks** — `FRIDAY/src/friday/agent/mixins/cognitive.py` and `FRIDAY/src/friday/api/server.py`, mirroring the morning-brief wiring exactly (guarded try/except, never breaks a greeting).
- **Decisions on checkpoint 1's open questions** (for Muse to correct if wrong): (1) news = keyword filtering over returned headlines — accepted; (2) attendees = `ATTENDEE` added to `_parse_ics_content`; (3) delivery = notification push (morning-brief style), 30-minute lead window.

## Verification (first-hand this run)

- Test venv built at `/home/hatch/friday-test-venv` (`pip install -e ".[dev]"` + `requirements.txt`; first attempt failed on /tmp tmpfs space — rebuilt on /home).
- `pytest tests/test_pre_call_brief.py tests/test_morning_brief.py tests/test_calendar_briefing_phase29.py tests/test_ig_frd_009_life_calendar.py -q -m "not live and not hardware and not windows"` → **42 passed** (17 new pre-call tests + morning-brief + calendar regressions).
- `ruff check` on all five touched files → clean. `py_compile` → clean.
- New tests are repo-side only: file:// ICS feed with a dated call + ATTENDEE, fakes for Gmail/news; no credentials, no network.

## Known limitations (honest, not hidden)

- **Pre-05:30 IST calls may be missed on a UTC host.** `_parse_ics_content` builds its day window in system-local time while the "day" is the owner's IST date — a pre-existing gap in the shared parser (the morning brief's calendar line has the same gap). Today + tomorrow parsing covers 05:30 IST onward. Fixing the parser's window is a shared-behaviour change — left for a Muse ruling, not smuggled into this task.
- **Rebase debt:** branch base `fb086e16`; main is now `70ce1089`, 28 commits behind. No rebase this run — it would rewrite the cited checkpoint-1 commit `008d922a`, and the API push helper is fast-forward only. Rebase (or a stale-base work PR) is owed at work-PR time; flagging to Muse.
- **Live leg HELD** — owner stop order / fleet CD broken; no live move until Muse clears it.

## Run context (01:01 IST self-check)

- Claim stands: no competing FRD-047 claim in hub comments through #1617 (WATCH113/114 read first-hand). WATCH114 carries the FRD-052 close ruling as still owed (since 17:18 IST) — holding, no FRD-052 work PR beyond merged #1867.
- Schedules verified: `musetp7-hourly-self-check` enabled (1h), `musetp7-weekly-reset` enabled (Wed 17:11 IST); `musetp7-work-request` absent — correct mid-task, NOT re-created.
- Usage: 3% of free weekly limit, reset Wed Dec 2, 17:01 IST (verified via subscription-status this run; was 2%).

## Next steps

1. Work PR with the board hunk using the true branch name `musetp7/task-frd-047-pre-call-brief` (WATCH110 instruction); rebase-or-stale-base decision owed from Muse.
2. Live leg only after Muse clears it — owner stop order still in force.
