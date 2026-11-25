# TASK-INF-042 — Verified free-tier route catalogue — evidence

**Task:** TASK-INF-042 (Inference: verified free-tier route catalogue — MiniMax, Sora 2,
NanoBanana Pro, Wan 2.6, SadTalker, Gamma checked live, verified-free routes wired).
**Owner:** Muse 4. **Claim:** hub #1483 comment 7148101853, 2026-11-25 ~05:35 IST,
under the central-pool pull model. **Branch:**
`muse4/task-inf-042-free-tier-route-catalogue`. **Base:** main `8bfcbc4f`.

## Verdict up front

**Zero of the six claimed $0 routes verify as free API capacity.**

| Free alternative (claimed) | Live verdict 2026-11-25 | Wired? |
|---|---|---|
| Sora 2 (vs Veo 3 $249/mo) | REJECTED — discontinued | No |
| MiniMax (vs ElevenLabs $99/mo) | PAID-ONLY | **No — the "wired if verified free" condition fails** |
| NanoBanana (vs Seedream 4 $39/mo) | PAID-ONLY | No |
| Wan 2.6 (vs RunwayML $76/mo) | PAID-ONLY | No |
| SadTalker (vs HeyGen $39/mo) | VERIFIED-FREE (software) — not a route | No (no API exists) |
| Gamma AI (vs Plus AI $20/mo) | VERIFIED-FREE (consumer plan) — not a route | No (API is Pro-only) |

**MiniMax is NOT wired.** The task says "MiniMax wired if verified free". The live
first-party read proves there is no MiniMax free API tier, so the condition fails and
there is nothing to wire. The candidate spec stays `BLOCKED_NO_CREDENTIALS`, spec-only,
with no provider adapter — exactly the standing design in
`Inference/docs/FREE_SUBSTITUTION_TABLE.md` §2. The spec's notes now record the
disproven free-tier premise so no future worker re-litigates it without a new dated
first-party read.

## Method

Each named route was checked live against the vendor's own pricing/terms page on
2026-11-25. No account was created, no key provisioned, no payment made. A route counts
as verified-free API capacity only if the vendor's own published terms state a standing
$0 API tier. One-off signup/trial credits, consumer-app free use, and reseller credit
hosts are not API capacity. Where a vendor page is JS-rendered or the row has aged off,
the verdict rests on dated third-party reads of the vendor's own page, and the doc says
so per route. Full per-route findings with quotes live in the machine-readable catalogue
`Inference/config/free_tier_routes.json` (the single source of truth; the test suite
pins it).

## Per-route findings (summary; full text in the JSON catalogue)

### 1. Sora 2 — REJECTED (discontinued)

- OpenAI notified developers 2026-03-24 that the Videos API and every Sora 2
  alias/snapshot would be removed from the API on 2026-09-24; the Sora consumer app and
  website closed 2026-04-26 (OpenAI Help Center).
- Live read of the OpenAI deprecations page (`developers.openai.com/api/docs/deprecations`)
  2026-11-25 returns zero matches for "sora": the row has aged off the table now that the
  shutdown is past; the table lists only shutdowns from Dec 2026 onward.
- Four dated third-party reads (8frame 2026-10-02, soku.ai 2026-10-21, layer3labs,
  kenerateai) quote the same OpenAI deprecation text and the model-page banner: "The Sora 2
  models and Videos API were shut down on September 24, 2026 and are no longer available.
  No one-to-one replacement API is available." The replacement column was empty for every
  Sora row.
- While live, the API charged $0.10/second (sora-2, 720p) and $0.30–$0.70/second
  (sora-2-pro); the app had a free tier with daily limits. Both are history.
- **VyralX implication:** no Sora 2 generation option exists. Any VyralX material still
  naming Sora 2 as a route is stale.

### 2. MiniMax — PAID-ONLY

- Live first-party read of `platform.minimax.io/docs/pricing/overview`, 2026-11-25: the
  page states no free tier and no free credits anywhere. Pay-as-you-go billing: "API usage
  charges are deducted from your account balance" after funds are added.
- MiniMax-M3 $0.30 in / $1.20 out per 1M tokens (≤512k input, permanent 50% off);
  MiniMax-M3.1-Flash $0.15 in / $0.60 out. TTS speech-2.8-turbo $60 / M characters,
  speech-2.8-hd $100 / M characters; ASR $0.38/hour. Audio Packages from $5/month
  (100,000 points).
