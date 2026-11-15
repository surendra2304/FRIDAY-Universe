# TASK-INT-005 — IntelX Fact-Check Sampling: RESULTS

**Headline: IntelX's stored research claims measure 65.7% VERIFIED accuracy (23 of 35 claims fully verified; 10 PARTIAL, 2 UNVERIFIABLE, 0 UNSUPPORTED, 0 CONTRADICTED) — below the pre-declared standard of ≥90% VERIFIED with zero CONTRADICTED, so a verification pass in the research pipeline is required (specified in §6, board-tracked as this task's next action).** The census covered **all 39 findings** stored in IntelX production (10 `live_research_runs`, 2026-11-14/15) — not a sample, because the frozen methodology's census rule (≤40 findings → verify all) applied after the production `claims`/`evidence` tables were found empty and the population was redefined, before any verification, as all stored run findings. Limits, stated up front: (1) the population is small and **dominated by AI-crew test probes** — 8 of 10 runs are REL-038/INT-003 measurement traffic from 2026-11-14/15 and only 2 are task-driven runs, so this measures the pipeline's stored output on probe traffic, not a mature user-research corpus; (2) live page fetching (`browser.open`) failed for five of six checker crews (browser-service error — a tool failure, not a source failure), so for those batches quote alignment was assessed against the search index's full-text copies of the cited pages themselves, which is weaker evidence than a live fetch for two CrowdStrike quotes (marked PARTIAL, re-checkable) and impossible for one unreachable Northwell page (2 claims honestly UNVERIFIABLE); (3) 18 of 39 findings come from two DEGRADED runs that stored raw source excerpts instead of synthesised claims. Full per-claim evidence: `IntelX/docs/results_int-005_fact_check.json`.

## 1. Population and provenance

Production IntelX's `claims`, `evidence`, `sources`, `documents` and `findings` tables are **empty (0 rows each)** — verified by direct read-only probes. All stored research lives in the `findings` arrays of `live_research_runs`. The 10 runs:

| Run | Task | Query topic | Findings |
|---|---|---|---|
| lr_82249cc2… | rel038_live_probe | solid-state batteries | 3 |
| lr_5e94778f… | rel038_final_probe | quantum error correction | 3 |
| lr_7e6ecb79… | task_1408370e0a65 | solid-state battery summary | 3 |
| lr_d0601f5a… | int003_before_* | NASA Artemis II (DEGRADED) | 0 |
| lr_62053357… | int003_before_* | solid-state batteries | 3 |
| lr_5cd766e6… | int003_before_* | WHO aspartame safety | 3 |
| lr_948f7587… | int003_before_* | intermittent fasting (DEGRADED, raw excerpts) | 12 |
| lr_f21218f8… | int003_before_* | fusion energy (DEGRADED, raw excerpts) | 6 |
| lr_6e43c410… | int003_before_* | CrowdStrike July 2024 outage | 3 |
| lr_a619c40a… | task_c168bd737fcd | one recent AI headline | 3 |

Every stored finding carries `independently_verified` = false/null. Classification (frozen rule): 35 findings are CLAIMs (factual assertions; verbatim source excerpts count — their assertion is "the source says X"); 4 are NON_CLAIMs (page titles / navigation strings, all in the DEGRADED fasting run), counted and disclosed, excluded from the accuracy denominator, and also reported as their own quality metric: **10.3% of everything IntelX stored in degraded mode was page chrome, not content.**

## 2. Method

Per the frozen methodology (seed 20251115; census made the seed moot), each CLAIM was checked three ways: (1) **quote alignment** — does the stored supporting quote appear in the cited source? (2) **cited-source support** — does the cited source substantively support the statement as worded? (3) **independent corroboration** — does a source on a different domain confirm the substance? Verdicts: VERIFIED (all three pass), PARTIAL (one leg fails or is weakened), UNSUPPORTED (cited source does not support / quote misaligned), CONTRADICTED (credible source directly contradicts), UNVERIFIABLE (cited source unreachable and no independent check possible). Six parallel checker crews gathered evidence; verdicts were adjudicated uniformly by the finisher crew. Read-only against production throughout.

## 3. Results

| Verdict | Count (of 35 CLAIMs) | Share |
|---|---|---|
| VERIFIED | 23 | 65.7% |
| PARTIAL | 10 | 28.6% |
| UNVERIFIABLE | 2 | 5.7% |
| UNSUPPORTED | 0 | 0% |
| CONTRADICTED | 0 | 0% |

