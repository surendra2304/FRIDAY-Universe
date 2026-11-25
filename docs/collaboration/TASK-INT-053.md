# TASK-INT-053 — INT-020 synthesis/entailment fix on the live chat route (INT-033 follow-up)

## 1. Task

- **Task:** TASK-INT-053 (P2, IntelX)
- **Title (board):** 'INT-020 synthesis/entailment fix on the live chat route (INT-033 follow-up) - root-cause chat-route vs bus + fix + 3 consecutive live INT-020 runs passing'
- **Claim:** hub #1483, comment 7169108662, 2026-11-25 ~22:40 IST, in the 22:36 hourly self-check run — IG-INF-01-FIX-01 MERGED (work PR #1865, merge 9025af4e), live leg blocked on deployment clearance, so per the blocked-head rule the queue head moves to this task. Filed by coordinator watch102 from my INT-020 block post 7163772133; assigned to muse_13 as queue position 2 behind IG-INF-01-FIX-01.
- **Branch:** `muse13/task-int-053-synthesis-fix` from main `a759a031` (created via Git Data API, verified read-back).
- **Work PR:** #1875 (https://github.com/surendra2304/FRIDAY-Universe/pull/1875), head `8d2381ff`, base main `a759a031`. Commit 1 `10c7c673` (evidence doc + IG-INF-01-FIX-01 MERGED note); commit 2 `8d2381ff` (board flip INT-053 → CLAIMED / pr 1875 + this PR number).

## 2. Board verification (first-hand, main a759a031, 22:36 run)

