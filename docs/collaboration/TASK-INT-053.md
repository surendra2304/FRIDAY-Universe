# TASK-INT-053 — INT-020 synthesis/entailment fix on the live chat route (INT-033 follow-up)

## 1. Task

- **Task:** TASK-INT-053 (P2, IntelX)
- **Title (board):** 'INT-020 synthesis/entailment fix on the live chat route (INT-033 follow-up) - root-cause chat-route vs bus + fix + 3 consecutive live INT-020 runs passing'
- **Claim:** hub #1483, comment 7169108662, 2026-11-25 ~22:40 IST, in the 22:36 hourly self-check run — IG-INF-01-FIX-01 MERGED (work PR #1865, merge 9025af4e), live leg blocked on deployment clearance, so per the blocked-head rule the queue head moves to this task. Filed by coordinator watch102 from my INT-020 block post 7163772133; assigned to muse_13 as queue position 2 behind IG-INF-01-FIX-01.
- **Branch:** `muse13/task-int-053-synthesis-fix` from main `a759a031` (created via Git Data API, verified read-back).
- **Work PR:** checkpoint 1 — see §9.

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

Implemented NO / tested NO / merged NO / deployed NO / production-verified NO — checkpoint 1 (claim + board verification) filed; recon starts next.

## 7. Queue

INT-053 (head) → VOI-030 (pos 2, blocked — calm window). INT-020 CLAIMED, held for this fix (0/3). IG-INF-01-FIX-01 MERGED (work PR #1865, merge 9025af4e); its live re-probe leg is blocked on Muse's deployment clearance (requested on #1483, comment 7169108662).

## 8. Run log

### Checkpoint 1 — claim + board verification (2026-11-25 ~22:40 IST, hourly self-check run)

- **State check first:** work PR #1865 **MERGED** by Surendra (merge 9025af4e, 22:07:37 IST, head b3aa5828, CI 10/10 green — 8 success, 2 skipped, verified first-hand via check-runs). Board on main a759a031 verified first-hand (§2): IG-INF-01-FIX-01 → MERGED. No stall — progress real; the merge is the state change this run.
- **Hub read:** WATCH107 (7167935280, ~22:07 IST) + WATCH108 (7168661479, ~22:20 IST) read in full; no new M13 directive. WATCH108 confirms #1865 merged + board PR #1874 open (7 MERGED flips incl. IG-INF-01-FIX-01; merged since — main now a759a031). Page 17 of hub comments empty — nothing newer than 7168967199.
- **Claim:** INT-053 per board next_action (reached queue head: IG-INF-01-FIX-01 merged, live leg blocked on clearance). Claim + MERGED status + deployment-clearance request posted on #1483, comment 7169108662.
- **Branch:** `muse13/task-int-053-synthesis-fix` @ main a759a031 (Git Data API, verified read-back).
- Usage: 39% of free weekly limit (last verified 20:36 IST), reset Nov 29 6:09 PM IST. No subscription.

— Muse 13
