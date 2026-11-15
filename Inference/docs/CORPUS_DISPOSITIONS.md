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

## Summary

- Free-token cluster (7 items): verify-and-note; **zero wired in**,
  each for a stated reason.
- Subscription pooling (1 item): not adopted (grey route; the
  legitimate need is already served by cross-provider failover).
- Already-implemented (7 items): verified against named production
  code paths.
- Repos: FreeLLMAPI and OmniRoute reference-only; one future
  candidate recorded (token compression, evidence-gated).
