# TASK-ORCH-010 — Routing re-probe: trace + verdict

- **Task:** Re-verify TASK-ORCH-001 — re-probe the intent-classification routing table end-to-end, file the trace + verdict. No re-implementation.
- **Date:** 2026-11-22 ~10:00–11:00 IST. Worker: Muse 1.
- **Probe base (main):** `01254f1` (board blob `0e9eee68…`, verified against the true main blob before claiming).
- **Live fleet checkout (S1, FRIDAY.service):** `ef42312f` — 22 commits behind the probe base; the compare shows **only docs changed** between the two (INF-LLM-003 doc, audits, board, STRATEX-PROFIT doc), so the live service runs the **exact routing code probed**. FRIDAY.service active, MainPID 2008492, NRestarts 0, listening on :10000.
- **Claim:** issue #35 comment 7074197566; board claim PR #1313 (merged).

## What "the routing table" is

Two layers, in live pipeline order (`FRIDAY/src/friday/agent/mixins/cognitive.py`,
`process_message`):

1. **15 fast paths first** (`FRIDAY/src/friday/agent/mixins/fast_paths.py`):
   greeting → conversational → pipeline → task-status → delegation → security →
   forecast → batch3-delegation → diagnostics → fleet-status → research-dispatch →
   portfolio → direct-desktop-action → deterministic-action → time. A fast path that
   fires answers the turn and `route_request` is never called.
2. **The router** (`FRIDAY/src/friday/routing/capability_router.py`):
   `CapabilityRouter.route_request` over 20 keyword tables (`_INTENT_TABLES`,
   line 342) plus DIRECT_REASONING / LOCAL_COMPUTATION / screen / background /
   fallback-tool candidates, picked by lowest `compute_selection_score`
   (line 61: latency×0.01 + (1−confidence)×100 + ±20 local bonus).
3. **The LLM intent mid-tier** (`FRIDAY/src/friday/routing/intent_classifier.py`,
   gated by `LLMIntentClassifier.signal_is_weak` — fires only when 0 or ≥2 tables
   match; wired in `cognitive.py:380–405`). Fail-open by design.

## Method (three independent evidences)

