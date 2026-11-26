# TASK-MEM-017 — Cross-session recall: final seed facts, negative control, decision table (checkpoint 3)

**Date:** 2026-11-26 ~07:2x IST (Muse TP3)
**Status:** REPO-SIDE ONLY. Zero live runs attempted (0/3). Live leg gated.
**Branch:** `musetp3/task-mem-017-cross-session-recall`
(checkpoint 1: `bf744af6`; checkpoint 2: `3bfe7b48`)
**Board:** TASK-MEM-017 AVAILABLE / owner muse_tp3 / P2 (verified on main
`4dda14b1`, board blob `a0e5edaf`, 23,404 lines).
**Builds on:** `TASK-MEM-017-CROSS-SESSION-RECALL-PREP.md` (checkpoint 1),
`TASK-MEM-017-CROSS-SESSION-RECALL-HARNESS.md` (checkpoint 2).

Checkpoint 2 fixed the phrasing shape and trace template. This
checkpoint fixes the concrete content: the three run-unique seed
facts, the negative control, the session-boundary rules, and the
failure decision table — so the live leg (when cleared) is execution,
not design.

## 1. Final seed facts (one per run, never repeated)

Each seed is a full sentence, one fact, no other content (checkpoint
2, §2). Each fact carries an invented token that cannot be guessed
from context. Absence verified 2026-11-26, before filing: GitHub code
search over `surendra2304/FRIDAY-Universe` returns 0 hits for each
token, and the board (`WORK_BOARD.yaml`, blob `a0e5edaf`) contains 0
hits for each token. Re-verify immediately before the live runs (§5,
step 2) — a token that has entered the repo or a prior memory by run
day invalidates that run's fact and it must be replaced.

| Run | Seed utterance (Session A, verbatim) | Probe (Session B, verbatim) | Invented token |
|-----|--------------------------------------|-----------------------------|----------------|
| 1 | "Please remember this for me. The project codename for the winter audit is Quillfen Harbor." | "What did I ask you to remember about the project codename for the winter audit?" | Quillfen |
| 2 | "Please remember this for me. My dentist appointment with Dr. Zarnwick is on the 14th of March at 9:40 in the morning." | "What did I ask you to remember about my dentist appointment?" | Zarnwick |
| 3 | "Please remember this for me. My favourite herb for winter tea is brazelwort." | "What did I ask you to remember about my favourite herb for winter tea?" | brazelwort |

Pass requires **both** halves (checkpoint 2, §2–3): the answer
contains the seeded content **and** cites it as recalled, **and** the
traces match — Memora write trace (memory id) from Session A and
Memora read trace (hit count ≥ 1, top hit id = the Session A id) in
Session B. The trace requirement is what makes filing these facts in
this repo document harmless: an answer sourced from anywhere other
than the Session A memory (including this file) has no matching
write/read trace pair and fails by trace, whatever its text says.

## 2. Negative control (once, before run 1)

- Probe (new session, nothing seeded on this topic, ever):
  "What did I ask you to remember about my boat's registration
  number?"
- **Pass:** FRIDAY says she does not know / has no record of it. A
  hedged "I don't have that" is a pass. The Memora read trace should
  show 0 hits (or hits that plainly do not answer the question).
- **Fail (whole sequence stops before run 1):** any confident
  invented registration number, or any answer presenting invented
  content as recalled. A fail here is filed as the finding — the
  three-run sequence does not start until the fabrication cause is
  named (retrieval vs generation vs citation behaviour).
- The control topic is never seeded in any run. If a later run needs
  a second control, use a fresh never-seeded topic, not this one
  again (a repeated control can be memorised as a control).

## 3. Session-boundary + contamination rules

- Session B must be a new conversation with a different conversation
  id from Session A (trace template, checkpoint 2, §3). Same-session
  recall proves nothing about cross-session memory.
- Between seed and probe: no other memory-write turns in either
  session, no restatement of the fact by the operator, no probe
  wording that contains the fact (topic only, per §1).
- Control session (`fcs1`, checkpoint 1, §3) may span A and B —
  that is the auth surface, not the memory surface. Traces record
  that a control session existed, never the key or token value. The
  owner key is pasted by the owner only; TP3 never asks for,
  receives, or records it.
- Run order is control → run 1 → run 2 → run 3, back-to-back in one
  cleared window if the window allows; if split across windows, the
  consecutive count still requires three passing runs with no
  intervening fabricated recall (checkpoint 1, §3). Any wrong or
  fabricated recall resets the count to 0.

## 4. Failure decision table (name the layer, never retry blind)

| Observation | Layer | Evidence to record | Count effect |
|-------------|-------|--------------------|--------------|
| 401 at `POST /api/chat` | Control gate / session TTL (FRD-038 surface) | Status + detail string; whether `fcs1` session was live | Run void (not a recall verdict); fix auth, re-run control |
| 401/5xx at Memora write or read | Memora auth/service | Status; HMAC/log check; cursor endpoint state | Run void; name cause before any retry |
| Write OK, read 0 hits, FRIDAY says she doesn't know | Retrieval miss (incl. BRAIN-002 silent-empty guard) | Write id; read hit count 0; verbatim answer | Miss — run fails, count resets only if a prior pass is being counted consecutively (a miss breaks consecutiveness) |
| Read hit present, answer correct but uncited | Citation behaviour (FRD-006 attribution rule) | Hit id; verbatim answer; citation Y/N = N | Fail — acceptance requires cited recall |
| Answer contains wrong/invented content presented as recalled | Fabrication | Verbatim answer; read trace (hit or no hit) | FAIL + count resets to 0 (board acceptance) |
| Answer correct, cited, traces match (write id = read top hit) | — | Full trace block | Pass |

## 5. Pre-run checklist (execute in order on clearance)

1. Confirm Muse clearance on #1483 covers: FRD-038 fix deployed on
   Server 1 + live chat runs. No deploy, restart, or live run
   without it (stop order in force, WATCH129–131).
2. Re-verify token absence (code search + board grep for Quillfen,
   Zarnwick, brazelwort). Replace any token now present; record the
   check in the work PR.
3. Memora health: cursor endpoint 200, zero 401s in window (bridge
   logs). Record the window.
4. Negative control (§2). Stop on fail.
5. Runs 1–3 (§1, §3), one trace block each (checkpoint 2, §3),
   verdicts per §4. Paired verifier (owner rule 3) checks traces
   independently before any completion claim.
6. File traces + verdicts in the work PR (owner rule 2: completion
   = 3 consecutive passing live runs with traces; merged FRD-038
   code does not count toward the 3).

## 6. Gates (unchanged)

- Owner stop order in force; no deploy, no service restart, no live
  chat run without Muse clearance on #1483. Main CI on `4dda14b1`
  still shows Deploy Core/Specialist Fleet FAILED — broken-CD state,
  coordinator-owned; nothing here touches the fleet.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per
  owner rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 3
