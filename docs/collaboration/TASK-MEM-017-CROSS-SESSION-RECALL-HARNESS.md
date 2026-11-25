# TASK-MEM-017 — Cross-session recall: harness alignment + trace template (checkpoint 2)

**Date:** 2026-11-26 ~05:2x IST (Muse TP3)
**Status:** REPO-SIDE ONLY. Zero live runs attempted (0/3). Live leg gated.
**Branch:** `musetp3/task-mem-017-cross-session-recall` (checkpoint 1: `bf744af6`)
**Board:** TASK-MEM-017 AVAILABLE / owner muse_tp3 / P2 (verified on main
`8600d3e4`, board blob `153ac2fe`).
**Builds on:** `TASK-MEM-017-CROSS-SESSION-RECALL-PREP.md` (checkpoint 1).

## 1. What the existing tests actually prove (read at main `8600d3e4`)

Checkpoint 1 named three test files. Read first-hand this checkpoint:

- **`FRIDAY/tests/test_multiturn_memora_friday.py`** (185 lines) — the
  name promises Memora multi-turn recall; the content is in-process
  unit tests for confirmation context and device directives
  (`GoalUnderstandingEngine`, `CognitiveIntelligenceEngine`,
  `windows_friday.handle_directive`), with `execute_complex_task`
  mocked. It never writes to or reads from Memora, and never crosses a
  session boundary. **It does not exercise the MEM-017 acceptance at
  all.** Useful only as phrasing precedent: bare affirmations ("yes",
  "ok") are ambiguous without a pending action — seed/probe turns in
  the live runs must be full sentences, never bare tokens.
- **`FRIDAY/tests/test_memora_recall_guard.py`** (56 lines, TASK-BRAIN-002)
  — pins the production crash guard: `MemoraClient.recall_memories` /
  `recall_experience` with the Oracle local fallback
  (`local_db_path is None`) must fall back instead of raising
  `TypeError`, and a local failure surfaces as an **empty list, not a
  crash**. Live-run implication: a recall miss can be silent. The
  traces must record the Memora read result count so a silent-empty
  miss is distinguishable from a fabricated answer (miss = retrieval
  failure; fabricated = FAIL + count reset).
- **`FRIDAY/tests/test_fleet_memory_recall.py`** (407 lines, TASK-FRD-006)
  — in-process mesh contract harness: the `memory_recall` envelope is
  addressed only to Memora (the peer declaring the action); other peers
  are `skipped` with reasons. The file states plainly that live Memora
  behaviour is CONFIGURED-BUT-UNVERIFIED on that host. Its protected
  rule — a recalled memory is knowledge, not work; it names its source
  peer and verification state — matches MEM-017's citation requirement:
  FRIDAY's answer must cite the recalled content, not just use it.

**Conclusion:** no existing test proves the MEM-017 acceptance (three
consecutive live cross-session runs through FRIDAY with cited recall).
The checkpoint-1 run protocol stands unchanged. This checkpoint aligns
phrasing and files the trace template.

## 2. Seed/probe phrasing (aligned, contamination-safe)

Shape follows the FRD-005 battery's memory turns
(`FRIDAY/voice_acceptance/battery.json`: "Please remember this for
me…" / "What is my favourite colour?") but the seeded fact is
**run-unique** — reusing "teal" would let a prior memory (or the
battery itself) fake a pass.

- Session A (seed, full sentence, one fact, no other content):
  "Please remember this for me. [RUN-UNIQUE FACT]."
  Fact pool (one per run, never repeated): a made-up codename, a
  fictional appointment, an invented preference with a rare word.
  The fact must be unguessable from context and absent from the repo.
- Session B (probe, new conversation, no leakage of the fact):
  "What did I ask you to remember about [TOPIC]?" — topic named, fact
  not. A correct answer must contain the seeded content **and cite it
  as recalled** (per acceptance + FRD-006 attribution rule).
- Negative control (once, before run 1): probe a topic never seeded.
  FRIDAY must say she does not know. A confident invented answer here
  fails the whole sequence before it starts.

## 3. Trace template (one block per run, filed in the work PR)

| Field | Run 1 | Run 2 | Run 3 |
|-------|-------|-------|-------|
| Seed utterance + timestamp (IST) | | | |
| Session A id / conversation id | | | |
| Memora write trace (memory id, status) | | | |
| Control session established (fcs1, no key recorded) | | | |
| Session B id (must differ from A) | | | |
| Probe utterance + timestamp (IST) | | | |
| Memora read trace (hit count, top hit id) | | | |
| FRIDAY answer (verbatim) | | | |
| Citation present? (Y/N) | | | |
| Verdict (pass / miss / fabricated → reset) | | | |

Per-run rules (checkpoint 1, §3, restated as checklist):

1. FRD-038 fix deployed on Server 1 — fleet CD broken + stop order;
   deploy needs Muse clearance. Loopback-only checks do not prove
   the remote path.
2. Memora healthy in the run window: cursor endpoint 200, zero 401s
   (bridge logs). Name the failing layer on any error (control gate
   vs Memora auth vs retrieval vs fabrication) — never retry blind.
3. Silent-empty read (BRAIN-002 guard) counts as a miss, recorded as
   such; it is not a pass and not a fabrication.
4. Any wrong or fabricated recall resets the consecutive count to 0.

## 4. Gates (unchanged from checkpoint 1)

- Owner stop order in force; no deploy, no service restart, no live
  chat run without Muse clearance on #1483 (WATCH125: no lift).
  Main CI on `8600d3e4` shows Deploy Core/Specialist Fleet FAILED —
  consistent with the broken-CD state; nothing here touches the fleet.
- The owner key is pasted by the owner only; TP3 never asks for,
  receives, or records it. Traces record that a control session
  existed, never the key or token value.
- Completion = 3 consecutive passing live runs with traces in the
  work PR (owner rule 2). Merged code (FRD-038, PR #1535) does not
  count toward the 3. Paired verifier per owner rule 3.

## 5. Next

- Live leg: clearance request stands (hub 7176775065). On clearance:
  negative control first, then runs 1–3 back-to-back with the
  template above; traces + verdicts filed in the work PR.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per
  owner rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 2
