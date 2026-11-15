# TASK-INT-005 — IntelX Fact-Check Sampling: Measured Accuracy of Stored Research

**Crew:** muse_ai (Muse) · **Date:** 2026-11-15 · **Claim:** issue #35, comment 6891563433
**Status of this document:** audit results + the verification pass implemented in the same PR.
Coordinator merges; this crew does not merge or deploy.

## Headline result

| Measure | Result |
|---|---|
| Stored factual claims verified end-to-end (VERIFIED) | **24 / 27 = 88.9%** |
| Pre-declared accuracy standard | ≥ 90% VERIFIED and zero CONTRADICTED |
| **Verdict vs standard** | **BELOW STANDARD** → verification pass implemented (below) |
| PARTIAL | 2 |
| UNSUPPORTED | 1 |
| CONTRADICTED | 0 |
| Stored findings that are not factual claims at all | 9 / 36 (4 boilerplate, 5 opinion) |
| VERIFIED share of ALL stored findings | 24 / 36 = 66.7% |

## What "stored research" actually is (population discovery)

The audit was scoped to IntelX's evidence data model (`claims` / `evidence` /
`sources` / `documents` / `findings`). Read-only probes of the production INTELX
schema on Server 1 (2026-11-15, via the app's own configured DSN) found:

- `claims`, `evidence`, `sources`, `documents`, `chunks`, `findings`,
  `research_runs`, `entities`, `artifacts`, `events`: **0 rows each.**
  The span-verified evidence pipeline (extractor → ClaimVerifier →
  VerifierAgent → orchestration engine) has never persisted a single row
  in production.
- `live_research_runs`: **9 rows** — the only stored research in the system,
  written by the live brief pipeline (`live_research_task.collect_live_brief`
  + `grounded_live_research.synthesize_grounded`, persisted by REL-038's
  `live_research_store`).

The population was therefore redefined (methodology amendment, recorded
before any verification began) as **all findings in the 9 stored live
research runs: 36 findings**. With ≤ 40 findings, the audit is a **census**,
not a sample — every stored finding was checked.

**Provenance disclosure:** all 9 runs are engineering acceptance probes from
2026-11-14/15 (task ids `rel038_live_probe`, `rel038_final_probe`,
`task_1408370e0a65`, six `int003_before_*`). The store contains **no organic
user research**. One run (Artemis II) stored 0 findings (DEGRADED).

## Method

Each finding was classified CLAIM / BOILERPLATE / OPINION, then each CLAIM was
checked three ways (methodology fixed before results were seen):

1. **Quote alignment** — the stored `quote` must be found verbatim on the
   cited page today.
2. **Cited-source support** — the quote plus its page context must support
   the statement as stated (no material facts added beyond the source).
3. **Independent corroboration** — a source on a different domain must
   corroborate the claim's central fact.

Verdicts: VERIFIED (all three pass) · PARTIAL (cited supports but independent
evidence is mixed/contesting, or corroboration is incomplete) · UNSUPPORTED
(cited source does not support / quote absent) · CONTRADICTED · UNVERIFIABLE.
Four collector agents gathered evidence per claim cluster; the crew lead
independently re-checked the WHO aspartame page, the Quantinuum release and
the ScienceDaily Max Planck article first-hand.

## Per-finding verdicts (all 36)

Model-draft claims (runs marked `quotes_verified=true`, `semantic_entailment_verified=false`):

| # | Run (task) | Claim (short) | Verdict | Basis |
|---|---|---|---|---|
| 0 | lr_82249… (rel038_live_probe) | SSBs use solid electrolytes, improving safety/density/thermal stability | VERIFIED | Quote exact in review abstract; Ossila corroborates |
| 1 | lr_82249… | UT Dallas: mixing particles between two solid electrolytes creates a "space charge layer" enhancing ionic conductivity | VERIFIED | Quote exact; page context supplies the conductivity mechanism; primary ACS Energy Lett. paper corroborates. Note: the quote alone does not contain the mechanism — page context does |
| 2 | lr_82249… | Bruker provides specialised solid-state NMR probes for in-situ/operando energy-storage research incl. batteries and supercapacitors | **UNSUPPORTED** | Stored quote NOT FOUND on the cited page; cited page (Specialty Solids Probes) contains no in-situ/operando, battery or supercapacitor content. Similar wording exists in a *different* Bruker catalogue. See failure analysis |
| 3 | lr_5e947… (rel038_final_probe) | Quantinuum Helios: world-record 99.9995% logical fidelity, 10× own record, 100× other modalities | VERIFIED | Quote exact; added figures present on the same page; independent trade coverage corroborates (vendor-originated, not peer-reviewed — disclosed) |
| 4 | lr_5e947… | Google Willow (Dec 2024): first empirical proof of below-threshold QEC | VERIFIED | Quote exact; independent corroboration |
| 5 | lr_5e947… | Quantum threshold theorem (1997-98) guarantee | VERIFIED | Quote exact; theorem statement on same page; QuEra glossary corroborates |
| 6 | lr_7e6ec… (task_1408…) | SSBs "transitioning … to commercial production in 2026", Toyota/BYD/CATL timelines | **PARTIAL** | Quote exact and page names the companies, but the page itself qualifies timelines to 2027+; independent sources contradict the 2026 commercial-production framing (2026 = pilot/testing). IntelX's own finding #11 contradicts it too |
| 7 | lr_7e6ec… | Zirconium-based halide electrolytes reached 1.78 mS/cm room-temperature ionic conductivity | VERIFIED | Quote exact; TechXplore corroborates the exact figure |
| 8 | lr_7e6ec… | SSBs: >500 Wh/kg, reduced thermal-runaway risk from non-flammable electrolytes | VERIFIED | Quote exact; thermal-runaway content on same page; independent corroboration (independent source adds a "theoretically" qualifier the statement omits) |
| 9 | lr_62053… (int003_before) | Max Planck Institute: soft lithium dendrites fracture hard ceramic electrolytes via hydrostatic stress | VERIFIED | Quote exact (crew lead re-checked first-hand); TechXplore corroborates |
| 10 | lr_62053… | Samsung SDI targeting SSB mass production by 2027; positive sample feedback; 40% higher energy density | VERIFIED | Quote exact; page context supplies feedback/density; independent corroboration |
| 11 | lr_62053… | As of 2026 the SSB market has not achieved scalability/commercialisation | VERIFIED | Quote exact on Wikipedia; independent corroboration |
| 12 | lr_5cd76… (int003_before) | IARC classified aspartame possibly carcinogenic (Group 2B), limited evidence, liver cancer | VERIFIED | Quote exact on WHO page (crew lead re-checked first-hand); independent corroboration |
| 13 | lr_5cd76… | JECFA reaffirmed ADI of 40 mg/kg body weight | VERIFIED | Quote exact on WHO page; independent corroboration |
| 14 | lr_5cd76… | WHO: safety not a major concern at common doses; effects need more study | VERIFIED | Quote exact on WHO page; independent corroboration |
| 33 | lr_6e43c… (int003_before) | CrowdStrike outage caused by channel file 291 logic error crashing Falcon sensor | VERIFIED | Quote exact on TechTarget; independent corroboration |
| 34 | lr_6e43c… | Falcon sensor is a Windows kernel driver → BSOD, machines inoperable | VERIFIED | Quote exact; page supplies "kernel driver" verbatim; independent corroboration |
| 35 | lr_6e43c… | Outage disrupted airlines, payments, hospitals, emergency services | VERIFIED | Quote exact on USENIX; sector disruption corroborated. The harm element is the cited author's own hedged speculation, relayed hedged |

Excerpt findings from the two DEGRADED unsynthesised runs (statement == quote by construction):

| # | Run | Excerpt (short) | Class | Verdict / note |
|---|---|---|---|---|
| 15 | lr_948f7… (fasting) | "Some scientists believe these responses could translate…" (article lede) | OPINION | Verbatim body text; attributed belief, no factual assertion |
| 16 | lr_948f7… | 2017 Longo review + 2019 NEJM review on IF benefits | CLAIM | VERIFIED — exact, supported, corroborated |
| 17 | lr_948f7… | IF improves weight/insulin/inflammation…; mouse tumour/lifespan effects | CLAIM | VERIFIED — exact, supported, corroborated (PMC review) |
| 18 | lr_948f7… | "Eat less, live longer? … - USC Leonard Davis School of Gerontology" | BOILERPLATE | Page title stored as a finding |
| 19 | lr_948f7… | "Eat less, live longer? The science of fasting and longevity" | BOILERPLATE | Page title (no suffix) stored as a finding |
| 20 | lr_948f7… | "Home » Eat less, live longer? …" | BOILERPLATE | Breadcrumb navigation stored as a finding |
| 21 | lr_948f7… | IF can improve heart-disease risk factors | CLAIM | VERIFIED — exact, supported, corroborated |
| 22 | lr_948f7… | Human IF/cancer research inconsistent; more research needed | CLAIM | VERIFIED — exact, supported, corroborated |
| 23 | lr_948f7… | IF helps prevent cancer in animals; may reduce chemotherapy side effects in humans | CLAIM | **PARTIAL** — exact and supported by cited page and one PMC review, but a 2025 systematic review found no demonstrated chemo-toxicity improvement; claim is contested |
| 24 | lr_948f7… | "When it comes to longevity, the internet loves a shortcut…" (16:8 description) | OPINION | Cited page returns HTTP 403 to the audit fetcher; presence unconfirmed |
| 25 | lr_948f7… | "longevity isn't something you can hack…" | OPINION | Same 403; presence unconfirmed |
| 26 | lr_948f7… | "Fasting for Longevity? … Skip to main content" | BOILERPLATE | Page title + accessibility-nav string stored as a finding; same 403 |
| 27 | lr_f2121… (fusion) | Holdren: "My views … are at odds with the last few years' breathless publicity…" | OPINION | Verbatim; signed expert commentary |
| 28 | lr_f2121… | NIF best shot 8.6 MJ (April 2025) etc. inside evaluative framing | CLAIM | VERIFIED — exact; LLNL's own publication corroborates the figures |
| 29 | lr_f2121… | "I think it's fair to say the problems … are not much easier than breakeven…" | OPINION | Verbatim expert judgement |
| 30 | lr_f2121… | NIF: $3.5B facility, completed March 2009, NNSA-funded… | CLAIM | VERIFIED — exact; PMI corroborates NIF cost/date (LMJ date rests on WNA alone) |
| 31 | lr_f2121… | Fusion powers the Sun and stars; H→He; plasma… | CLAIM | VERIFIED — exact, corroborated (textbook) |
| 32 | lr_f2121… | Fusion fuel must reach ~50 million °C… | CLAIM | VERIFIED — exact, corroborated (independent wording partly derivative of WNA; facts textbook-standard) |

## Failure analysis

1. **Citation-integrity failure (#2, Bruker).** The run is stored with
   `quotes_verified=true`, yet the stored quote does not exist on the cited
   page today and the page does not support the statement. The synthesis gate
   checks the quote against the *fetched snapshot supplied to the model*, not
   against the live page, so a fetch/extraction divergence (or page change)
   leaves a permanently unverifiable citation in the store. The statement
   also drifts from its own quote ("probes" vs the quote's "systems").
2. **Entailment was never checked.** Every SUCCESS run stores
   `semantic_entailment_verified=false` — by design in the current code
   (`synthesize_grounded` hardcodes it). Quotes were verified; whether the
   *statement* is supported was not. Findings #1, #5, #10, #34 are saved only
   by page context beyond the quote; #6 shows the failure mode: a statement
   whose framing ("commercial production in 2026") outruns its source's own
   qualifications and is contradicted by independent sources — and by
   IntelX's own finding #11 from another stored run.
3. **Boilerplate stored as findings.** 4 of 36 findings are page chrome:
   two copies of a page title, a breadcrumb, and a title + "Skip to main
   content". The excerpt extractor's paragraph filter admits titles because
   they can contain sentence punctuation ("…live longer?").
4. **Contested claim presented flat (#23).** A hedged but contested
   health claim (IF reducing chemotherapy side effects) is stored without
   any contestation marker.
5. **The verified-claims store is empty.** The claims/evidence data model
   with span verification, the `ClaimVerifier`, and the `VerifierAgent`
   exist and are wired into the orchestration engine, but no production
   path has ever written to them. Everything FRIDAY serves as "IntelX
   research" comes from the live-brief payloads audited here.

## Verification pass implemented in this PR

Because measured accuracy (88.9%) is below the pre-declared standard
(≥ 90%), this PR adds a verification pass to the live research pipeline:

1. **Deterministic entailment screen** (`grounded_live_research.py`):
   after the existing exact-quote gate, each draft statement must pass
   `statement_support()` against its cited source's supplied text —
   every number in the statement must appear in the source text, every
   multi-word capitalised entity / acronym must appear, and ≥ 80% of the
   statement's content words must be covered by the source text. Failure
   degrades the whole draft (`synthesis_entailment_unverified`), failing
   closed exactly like the quote gate. On success the result now sets
   `semantic_entailment_verified=true` truthfully, and each finding
   carries per-finding `quote_verified` / `entailment_verified` flags.
   This screen would have caught the #2 class (statement vocabulary —
   "operando", "supercapacitors", "batteries" — absent from the cited
   page's text) even against a divergent fetch snapshot.
2. **Chrome/boilerplate filter** (`live_research_task.py`):
   `collect_live_brief` now drops candidate passages that are the page
   title (or a prefix/suffix variant of it), breadcrumbs ("Home » …"),
   or accessibility chrome ("Skip to main content") before ranking, so
   they can never become findings (#18–#20, #26 class).
3. **Tests** (`IntelX/tests/test_int005_verification_pass.py`): the
   entailment screen accepts supported statements and rejects invented
   numbers/entities; synthesis degrades on an unentailed draft and
   reports `semantic_entailment_verified=true` on a clean one; the brief
   collector excludes title/breadcrumb/skip-link passages and keeps real
   paragraphs.

**What the pass does not do** (stated plainly): it verifies support in the
*cited* source, not independent truth. Independent corroboration remains
outside the pipeline — IntelX's existing labels already say findings are
"source-attributed, not independent verification", and this audit confirms
that label is accurate. Wiring the claims/evidence store into the live
path is recommended follow-up work, out of scope here.

## Reproducibility

- Population probes: read-only SQL against the production INTELX schema
  via the app's own session factory (counts + seeded extraction; seed
  20251115). Census: 9 runs / 36 findings, extracted 2026-11-15.
- Verification: live page fetches + independent-source searches,
  2026-11-15; per-finding evidence retained by the crew
  (~/workspace/int-005/census.json, verdicts.json).
- One cited domain (thewell.northwell.edu) returns HTTP 403 to automated
  fetching; its 3 findings are non-claims whose text presence could not
  be re-confirmed — recorded as such, not guessed.
