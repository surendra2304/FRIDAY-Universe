# Free-for-Paid Substitution Table — routing & evaluation knowledge (TASK-IG3-INF-01)

Source: Instagram corpus item **DTVYncBj6E1** (@fahm.ai, 2026-01-10),
an 8-slide "Paid AI VS Free AI" carousel, browser-watched in full and
graded FULL in the re-watch (package entry I-10, shared with the
VyralX lane as V-06). Framing pattern: **DTA4DlUEXDH** (@ai.mowa,
2026-01-02 — LM Arena + OpenAlternative + OpenApps Pro walkthrough,
package cross-reference in `docs/CORPUS_DISPOSITIONS.md`).

This file closes the gap the Inference baseline recorded as B44:
until now no substitution-table artifact existed anywhere in
Inference — the wave-1 "free-vs-paid shortlist" survived only as
narrative in the dispositions doc.

**What this table is:** catalogue knowledge for model/tool
selection — the owner's design rule is that Inference "should give
the best suitable model from the models it has", and knowing the
free alternative for a paid capability is part of that knowledge.

**What it is not:** capacity. A row here is not wired, not routed,
and not a claim that the named alternative is actually free. Lane
standing rules apply unchanged: free tiers only; nothing enters
routing without the TASK-IG-INF-03 evaluation (serve-check + fixed
INF-005 bench, `benchmarks/candidate_eval.py`); no grey-market
intermediaries as capacity.

## 1. The evaluation pattern (DTA4DlUEXDH)

The reel walks three sites that answer "which tool should I use,
and what is the free alternative?" in two distinct ways. Both
halves exist in Inference, in different states:

1. **Side-by-side comparison evidence (LM Arena).** The walkthrough
   recovers LM Arena's Battle / Side-by-Side / Direct Chat modes
   and its leaderboards. Inference's form of this is already
   implemented: `benchmarks/candidate_eval.py` benches every
   candidate on the fixed INF-005 testset against the recorded
   reference baseline and emits the candidate-vs-reference
   comparison table (TASK-IG-INF-03). There is deliberately no
   blind A/B arena UI — the bench is deterministic and
   programmatic, which is stronger evidence than arena votes for
   an admission decision.
2. **Alternatives shortlist (OpenAlternative / OpenApps).** A
   maintained per-category list of free/open alternatives to paid
   tools. This half was the missing artifact; §2 is that list,
   seeded from the one corpus item that states it concretely.

## 2. The table (verbatim from DTVYncBj6E1)

Prices and names are the carousel's own, recorded as written.
The closing slide reads: *"Paid AI or Free AI? Choose smart.
Not expensive."*

| Category | Paid tool (claimed) | Free alternative (claimed) | Verification status | Inference disposition |
|---|---|---|---|---|
| Video Creation | Google Veo 3 — $249/month | Sora 2 — $0/month | **Disputed in the source's own comments** ("Sora 2 not free"; free version reported limited to 5-second clips) | Media-generation route, not an LLM-gateway provider. No Inference action; catalogue knowledge, VyralX-shared (V-06). |
| Audio Generation | ElevenLabs — $99/month | MiniMax — $0/month | **Disputed in the source's own comments** (MiniMax reported to require payment / credits) | The one row touching an existing Inference candidate. MiniMax already has a candidate spec (`benchmarks/candidates/minimax.json`) and stays **spec-only, BLOCKED_NO_CREDENTIALS — no provider adapter**, by standing design. This row changes nothing about that state; if a first-party MiniMax free tier with published terms is ever provisioned a key, it graduates via §3 like any other candidate. |
| Image Generation | Seedream 4 — $39/month | NanoBanana — $0/month | **Disputed in the source's own comments** (commenters asking where the free tier is; limits reported) | Media-generation route, not an LLM-gateway provider. No Inference action; catalogue knowledge, VyralX-shared (V-06). |
| Cinematic Creation | RunwayML — $76/month | Wan 2.6 — $0/month | **Disputed in the source's own comments**; the creator's own replies name the access points `wan.ai` / `wan.video` | Media-generation route, not an LLM-gateway provider. No Inference action; catalogue knowledge, VyralX-shared (V-06; the Wan2GP item is packaged separately as V-08). |
| Avatar Creation | HeyGen — $39/month | SadTalker — $0/month | **Unverified** — not individually disputed in the fetched comments; the $0 claim itself is unproven (the post-wide comment "Not even a single ai is free everything is fake" is recorded against the carousel as a whole) | Media-generation route, not an LLM-gateway provider. No Inference action; catalogue knowledge, VyralX-shared (V-06). |
| Presentations / Design | Plus AI — $20/month | Gamma AI — $0/month | **Unverified** — not individually disputed in the fetched comments; $0 claim unproven | Productivity-tool surface, outside Inference's provider pool. No Inference action; catalogue knowledge only. |