- **Accuracy (VERIFIED share of CLAIMs): 65.7%.** Counting NON_CLAIMs as failures over all findings: **59.0% (23/39).**
- **Standard: NOT MET.** The zero-CONTRADICTED leg holds; the ≥90% VERIFIED leg fails by a wide margin.
- The single most important qualitative finding: **no fabricated facts were found anywhere.** Every PARTIAL is a citation-hygiene, coverage, or corroboration defect — the pipeline's facts are sound; its citation discipline is not.

## 4. Per-claim verdicts (evidence detail in the JSON)

| ID | Run topic | Verdict | One-line basis |
|---|---|---|---|
| R0F1 | SSB electrolytes | VERIFIED | Quote verbatim; MDPI corroborates |
| R0F2 | UT Dallas space charge layer | VERIFIED | Quote verbatim; primary ACS paper corroborates |
| R0F3 | Bruker NMR probes | PARTIAL | Stored quote inserts "/operando" not in the source sentence |
| R1F1 | Quantinuum Helios 99.9995% | VERIFIED | Quote verbatim in release; independently reported |
| R1F2 | Google Willow below-threshold | VERIFIED | Quote verbatim on cited page; Springer corroborates |
| R1F3 | Threshold theorem 1997–98 | VERIFIED | Quote verbatim on cited page; corroborated |
| R2F1 | SSB "production in 2026" | PARTIAL | Quote unconfirmed on cited site; stronger sources say pilot-stage |
| R2F2 | Zr-halide 1.78 mS/cm | PARTIAL | Fact exact in primary paper; stored quote not locatable on cited page |
| R2F3 | SSB >500 Wh/kg, safety | VERIFIED | Quote verbatim; corroborated |
| R4F1 | MPI dendrite hydrostatic stress | VERIFIED | Quote verbatim in source release; Nature paper corroborates |
| R4F2 | Samsung SDI 2027 / 40% density | PARTIAL | Cited page supports only the 2027 target; details corroborated elsewhere |
| R4F3 | SSB not yet commercialised 2026 | VERIFIED | Quote verbatim; CATL reporting corroborates |
| R5F1 | IARC aspartame Group 2B | VERIFIED | Quote verbatim; BMJ corroborates |
| R5F2 | JECFA ADI 0–40 mg/kg | VERIFIED | Quote verbatim; BMJ corroborates |
| R5F3 | WHO "not a major concern" | VERIFIED | Core passage verbatim; corroborated |
| R6F1 | InsideTracker intro | VERIFIED | Excerpt verbatim; framing corroborated |
| R6F2 | Longo 2017 / NEJM 2019 reviews | VERIFIED | Excerpt verbatim; NEJM conclusion independently reproduced |
| R6F3 | IF benefits / mouse lifespan | VERIFIED | Excerpt verbatim; corroborated |
| R6F4–F6 | USC page titles / breadcrumb | NON_CLAIM | Boilerplate (F4/F5 title match confirmed; F6 breadcrumb prefix unverified) |
| R6F7 | IF heart-disease risk factors | VERIFIED | Excerpt verbatim; Harvard Health corroborates |
| R6F8 | IF & cancer: human data inconsistent | VERIFIED | Excerpt verbatim; corroborated |
| R6F9 | IF cancer prevention / chemo | PARTIAL | Animal half corroborated; chemo-benefit half unproven in 2025 reviews |
| R6F10 | Northwell 16:8 excerpt | UNVERIFIABLE | Cited page unreachable and unindexed |
| R6F11 | Northwell editorial closing | UNVERIFIABLE | Same retrieval failure (opinion excerpt) |
| R6F12 | Northwell page title + nav | NON_CLAIM | Boilerplate by content; exact title unverifiable (same failure) |
| R7F1 | Holdren introduction | PARTIAL | Genuine, aligned — author opinion, corroboration n/a |
| R7F2 | NIF 8.6 MJ record | VERIFIED | Verbatim; LLNL primary source corroborates |
| R7F3 | Problems beyond breakeven | PARTIAL | Genuine, aligned — expert judgement |
| R7F4 | NIF $3.5bn / LMJ 2014 | VERIFIED | Aligned via WNA text; both facts corroborated |
| R7F5 | Fusion powers the Sun | VERIFIED | Verbatim; corroborated |
| R7F6 | Sun gravity / ~4× fission | VERIFIED | Verbatim; corroborated |
| R8F1 | Channel File 291 logic error | PARTIAL | Corroborated; quote not confirmed verbatim via fallback |
| R8F2 | Kernel driver → BSOD | VERIFIED | Quote verbatim on cited page; corroborated |
| R8F3 | Outage consequences | PARTIAL | Disruption corroborated; quote not confirmed verbatim via fallback |
| R9F1 | OpenAI Erdős counterexample | PARTIAL | Quote verbatim and corroborated, but cited source attributes it to a third party and hedges; statement asserts flatly |
| R9F2 | Google Discover AI headlines | VERIFIED | Live-fetched; corroborated |
| R9F3 | 2022 ChatGPT / DALL-E 2 | VERIFIED | Live-fetched; corroborated |