- Board file `docs/collaboration/WORK_BOARD.yaml`, blob `31ae33e4`, 2,911,147 bytes; 990 `- id:` records by the `^  - id:` regex, 0 dups (coordinator's validator parses 985+ — my regex counts nested records slightly differently; no duplicates among the records it sees).
- TASK-INT-053: **AVAILABLE / owner muse_13 / branch null / pr null**, P2, `created_at: '2026-11-25'`, `updated_at: '2026-11-25T19:40:00+05:30'`. `next_action: 'Assigned to muse_13 as queue position 2 by coordinator watch102 (2026-11-25, hub #1483); claim via hub #1483 when it reaches queue head.'`
- No competing claim: full hub read through comment 7168967199 + page 17 empty — zero INT-053 claims by anyone else.
- Neighbours on main a759a031:
  - TASK-IG-INF-01-FIX-01: **MERGED / muse_13 / muse13/task-ig-inf-01-fix-01-impl / pr 1865** (flip rode in coordinator board PR #1874, WATCH108)
  - TASK-VOI-030: CLAIMED / muse_13 / muse13/task-voi-030-acceptance-run-17 / pr null, P1 (blocked — calm window)
  - TASK-INT-020: AVAILABLE / muse_13 / null / null (its CLAIMED flip rides in open work PR #1834, held for this fix)

## 3. Acceptance (board record, verbatim substance)

- Root-cause the INT-020 synthesis/entailment failure on the live chat route vs the bus (INT-033 merged #1511 yet the failure persists: 0/3, `synthesis_entailment_unverified` every time, retrieval healthy).
- Fix the chat-route fault and file the evidence; then 3 consecutive live INT-020 runs passing.

## 4. The failure to fix (evidence carried from TASK-INT-020, full detail in ~/workspace/muse13/int020/TASK-INT-020-INTELX-RESEARCH-RUNS.md)

Three loopback attempts 2026-11-25 ~19:14–19:25 IST, route `POST /api/chat` on FRIDAY-Server (loopback, no credential, per WATCH099 ruling 7162851838):

| Attempt | Brief | Stored run | Outcome |
|---|---|---|---|
| 1a ~19:14 IST, 70.9 s | AI model releases | lr_c5f08d9c5b2e4320be6d31d6 | DEGRADED, synthesis failed (`synthesis_entailment_unverified`), 5 sources / 15 raw findings |
| 1b ~19:20 IST, 55.6 s | Same brief (flakiness retry) | lr_365e94dd989243e296c64915 | DEGRADED, same verdict — not flaky |
| 1c ~19:25 IST, 34.8 s | SpaceX Starship news | lr_b10f970668fa4fd78519d441 | DEGRADED, same verdict, 1 source / 3 findings — not topic-specific |

Verbatim FRIDAY reply every time: "IntelX could not complete that research: sourced_findings_unverified. That is the real outcome — no highlights were fabricated." (Label note: the reply says `sourced_findings_unverified` while the stored run says `synthesis_entailment_unverified` — same DEGRADED outcome, mismatch recorded.)

What works: retrieval (Tavily + Google News RSS 200, source fetches live), synthesis call to Inference 200, run persisted. What fails: the synthesis/entailment stage, every time, on the chat route.

What is already ruled out / known:
- INT-033 (MERGED PR #1511, merge cfe211cf 2026-11-23): three tokenisation defects in `statement_support` (`IntelX/intelx/api/grounded_live_research.py`) — false-negative-only repairs (unicode normalisation, trailing-punctuation strip, substring coverage). 11/11 live runs had been DEGRADED before the fix.
- INF-028 (MERGED PR #1561): fix deployed to live IntelX; synthesis re-probe GREEN 2026-11-24 on the **bus** (run 2 completed, synthesis succeeded, entailment + quotes verified, archive and bus agree, `lr_70c54f7c36604cbeb9922c8b`). Verdict then: "`synthesis_entailment_unverified` is gone from the live path."
- The deployed `grounded_live_research.py` on IntelX-Server carries exactly the INF-028-verified sha256 (`c3a39b2d8b06871d8ab02c3a1e92552b128e05279fbdbafab4d7178d7e9e9eab`) — the INT-033 fix IS live on the current IntelX home.
- FRIDAY on FRIDAY-Server active (MainPID 40483, :10000); IntelX on IntelX-Server active (MainPID 4973, /health 200, mock_mode false).

Open question: why the chat route fails while the bus passed. Candidates (NOT adjudicated): route difference (chat path vs bus path into the same synthesis stage), IntelX home move S2 → server 6, remaining false negatives outside INT-033's three repairs (e.g. a different entailment check on the chat path, a synthesis-model or prompt difference, a timeout/truncation on the longer chat-route synthesis).

## 5. Repair plan

1. **Recon (read-only first):** read `grounded_live_research.py` on main — the synthesis/entailment stage as it stands; identify every place the chat route and the bus route can diverge (entry point, request construction, synthesis call parameters, entailment/verification checks, timeouts, model selection). Read the INT-033 evidence doc (`docs/collaboration/TASK-INT-033-ENTAILMENT-ROOT-CAUSE.md`) and the INF-028 re-probe evidence for what the bus path does differently.
2. **Reproduce the divergence in evidence, not in assertion:** compare a failing chat-route run's stored record against the green bus run `lr_70c54f7c36604cbeb9922c8b` — same synthesis inputs? same model? same entailment function? Pin the first point of divergence.
3. **Fix the chat-route fault** (false-negative-only if it is an entailment check; otherwise the real fault), with tests that pin the repaired behaviour.
4. **Live verification:** after the fix lands (deployment clearance per the live-servers rule), run INT-020's 3 consecutive live runs via the loopback `/api/chat` route (WATCH099 route). No further INT-020 attempts until the fix lands — three identical failures are enough evidence.

Constraints: no provider kills, no restarts, no fleet writes without clearance; no credential read or supplied (loopback stays keyless per the D-023 gate); free tiers only. Do NOT re-run INT-020 attempts before the fix — held.

## 6. Five states

Implemented NO / tested NO / merged NO / deployed NO / production-verified NO — checkpoint 1 (claim + board verification) filed; **recon code-level DONE (checkpoint 2, §9)**; live reproduction PENDING (needs bridge/server access — no bridge tool in this run); live re-probe still blocked on deployment clearance (WATCH109: NOT granted, owner stop order stands).

## 9. Recon — code-level root cause (checkpoint 2, 2026-11-25 ~23:50 IST)

Read first-hand from main (GitHub API, no clone): `IntelX/intelx/api/grounded_live_research.py` (486 lines, blob 9e43d784), `IntelX/intelx/api/live_research_task.py` (557 lines), `IntelX/intelx/api/router.py` (`execute_task`, `research_live` branch), `FRIDAY/src/friday/tools/builtin/intelx_research.py` (192 lines), `docs/collaboration/TASK-INT-033-ENTAILMENT-ROOT-CAUSE.md`, `docs/collaboration/TASK-INF-028-DEPLOY-EVIDENCE.md`. INT-033's fix IS present in the main file (`_normalize_text`, `_UNICODE_PUNCT_TRANSLATION`, entity strip, substring coverage).

### 9.1 Adjudicated: there is NO code divergence between the chat route and the bus route

- **Chat route:** FRIDAY chat → `IntelXResearchTool` → `TaskEnvelope(capability="intelx.research", action="research_live", payload={"topic": query})` → `fleet_client.dispatch_task` → IntelX `POST /v1/task/execute`.
- **Bus route (INF-028 re-probe):** `POST /api/v1/dispatch/send?agent=IntelX&action=research_live` with `{"topic": "latest AI model releases"}` — the same dispatch, the same IntelX endpoint.
- **One funnel inside IntelX:** `execute_task` (action `research_live`) → `collect_live_brief(query, ..., synthesize=synthesize_grounded)` → `run_live_research` envelope. Same pipeline, same synthesis function, same gateway (`qwen/qwen3.8-27b`, max_tokens 2400, temp 0), same gates. The "chat route vs bus" divergence is NOT in code. Remaining differentiators: (a) retrieved-document freshness — bus green runs 2026-11-24 ~01:18–01:43 IST, chat failures 2026-11-25 ~19:14–19:25 IST, ~18 h apart, news pages changed; (b) per-call draft variance — the draft is generated fresh every call and the gateway routes across providers/models per call (REL-007). Attempts 1a/1b used the same topic ("latest AI model releases") as the green bus run, so query text is not the differentiator.
- **Label mismatch resolved (not a bug):** FRIDAY's verbatim reply quotes the *envelope* error `sourced_findings_unverified` (`run_live_research`: `evidence_ok` False → error `sourced_findings_unverified`); the stored run records the *inner* cause `synthesis_entailment_unverified` (`collect_live_brief` synthesis error). Two layers, one outcome. The `IntelXResearchTool` formats the envelope error into the reply (`"IntelX could not complete that research: {error}. ..."`).

### 9.2 Adjudicated: the failing leg cannot be named from the stored runs — the reason is discarded

- `synthesize_grounded`: `supported, _reason = statement_support(item.statement, source["text"])` — the specific reason (`unsupported_entity:X`, `unsupported_number:N`, `low_content_coverage:a/b`) is thrown away; the degraded error is the generic `synthesis_entailment_unverified`.
- `collect_live_brief` stores only `{"reason": "synthesis_entailment_unverified"}` in the run record. The archive therefore cannot say which leg failed on lr_c5f08d9c / lr_365e94dd / lr_b10f9706. Root-causing requires reproduction with reason logging (Muse 9's probe method: re-fetch the run's 5 source URLs, rebuild the documents exactly as `collect_live_brief` builds them, re-synthesize, log per-finding reasons). Note the router pops `source_documents` out of the brief before archiving, so the archive holds URLs, not page text — reproduction re-fetches.
- **Live reproduction is PENDING and NOT doable from this run:** it needs bridge/server access (read the archived runs, run the probe on/against the servers). No bridge tool or skill is available in this run (skill search: no match). Owed in a work run with bridge access, or by coordinator direction.

### 9.3 Code-grounded hypotheses (unverified as the cause of the three runs — the discarded reason blocks confirmation)

1. **Possessive entities (NEW class, not covered by INT-033).** Entity leg: `probe = token.rstrip(".-'")`, then `probe.lower() not in source_lower`. A mid-statement possessive token such as `Google's` ends in `s`, so the strip does nothing and `google's` must appear verbatim in the source; a source writing `Google Gemini` (no possessive) fails the whole draft. INT-033 stripped only trailing sentence punctuation. The entity leg is all-or-nothing (one unsupported entity degrades all three findings), so one possessive in one finding kills the run. Same false-negative-only repair shape as INT-033 (strip a trailing `'s`/`'` from the probe) — pending confirmation that this is the failing class.
2. **Numbers leg, dates.** Statement numbers must appear verbatim as number tokens in the supplied text. A model-written date such as "November 17, 2026" needs `17` and `2026` in the source; a source writing "Nov 17" without the year fails (`unsupported_number:2026`). Same all-or-nothing shape. Date-format tolerance is NOT obviously false-negative-only — recorded as a question, not a fix claim.
3. **Whole-draft fail-closed + no retry on entailment failure (amplifiers, already noted by INT-033).** One finding failing any leg degrades the entire draft; `synthesize_grounded` retries once only on `incomplete_completion` — an entailment-failed draft is final, no second draw. Bus-green vs chat-0/3 is consistent with draft variance across draws. A retry-on-entailment-failure (fresh draft, same gates) spends one more Inference call and relaxes no gate.
4. **Second post-synthesis stage (not the observed mode, noted for completeness).** After a SUCCESS draft, `_reverify_against_live` re-fetches each cited page and re-checks every quote; any downgrade sets `quotes_verified=False`, all-fail → `quote_live_reverification_failed`. The three runs failed at entailment, before this stage. Timeout is also not the differentiator: the chat tool allows 125 s, the runs took 35–71 s and reached a synthesis verdict.

### 9.4 Fix candidates (implementation step; semantics-changing items need a coordinator decision)

- (a) **Persist the per-finding `statement_support` reason** in the degraded error / stored run (diagnostic; no gate change). Makes the next failure diagnosable from the archive.
- (b) **Retry synthesis once on entailment failure** with a fresh draft, same gates (robustness; one extra Inference call; no gate relaxation).
- (c) **Possessive-strip in the entity leg** (false-negative-only, same argument as INT-033) — implement once (a) or a reproduction confirms the class.
- (d) **NOT recommended without evidence:** per-finding degradation instead of whole-draft fail-closed (semantics change; coordinator decision).

## 7. Queue

INT-053 (head) → VOI-030 (pos 2, blocked — calm window). INT-020 CLAIMED, held for this fix (0/3). IG-INF-01-FIX-01 MERGED (work PR #1865, merge 9025af4e); its live re-probe leg is blocked on Muse's deployment clearance (requested on #1483, comment 7169108662).

## 8. Run log

### Checkpoint 1 — claim + board verification (2026-11-25 ~22:40 IST, hourly self-check run)

- **State check first:** work PR #1865 **MERGED** by Surendra (merge 9025af4e, 22:07:37 IST, head b3aa5828, CI 10/10 green — 8 success, 2 skipped, verified first-hand via check-runs). Board on main a759a031 verified first-hand (§2): IG-INF-01-FIX-01 → MERGED. No stall — progress real; the merge is the state change this run.
- **Hub read:** WATCH107 (7167935280, ~22:07 IST) + WATCH108 (7168661479, ~22:20 IST) read in full; no new M13 directive. WATCH108 confirms #1865 merged + board PR #1874 open (7 MERGED flips incl. IG-INF-01-FIX-01; merged since — main now a759a031). Page 17 of hub comments empty — nothing newer than 7168967199.
- **Claim:** INT-053 per board next_action (reached queue head: IG-INF-01-FIX-01 merged, live leg blocked on clearance). Claim + MERGED status + deployment-clearance request posted on #1483, comment 7169108662.
- **Branch:** `muse13/task-int-053-synthesis-fix` @ main a759a031 (Git Data API, verified read-back).
- **Checkpoint 1 PR:** #1875 open (head 10c7c673, commit 1 evidence doc + IG-INF-01-FIX-01 MERGED note; commit 2 `8d2381ff` board flip INT-053 → CLAIMED / pr 1875). Board hunk verified first-hand vs main a759a031: exactly 1 diff.
- Usage: 39% of free weekly limit (last verified 20:36 IST), reset Nov 29 6:09 PM IST. No subscription.

### Checkpoint 2 — code-level recon (2026-11-25 ~23:50 IST, hourly self-check run)

- **State check first:** work PR #1875 **open, mergeable true, CI 9/9 green** on head 8d2381ff (7 success, 2 skipped — verified first-hand via check-runs). No stall. Board on current main `3efe8b04` verified first-hand (API-fetched board blob, 990 `- id:` records): INT-053 **AVAILABLE / owner muse_13** / branch null / pr null — no competing claim; IG-INF-01-FIX-01 MERGED / pr 1865; VOI-030 CLAIMED; INT-020 AVAILABLE / muse_13. **Note:** a scratch clone used for this board read tripped an execution-risk check; the clone was removed and no further git operations were run on repo content — subsequent reads used the GitHub API only.
- **Hub read:** WATCH109 (7169671316) + WATCH110 (7170134760) read in full. **M13 items:** WATCH109 acknowledges the INT-053 claim (blocked-head skip from IG-INF-01-FIX-01) and rules **deploy clearance for IG-INF-01-FIX-01 is NOT granted — the owner stop order still stands**; the live re-probe leg stays owed until the owner lifts it. WATCH110 carries no M13 items. Main is now `3efe8b04` (board PR #1876 + VOI-031 PR #1872 merged).
- **Recon (§9, code-level, done):** no code divergence between the chat route and the bus route — one funnel (`/v1/task/execute` action `research_live` → `collect_live_brief` → `synthesize_grounded`); the bus re-probe used the same dispatch with the same topic. Label mismatch resolved (envelope vs inner error). Failing leg unnameable from the archives — `synthesize_grounded` discards the `statement_support` reason. New hypothesis: possessive entities (`Google's`) fail the all-or-nothing entity leg. Fix candidates (a)–(c) filed in §9.4; (d) not recommended without evidence.
- **Pending:** live reproduction (re-fetch the 3 failing runs' sources, rebuild documents, re-synthesize with reason logging) — needs bridge/server access, unavailable in this run; implementation of (a)–(c) next; live re-probe still blocked on deployment clearance.
- **Filing:** this doc updated as commit 3 on branch `muse13/task-int-053-synthesis-fix`, PR #1875 (board unchanged — CLAIMED flip already rides in the PR). Doc note: §1 "head 8d2381ff" is the checkpoint-1 head; the checkpoint-2 head is recorded by PR read-back (see daily log 2026-11-25).
- Usage: 40% of free weekly limit (verified this run via subscription-status), reset Nov 29 6:09 PM IST. No subscription. Work-request task correctly absent (claimed); hourly self-check + weekly reset armed.

— Muse 13
