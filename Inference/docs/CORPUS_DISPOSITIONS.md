# Corpus Dispositions — Free-Token Cluster, Subscription Pooling, Already-Implemented (TASK-IG-INF-05)

The Instagram reference corpus sent 23 items to the Inference lane.
Nine distinct new ideas were implemented as TASK-IG-INF-01…04 and
-06. This record disposes of the remainder — the free-token cluster,
the subscription-pooling item, and the seven items the roll-up
classified already-implemented — each verified against the production
code paths it claims, not against the reels' own descriptions.

Rules applied (lane standing orders): free tiers only; **no
grey-market token schemes wired in as capacity**; INF-005 discipline
— nothing enters routing without the TASK-IG-INF-03 evaluation;
THIRD_PARTY_* key sets stay isolated from the main pools.

## The production baseline these items were checked against

All of this is in production code on main today:

- **Multi-provider key pools** — `app/providers/gateway.py`:
  one `KeyPool` per provider, round-robin across that provider's
  keys, 60-second quarantine of a key on 429/503. Keys come from
  per-provider env lists (`app/core/config.py`
  `get_provider_keys`: `<PROV>_API_KEY` / `<PROV>_API_KEYS`,
  comma-separated — e.g. five Gemini keys on one line, the
  11+14+14 Inference pools).
- **Quota ledger** — `app/providers/quota_ledger.py` (`QuotaLedger`):
  per-provider quota state recorded per call.
- **Failover ladder** — `ModelGateway.execute`: on exhaustion or
  transient failure, capability-matched fallback to another provider
  rather than an error to the caller.
