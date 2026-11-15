# RESULTS — TASK-INT-009: IntelX verification pass (live-research path)

**Date:** 2026-11-15 · **Crew:** muse_ai (Muse, Wave 5 — IntelX truthfulness) ·
**Coordinator:** Muse (lead) · **Status:** implemented + tested locally; PR open
for coordinator merge; NOT deployed; NOT production-verified.

## Origin

TASK-INT-005's fact-check (PR #325,
`IntelX/docs/RESULTS_INT-005_FACT_CHECK.md`) measured IntelX's stored live
research at **65.7% VERIFIED (23/35 claims)** against a pre-declared ≥90%
standard (the original crew's claims-only census read 88.9%, 24/27 — same
defect classes, smaller population). Zero fabricated facts, zero contradicted
claims; every defect was citation hygiene: quotes not verbatim, claims
extending beyond their quote, page boilerplate counted as findings,
single-source claims unflagged. RESULTS §6 specified the remediation
implemented here.

**Adopted base.** The original INT-005 crew had independently built and
tested a verification pass (staged in their workspace, never shipped). This
task adopted it as the base — `statement_support` entailment screen in
`synthesize_grounded`, the page-chrome filter in `collect_live_brief`, their
8 tests, and their audit doc — re-verified it in this clone (8/8 pass), and
implemented only the gaps below. Nothing was re-implemented from scratch.

## The Bruker lesson (drives gap 1)

Coordinator-verified live on 2026-11-15: the stored Bruker claim's quote does
**not** exist on the live cited page (the page contains no
operando/battery/supercapacitor content at all), yet the run recorded
`quotes_verified=true` — because the quote gate checked the quote against the
**fetched snapshot**, not against the source as it can be retrieved. A gate
that only ever sees its own snapshot cannot catch snapshot-vs-live
divergence. This pass treats that divergence as a first-class failure mode.

## What shipped, gate by gate (RESULTS §6)

1. **Verbatim quote gate + live re-verification** (`live_research_task.py`,
   `grounded_live_research.py`). The pre-existing gate (quote must appear
   verbatim, whitespace-normalised, in the synthesis snapshot) is unchanged.
   New: after a successful synthesis, every cited URL is **re-fetched live**
   through the same fetch connector and each synthesized finding's quote is
   re-checked against the freshly retrieved page text
   (`reverify_findings_against_texts`). A finding whose quote is absent from
   the live page is downgraded with reason `quote_not_in_live_source`; a
   finding whose source cannot be re-retrieved is downgraded with
   `quote_reverification_unavailable` — **fail-closed: unverifiable never
   passes**. Partial downgrade: surviving findings ship with
   `quotes_verified=false`, the downgraded findings are preserved in the
   payload under `downgraded_findings`, and a `live_reverification` summary
   `{checked, kept, downgraded}` is recorded. Total downgrade: the brief
   falls back to the unsynthesised extractive findings with
   `synthesis_failure.reason = quote_live_reverification_failed` and status
   DEGRADED — the same honest shape REL-016 established for synthesis
   failure. Kept findings carry `live_quote_reverified=true`.
2. **Coverage check.** The crew's deterministic entailment screen
   (`statement_support`: every number in the statement must appear in the
   cited source text; capitalised named entities must appear; ≥80% of
   content words must be covered) runs inside `synthesize_grounded` and
   fails closed (`synthesis_entailment_unverified`); `semantic_entailment_verified`
   is now set truthfully and per-finding `quote_verified` /
   `entailment_verified` flags are emitted. **On reuse of
   `intelx/core/citation_integrity.py`:** that module was **not on main**
   when this pass was built — it existed only in the INT-008 crew's
   workspace. (INT-008 has since completed crew-side as PR #349; the module
   lands when the coordinator merges it.) This
   PR deliberately does **not** duplicate `check_claims` and does **not**
   stack on INT-008's unmerged branch. Mapping: live-research path coverage
   = `statement_support` (here); stored claims/evidence path coverage =
   INT-008's `check_claims` wiring (theirs). When INT-008 lands, the two
   coverage implementations should be reconciled behind one import.
