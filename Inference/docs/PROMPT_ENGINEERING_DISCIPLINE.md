# Prompt-Engineering Discipline (TASK-IG-INF-06)

Corpus source Dd1MCKhhp3Y: an explainer on how much of what looks
like "the model" is actually its system prompt — the instructed
behaviour layer — versus the underlying model. The lane idea:
**treat prompts as the behaviour layer when tuning FRIDAY/Inference
personas.** This document makes that a working discipline for
Inference, with FRIDAY's surfaces following the same rules.

## Why this is load-bearing here, specifically

Behaviour = model × prompt. In this fleet the model factor is
deliberately unstable: pooled free tiers churn, quotas die, and
REL-043/REL-049 exist precisely because *which model serves* changes
under us. The prompt factor is the one layer we fully control — and
today it is the least engineered layer we have:

- Prompts live scattered: the ASTRA persona profile
  (`app/core/astra_profile.py`), agent role definitions
  (`app/agents/roles/`, `app/agents/deliberation_engine.py`,
  specialist agents), and inline strings across route modules.
- None of them carries a version, a changelog, or a recorded
  before/after measurement. A prompt can be edited in a PR about
  something else and silently change every answer a surface gives.

Models are admitted to the catalogue only on benchmark evidence
(INF-005, TASK-IG-INF-03). Prompts get the same standard.

## The rules

**R1 — Prompts are versioned artefacts.** Every production prompt
(persona profile, role definition, route-level system prompt) has an
id and a version (e.g. `astra-core v3`), bumped on every change and
recorded in the changelog below. A prompt change ships as its own
PR, or as a clearly separated commit in a larger PR — never as an
unlabelled side edit, and never as a live edit on a server.

**R2 — One behaviour claim per change.** The PR states, in one
sentence, the behaviour delta it intends ("shorter first answers",
"stops volunteering code unless asked"). If the delta can't be
stated, the change isn't ready — an unstated delta can't be benched.

**R3 — Bench before/after, or it doesn't merge.** Before the change
and after it, run (a) the fixed INF-005 bench (benchmarks/testset.json)
for any gateway-visible surface, and (b) the surface's own frozen
prompt set — a small, checked-in list of representative prompts with
deterministic checks where the behaviour allows it (format, length
caps, required/refused content), human-scored only where it doesn't.
Both scores go in the PR. A regression in any category needs an
explicit justification in the PR, not a shrug.

**R4 — Verify as-served, on the models that will actually serve.**
Routing substitutes models (REL-043), and a prompt tuned against one
model can behave differently on its substitute. Before/after runs
must record the served model per call (the INF-005 lesson: a result
is evidence only when served_model is known) and must cover the
top-2 likely serving models for the surface.

**R5 — Code is the source of truth.** Configuration may *select* a
prompt version; it may not rewrite prompt text. No prompt text in
server env files, no hot-patching prompts on a live service. If it
isn't in git, it doesn't run.

**R6 — Security prompts are not persona prompts.**
`app/security/prompt_isolation.py` and the prompt-guard components
are security controls. They change only with a security-focused
review and their existing regression suites green
(e.g. `tests/test_advanced_prompt_guard.py`) — never as part of
persona tuning, and R3's quality benches do not substitute for
their security tests.

**R7 — Rollback is a revert.** The changelog names the previous
version for every change, so rollback is unambiguous: revert the
prompt PR, redeploy, done. No forward-fixing a bad prompt under
time pressure without re-running R3.

## Changelog

| Date | Prompt id | Version | Change | Bench before → after | PR |
|---|---|---|---|---|---|
| 2026-11-15 | astra-core (app/core/astra_profile.py) | baseline | Pre-discipline state; never benched as a prompt | — | — |
| 2026-11-15 | deliberation roles (app/agents/roles/, deliberation_engine.py) | baseline | Pre-discipline state; never benched as prompts | — | — |
| 2026-11-15 | route-inline system prompts (app/api/*) | baseline | Pre-discipline state; inventory in R1 order is the first follow-up | — | — |

"Baseline" is stated honestly: these prompts work in production,
but their current wording was never itself admitted on evidence.
The first change to any of them runs the full R1–R7 path and
replaces its baseline row with a measured one.

## Worked example (the shape every prompt PR should take)

Change: `astra-core v3 → v4`, "first answers get shorter; detail
moves behind follow-up". Before: INF-005 bench overall X, astra
prompt-set (12 frozen prompts) length-cap checks 9/12. After: bench
X±, length-cap checks 12/12, served-model recorded for both runs
(gpt-oss-120b and qwen3.8-27b). One regression (extract category
−0.1) justified in the PR as the intended brevity trade. Rollback
target: v3. That is the whole ceremony — an hour of measurement
around a five-line text change, which is exactly the proportion the
behaviour layer deserves.
