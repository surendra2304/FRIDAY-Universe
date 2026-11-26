# TASK-VYR-082 — VyralX layered marketing architecture

**Task:** TASK-VYR-082 — VyralX: layered marketing architecture, the
seven-layer growth system on top of `channel_operator` (P2).
**Branch:** `muse2/task-vyr-082-layered-marketing`
**Claimed:** 2026-11-26 ~04:45 IST (hub #1483 comment 7177250025) per
WATCH122 assignment (hub 7176443876) and the WATCH123 nudge (hub
7176656559). TP11 re-slotted after ~4h zero activity; TP11 claimed
REL-100 instead.
**Status:** implemented YES / tested YES (repo CI) / merged NO /
deployed NO / production-verified NO.

## Source

Board record, vyralx package V-03 (item DeihbtONYtH) — the layered AI
marketing-team reference architecture, frame-verbatim: Layer 01
SIGNALS (competitor ads, comments & DMs, website visitors, lead
forms, reviews & mentions, sales calls); Layer 02 SYSTEM OF RECORD
(customers & deals, ad accounts, content calendar, asset library);
Layer 03 THE BRAIN / Growth Director; Layer 05 DEPARTMENTS (market
intelligence, paid ads, content studio, publishing, lead capture,
sales response, nurture & retargeting, reputation); Layer 06 DATA &
OBSERVABILITY (cost per lead, speed to lead, booked & paid, ad to
customer, agent activity log); Layer 07 HUMAN HANDOFF (approvals) —
with per-domain databases (ads.db / leads.db / sales.db pattern).
Richer than VyralX's implemented `channel_operator`; left
reference-only until now.

## What was built

New module `VyralX/app/services/layered_marketing.py` (704 lines) +
28 tests in `VyralX/tests/test_vyr082_layered_marketing.py` +
this doc. One function per layer, all pure over plain dicts,
deterministic, no network, no clock except caller-supplied
timestamps. The weekly cycle `run_weekly_cycle(week_input, start,
now=...)` runs signals → record → Brain → departments →
observability → handoff and returns a `layered_marketing_plan` with
`status="pending_review"`, `requires_approval=True`,
`publishes_anything=False`. Test file registered in the VyralX tier-1
list in `.github/workflows/friday-universe-ci.yml` (REL-068 guard).

### Layer mapping

| Source layer | Built as | Evidence |
|---|---|---|
| 01 SIGNALS | `collect_signals` — validates competitor-ad records one by one via `competitor_ads.normalise_ad`; invalid records listed with the reason, never silently dropped; the three kinds with no VyralX source (website visitors, lead forms, sales calls) reported `available=False` with the reason | `test_signals_collects_supplied_kinds`, `test_signals_missing_kinds_reported_not_synthesised`, `test_signals_invalid_ad_record_listed_not_dropped` |
| 02 SYSTEM OF RECORD | `build_system_of_record` — assembles caller-supplied content calendar + asset library; customers & deals and ad accounts always unavailable; per-domain ads/leads/sales with row counts; plain-dict snapshot, no sidecar SQLite files (VyralX persists through `database.py` / Oracle) | `test_record_assembles_supplied_stores`, `test_record_domains_ads_leads_sales` |
| 03 THE BRAIN / Growth Director | `growth_director_decide` — winners and lane priorities from measured views only (`channel_operator.analyse_channel`); no metrics means no winner is named and the gap is listed; next topics capped at the 3 weekly slots, ordered by lane priority; bad candidates skipped with reasons; recommendations are continue / review / explore — stopping anything is never recommended | `test_brain_picks_winners_from_measured_views`, `test_brain_no_metrics_names_no_winner`, `test_brain_next_topics_capped_to_slots_and_ordered`, `test_brain_skips_bad_topics_with_reasons`, `test_brain_recommendations_continue_review_explore` |
| 05 DEPARTMENTS | `run_departments` — the four that map to VyralX: content studio (`operator.propose_packaging`, one proposal per chosen topic), publishing (`operator.build_schedule` + a distribution plan that is planned, never executed), market intelligence (`competitor_ads.pattern_brief` on validated records + `trends.rank_candidates` as a watch list), reputation (`operator.draft_comment_replies`, drafts only) | `test_studio_proposals_gated`, `test_publishing_schedule_is_plan_only`, `test_market_intelligence_brief_from_records`, `test_market_intelligence_no_records_no_brief`, `test_reputation_drafts_post_nothing`, `test_unmapped_departments_listed_with_reasons` |
| 06 DATA & OBSERVABILITY | `observe_layer_kpis` — the four funnel KPIs reported unavailable with the reason, never estimated; the agent activity log is the one measurable source KPI (one entry per layer step, counted per layer); channel-native KPIs (proposals, schedule entries, drafts, brief) alongside | `test_source_kpis_unmeasured_never_estimated`, `test_activity_log_one_entry_per_layer_step`, `test_channel_kpis_match_cycle_counts` |
| 07 HUMAN HANDOFF | `human_handoff` + `enqueue_growth_plan` — the owner's unlisted review-first gate, unchanged; the plan enqueues into the VYR-004 review queue as `pending_review` via `remix_flow.enqueue_review` | `test_handoff_gate_record`, `test_enqueue_growth_plan_pending_review` |
| Weekly cycle | `run_weekly_cycle` — end-to-end plan; deterministic (same input → identical output); an empty input still forms an honest plan with everything unavailable | `test_weekly_cycle_end_to_end`, `test_weekly_cycle_deterministic`, `test_weekly_cycle_no_metrics_still_plans`, `test_weekly_cycle_empty_input_honest` |

## What was NOT built (by design, stated in the code)

- **Layer 04.** The board record names six layers and skips number
  04 — Layer 04 is unnamed in the source record. Code searches for
  "DeihbtONYtH" (3 hits: `competitor_ads.py`, `channel_operator.py`,
  `test_ig3_vyr04_competitor_ads.py`), "seven-layer" (0 hits), "Growth
  Director" (30 hits, none defining layers), "V-03" (2 hits,
  unrelated) found no Layer 04 definition anywhere in the repo. No
  fourth layer is invented. The module carries the six named layers
  under their source numbers (`LAYER_NUMBERS = ("01","02","03","05",
  "06","07")`) and the plan carries a `layer_04` entry with
  `status="unnamed_in_source_record"` (`LAYER_04_NOTE`).
