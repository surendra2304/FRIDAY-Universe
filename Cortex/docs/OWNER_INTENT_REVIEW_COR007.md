# TASK-COR-007 — Owner-Intent Interpretation Review

**Question.** When an ambiguous, shorthand, owner-style request reaches
Cortex's goal decomposition (`POST /plan`, `POST /decompose`), does
Cortex read it the way the owner means it — resolve the right governed
operation, refuse honestly what it cannot serve, and never fire an
action the owner forbade?

**Method.** A 36-case test set (`Cortex/tests/unit/test_owner_intent.py`,
cases also in `results_cor007/` working papers) written *before* scoring,
in seven categories: clear in-domain shorthand (A), ambiguous in-domain
(B), out-of-domain owner shorthand (C), negations/stop commands (D),
typos/truncations (E), multi-intent bundles (F), high-impact phrasing
where approval gates are mandatory (G). Ground truth is Cortex's own
governed-operation vocabulary and impact classes; verdicts are
PASS / ACCEPTABLE / FAIL / WORST (dangerous misread: intent inversion,
firing a forbidden action, or a high-impact plan with no approval gate).
Each case was executed against the real planner code — no hand-scoring.

## Scores

| Planner | PASS | ACCEPTABLE | FAIL | WORST | Correct-or-acceptable |
|---|---|---|---|---|---|
| Template planner (pre-COR-005 `main.py`) | 0 | 0 | 17 | 19 | **0/36** |
| COR-005 `cognitive_planner` 1.0.0 | 23 | 4 | 3 | 6 | **27/36** |
| COR-005 planner + COR-007 fixes | 28 | 5 | 0 | 3* | **33/36** |

\* The 3 remaining WORST are one repeated pattern, not three different
defects: rollback now resolves to the *correct* operation but carries
no approval-gate step (see "Reported, not forced" below). Dangerous
misreads after the fix: **0**.

The template planner is what the old Server-2 checkout serves and what
COR-005 reviewed qualitatively; this set quantifies it: it returns the
same 3-step execution-shaped decomposition for *every* request —
including "don't publish anything yet" and "make stratex profitable" —
with no refusal path and no gates. 0/36.

## The six dangerous misreads in the COR-005 planner (all fixed)

All six live in the goal-keyword layer of `_resolve_operation`
(substring first-match, no context guards):

1. **A3 — intent inversion.** "roll back the last deploy" resolved to
   `page_deploy`, because `"deploy"` precedes `"roll back"` in the
   keyword list and first match wins. The owner ordered an undo; the
   planner planned the opposite.
2. **C3 — cross-domain claim.** "publish the video" resolved to
   `content_publish` (website content). Video publishing is VyralX's
   domain; Cortex would have planned a site operation for a video ask.
3. **D1 — negation fired.** "don't publish anything yet" →
   `content_publish`: the exact action the owner forbade.
4. **D2 — stop fired.** "stop the email campaign" → `email_dispatch`:
   the campaign the owner ordered stopped was planned for dispatch.
5. **D3 — prohibition fired.** "never send email to them again" →
   `email_dispatch`.
6. **D4 — prohibition fired.** "do not change the price" →
   `pricing_change`.

## Fixes shipped in this task (keyword layer only, ~25 lines)

* **Negation guard** — a goal containing `don't / do not / never / stop`
  never resolves via keywords; it degrades honestly to
  `plannable=False`. Fixes D1–D4.
* **Video-context guard** — a goal mentioning `video / youtube / short(s)
  / reel(s)` never resolves to a site operation. Fixes C3.
* **Rollback precedence** — `roll back / rollback / undo` are matched
  before `deploy / publish`. Fixes A3 (and A4, "undo that change",
  previously unresolved).
* **Three shorthand keywords** the owner actually types:
  `site health` → health_summary (A1), `undo` → rollback (A4),
  `change all the prices` → pricing_change (G2).

Re-scored after the fix: **28 PASS / 5 ACCEPTABLE / 0 FAIL**, dangerous
misreads **0**. The shipped pytest module
(`Cortex/tests/unit/test_owner_intent.py`, 41 tests) passes **41/41**
against the patched planner and fails **10** against the unpatched
1.0.0 planner (the 9 bad resolutions + G2's gate test). COR-005's own
unit suite against the patched planner: **14 passed, 1 skipped —
identical to the unpatched baseline** (no regression). The remaining
FAILs before the fix were honest refusals (A1, A4, G2), not misreads;
all three now resolve correctly.

## Reported, not forced (larger design questions)

* **Rollback/cancel carry no approval gate in either planner
  generation.** The governed executor classes them as DIRECT actions,
  so `build_plan` never adds `await_supervisor_approval` — yet
  "roll back the last deploy" against production is exactly the kind
  of act the gate exists for. Whether task-level rollback is safe
  ungated is an executor-design decision (COR-002/COR-005 territory);
  this task flags it and does not change executor semantics.
* **Multi-intent bundles lose intents silently.** The resolver is
  single-operation by design: "check health and send the email
  campaign" plans only one half (F1 resolved to the gated
  email_dispatch; the health half vanished without a note). A
  multi-operation split belongs with COR-005's noted follow-up
  (multi-operation goal splitting), not in a keyword patch.
* **Goal-text "production" does not trigger the Sentinel gate.** The
  gate step appears only when `context.environment == "production"`;
  "deploy it to production now" (G3) got its approval gate but no
  Sentinel step. Callers that forward owner text without context
  should know the gate is context-driven, not goal-driven.

## Honest limits of this test set

* Scoring ran against the planner *code* (both generations), executed
  locally — not against the live Server-2 HTTP service, whose checkout
  predates both (the plan endpoints had zero production calls in the
  journal COR-005 reviewed, so there is no live traffic to sample).
* 36 cases is a focused set, not a corpus; categories D and A carry
  the safety weight by design. The set is shipped as a pytest module
  so it can grow and run in CI against future planner changes.
* Cases where reasonable readers disagree (B1 "cancel it" resolving
  to `cancel`; C8 personal-contacts email resolving to the governed
  campaign op) are scored ACCEPTABLE and named here rather than
  hidden in the tally.
