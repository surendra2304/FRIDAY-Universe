# TASK-INT-003 — IntelX research depth: rubric, baseline, fix, re-score

Measured 2026-11-15 by the INT-003 crew (muse_ai). The rubric was
**pre-declared before any measurement**; every score below cites a stored
output envelope. No estimated numbers.

## Fixed question set (identical for before and after)

| # | Question | Primary expected | Disagreement topic? |
|---|----------|------------------|---------------------|
| Q1 | What is the current status of NASA's Artemis II mission? | nasa.gov | No |
| Q2 | What is the latest progress on solid-state batteries? | journals / institutions | No |
| Q3 | What does the WHO say about the safety of aspartame? | who.int | **Yes** (IARC vs JECFA) |
| Q4 | Does intermittent fasting improve longevity in humans? | peer-reviewed / NIH | **Yes** |
| Q5 | What are the latest developments in fusion energy research? | iter.org / IAEA / labs | No |
| Q6 | What caused the July 2024 CrowdStrike outage and what were its effects? | crowdstrike.com / Microsoft | No |

Q1/Q2/Q5 are TASK-REL-021's 2026-11-14 production-proof questions (continuity).

## Rubric (each dimension 0–4 per question, mechanical)

- **D1 Source diversity** — distinct registrable domains among `sources`:
  0→0, 1→1, 2→2, 3→3, ≥4→4.
- **D2 Primary-source ratio** — PRIMARY = the originator itself
  (institution/company/journal/.gov publishing its own material);
  SECONDARY = news, blogs, aggregators, Wikipedia, vendor marketing.
  score = round(4 × primary/total). Per-source classification recorded below.
- **D3 Contradiction handling** — Q3/Q4 only. 4 = ≥2 distinct positions,
  each attributed; 2 = disagreement visible but positions not presented as
  such / only one substantiated; 0 = one position as settled.