- **A. S1 router probe (faithful harness on the fleet's own code, no dispatch).**
  Ran the deployed `CapabilityRouter.route_request` + `deterministic_match_count` +
  `signal_is_weak` over a 36-case matrix (+ 6 supplementary cases) on S1 via the
  bridge, using the service venv (`/opt/friday_universe/venv`). Read-only: no
  dispatch, no network, no writes. Script kept at `~/workspace/orch-010/router_probe.py`
  (local copy only — not shipped).
- **B. Live `/api/chat` probes.** 8 messages sent to the live FRIDAY service on S1
  (`POST http://127.0.0.1:10000/api/chat`, keyless origin-gated surface), routing
  decisions observed in `/opt/friday_universe/FRIDAY/logs/friday.log`
  (`"Routed query … to … (Score: …)"`) and in the API response metadata.
  Each probe persists one conversation-history entry (listed in §5).
- **C. Journal mining.** All 157 `"Routed query"` lines in the live log
  (2026-11-12 → 2026-11-17; no routing decisions logged since Nov 17 21:07 IST).
- **Not done:** no local execution of a repo clone (a clone tripped an
  execution-risk check; the clone was deleted unused — the live-fleet methods
  above replace it), no live dispatch of write/send/publish/render/code/research
  routes (unsafe side effects — see §6).

## Evidence A — S1 router probe (36 cases, 30 PASS)

Score = `compute_selection_score` of the winning candidate. `weak` = `signal_is_weak`.

| # | Utterance | Tables | Weak | Selected → tools | Score | Verdict |
|---|-----------|--------|------|------------------|-------|---------|
| 1 | look at screen and tell me what you see | SCREEN 1 | no | VISION_MODEL | 56.0 | PASS |
| 2 | same, cached screen context | SCREEN 1 | no | LOCAL_SCREEN_INSPECTION | −14.98 | PASS |
| 3 | what do you remember about our last chat | MEMORY 1 | no | MEMORY_RETRIEVAL | −14.95 | PASS |
| 4 | calculate 2 + 2 | LOCAL_CALC 1 | no | LOCAL_COMPUTATION | −19.99 | PASS |
| 5 | how's the fleet? | FLEET 1 | no | TOOL_EXECUTION → get_fleet_status | −9.0 | PASS |
| 6 | research the latest fusion energy papers | RESEARCH 1 | no | TOOL_EXECUTION → intelx_research | 78.0 | PASS |
| 7 | how is my portfolio doing? | PORTFOLIO 1 | no | TOOL_EXECUTION → stratex_portfolio | 67.0 | PASS |
| 8 | write me a script to bulk-rename my photos | CODE_TASK 1 | no | TOOL_EXECUTION → **(no tools)** | −9.9 | **MISMATCH (F1)** |
| 9 | what is our security posture? | SECURITY 1 | no | TOOL_EXECUTION → sentinel_security | 57.0 | PASS |
| 10 | give me a forecast for Bitcoin | FORECAST 1 | no | TOOL_EXECUTION → futuris_forecast | 110.0 | PASS |
| 11 | draft a video script about the ocean | SCRIPT 1 | no | TOOL_EXECUTION → vyralx_script | 130.0 | PASS |
| 12 | how are my websites doing? | WEB_OPS 1 | no | TOOL_EXECUTION → cortex_web_ops | 90.0 | PASS |
| 13 | save this to fleet memory: my favourite colour is blue | FLEET+MEMORA 2 | **yes** | TOOL_EXECUTION → get_fleet_status | −9.0 | **MISMATCH (F2)** |
| 14 | search memora for my favourite colour | MEMORA_OP 1 | no | TOOL_EXECUTION → memora_memory | 73.0 | PASS |
| 15 | summarize this article https://example.com | FETCH 1 | no | TOOL_EXECUTION → web_fetch_summarize | 106.0 | PASS |
| 16 | render this script into a short video | RENDER 1 | no | TOOL_EXECUTION → vyralx_render | 327.0 | PASS |
| 17 | make a video about black holes | PROJECT 1 | no | TOOL_EXECUTION → vyralx_project | 322.0 | PASS |
| 18 | publish this clip to YouTube | PUBLISH 1 | no | TOOL_EXECUTION → vyralx_publish | 328.0 | PASS |
| 19 | alert me when Bitcoin goes above 100000 | ALERT 1 | no | TOOL_EXECUTION → price_alert | −13.0 | PASS |
| 20 | what are my alerts? | ALERT 1 | no | TOOL_EXECUTION → price_alert | −13.0 | PASS |
| 21 | define the word serendipity | DICTIONARY 1 | no | TOOL_EXECUTION → dictionary | −10.0 | PASS |
| 22 | draft an email to Alice about the meeting | GMAIL 1 | no | TOOL_EXECUTION → send_gmail | 48.0 | PASS |
| 23 | open WhatsApp and message Bob | WHATSAPP 1 | no | TOOL_EXECUTION → open_whatsapp | 43.0 | PASS |
| 24 | monitor this continuously in the background | 0 (BACKGROUND kw) | **yes** | BACKGROUND_TASK | −14.8 | PASS |
| 25 | list the files in the folder | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS (expectation corrected — see note) |
| 26 | explain how HTTPS works | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS |
| 27 | **ORCH-001 regr:** run a quick research check | RESEARCH 1 | no | TOOL_EXECUTION → intelx_research | 78.0 | PASS |
| 28 | **ORCH-001 regr:** answer this quietly please | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS |
| 29 | **ORCH-001 regr:** build a summary of today | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS |
| 30 | **ORCH-001 regr:** explain historic market patterns | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS |
| 31 | **ORCH-001 regr:** give me a running commentary on the news | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS |
| 32 | **ORCH-001 regr:** check the history of this file | MEMORY 1 | no | MEMORY_RETRIEVAL | −14.95 | PASS |
| 33 | write a script to bulk-rename my photos | CODE_TASK+SCRIPT 2 | **yes** | TOOL_EXECUTION → **(no tools)** | −9.9 | **MISMATCH (F1)** |
| 34 | research the fleet's security posture | RESEARCH+FLEET+SECURITY 3 | **yes** | TOOL_EXECUTION → get_fleet_status | −9.0 | **MISMATCH (F2)** |
| 35 | calculate 17 times 23 and define serendipity | LOCAL_CALC+DICTIONARY 2 | **yes** | LOCAL_COMPUTATION | −19.99 | AMBIGUOUS BY DESIGN (see note) |
| 36 | explain the theory of general relativity to me | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS |

Supplementary cases (same probe, second run):

| # | Utterance | Tables | Weak | Selected → tools | Score | Verdict |
|---|-----------|--------|------|------------------|-------|---------|
| S1 | read this page https://example.com | FETCH 1 | no | TOOL_EXECUTION → **(no tools)** | −9.9 | **MISMATCH (F1, live-reachable)** |
| S2 | create a video about black holes | PROJECT 1 | no | TOOL_EXECUTION → **(no tools)** | −9.9 | **MISMATCH (F1)** |
| S3 | list the agents | FLEET 1 | no | TOOL_EXECUTION → **(no tools)** | −9.9 | **MISMATCH (F1)** |
| S4 | read the security findings | SECURITY 1 | no | TOOL_EXECUTION → **(no tools)** | −9.9 | **MISMATCH (F1)** |
| S5 | write a summary of the meeting | 0 | **yes** | DIRECT_REASONING | −16.5 | PASS |
| S6 | run diagnostics | 0 (DIAGNOSTICS kw exists but is not a table) | **yes** | DIRECT_REASONING | −9.0 | PASS (router has no diagnostics route; fast path handles it live) |

Notes on corrected expectations: case 25 — my first expectation (fallback TOOL_EXECUTION)
was wrong; the fallback candidate (−9.9) can only win when DIRECT_REASONING is
suppressed by a table match, and DIRECT (−16.5) wins when no table matches. Case 35
is genuinely two intents in one sentence; the deterministic pick (LOCAL_COMPUTATION,
cheaper) is defensible and the weak-signal gate is the designed disambiguator —
but see F3: the tier never fires live, so nothing disambiguates it in production.

## Evidence B — live `/api/chat` probes (2026-11-22 ~10:25–10:31 IST)

Routing lines from `/opt/friday_universe/FRIDAY/logs/friday.log`
(157 lines before the probes → 165 after; 8 new lines):

| # | Probe (UTC ≈ IST−5:30) | Live routing line | Reply / metadata |
|---|------------------------|-------------------|------------------|
| P1 | calculate 17 times 23 | LOCAL_COMPUTATION, Score −20.0 (10:25:00) | "17 × 23 = 391"; intent_classify_seconds 0.0 |
| P2 | explain how HTTPS works | DIRECT_REASONING, Score −16.5 (10:25:37) | Full HTTPS explainer |
| P3 | what do you remember about our last chat | **no router line** — conversational fast path answered (memory_recall, store empty) | "I don't have anything stored on that yet, Boss…" |
| P4 | define the word serendipity | TOOL_EXECUTION, Score −10.0 (10:26:04) | Dictionary definition; intent_classify_seconds 0.0 |
| P5 | explain the theory of general relativity to me | DIRECT_REASONING, Score −16.5 (10:27:03) | Relativity explainer; **intent_classify_seconds 0.0, intent_classification None — tier did NOT fire** (0-table weak signal) |
| P6 | calculate 17 times 23 and define serendipity | LOCAL_COMPUTATION, Score −20.0 (10:28:22; re-run 10:30:24) | Answered both parts; **intent_classify_seconds 0.0, None — tier did NOT fire** (2-table weak signal) |
| P7 | read this page https://example.com | TOOL_EXECUTION, **Score −9.9** (10:28:35) | **Live misroute confirmed:** −9.9 is the generic fallback, not web_fetch_summarize (106.0). The generic loop then executed `fetch_webpage_content` successfully (10:28:41), so the page was still fetched — by luck of the LLM loop, not by the table. |
| P8 | what are my alerts? | **no router line** — dispatch-layer alert handler answered | "No price alerts active, Boss…"; the alert store answered directly (`FRIDAY/src/friday/api/server.py` ~3472) |

## Evidence C — journal mining (real owner traffic, 157 decisions)

`friday.log`, 2026-11-12 → 2026-11-17 (no routing decisions logged since Nov 17
21:07 IST): 128 DIRECT_REASONING, 21 LOCAL_COMPUTATION, 5 MEMORY_RETRIEVAL,
2 TOOL_EXECUTION (`Portfolio status` → TOOL_EXECUTION 67.0 on Nov 12 23:06;
`Give me a short forecast: what should I…` → TOOL_EXECUTION 67.0 on Nov 14 14:15),
1 VISION_MODEL (`Access my screen`, Nov 12 22:04). **Zero "LLM intent tier" lines in
the whole window.** Notable: `Describe the complete history of aviation` and
`Describe the history of the Olympic Games` (Nov 14 23:28/23:29) both routed to
MEMORY_RETRIEVAL — the bare keyword `history` in MEMORY_KEYWORDS sends
general-knowledge history questions to memory recall (see O1).

## Verdict

**RE-PROBED — table verified with exceptions. No routing change in this task.**

- The ORCH-001 fix holds: all 5 word-boundary regressions pass, and the live
  incident phrase `run a quick research check` routes to `intelx_research`
  (78.0), never to VISION_MODEL — confirmed at the router (case 27) and by the
  fast-path analysis (the research fast path requires a leading research verb,
  so this phrase reaches the router, which now routes it correctly).
- 30/36 matrix cases pass at the router; all live-reached routes pass except P7.
- Three follow-ups are filed below (F1, F2, F3) with file/line. Nothing was
  silently fixed; the only repo changes in this task are this document and the
  board record.

## Follow-ups filed

### F1 — Generic fallback candidate outranks specific tools (live misroute: fetch)
- **File/line:** `FRIDAY/src/friday/routing/capability_router.py:757`
  (fallback candidate, score −9.9) vs `compute_selection_score` at `:61`.
- **Proven:** S1 probe cases 8, 33, S1–S4 — any utterance matching a specific
  table AND containing a generic verb (`write`/`read`/`create`/`list`/…) loses
  its specific tool to the tool-less fallback candidate. Live proof: P7
  `read this page https://example.com` → TOOL_EXECUTION score −9.9 instead of
  `web_fetch_summarize` (106.0). The page was still fetched only because the
  generic LLM loop happened to pick `fetch_webpage_content`.
- **Live reachability:** only the FETCH phrasings (`read this page/article/link`)
  reach the router live — code/project/fleet/security phrasings are intercepted
  by fast paths first (batch3-delegation, fleet-status, security), which mask
  the defect in production. The defect is in the table, not the fast paths.
- **Proposed fix (separate task, not done here):** make the fallback candidate
  lose to any candidate that names `required_tools` (or exclude it when a
  specific table matched), and add regression tests for `read this page`,
  `write me a script`, `create a video about`.

### F2 — Cheap generic fleet ping beats specific tools on multi-table matches
- **File/line:** `FRIDAY/src/friday/routing/capability_router.py:466`
  (`get_fleet_status`, 800 ms, local → score −9.0) vs `:595`
  (`memora_memory`, 5000 ms, non-local → 73.0) and the C11 comment at `:583`.
- **Proven:** S1 probe cases 13, 34 — `save this to fleet memory` → fleet status
  instead of `memora_memory`, contradicting the C11 comment ("the SPECIFIC
  memory-op intent must win over the generic fleet ping"); `research the fleet's
  security posture` → fleet status instead of `sentinel_security`. Evaluation
  order does not matter — candidates are sorted by score at the end, so the
  comment's reasoning is wrong.
- **Live reachability:** masked live — the batch3 fast path intercepts MEMORA_OP
  and the security fast path intercepts security phrasings before the router.
- **Proposed fix (separate task):** score the specific intent above the generic
  fleet ping when both match (e.g. specificity bonus), or exclude the fleet
  candidate when a more specific table matched; regression-test the two phrases.

### F3 — LLM intent mid-tier never fires live (the safety net is inert)
- **File/line:** `FRIDAY/src/friday/routing/intent_classifier.py:155`
  (`_get_provider`), `:285` (`get_intent_classifier`); gate at
  `FRIDAY/src/friday/agent/mixins/cognitive.py:380–405`.
- **Proven:** two weak-signal live probes (P5 0-table, P6 2-table) both returned
  `intent_classify_seconds: 0.0` and `intent_classification: None`; the live log
  contains **zero** "intent tier" lines across 157 real turns + 8 probes.
  Configuration does **not** disable it: no `FRIDAY_INTENT_CLASSIFIER` / intent
  flag in `FRIDAY/.env`, `/etc/friday/dispatch.env`, or the unit environment
  (checked by name only, no secret values read), and
  `intent_classify_enabled` defaults to `True`
  (`FRIDAY/src/friday/core/config.py:289`). The gate logic itself is sound
  (S1 probe: `weak=True` for both probe strings; test suite pins it) — so the
  failure is inside `classify()`/`_get_provider()` failing silently (fail-open
  + debug-only logging), and the cause cannot be determined from INFO-level
  logs. The tier is the designed disambiguator for exactly the ambiguous
  inputs in cases 33–35, so those inputs currently get only score arithmetic.
- **Proposed fix (separate task):** diagnose why `_get_provider()` returns None
  in the live process (debug logging around the classifier call), and add a
  live health signal for the tier (e.g. log at INFO when the gate opens but
  the provider is unavailable).

## Observations (not filed as misroutes)

- **O1 — `history` keyword is over-broad.** `MEMORY_KEYWORDS` contains bare
  `history` (`capability_router.py`, MEMORY_KEYWORDS block). Live traffic shows
  general-knowledge questions (`Describe the complete history of aviation`)
  routing to MEMORY_RETRIEVAL. This is the table working as written (and pinned
  by the `check the history of this file` test), so it is a design question for
  Muse, not a proven misroute.
- **O2 — `DIAGNOSTICS_KEYWORDS` is a dead set.** Defined at
  `capability_router.py:138` but never used by `route_request` (no diagnostics
  candidate; `run diagnostics` falls to the default DIRECT_REASONING at the
  router). Diagnostics is handled by the diagnostics fast path live, so there
  is no user-visible gap — but the table lists 20 tables and diagnostics is not
  one of them despite the keyword set existing.
- **O3 — Fast paths mask router defects.** Most tool routes (fleet, research,
  portfolio, security, forecast, diagnostics, code, script, web-ops, memora,
  project) never reach `route_request` live — their fast paths fire first.
  The router is the safety net for phrasings the fast paths miss (e.g. the
  ORCH-001 incident phrase), which is exactly where F1/F2 bite.

## What was NOT probed live, and why

Live dispatch of these routes would cause real side effects or cost, so they
were verified at the router (Evidence A) only, not via `/api/chat`:
research brief (real IntelX job + possible Telegram follow-up), forecast (real
Futuris compute), code task (real Forge build in sandbox), script/render/publish
(draft/render/upload artifacts; publish uploads a YouTube draft), gmail/whatsapp
(would draft/send real messages), memora save (persistent write), alert-create
(persistent rule), background task (starts a background job), screen/vision
(no screen on S1; external vision call). No probe message was sent for any of
these; the 8 live probes in §B are the complete list of messages sent, each
persisting one conversation-history entry in FRIDAY's store (timestamps in the
log lines above).