3. **Boilerplate filter.** Page chrome (skip-links, breadcrumbs, bare page
   titles) can no longer become a finding: the predicate now lives in one
   place — `is_boilerplate_text()` in `grounded_live_research.py` — and the
   collector's filter delegates to it. In audit output, boilerplate is
   classified `NON_CLAIM` / verdict `BOILERPLATE` and **excluded from the
   accuracy denominator** (see the re-audit hook's partition).
4. **Corroboration flag.** Synthesized findings carry `single_source: true`
   (live synthesis is single-source per finding by construction — each
   finding cites exactly one source); extractive findings carry
   `single_source: true` and `independently_verified: false`. The flag is
   disclosure, not verification: nothing in this pass manufactures
   corroboration.
5. **Re-audit hook.** New `IntelX/scripts/reaudit_live_research.py`
   (SELECT-only, same conventions as INT-008's audit script): loads stored
   `live_research_runs`, re-fetches every cited URL **live**, classifies
   each stored finding via `reaudit_finding()` — VERIFIED (quote present in
   the live page **and** coverage screen passes), PARTIAL (quote present,
   coverage fails), UNSUPPORTED (quote absent from the live page — the
   Bruker mode), UNVERIFIABLE (source not retrievable now), NON_CLAIM
   (boilerplate) — and reports the AFTER partition
   `{grounded, downgraded, excluded_boilerplate, unverifiable}` plus the
   verified share of claims against the 0.90 standard. It also surfaces each
   run's **stored** `quotes_verified` next to the live verdict, so a stored
   `true` that no longer re-verifies is visible at a glance. Scope note
   printed in its output: corroboration and contradiction are **not**
   mechanically assessed by the hook.

## Test evidence (this clone, venv interpreter, 2026-11-15)

- Adopted crew tests `tests/test_int005_verification_pass.py`: **8/8 pass**.
- New gap tests `tests/test_int009_verification_gaps.py`: **14/14 pass** —
  reverify keep / Bruker-downgrade / unverifiable-downgrade; re-audit
  boilerplate / Bruker-UNSUPPORTED / UNVERIFIABLE / VERIFIED+single_source /
  coverage-PARTIAL; pipeline integration: happy path (kept, `quotes_verified`
  stays true), diverged live page (total downgrade → DEGRADED +
  unsynthesised fallback), fetch-failure downgrade, two-source partial
  downgrade (kept findings ship, `quotes_verified=false`, partition
  recorded); extractive flags; re-audit script import smoke.
- Neighbour ring (`tests/test_rel038_intelx_honesty_persistence.py` +
  `tests/test_citation_validation.py`): **20 passed**, identical to the
  pristine-main baseline (20 passed) measured before any edit — no
  regressions. (Tests run under the INT-008 crew's venv interpreter; the
  sandbox system python lacks `prometheus_client`.)

## Limits, stated plainly

- Brief-time re-verification compares the synthesis snapshot with a **fresh
  retrieval seconds later**. It catches redirect-target drift, changed
  pages, and wrong-document synthesis; it cannot prove what the page
  contained at the original fetch instant. Stored-claim drift over time is
  the re-audit hook's job.
- `statement_support` is a deterministic screen, not an entailment model:
  it catches number/entity drift and topic drift, not subtle paraphrase
  overreach. The INT-005 audit's two PARTIAL claims are the class it
  targets; it will not catch every member of that class.
- The re-audit hook has **not** been run against production (bridge/DB
  access is a coordinator step post-merge). The BEFORE partition is
  INT-005's: 23/35 VERIFIED (65.7%).
- Overlap: PR #322 (TASK-INT-003) also edits `live_research_task.py`
  (candidate-supply hunks — disjoint regions from this PR's chrome /
  DocumentText / re-verification hunks). Whichever lands second rebases.

## Addendum — INT-008's production finding (2026-11-15, after this work was built)

TASK-INT-008 (PR #349) completed crew-side and its production audit found
IntelX's seven research tables (`research_runs`, `sources`, `documents`,
`chunks`, `claims`, `evidence`, `findings`) **all empty** in the production
Oracle store — IntelX has never persisted a run on that path. This is
consistent with INT-005's census (its population was `live_research_runs`)
and it does **not** change this pass's design, which never depended on
those tables:

- The coverage screen runs **inside live synthesis** (`synthesize_grounded`),
  before anything is stored.
- Live re-verification runs **inside the live brief pipeline**, on the
  findings being shipped in that request.
- The re-audit hook reads **`live_research_runs`** — the live-run store the
  router actually persists to via `live_research_store.persist_live_research`
  — not the claims/evidence tables. There is no stored claims corpus to
  re-audit; the hook's corpus is the live-run history (9 runs at INT-005
  census time, all crew acceptance probes).

**Persistence evidence for TASK-INT-010** (noted, not investigated — their
scope): the live route (`router.py` → `collect_live_brief`) does call
`persist_live_research`, and `live_research_runs` rows exist in production,
so the live path persists; the seven empty tables belong to a separate
research path that the live route never writes to.

## Five states

Implemented ✔ · Tested ✔ (22 pass + ring at baseline) · Merged ✘
(coordinator) · Deployed ✘ · Production-verified ✘ — owed post-merge:
deploy via Fleet CD, run `scripts/reaudit_live_research.py` against
production for the AFTER partition, then flip the board entry VERIFIED.