Net reading: of the six claimed $0 routes, four are disputed by
name in the source's own comment thread and two are unverified.
**Zero rows are verified free capacity.** That is the expected
state for a social-media shortlist, and it is exactly why the
table is knowledge, not routing.

## 3. How a row graduates (and how this table is maintained)

A row becomes capacity only through the existing pipeline —
the same one MiniMax and Bytez sit in:

1. The alternative resolves to a **named provider's first-party
   free API tier with published terms** (a reel's say-so, a
   gateway's aggregate headline, or a comment thread does not
   meet this bar).
2. A candidate spec is filed in `benchmarks/candidates/`.
3. TASK-IG-INF-03 evaluation: credential/route gate →
   serve-check (the served model id must equal the requested
   id) → fixed INF-005 bench → candidate-vs-reference table →
   verdict ADMIT / REJECT / BLOCKED_*.
4. Admission to the catalogue itself remains a
   coordinator step (MODEL_CATALOG + REL-043 rankings), on the
   pipeline's evidence.

Maintenance: rows are added or reworded only from watched
corpus items or first-party provider pages, with the source
named in the row's status cell. A row's status moves to
VERIFIED only with IG-INF-03 evidence or the provider's own
published free-tier terms — and the dispute notes move with it,
so a later reader sees both the claim and what was said against
it.

## 4. Live verdicts (TASK-INF-042, 2026-11-25)

Every row in §2 was checked live against the vendor's own
pricing/terms page by Muse 4 on 2026-11-25. The machine-readable
record is `config/free_tier_routes.json`; the full evidence
(method, per-route findings with quotes, re-check triggers) is
`docs/collaboration/TASK-INF-042-FREE-TIER-ROUTE-CATALOGUE.md`.
No account was created, no key provisioned, no payment made.
A route counts as verified-free API capacity only if the
vendor's own published terms state a standing $0 API tier.
One-off signup/trial credits, consumer-app free use, and
reseller credit hosts are not API capacity.

| Free alternative (claimed) | Live verdict 2026-11-25 | What the vendor's own page says |
|---|---|---|
| Sora 2 | **REJECTED — discontinued** | OpenAI shut the Sora app 2026-04-26 and the Videos API + all `sora-2` snapshots 2026-09-24, no replacement. The live deprecations page no longer lists it (the row aged off after shutdown). No free tier, no paid tier, no route at any price. |
| MiniMax | **PAID-ONLY** | `platform.minimax.io/docs/pricing/overview`, read live: no free tier and no free credits stated anywhere; pay-as-you-go deducted from a funded balance. M3 $0.30/$1.20, M3.1-Flash $0.15/$0.60 per 1M tokens; TTS $60–$100/M chars; Audio Packages from $5/mo. **MiniMax is NOT wired** — the TASK-INF-042 condition "wired if verified free" fails. The candidate spec stays `BLOCKED_NO_CREDENTIALS`, spec-only, no provider adapter. |
| NanoBanana | **PAID-ONLY** | Gemini Developer API pricing page, read live: Free Tier "Not available" for `gemini-2.5-flash-image` on every tab; $0.039/image. The model is deprecated, shutdown 2027-03-15. Free only inside Google's consumer apps (Gemini app / Flow / AI Studio), not the API. |
| Wan 2.6 | **PAID-ONLY** | Alibaba hosted-only, no public weights for 2.6. Model Studio API $0.10/s (720p) / $0.15/s (1080p) in Singapore, with a 50-second new-user trial quota per model, valid 90 days — a trial, not a standing free tier. `wan.video` Free $0 plan is daily check-in credits with a watermark, testing-only, no commercial licence. (Direct `wan.video` read failed — JS page; figures are dated third-party reads of Alibaba's own pages, 2026-10-02 / 2026-10-25 / 2026-11-03.) |
| SadTalker | **VERIFIED-FREE (software) — not a route** | Open-source, Apache 2.0 per the README (GitHub's licence detector reports NOASSERTION — discrepancy recorded), runs offline, no hosted service, no API. A local-GPU pipeline component would need its own evaluation; it cannot be wired as an Inference provider. |
| Gamma AI | **VERIFIED-FREE (consumer plan) — not a route** | `gamma.app/pricing`, read live: Free $0 plan, no credit card required, up to 10 slides per prompt, import/export. API access is a Pro feature ($18/mo), so there is no free API tier; presentations are outside Inference's provider pool in any case. |

Net reading after the live check: **0 of 6 routes verify as free
API capacity.** The carousel's $0 column is, as §2 already
suspected, entirely unusable as routing. The two verified-free
entries are not API routes, so nothing in this catalogue enters
routing — every entry in `config/free_tier_routes.json` has
`wired: false`, and `tests/test_inf042_free_tier_routes.py`
fails if that ever changes without a new dated first-party read.
