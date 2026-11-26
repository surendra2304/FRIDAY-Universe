# TASK-FRD-052 — CHECKPOINT 1 — repo-side mapping (scoping)

- **Worker:** Muse TP7
- **Task:** TASK-FRD-052 (P1, PRODUCTION-VERIFY: FRIDAY corpus IG-FRD-006, IG-FRD-007, IG-FRD-008, IG-FRD-009 — live extreme-condition verification, wave 2)
- **Claim:** hub #1483 comment 7156063432, 2026-11-25 ~13:20 IST
- **Checkpoint:** 2026-11-25 ~14:10 IST
- **Base:** main `a0a9f1ba` (merges #1793 + #1800; claim branch fast-forwarded be3f303 → a0a9f1ba, zero work commits before this one)
- **Branch:** `musetp7/task-frd-052-prod-verify-wave2`
- **Scope of this checkpoint:** repo-side leg only — corpus-item → merged-artefact mapping verified first-hand on main, per the STR-075 / VYR-074 checkpoint-1 precedent. No live move. Live leg is gated (owner stop order; no live step until Muse clears it — see below).

## Mapping — verified first-hand on main a0a9f1ba

Method: `git ls-tree origin/main` for every listed file (all 10 present, blob SHAs below);
`git merge-base --is-ancestor` for each landing commit (all 4 on main);
`git hash-object` on the checked-out files equals the origin/main blob SHAs exactly;
`python3 -m py_compile` on all 10 files passes. Board record read first-hand from
`WORK_BOARD.yaml` on origin/main. Mapping-test counts below are the board's evidence
claims, not re-runs here: this VM has no pytest installed, so the four mapping test
files were NOT executed locally; they run in CI on the work PR.

| Item | Source task (board, MERGED) | Landing commit / PR | Mapped files on main a0a9f1ba (blob SHA) | Key symbols verified |
|---|---|---|---|---|
| IG-FRD-006 | Source cards on answers: sources extracted from the turn's real tool results, wired at process_message (IG corpus DfO5vLSjodF) | 82f9b73a / PR #502 | FRIDAY/src/friday/cognition/source_cards.py (9b1aa2f1); FRIDAY/src/friday/agent/agent.py (08e126cf); FRIDAY/tests/test_ig_frd_006_source_cards.py (805945ed) | extract_source_cards, render_sources_section ("Sources:"), attach_source_cards |
| IG-FRD-007 | Offline-first fallback: cached-knowledge provider as last fallback rung, env-gated (IG corpus Ddy9EMkCb3Z) | 9a821ae0 / PR #505 | FRIDAY/src/friday/llm/offline_fallback.py (c65dc198); FRIDAY/src/friday/llm/factory.py (7172098e); FRIDAY/tests/test_ig_frd_007_offline_fallback.py (497f9a9a) | OfflineFallbackProvider, offline_fallback_enabled, FRIDAY_OFFLINE_FALLBACK=on gate |
| IG-FRD-008 | Screen-vision: laptop_describe_screen via bridge capture + Gemini vision, honest OCR fallback (IG corpus DfEoqPfClGT) | d909d4da / PR #509 (replacement) | FRIDAY/src/friday/tools/builtin/laptop_screen_vision.py (64042061); FRIDAY/tests/test_ig_frd_008_screen_vision.py (73355c19) | LaptopDescribeScreenTool, name "laptop_describe_screen" |
| IG-FRD-009 | Life-in-weeks dot-grid calendar computation tool, stateless, grid as data (IG corpus DTjp4aaE_bT) | 5a86802d / PR #511 (replacement) | FRIDAY/src/friday/tools/builtin/life_calendar.py (d1440fc0); FRIDAY/tests/test_ig_frd_009_life_calendar.py (a2cbf6ba) | compute_life_calendar, LifeCalendarTool, per-year 52-char grid |

Board-claimed local test results (evidence on the IG records, not re-run here): IG-FRD-006 8 passed,
IG-FRD-007 8 passed incl. chain fall-through, IG-FRD-008 5 passed, IG-FRD-009 5 passed.

## Live leg — plan and gate (not run)

Per the FRD-052 acceptance, each item closes only on live evidence: a real owner-style
request end-to-end through the live FRIDAY service on FRIDAY-Server, plus a
downstream-agent-down failure injection, plus latency measured per item. Per-item
live proofs named in the board next_actions:

- IG-FRD-006: ask FRIDAY a question that triggers web research; confirm the answer carries a `Sources:` section whose URLs match the tool results.
- IG-FRD-007: set FRIDAY_OFFLINE_FALLBACK=on on Server 1, warm the store, kill network egress briefly in a drill window, confirm a labelled cached answer.
- IG-FRD-008: once the owner's laptop is connected (LAP-001 client), ask FRIDAY by voice "what is on my laptop screen" and confirm a real vision description returns.
- IG-FRD-009: ask FRIDAY for a life-in-weeks view for a sample DOB and confirm the numbers + grid metadata.

**Gate: none of the above has been run. Owner stop order not lifted; live leg awaits
Muse's clearance (per claim comment 7156063432). No live step, no service restart,
no deployment move in this checkpoint.**

## Queue and usage

- **Head:** TASK-FRD-052 (this task). **Pre-staged next:** TASK-FRD-053 (IG-FRD-010, IG-FRD-011, IG2-FRD-01, IG2-FRD-02), verified AVAILABLE / owner null on main a0a9f1ba — pre-staged by Muse in WATCH087 (hub 7156907146). Queue depth 2 (current + 1 pre-staged).
- **Usage:** 1% of free weekly limit, resets 2026-11-25 16:58 IST. No subscription.
- **Roster PR:** #1795 open, head d1e81960 (Register Muse TP7 in TEAM_ROSTER). Local branch state repaired this run: local musetp7/onboarding reset to origin/musetp7/onboarding (identical content, was sitting uncommitted at be3f303).

## Next

Checkpoint 2: live-leg clearance request to Muse on the hub (per-item live steps, servers,
read-only scope) + mapping-test run in CI once the work PR opens. Board flip
(FRD-052 AVAILABLE → CLAIMED, owner muse_tp7, branch musetp7/task-frd-052-prod-verify-wave2)
rides in the work PR.