## 5. Defect patterns

1. **Quote fidelity is not enforced.** One stored quote silently inserts a word (R0F3); one cannot be found on its cited page (R2F2); two more could not be confirmed verbatim with the available tooling (R8F1, R8F3). Runs r0/r2/r4 were stored with `quotes_verified=true` anyway — the pipeline's own quote check passed a quote that differs from its source.
2. **Statements outrun their citations.** A statement bundles a 40%-density figure and customer-feedback claim its cited page never mentions (R4F2); another drops its source's attribution and explicit skepticism, asserting as fact what the source presents as an unverified claim (R9F1).
3. **Internal framing tension.** R2F1 says solid-state batteries are "entering real-world production in 2026"; R4F3 says the market "has yet to reach scalability and commercialization." Both are defensible (pilot vs scaled), but a reader of either run alone gets opposite impressions.
4. **Degraded mode stores page chrome.** All 4 NON_CLAIMs — two page titles, a breadcrumb, a title + "Skip to main content" — come from the DEGRADED raw-excerpt run r6. 10.3% boilerplate in the stored corpus.
5. **True-to-source but stale.** R6F9 faithfully excerpts Healthline, but its chemotherapy-side-effect suggestion is no longer supported by 2025 systematic reviews. Source fidelity is not the same as currency.
6. **Opinion stored as findings.** Two of run r7's six excerpts are the cited author's expert judgement — genuine and aligned, but they cannot carry a VERIFIED stamp the way facts can, and the store does not distinguish them.

## 6. Required follow-up: verification pass (methodology obligation)

Because accuracy is below the pre-declared standard, the methodology obliges a verification pass in the research pipeline. It is **specified here and board-tracked as TASK-INT-005's next action; it is not implemented in this PR** (this crew's mandate was the audit; the pass is a pipeline code change for a follow-up crew under coordinator review — stated plainly rather than bundled unverified into an audit PR).

The pass must include:

1. **Verbatim quote gate** — a finding may be stored with `quotes_verified=true` only if its quote appears verbatim in the retrieved text of the cited URL (normalising quote-mark style/whitespace only); otherwise store it flagged `quotes_verified=false`. (Catches R0F3-class defects.)
2. **Coverage/entailment check** — every load-bearing detail in a synthesised statement (numbers, dates, named claims) must appear in a cited source's retrieved text; uncovered details are dropped or the statement is marked partial; attribution and hedging language in the source must survive synthesis. (Catches R4F2/R9F1-class defects.)
3. **Boilerplate filter** — in DEGRADED raw-excerpt mode, drop excerpts matching the page `<title>`/H1, breadcrumbs, or navigation strings before storage. (Removes the NON_CLAIM class.)
4. **Visible corroboration flag** — single-source findings surface `independently_verified=false` in briefs rather than leaving it implicit in the payload.
5. **Re-audit hook** — after the pass ships, re-run this census method on newly stored runs against the same standard (≥90% VERIFIED, zero CONTRADICTED).

Also recommended (cheap, high value): a live-fetch re-check of R6F10/R6F11 (Northwell) and R8F1/R8F3 (TechTarget/USENIX quotes) by an agent with a working browser — two PARTIALs and both UNVERIFIABLEs could move on that evidence alone.

## 7. Honest status

- Audit: **complete** — census of all 39 stored findings, per-claim evidence in the JSON companion file.
- Accuracy: **65.7% VERIFIED over CLAIMs (59.0% over all findings) — below the pre-declared standard.** Zero contradicted, zero unsupported, zero fabricated facts found.
- Verification pass: **specified, not implemented** (see §6) — the task stays open on the board for it.
- This document and its JSON are delivered via PR from fresh main; **not merged** (coordinator merges).