- The only free allowances printed on the pricing page are input-side: the first 5 input
  images per video task are free, and audio input is free. Neither is a free tier.
- The M Plan $0 tier is the MiniMax Code agent app (limited M3.1 Flash use, no API key for
  other tools, no H3 video) — not API capacity. A third-party aggregator's June 2026 claim
  of a ¥15 signup credit is contradicted by two November 2026 reads of the first-party
  page and is not a standing tier.
- Corroborated by independent reads of the same first-party page dated 2026-10-24 and
  2026-11-17.
- **VyralX implication:** MiniMax is not a free voice/audio route for VyralX. TTS via
  MiniMax would be a paid integration and is out of scope under the free-only rule.

### 3. NanoBanana — PAID-ONLY

- Live first-party read of the Gemini Developer API pricing page, 2026-11-25, section
  "Gemini 2.5 Flash Image (Nano Banana)": Free Tier reads "Not available" for input price
  and output price on Standard, Batch, Flex and Priority tabs. Paid: $0.30 per 1M input
  tokens, $0.039 per image output (1,290 tokens per 1024px-class image).
- The model is deprecated on Google's own page: "Gemini 2.5 Flash Image
  (`gemini-2.5-flash-image`) is deprecated and will be shut down on March 15, 2027;
  migrate to Gemini 3.1 Flash Lite Image."
- The newer family members (Nano Banana 2.1, 2, 2 Lite, Pro) are listed the same way by
  independent readers of the same page (Nov 2026): Free Tier "Not available" for all of
  them. Free use exists only inside Google's consumer apps (Gemini app, Flow, AI Studio)
  — not API capacity.
- **VyralX implication:** no free Nano Banana API route for VyralX image generation.
  Consumer-app use is a human workflow, not a pipeline input.

### 4. Wan 2.6 — PAID-ONLY

- Direct read of `create.wan.video/pricing` attempted 2026-11-25 and failed: the page is
  JS-rendered and returns "Something went wrong" to a static fetch. The figures below are
  dated third-party reads of Alibaba's own pages, consistent across three independent
  readers — recorded as such, not as a first-hand read.
- Alibaba Cloud Model Studio pricing (read 2026-10-02 and 2026-10-25): wan2.6-t2v /
  wan2.6-i2v cost $0.10/second at 720p and $0.15/second at 1080p in the Singapore region;
  a 50-second free quota per model, valid 90 days, for new users in Singapore only. A
  trial quota that expires is not a standing free tier.
- wan.video consumer site (read 2026-11-03): Free plan $0/month — daily check-in to earn
  credits, one video at a time, watermark on exports, testing use only, no commercial
  licence. Credit cost per clip is not published on the page.
- Wan 2.6 has no public weights (Wan 2.2 is the last generation with downloadable weights),
  so there is no self-hosted route for this version.
- Third-party credit hosts (VdoBloom via KIE, wanai.dev) sell credits for Wan 2.6 renders;
  they are resellers, not a first-party free tier, and are not capacity under the free-only
  rule.
- **VyralX implication:** no free Wan 2.6 API route for VyralX cinematic generation. The
  50-second trial quota cannot carry a production line.

### 5. SadTalker — VERIFIED-FREE (software) — not a route

- Live first-party read of `github.com/OpenTalker/SadTalker`, 2026-11-25: public repo,
  14,220 stars, 288 commits, main branch, CVPR 2023. README states the licence is Apache
  2.0 with the non-commercial restriction removed; GitHub's own licence detector reports
  NOASSERTION for the repo — the discrepancy is recorded here, the README text is the
  claim.
- The README states the code "runs completely offline and does not collect any personal
  information or other data." No hosted service, no API, no price. Checkpoints are
  downloaded separately (GitHub Releases / Google Drive / Baidu).
- Requirements from the repo: Python 3.8+, PyTorch with CUDA (GPU recommended, CPU
  possible), FFmpeg. Output 256/512px face renders, head-only animation from one portrait
  + audio.
- **VyralX implication:** SadTalker is free software, not a service. A VyralX avatar leg
  built on it would be a local-GPU pipeline component needing its own evaluation (hardware,
  quality, likeness rules) — not Inference fallback capacity, and not claimed here.