- **Best-suitable selection** — TASK-REL-043 in
  `app/api/v1_core_routes.py`: a named model the gateway does not
  have is never forwarded; the best suitable verified-catalogue
  model for the task type serves, with provenance recorded.
  TASK-REL-049's servability quarantine policy composes on top
  (in the merge queue as PR #371 at the time of writing).
- **One OpenAI-compatible surface** — `/v1/chat/completions` and
  `/v1/models` over all pools, behind `X-INFERENCE-API-KEY` auth.

## Free-token cluster — VERIFY-AND-NOTE (none wired in)

The cluster's shared claim shape: a third party offers a very large
number of "free" frontier-model tokens. In every case the legitimate
core of the idea — *pool first-party free tiers behind one gateway* —
is already the production baseline above. What the reels add on top
is an unverified intermediary, and that part is not adopted.

| Item | Claim | Verification | Disposition |
|---|---|---|---|
| DcqsV6Sxg63 | A GitHub repo gives ~1.6B free tokens/month across 300+ providers | The figure is the OmniRoute/FreeLLMAPI-class headline; OmniRoute's own card states it is *an aggregate of third-party free tiers you connect yourself, not a grant*. The aggregation is what Inference already does with first-party tiers. | Noted; nothing to wire — the mechanism exists, the "grant" does not |
| Ddd2p9qCioT | Websites offering free "ChatGPT-6 Astra" access | No provider in our pools (or any first-party catalogue checked) serves a model by that name; the portals are unnamed and unverifiable. | Noted as unverified; a named candidate would enter via IG-INF-03 |
| Dd6c-FUiby4 | Free "GPT-6 Astra/Sol" via OmniRush | The creator's own test was mixed, per the corpus gist; the gateway is unverified and the model names unverifiable. | Noted with scepticism; not wired |
| DdeOtvDk9lh | 100M free tokens in VS Code via Atria / an "OLLKIL" gateway | A third-party token gateway of unknown provenance — the grey-market pattern (aggregated/resold tokens) the lane rule excludes. | Not wired |
| Dd_oQGSzUfQ | 100M free "GPT-6 Astra" tokens received, with setup guide | Same family as above: unverifiable model name, unverified grant, unknown intermediary. | Not wired |
| DcbD5wOtqJd | "Unlimited Claude Code (Free)" workaround | By construction this spends a consumer app's allowance as API capacity — a terms-circumvention pattern, not a free API tier. | Not wired; named here as the category the no-grey-market rule exists for |
| Dd6dFTXKxHg | 5M free tokens + free "ChatGPT-6 Astra" access | Advertisement-grade claim, no verifiable provider, model, or terms. | Not wired |

What would change any of these: the offer resolving to a *named
provider's first-party free API tier* with published terms. Then it
becomes a candidate spec and goes through IG-INF-03 (serve-check +
bench) like MiniMax and Bytez — it does not get wired in on a reel's
say-so.

## Subscription pooling — NOT ADOPTED

| Item | Claim | Verification | Disposition |
|---|---|---|---|
| DdHqQSCqbH_ | An open-source bridge lets Codex spend the ChatGPT **web** allowance when the API quota hits 0% | The mechanism is real as described, but it consumes a consumer subscription through a surface it was not sold for. Inference's legitimate version of "work continues when one quota is exhausted" already exists: failover across *independent API free tiers* (ladder + quota ledger above). | Not adopted — grey route, and unnecessary given the ladder |

## Already-implemented — verified against code

Each item's idea was checked against the production mechanism named;
"already-implemented" here means the mechanism is in the code paths
cited in the baseline section, not merely that something similar
exists.

| Item | Idea | Verified in |
|---|---|---|
| DdPncBxAQoz | Automatic provider failover on quota exhaustion (OmniRoute et al.) | KeyPool 429/503 quarantine + gateway capability-matched fallback ladder + quota ledger. OmniRoute itself: reference-only per its card |
| DdoWt0xju0C | One platform unifying many frontier models (ChatLLM) | `/v1/*` OpenAI-compatible surface over all provider pools |
| DebPn6BCd43 | One workspace, many top models, free credit allowance (SuperApp) | MODEL_CATALOG over pooled first-party free tiers behind one endpoint; the "allowance" is the providers' own free tiers |
| DeZfUfnAH5w | Proxy over free models, auto-switching on rate limits ("Free Claude Code") | Multi-model routing with failover on limits: quarantine + ladder + REL-043 best-suitable substitution with provenance |
| DehGGzLiaNI | 40+ models behind one key with a daily free allowance (xKiro) | Multi-provider key pool behind the single gateway credential (`X-INFERENCE-API-KEY`) |
| Dew8LfBDvhf | 34 models served free from one setup | The gateway's pooled free tiers across providers |
| DezJrpTRAQh | FreeLLMAPI: pool 30+ providers' free tiers behind one endpoint/key | The pattern itself, in production (see baseline). FreeLLMAPI: reference-only per its card |

## Repo dispositions (Inference cards)

- **FreeLLMAPI** (github.com/tashfeenahmed/freellmapi) —
  **reference-only**. Inference already implements the pattern in
  production; the card's only cherry-pick is comparing catalogue
  breadth, which is a reading exercise, not a build.
- **OmniRoute** (github.com/cheaper-inference/OmniRoute) —
  **reference-only** for the gateway itself. One genuine cherry-pick
  is recorded as a **future candidate, not implemented here**:
  *token compression* (the card reports a claimed 15–95% saving) to
  stretch free-tier quotas. It is explicitly distinct from
  TASK-REL-047's Groq prompt guard: the guard is a
  safety/correctness control, compression is a quota-economics
  transform that can degrade answer quality — so if it is ever
  pursued, it needs IG-INF-03-style before/after bench evidence on
  the fixed testset first, and its own task.
  *Update (2026-11-16, TASK-IG3-INF-02): token compression has
  since been implemented natively as TASK-IG2-INF-04 (PR #710 —
  `app/providers/token_compression.py`, wired fail-open into the
  gateway), so the future-candidate status above is superseded.*

## Re-watch evaluations — 2026-11-16 (TASK-IG3-INF-02)

The full re-watch sent three further Inference items for
evaluation (package entries I-11 and I-12). Each was evaluated
against the production baseline above and against the projects'
own current documentation. **No adapter was built for any of
them**; the reasons are the deliverable.

| Item | Claim | Verification | Disposition |
|---|---|---|---|
| Da-cwtZs1T7 (I-11) | FreeLLMAPI: "4 billion free tokens/month", hundreds of free endpoints, a fallback chain incl. MiniMax 2.5 / Qwen 3 / GPT-OSS 120B / Gemini 2.5 Pro & Flash | FreeLLMAPI is **self-hosted software, not a hosted route** (github.com/tashfeenahmed/freellmapi, MIT): it pools the user's *own* first-party free-tier keys behind one OpenAI-compatible `/v1` endpoint, and the token figure is the aggregate of listed free tiers, not a grant — the project's own docs state it does not generate extra quota. The project scopes itself to personal experimentation, not production; its only paid element is an optional live-catalog subscription ($19/yr), which matches the "Not free 19/month" dispute in the item's comments. The pooling mechanism is Inference's production baseline, in production today. | **No adapter** — there is no hosted endpoint to adapt to, and running a second gateway beside the native one adds an unmaintained hop, not capacity. If an instance is ever run, TASK-IG-INF-02 custom endpoints already consume any OpenAI-compatible endpoint with zero new code. Reference-only, extending the wave-1 DezJrpTRAQh disposition to this second source |
| DcqsV6Sxg63 (I-12) | OmniRoute README detail: 351 providers, ~1.51B free tokens/month, RTK compression, /v1 API translation, 35 CLI integrations | Also **self-hosted gateway software** (MIT). Repo provenance is inconsistent across records — the item's narrative names diegocousapw/OmniRoute, current project sources name diegosouzapw/OmniRoute, and the wave-1 card above names cheaper-inference/OmniRoute; the discrepancy is recorded, not resolved. The free-token figure is an aggregate of providers' free tiers. An independent hands-on review found the keyless out-of-box path does not serve until credentials are configured. **Security:** CVE-2026-88062 / GHSA-hf57-cqmx-p4gr (disclosed 2026-09-03) — unauthenticated remote code execution via the custom ACP agent endpoint when `requireLogin` is off, in a gateway whose job is to hold every provider key; vendor, NVD and advisory-database reports disagree on which version is fixed. | **No adapter** — the pattern is already native (baseline), and a third-party key-holding gateway with a critical unauthenticated-RCE record does not enter this fleet's request path. Reference-only stands (repo disposition above, updated). Its one transferable idea, token compression, has since been implemented natively (TASK-IG2-INF-04) |
| Ddlk8oQyOVO (I-12) | "Model Router for Codex": add any model — including free ones — to Codex and avoid weekly limits | The GitHub URL is truncated in-frame and was never recovered, so the project **cannot be identified** — and an unidentifiable project cannot become a candidate spec (IG-INF-03 requires a named provider and a route). What is visible is a client-side Codex CLI configuration tool; the creator's own comment records a bug in a previous version where requests still went to OpenAI instead of the selected model. Editor/CLI surfaces are outside the Inference server scope (wave-2 baseline B42/B43), and the server-side capability such tools rely on — arbitrary OpenAI-compatible endpoints — already exists (TASK-IG-INF-02 + the `/v1` surface). | **Not a candidate; no adapter.** Recorded as evaluated so the item is not re-triaged from scratch |

What would change any of these: the same bar as the free-token
cluster above — a *named provider's first-party free API tier*
with published terms appearing behind one of them. That becomes
a candidate spec and goes through IG-INF-03; it does not become
an adapter to the intermediary.

## Summary

- Free-token cluster (7 items): verify-and-note; **zero wired in**,
  each for a stated reason.
- Subscription pooling (1 item): not adopted (grey route; the
  legitimate need is already served by cross-provider failover).
- Already-implemented (7 items): verified against named production
  code paths.
- Repos: FreeLLMAPI and OmniRoute reference-only; the one
  recorded future candidate (token compression) has since been
  implemented natively (TASK-IG2-INF-04).
- Re-watch evaluations (3 items, TASK-IG3-INF-02): FreeLLMAPI
  second source, OmniRoute README detail, Codex model-router —
  no adapters built, each for a stated reason.