- **D4 Citation verifiability** — independent refetch of each cited URL;
  whitespace-normalised quote substring check (same `normalized()` as
  `grounded_live_research`). score = round(4 × verified/checkable).
  Refetch failures reported separately; a question with zero checkable
  findings is N/A, flagged low-confidence. Caveat: the refetch extractor is
  a crude tag-stripper, not the production connector — NOT_FOUND ≠ fabricated
  (the pipeline's own gate verified synthesised quotes exactly at run time).

## How the runs were produced (traceability)

- **Before** = the production IntelX service on Server 1
  (`research_live`, REL-038 persistence on). Envelopes verbatim at
  Server 1 `/tmp/int003/before/q1..q6.json`, persisted in Oracle under
  run_ids lr_d0601f5a5b494ac4b8f229d9 (Q1), lr_6205335738fb4b6cba960733 (Q2),
  lr_5cd766e6f64b4947aeb6ae12 (Q3), lr_948f7587aae74c2188a5c845 (Q4),
  lr_f21218f875f34354ba4d0a19 (Q5), lr_6e43c4106e8e46a19b7af72a (Q6).
  Config: Tavily primary (key set), SearXNG unset.
- **After** = candidate probe, NOT a deploy: the PR version of
  `live_research_task.py` was assembled on Server 1 from the deployed file
  and run with the production connectors + production synthesis, envelopes
  at `/tmp/int003/after/q1..q6.json` (not persisted; run_id null).
  Fingerprint chain: deployed file git blob `52d81b1d…` == repo HEAD before
  the fix; candidate blob `3de00dce…` == the file in this PR, byte-identical.
  Production code was never modified and the service never restarted.

## Baseline results (production, before)

| Q | Envelope | Synthesis | Sources | Findings | Fetch fails | Notes |
|---|----------|-----------|---------|----------|-------------|-------|
| Q1 | DEGRADED | not_attempted | 0 | 0 | 15 (13×403, 2×404) | 7 of 15 candidates were news.google.com redirectors; nasa.gov never entered the pool |
| Q2 | SUCCESS | succeeded | 3 | 3 | 10 | |
| Q3 | SUCCESS | succeeded | 1 | 3 | 5 | who.int itself; text presents IARC + JECFA attributed |
| Q4 | DEGRADED | failed (quote unverified) | 4 | 12 | 11 (all 403, incl. PubMed) | raw excerpts contain both positions, never presented |
| Q5 | DEGRADED | failed (quote unverified) | 2 | 6 | 13 | no ITER/IAEA/lab source |
| Q6 | SUCCESS | succeeded | 3 | 3 | 5 | |

Total fetch failures: **59, of which 45× HTTP 403**.

### Root-cause experiment (user-agent hypothesis killed)
From Server 1, production UA vs plain Chrome UA: investing.com,
mayoclinic.org, stocktitan.com → **403 under both** (IP-level bot
management); pubmed → 203 under both; **nasa.gov → 200 under both**
(fetchable — it was simply absent from the candidate pool).

**Weakest proven link = candidate supply and ordering**: a 15-candidate
hard cap (`min(15, max_sources*3)` requested, loop sliced `results[:15]`),
roughly half of some pools burned on documented-dead Google News
redirectors (TASK-REL-038), no deeper pool to fall back on, and no
final-URL dedupe (found during the after-probe, see below).

## The fix (this PR, `IntelX/intelx/api/live_research_task.py` only)

1. Pool widened: `max_results=min(30, max_sources * 6)`; the full pool is
   iterated (slice removed). `max_sources` still bounds accepted sources;
   every failure still recorded per candidate.
2. `news.google.com` / `*.news.google.com` redirector candidates are
   **demoted to last-resort** (stable sort) — never dropped; still attempted
   and recorded if nothing else succeeds.
3. **Final-URL dedupe**: a fetched document whose final URL was already
   accepted is skipped and recorded as `duplicate_final_url`, freeing the
   source slot. (Probe evidence: one brief held the same document twice
   among five sources via a tracking-parameter variant.)

Tests: `tests/test_int003_candidate_pool.py` (5 tests: wider request, full
iteration, redirectors last, redirector last-resort, duplicate final URL,
cap respected) + existing suites — 35 passed locally
(`test_int003_candidate_pool` 5, `test_live_research_task_contract` 22,
`test_grounded_live_research` 8). `test_grounded_research_synthesis.py`
needs pydantic (absent in the measuring sandbox) and covers a file this PR
does not modify; CI covers it.

## After results (candidate probe, exact PR code)

| Q | Envelope | Synthesis | Sources (entries/domains) | Findings | Fetch fails | Notes |
|---|----------|-----------|---------|----------|-------------|-------|
| Q1 | DEGRADED | failed (**ReadTimeout**) | 5 / 4 | 15 | 6 | **nasa.gov reached**; was 0 sources/95.5s. Synthesis timeout is LLM-call infra variance, not the quote gate |
| Q2 | SUCCESS | succeeded | 1 / 1 | 3 | 15 (12×403) | pool heavily 403'd this run; only one fetch survived |
| Q3 | SUCCESS | succeeded | 1 / 1 | 3 | 5 | CNBC reporting WHO; text presents WHO + JECFA + IARC positions attributed |
| Q4 | SUCCESS | succeeded | 2 / 2 | 3 | 4 (incl. **1× duplicate_final_url**) | dedupe fired and freed the slot; synthesis succeeded (failed in both earlier runs) |
| Q5 | SUCCESS | succeeded | 1 / 1 | 3 | 10 | sole source is a GitHub example file — shallow |
| Q6 | DEGRADED | failed (quote unverified) | 5 / 5 | 15 | 5 | |

Total fetch failures absorbed: **45** (vs 59 baseline) while still
producing briefs. Envelope SUCCESS: **4/6 after vs 3/6 before**, and every
question produced ≥1 source and ≥3 findings (baseline Q1 produced none).

## Scores

### D1 — source diversity (distinct domains)
| | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Mean |
|---|----|----|----|----|----|----|------|
| Before | 0 | 3 | 1 | 4 | 2 | 3 | **2.17** |
| After | 4 | 1 | 1 | 2 | 1 | 4 | **2.17** |

Mean unchanged; distribution changed. The catastrophic case is gone
(Q1 0→4 domains; no zero-source question), Q6 rose 3→4, but Q2/Q4/Q5 fell
on this run set — per-question diversity is dominated by which pool
Tavily returns and which fetches survive 403s, i.e. variance the pool
widening reduces but does not eliminate.

### D2 — primary-source ratio
Per-source classification (P = primary, S = secondary):

- Before — Q1: — (0 sources) → 0. Q2: monolithai.com (S, vendor blog),
  sciencedaily.com (S, news), en.wikipedia.org (S) → 0. Q3: who.int (P)
  → 4. Q4: blog.insidetracker.com (S), gero.usc.edu (P, USC institute's own
  site), healthline.com (S), thewell.northwell.edu (P, health system's own
  site) → 2. Q5: belfercenter.org (P, Harvard centre's own site),
  world-nuclear.org (P, association's own site) → 4. Q6: usenix.org (P),
  octopus.com (S, vendor blog), techtarget.com (S) → 1.
- After — Q1: newspaceeconomy.ca (S), sciencetimes.com (S), issinfo.net (S),
  **nasa.gov (P)** → 1. Q2: voltupbattery.com (S, vendor) → 0. Q3:
  cnbc.com (S) → 0. Q4: fastinginpractice.com (S), lifesum.com (S) → 0.
  Q5: github.com example file (S) → 0. Q6: substack (S), emergent.wiki (S),
  the-security-brief.com (S), cgaa.org (S), techtarget.com (S) → 0.

| | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Mean |
|---|----|----|----|----|----|----|------|
| Before | 0 | 0 | 4 | 2 | 4 | 1 | **1.83** |
| After | 1 | 0 | 0 | 0 | 0 | 0 | **0.17** |

**D2 regressed on this run set.** The fix widens the pool but does not
prefer primary sources; search ranking decides composition, and the after
pools happened to surface mostly secondary sources (the baseline pools
happened to include who.int, gero.usc.edu, belfercenter.org, usenix.org).
Recorded plainly: **primary-source preference is the next depth lever and
is NOT implemented by this PR** (see residuals).

### D3 — contradiction handling (Q3/Q4 only)
| | Q3 | Q4 | Mean |
|---|----|----|------|
| Before | 4 | 2 | **3.0** |
| After | 4 | 4 | **4.0** |

Q3 holds at 4 in both runs (IARC classification, JECFA "evidence not
convincing", and in the after run also FDA's stated disagreement — each
attributed with verbatim quotes). Q4 rose 2→4 because synthesis succeeded
and the draft juxtaposes the positions (biomarker/animal evidence vs
"no randomised trial has demonstrated that intermittent fasting extends
human lifespan"); note synthesis success itself is partly run variance —
the same question failed the quote gate in the baseline and first probe.

### D4 — citation verifiability (independent refetch)
| | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Mean (scoreable) |
|---|----|----|----|----|----|----|------------------|
| Before | N/A (0 findings) | 3 (2/3) | 3 (2/3) | 2 (7/12) | 3 (4/6) | 3 (2/3) | **2.8** (17/27 = 63% verified) |
| After | 4 (14/15) | 1 (1/3) | 3 (2/3) | 3 (2/3) | N/A (0/3 checkable — refetch HTTPError) | 3 (11/15) | **2.8** (30/39 = 77% verified) |

Mean score unchanged; verified fraction rose 63% → 77%. Q5-after is
flagged low-confidence per the rubric (zero checkable findings — the
refetch client was refused by github.com; the pipeline's own runtime gate
had verified those quotes against the fetched document).

## What this does and does not prove

- Proven: the candidate-supply ceiling is real and the fix removes the
  worst failure mode (a question returning **nothing**). Q1 went from
  0 sources / 0 findings / DEGRADED to 5 sources incl. nasa.gov /
  15 findings; the only remaining Q1 failure was a synthesis LLM timeout.
- Not proven: a general depth improvement. D1 mean flat, D2 down on this
  run set, envelope SUCCESS 4/6 vs 3/6 with different questions failing.
  Single-run-per-question measurement on a live, 403-heavy web has high
  variance; these are honest single samples, not averages.

## Residuals (named follow-ups, not fixed here)

1. **Primary-source preference** — boost/reorder candidates toward
   originator domains (the pool now has the depth to reorder within).
   This is the largest remaining D2 lever.
2. **Synthesis quote gate flakiness** (`synthesis_quote_unverified`
   failed Q4/Q5 baseline, Q6 in both probe runs; REL-021 documented model
   quote-splicing) and one `synthesis_ReadTimeout` (Q1 after) — the
   synthesis stage is now the weakest link; untouched by this PR.
3. **Content-level near-duplicates**: Q1-after held the same article in
   `?noamp=mobile` and `?amp=1` formats — distinct final URLs, so URL
   dedupe correctly does not merge them; passage-level dedupe would.
4. The contradiction engine (`intelx/core/contradiction.py`) remains
   wired only into a legacy route, not the live path.
5. Post-merge: re-run this fixed set against the deployed service for
   the production-verified state (coordinator step).
