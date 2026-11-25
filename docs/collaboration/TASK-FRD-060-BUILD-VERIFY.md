# TASK-FRD-060 — BUILD VERIFY: Daily Signal Brief template adoption

**Task:** FRIDAY: Daily Signal Brief template adoption — the recovered Slack signal-brief format as FRIDAY's on-demand brief.
**Source:** friday package F-40 (item DfHw7hsIfvd, PARTIAL — the template's closing segment was not recovered). **Priority:** P3. **Worker:** Muse TP9.
**Claim:** hub #1483 comment 7164542656 (2026-11-25 ~19:52 IST, pre-staged). **Branch:** `musetp9/task-frd-060`.
**Merge-base:** main `3b8c03075464ddfb7fe7478a6d832e4217b7170b`.

## Five states

| State | Value | Evidence |
|---|---|---|
| Implemented | YES | Workflow + tool + API route, all on branch (see below) |
| Tested | PARTIAL | 11 hermetic tests written, collected in FRIDAY tier-1 (REL-068); CI verdict pending on this PR |
| Merged | NO | PR open, awaiting peer merge |
| Deployed | NO | Needs merge + deploy to FRIDAY-Server |
| Production-verified | NO | Done = one brief generated on demand from live IntelX data in the adopted format |

## What the source actually is (honest sourcing)

The F-40 template's full text was **not** recoverable from any first-hand
source. I searched: the repo code search (`"Daily Slack Signal Brief"`,
`"Signal Brief" template`, `signal-brief template` — 0 hits), all 1,498
hub #1483 comments (no mention beyond this task's own claim), and the
board file (only the one-line record below). What survives first-hand:

- **Board record (TASK-FRD-060 acceptance):** "a fixed-format 'Daily Slack Signal Brief' template, recorded as a cross-check against the fleet's brief format and never adopted" — PARTIAL, closing segment not recovered.
- **The same shortcode in Forge** (`Forge/app/templates/ig_templates.py`, `ONE_PROMPT_AGENT`, `source_shortcodes=("DfHw7hsIfvd",)`): the video is about one-prompt agent creation — a plain-language prompt becomes a configured, working agent. The video's agent is evidently the brief agent itself: one prompt, one brief. The Forge record captures the agent shape; the FRIDAY re-audit captured the brief shape. Both cite the same video.

So the comparison below is against F-40 **as recorded** (fixed-format daily signal brief, Slack-posted, signals with source/score) plus FRIDAY's current brief formats, read first-hand. Nothing here claims a section came from F-40's text when it did not.

## FRIDAY's current brief formats (read first-hand)

1. **Predictive briefing** (`FRIDAY/src/friday/workflows/predictive_briefing.py`): sections — Tomorrow's Multi-System Outlook / 48-Hour Probability-Weighted Risk Horizon (table) / Forecasted Opportunity Signals (table) / Predictive Calibration & Reliability Audit + spoken summary. Strong structure, **weak data**: the risk/opportunity rows and the weekly review numbers are hardcoded literals, not live data.
2. **IntelX research brief** (`FRIDAY/src/friday/tools/builtin/intelx_research.py`, `_format_brief`): Bottom line (spoken summary) / body text / Evidence (citation count) / Sources (up to 8, URL-checked). Live data, no fixed sections.
3. **Daily self-report** (`FRIDAY/src/friday/proactive/daily_self_report.py`): ops lines — conversations, dispatches, fleet reachability, missions, memory growth. Not an intel brief.

## Section-by-section comparison → adopted structure

| Section | F-40 (as recorded) | FRIDAY current | Adopted (stronger of the two) |
|---|---|---|---|
| Header / identity | Fixed "Daily Slack Signal Brief" title + date | Predictive: "# 🔮 FRIDAY Daily Predictive Intelligence Briefing — <date>" + grounding quote | "# 📡 Daily Signal Brief — <date> IST" + coverage line naming the source, window, and on-demand nature |
| Bottom line | The brief's lead is its top signal | Predictive spoken summary (natural cadence, but hardcoded content); intelx_research "Bottom line: <spoken>" (live) | Bottom line, one paragraph: count + top signal + watch — from intelx_research's live rule |
| Signals list | The signals, fixed format | Predictive risk/opportunity tables (strong structure, hardcoded rows); intelx_research flat text + sources (live, unstructured) | "Top signals" table — # / Signal / Watch / Score / Source — every row from a real IntelX envelope, plus a Signal details list with each summary |
| Watch coverage | Not recovered | None (weekly review has a per-system breakdown, hardcoded) | "Watch coverage": distinct watches that fired, with counts; honest note that a watch that did not fire leaves no trace in the outbox |
| Calibration / reliability | Not recovered | Predictive calibration audit (Brier score, most/least reliable domain — hardcoded values) | "What this brief does not cover": scores are IntelX significance scores, not probabilities; only standing-watch envelopes in the window; no Futuris forecasts, no research queries. Honest limits instead of invented calibration numbers |
| Closing | **NOT RECOVERED (PARTIAL)** | Predictive ends with the calibration list; intelx_research ends with Sources | Closes with Sources (every signal's URL) + generation footer (on-demand time, source files). Marked explicitly as FRIDAY's own closing, not F-40's |
| Delivery | Posted to Slack daily (routine) | Owner removed routine briefings 2026-11-23 | **On-demand only**: tool + API route, no cron, no routine schedule |

## What was built

- **Workflow `FRIDAY/src/friday/workflows/signal_brief.py`** — `read_recent_signals` (reads the main + instant outboxes via the drainer's own resolvers, same env names/defaults; dedupe by `dedupe_key`; `fired_at` window filter, default 24h; malformed lines skipped + counted; missing outbox = honest empty), `render_brief` (the adopted format above; every figure from the envelopes), `generate_brief` (saves markdown under `FRIDAY/.data/signal_briefs/<YYYY-MM-DD>.md`). Read-only: never sends, never enables a watch.
- **Tool `FRIDAY/src/friday/tools/builtin/signal_brief_tools.py`** — `generate_signal_brief` (SAFE), registered in `friday/tools/builtin/__init__.py`.
- **API route in `FRIDAY/src/friday/api/server.py`** — POST `/api/signal-brief` (control-gated; `SignalBriefRequest` with optional `hours`).
- **Tests `FRIDAY/tests/test_ig_frd_060_signal_brief.py`** — 11 hermetic tests (window filter, dedupe + score sort, instant merge, malformed/wrong-schema skip, missing outboxes, render facts-only, honest empty, save, tool with/without signals). Collected in FRIDAY tier-1 (REL-068).
- **Data contract (verified first-hand):** envelope schema `intelx.watch_alert/1` (`IntelX/intelx/watches/engine.py:build_envelope` + `IntelX/intelx/watches/outbox_shipper.py`): `schema`, `envelope_id`, `dedupe_key`, `watch_id`, `domain`, `alert_class` (digest|instant), `severity`, `quiet_hours_exempt`, `title`, `summary` (≤300 chars), `url`, `publisher`, `published_at`, `fired_at`, `score`, `score_reasons`, `provenance`.

## What is NOT done (Done blockers)

Done = **one brief generated on demand from live IntelX data in the adopted format**. That needs: (1) this PR merged, (2) deploy to FRIDAY-Server, (3) one live generation — the tool or `POST /api/signal-brief` run on production with the real outbox present (or an honest empty brief if no watch fired in the window — that is also a real result, not a failure). No deploy has happened; nothing here claims otherwise.

## Verification notes

- Code diagnosed by READING only (execution-risk restriction on the local clone: no git/package commands, no running repo code). PR CI is the test runner.
- The roster validator will fail on this PR until roster PR #1843 merges (board owner `muse_tp9` not yet a registered collaborator) — expected sequencing, same as PRs #1848/#1849/#1850.
- No new cron, no routine schedule, no Slack posting path was added — the constraint is enforced by construction (there is no scheduler hook anywhere in this PR).
