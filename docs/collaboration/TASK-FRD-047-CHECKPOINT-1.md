# TASK-FRD-047 — CHECKPOINT 1 — repo survey + design (2026-11-26 ~00:10 IST)

- **Worker:** Muse TP7
- **Task:** TASK-FRD-047 (P2, "FRIDAY: Nod-style one-page pre-call brief from Gmail + Calendar")
- **Claim:** hub #1483 comment 7169685491, 2026-11-25 ~23:05 IST
- **Branch:** `musetp7/task-frd-047-pre-call-brief` (true name; WATCH110 noted the claim post carried a masked short name — the work-PR board hunk must use this true name)
- **Base:** rebased this run from `2f77de04` to main `fb086e16` (PR #1873 merged, VYR-084); 0 own commits before this checkpoint
- **Board:** FRD-047 still AVAILABLE / owner muse_tp7 on main `fb086e16`; CLAIMED flip is in coordinator board PR #1878 (WATCH110/111/112, CI pending, merge owed on green)

## Verdict: SURVEY + DESIGN DONE — implementation not started

| Leg | Status | One line |
|---|---|---|
| Repo survey (Gmail + Calendar + brief patterns) | DONE | All reusable pieces located first-hand; no pre-call code exists |
| Design (module, trigger, dedupe, safety) | DONE | Follows the `morning_brief.py` pattern; see below |
| Implementation (`pre_call_brief.py` + tests) | NOT STARTED | Next work run |
| Live leg (real Gmail/Calendar, FRIDAY-Server) | HELD | Owner stop order stands; no live clearance — repo-side first |

## Acceptance (board, TASK-FRD-047)

- Before each calendar call, FRIDAY reads Gmail + Calendar + the client's latest news and writes a one-page brief, unprompted.
- The brief flow keeps FRIDAY's existing pattern: she asks before send/pay/delete actions.

## Survey — first-hand this run (main `fb086e16`)

- **No pre-call brief code exists.** `grep -ri "pre.call\|pre_call"` across `FRIDAY/src` and `FRIDAY/tests`: zero hits.
- `FRIDAY/src/friday/proactive/morning_brief.py` (300 lines) — the pattern to follow: compose from real data, every failing probe contributes an honest "could not check" line (never a fabricated "all good"), once-per-window dedupe (`_last_morning_date`), push via `notifications.post_notification(..., category="morning_brief")`. Hooked from `FRIDAY/src/friday/agent/mixins/cognitive.py:188` and `FRIDAY/src/friday/api/server.py:4590` — the same two hook points are the pre-call trigger candidates.
- `FRIDAY/src/friday/tools/builtin/calendar.py` — `GetTodaysEventsTool` (ICS feed, `FRIDAY_CALENDAR_ICS_URL`); `_parse_ics_content(ics, target_date)` returns title/start/end/location per event. Gap: it lists *today only* — a pre-call brief needs the *next* event in a lookahead window, and the parser drops the ICS `ATTENDEE` field, so attendee identity is not currently available.
- `FRIDAY/src/friday/tools/builtin/gmail_tools.py` — `ReadGmailInboxTool` (IMAP, `query` TEXT search, max 20, 160-char snippets); `triage_inbox` in `FRIDAY/src/friday/proactive/agentic_inbox.py` gives unread counts by category + most urgent subject (already used by the morning brief). Gap: no attendee-scoped thread lookup — the `query` TEXT search against the attendee name/company is the available path.
- `FRIDAY/src/friday/tools/builtin/news.py` — `NewsTool` (`get_news`, category-based headlines, limit ≤ 10). Gap: category enum only, no free-text query — matching "the client's latest news" needs design (category + keyword filter over returned headlines, or a query-capable path).
- `FRIDAY/src/friday/tools/builtin/life_calendar.py` — IG-FRD-009 (verified live in FRD-052); unrelated to this task, no reuse.

## Design

- New module `FRIDAY/src/friday/proactive/pre_call_brief.py`, mirroring `morning_brief.py`: `compose_pre_call_brief(event)` (pure composition, never raises) + `maybe_deliver_pre_call_brief(notifications)` (once per event, dedupe by event start + title; fires inside a lead window before the call, e.g. 30 min).
- Sections (one page = bounded length, cap lines/chars): the call (title/time/location/attendees); recent Gmail threads with the attendees (via `query` search + triage counts); the client's latest news (via `get_news`, filtered); honest "could not check" line per failing source; nothing invented.
- Safety: composition is read-only; the brief itself never sends, pays, or deletes. Any follow-up action goes through FRIDAY's existing confirmation flow — the acceptance line is preserved by construction.
- Tests (repo-side, no credentials): `file://` ICS feed with a dated call + stubbed inbox/news fakes; assert the brief names the call, cites real thread subjects, caps length, dedupes per event, and degrades honestly when a source fails.

## Open questions (for Muse / next work run)

1. News matching: `get_news` is category-only — is keyword filtering over returned headlines acceptable, or is a query-capable news path required?
2. Attendee parsing: add `ATTENDEE` to `_parse_ics_content`, or derive attendees from the event title/description only?
3. Delivery surface: notification push (morning-brief style, spoken on next greeting) or also a direct pre-call push — and what lead window (30 min proposed)?

## Next steps

1. Implement `pre_call_brief.py` + tests on this branch; run the FRIDAY pytest slice.
2. Work PR with the board hunk using the true branch name `musetp7/task-frd-047-pre-call-brief` (WATCH110 instruction).
3. Live leg only after Muse clears it — owner stop order still in force (fleet CD broken, deploy clearances blocked).

## Run context (00:01 IST self-check)

- Claim stands: no competing FRD-047 claim in hub comments through #1597 (WATCH110/111/112 read first-hand). No FRD-052 close ruling yet in WATCH110–112 — the PARTIAL verdict (checkpoint 2, hub 7161531036) is still owed from Muse; holding, no FRD-052 work PR beyond merged #1867.
- Schedules verified: `musetp7-hourly-self-check` enabled (1h), `musetp7-weekly-reset` enabled (Wed 17:11 IST); `musetp7-work-request` absent — correct mid-task, NOT re-created.
- Usage: 2% of free weekly limit, reset Wed Dec 2, 17:01 IST (verified via subscription-status this run).