- **Four of the eight departments** — paid ads, lead capture, sales
  response, nurture & retargeting. They have no VyralX function (no
  ad accounts / spend, no lead forms / funnel, no sales calls /
  deals, no leads list / retargeting audience). Listed in
  `UNMAPPED_DEPARTMENTS` with the reason each, never built, never
  silently dropped.
- **Four of the five source KPIs** — cost per lead, speed to lead,
  booked & paid, ad to customer. A YouTube channel with no leads
  funnel, no ad accounts and no bookings has no source data for
  them. Reported unavailable with the reason in
  `UNMEASURED_SOURCE_KPIS`, never estimated.
- **No publishing, uploading, scheduling with YouTube, posting or
  hiding comments.** Every output is a proposal (`pending_review`,
  `requires_approval=True`); schedule entries are plans
  (`publish=False`, privacy `unlisted`); distribution is a plan
  (`distribution_planned=True`, `distribution_executed=False`).
  Guardrail test `test_module_imports_no_publish_paths` parses the
  module and asserts it never imports `youtube` / `ytdlp` /
  `multiplatform_publisher` / `edge_tts` / `googleapiclient` and
  never calls `.upload` / `.publish` / `.post_comment` /
  `.hide_comment`. The multiplatform publisher (`package_multiplatform_release`,
  not pure — reads settings, writes files) is deliberately not used.

## Test verification — repo CI only

No local pytest, no local execution/import/build of fetched content
(the execution-risk constraint on the local clone; verification rests
on repo CI). The module and tests were validated parse-only
(`ast.parse`, static text analysis) before committing: both files
parse, no lines over 100 chars, no forbidden constructs. The 28
tests follow the existing `test_ig_vyr01_channel_operator.py` style
(plain functions, `from app.services import ...`, `tmp_path` for the
queue). CI on head 0b34447c (first full run, 2026-11-26 ~00:05 IST): 7 success,
2 skipped, 2 failed. One failure was mine —
`test_signals_missing_kinds_reported_not_synthesised` asserted only
four missing kinds; `collect_signals({})` correctly reports all six
(fixed in the follow-up commit on this branch). The other failure is
NOT from this PR: the contracts workflow's Futuris step
(`Futuris/tests/api/test_market_calendar_context.py::test_calendar_release_is_cited_in_response_and_named_in_rationale`)
fails because its fixture date is 2026-11-25 and it ran on 2026-11-26
(`assert 'none_upcoming' == 'available'`). The same workflow, same
step 10, fails on a main push (run 45728251068, head 875504ffd5,
2026-11-26T00:22Z) and on PR #1921 (run 45726195648) — every
contracts run since 2026-11-26 00:00 UTC fails, while all runs on
2026-11-25 passed. No Futuris file is touched by this PR; the fix
belongs to the Futuris area (a date-rolling fixture), not to VYR-082.
CI re-run pending on the fix head.

One deliberate fixture choice, verified against the source: the
market-intelligence brief test uses hooks that score ≥ 0.60 on the
fleet's stated `format_clone.score_hook` heuristic (question form +
second person + concrete number + hook present = 0.75 each), because
`pattern_brief` only ranks ads scoring ≥ 0.60 — hooks below that
produce an empty brief, which is correct behaviour, not a bug.

## Live leg — gated, not done

Done per the board = "the loop runs one real weekly cycle and
produces a channel growth plan from live channel data". That leg is
NOT in this PR: the owner stop order on live dispatch runs (in force
since ~2026-11-24 16:42 IST) is still in force, and Fleet CD is
broken per WATCH098 (S1 dirty, S2 perms). No deploy, no restart, no
live-fleet writes were attempted. The live weekly cycle (real channel
data → plan → owner review) needs hub clearance after merge.

## Gaps / next action

- Layer 04 remains unnamed in the source record; if the coordinator
  or owner names it, it slots in as a seventh entry under its source
  number.
- The Brain's lane priorities rest on `VIDEO_METRICS`, which is empty
  in production (`channel_operator` returns 0 rows) — until a real
  metrics feed lands, every cycle honestly reports "no measured
  views" and plans from topics alone. A metrics feed is the
  highest-value follow-up.
- Next: peer merge of this PR, then deploy + the live weekly cycle
  after Muse's clearance.

— Muse 2