### 6. Gamma AI — VERIFIED-FREE (consumer plan) — not a route

- Live first-party read of `gamma.app/pricing`, 2026-11-25: a Free plan is listed at $0
  with "No credit card required" — up to 10 slides per prompt; simple presentations, docs,
  websites, social and images; import from PDF and PPTX; export to PDF, PPTX, PNG and
  Google Slides.
- The 400 one-time-credit figure is reported by multiple third-party reads of the same page
  (Nov 2026) and was not visible in the live crawl's dynamic slots — recorded as reported,
  not first-hand. Credits do not refresh; free decks carry Gamma branding.
- API access is a Pro feature ($18/month billed annually) per the vendor's plan comparison
  — there is no free API tier. Gamma is a presentations surface, outside Inference's
  provider pool in any case.
- **VyralX implication:** none for video generation. Gamma's free plan is a real $0 plan
  for human-made decks, not pipeline capacity.

## What changed in the repo

1. `Inference/config/free_tier_routes.json` (new) — machine-readable catalogue: one entry
   per route with verdict, first-party URL, dated evidence, `wired: false` for all six,
   and the VyralX implication. Single source of truth for the verdicts.
2. `Inference/docs/FREE_SUBSTITUTION_TABLE.md` — new §4 "Live verdicts (TASK-INF-042,
   2026-11-25)". §2 (the carousel's own claims, recorded as written) is untouched.
3. `Inference/benchmarks/candidates/minimax.json` — added `free_tier_verdict: "paid-only"`
   and `free_tier_evidence` (first-party page + figures); notes updated to record the
   disproven free-tier premise. `CandidateSpec.from_dict` ignores unknown keys, so the
   pipeline loader is unaffected (pinned by test).
4. `Inference/tests/test_inf042_free_tier_routes.py` (new, stdlib-only) — 9 tests: all six
   routes covered with verdicts in the allowed vocabulary; nothing wired; no verified-free
   entry is an API route; MiniMax paid-only and matching the catalogue; the spec still
   loads through `CandidateSpec.load`; no MiniMax provider adapter exists; the substitution
   table keeps its verbatim §2 rows and gains §4; Sora 2 stays "rejected", never
   "paid-only".
5. `.github/workflows/owner-workflows.yml` — the new test added to the Inference contracts
   pytest list (the `ci_test_collection_audit.py` guard fails a PR that ships an
   uncollected test).
6. `docs/collaboration/WORK_BOARD.yaml` — TASK-INF-042 AVAILABLE → CLAIMED, owner muse_4
   (flip rides in this PR per owner order 7143628341 rule 4).

## Tests

- Local: `python -m pytest -q Inference/tests/test_inf042_free_tier_routes.py` — **9/9
  passed** (venv, Inference requirements installed, conftest loaded).
- CI: the new test is in the owner-workflows Inference contracts job; the collection
  audit guard was run locally against the branch base (see below).
- No live fleet step was taken and none exists for this task: the "live" leg is the
  vendor-page verification, filed here with dates and quotes. No account, key, or payment
  was created. No paid tier was entered.

## Re-check triggers (when a verdict must be re-read)

- Sora 2: none — the product is gone. If OpenAI ever relaunches a video model under the
  Sora name, that is a new route, not a re-check of this one.
- MiniMax: a new $0 tier or free-credit line appearing on
  `platform.minimax.io/docs/pricing/overview`, or a published free API trial with terms.
- NanoBanana: Google changing any Nano Banana model's Free Tier cell from "Not available",
  or a new Nano Banana model shipping with a free tier.
- Wan 2.6: a standing (non-expiring) free quota on Alibaba Cloud Model Studio, or
  published Wan 2.6 weights.
- SadTalker: a hosted SadTalker API with published free terms (would make it a route).
- Gamma: a free API tier on `gamma.app/pricing` (would make it a route; still a
  presentations surface, not a video route).

## States

- implemented: YES (catalogue + spec update + table §4 + guardrail test + workflow wiring)
- tested: YES (9/9 local green; CI pending on the PR)
- merged: NO (work PR open, awaiting Muse)
- deployed: N/A (no service change; catalogue + docs + test only)
- production-verified: PARTIAL — the vendor pages were verified live and the verdicts are
  filed with dates and quotes; there is no fleet live leg for this task, and no fleet step
  was taken. No route is claimed as production capacity.

— Muse 4
