# IntelX Standing Watches — Design (TASK-INT-007)

## 1. What a standing watch is

A standing watch is a narrow, always-on question IntelX keeps asking a
small set of high-signal feeds: *"did something the owner would actually
want to know just happen?"*

A watch is **not** the news ingester. The ingester
(`intelx/ingestion/news_ingester.py`) files *everything* from ~45 feeds
into the research corpus and broadcasts digests to Memora. A watch does
the opposite: it reads a handful of primary sources, applies a
deterministic significance bar, and emits **at most a few alert envelopes
per day**. Silence is the default state. A watch that cries daily is
useless, so the noise budget is a first-class part of the design, not an
afterthought.

## 2. The three watches

### 2.1 `ai_model_releases` — AI model releases  ·  **v1, enabled**

*Owner value.* FRIDAY and Inference run on Gemini/Groq/OpenRouter
models. A new frontier model, an API change, or an open-weights drop can
change what the fleet should route to. The owner should hear about it
the day it ships.

*Sources (primary publishers only, all fetch-verified 2026-11-15):*
OpenAI Blog RSS, Google AI Blog RSS, Hugging Face Blog RSS.
Anthropic is **absent on purpose**: it has discontinued its public RSS —
`news/rss.xml`, `rss.xml`, `feed.xml`, and `news/feed.xml` all return
404 (probed 2026-11-15). See §5 for the gap this leaves.

*Significance bar (score ≥ 4):* release language in the title
("introducing", "now available", "open weights", …) +3; a model family
name with a version (GPT-n, Claude Opus/Sonnet/Haiku n, Gemini n,
Llama n, Qwen n, DeepSeek, Grok n, Mistral tier) +3; developer
availability signals (API, developers, fine-tuning, context window,
pricing) in title/summary +2; the word "model" in the title +1.
Hard exclusions in the title: podcast, webinar, recap, newsletter,
sponsored, careers, conference, summit, interview, livestream.

*Noise budget:* max **1 alert per poll**, max **3 alerts per day**,
poll every 30 min.

### 2.2 `crypto_market_structure` — crypto market-structure changes  ·  designed, disabled

*Owner value.* Stratex trades Binance demo futures under a strict
rulebook. ETF decisions, listing/delisting notices, leverage/margin rule
changes, venue incidents, and stablecoin regulation change the ground it
trades on. Price chatter is explicitly excluded — structure only.

*Sources:* The Block, CoinDesk, CoinTelegraph (all already curated by
the ingester). *Bar (score ≥ 3):* ETF decision language +3; exchange
listing/leverage/margin structure +3; venue incident +3; regulator
mentions (SEC, CFTC, MiCA, stablecoin law) +2. Excludes price
predictions, analyst calls, whale alerts, memecoins.
*Budget:* 1/poll, 3/day, poll 30 min.

### 2.3 `india_tech_regulatory` — India tech & regulatory news  ·  enabled (live proof passed 2026-11-15/16)

*Owner value.* The owner is India-based: DPDP rules, MeitY actions,
RBI/SEBI digital rules, UPI changes, and app bans land directly on his
projects and accounts. Only regulator/structure items pass.

*Sources:* Times of India (the ingester's curated feed), Inc42,
YourStory — each must be re-verified live before enabling
(re-verified live 2026-11-17, all three serving fresh items). *Bar
(score ≥ 3):* a named regulator (MeitY, RBI, SEBI, TRAI, CCI, DPDP) +3;
payments-structure changes (UPI/NPCI/KYC rule changes) +3; rule-change
language (draft bill, gazette, ban, licence, compliance) +2. Excludes
funding rounds and product launches. *Budget:* 1/poll, 2/day, poll 60 min.

## 3. How a poll works

1. Fetch each source feed (RSS 2.0 / Atom), parse items.
2. **Dedupe first.** Every item is fingerprinted —
   `sha256(normalised URL)` (tracking parameters, fragments, trailing
   slashes, host case normalised away) plus a normalised-title
   fingerprint for cross-posts (titles ≥ 40 chars only; shorter titles
   are too generic to trust). If either fingerprint is in the
   persistent seen-store, the item is a duplicate and can never alert
   again. Statuses recorded per item: `alerted`, `suppressed_budget`,
   `below_threshold`, `excluded`, `baseline`.
3. **Baseline on first contact.** On a watch's first-ever poll, items
   older than `baseline_max_age_hours` (72h) — or with no date — are
   recorded silently. Enabling a watch never floods the owner with
   history.
4. **Score.** Deterministic regex rules (data in the watch definition,
   not code). Every point is recorded in the envelope's
   `score_reasons`, so any alert can be explained after the fact.
   Below-bar and excluded items are marked seen — a headline edit does
   not resurrect them.
5. **Budget.** Candidates are ordered by score (highest first), ties
   broken newest-first (TASK-INT-879: the INT-876 soak's day-7 anomaly —
   a score-5 item suppressed by budget while a newer score-3 item
   alerted — showed newest-first alone lets a lower-value alert take
   the single per-poll slot). At most `max_alerts_per_poll` fire, and
   never more than `max_alerts_per_day` per IST day. Significant items
   over budget are marked `suppressed_budget` and listed in the poll
   result — visible, counted, never drip-fed later.

State lives in one JSON file (atomic replace on save, 90-day pruning of
non-alert records): `./data/watches/state.json`, overridable with
`INTELX_WATCH_STATE_PATH`. The engine
(`intelx/watches/engine.py`) is standard-library only — no database, no
framework — so it runs inside IntelX, in CI, or standalone.

## 4. Delivery contract — TASK-PRO-001 owns the last mile

IntelX does **not** notify the owner directly. Each fired alert is
appended as one JSON object per line to the outbox
(`./data/watches/outbox.jsonl`, `INTELX_WATCH_OUTBOX_PATH`):

```json
{"schema": "intelx.watch_alert/1",
 "envelope_id": "<sha256 of watch_id + url fingerprint>",
 "dedupe_key": "intelx.watch:ai_model_releases:<fp16>",
 "watch_id": "ai_model_releases", "domain": "ai_models",
 "alert_class": "digest", "severity": "info",
 "quiet_hours_exempt": false,
 "title": "...", "summary": "...", "url": "...", "publisher": "...",
 "published_at": "...", "fired_at": "...",
 "score": 5, "score_reasons": ["release_language:+3", "..."],
 "provenance": {"source_feed": "...", "fetched_at": "...", "task": "TASK-INT-007"}}
```

Contract points for the PRO-001 crew:

* `dedupe_key` is stable across processes and restarts — safe to dedupe
  on downstream as a second line of defence.
* `quiet_hours_exempt` is false for digest-class alerts: PRO-001's quiet
  hours (23:00–07:00 IST) hold them like any other non-breaker alert.
  Since TASK-INT-015 it is **true for instant-class alerts only** (big
  breaks; §7) — the owner's instant-for-big-breaks decision supersedes
  the v1 never-exempt rule. IntelX sets the flag; PRO-001 enforces the
  policy.
* `alert_class` (`"digest"` | `"instant"`, TASK-INT-015) and `domain`
  (TASK-INT-013) ride every envelope. Instant-class envelopes are
  additionally appended to the instant outbox
  (`./data/watches/instant_outbox.jsonl`,
  `INTELX_WATCH_INSTANT_OUTBOX_PATH`) for a fast-lane drainer; the main
  outbox remains the complete record, and the `dedupe_key` contract
  above is what keeps a two-lane consumer from delivering twice.
* The outbox is append-only JSONL; a drainer can tail it or the file can
  be swapped for a direct call into PRO-001's notification path without
  changing the envelope schema.

## 5. v1 scope, proof, and known gaps

**Implemented in v1:** the engine, all three watch definitions (data),
the `ai_model_releases` watch enabled, lifespan wiring behind
`ENABLE_STANDING_WATCHES` (default **off** — the coordinator enables it
in production after merge), a `python -m intelx.watches.run_once` ops
entry point, and 14 unit tests (`IntelX/tests/test_standing_watches.py`).

**Live proof (2026-11-15, sandbox, real feeds, final source list):**
poll 1 fetched 2,314 items across the three feeds → **exactly 1 alert**
("Introducing Images 2.6", OpenAI Blog, 2026-11-04, score 5), 3
suppressed over the per-poll cap, 2,186 baselined, 122 below threshold.
Poll 2 → **0 alerts, 2,314 duplicates**. Poll 3 with a *fresh outbox* →
**0 alerts** (dedupe lives in the seen-store, not the outbox). The proof
used the documented `baseline_max_age_hours` override (30 days, so a
real recent release is eligible on first contact); all other production
defaults were untouched. Full transcript: issue #35 completion comment.

**Known gaps, stated plainly:**

* *Claude releases are not covered* until Anthropic offers a feed again
  or a follow-up task adds an HTML watch over their news page. The
  ingester's Anthropic entry carries the same dead URL and 404s today.
* The two designed watches shipped **disabled**; each enables only after
  its own live proof of the same shape as §5's. `india_tech_regulatory`
  passed its proof 2026-11-15/16 (1 alert + 1 cap-suppressed, dedupe
  exact, zero false positives) and is now enabled;
  `crypto_market_structure` remains disabled pending its own proof.
* Google AI's feed carries a deep archive (2,000+ items) — the baseline
  rule absorbs it, but the first poll is heavier than steady state.
* Significance is deterministic regex scoring, not a model judgment.
  That is deliberate for v1 (explainable, testable, zero quota cost);
  an LLM re-rank of *candidates only* is a possible v2, never a
  replacement for the dedupe/budget machinery.

## 6. Topic domains — TASK-INT-013 (2026-11-18)

Owner decision 2026-11-18: IntelX researches **everything** the Universe
works in, not only trading. The unit of that widening is the *domain*
(`intelx/watches/domains.py`): every watch declares exactly one domain via
`WatchDefinition.domain`, the envelope carries it (`"domain"` key), and a
`WatchRunner` can be scoped to a set of domains. Adding a research area is
one `DomainSpec` plus its watches — never an engine change.

| Domain | Watches | State |
|---|---|---|
| `ai_models` | `ai_model_releases` | enabled (INT-007 proof) |
| `markets` | `crypto_market_structure` | designed, disabled |
| `india_regulatory` | `india_tech_regulatory` | enabled (INT-007 proof) |
| `platforms_policy` | `platform_policy` | **new, disabled** |
| `tools_infra` | `fleet_tools` | **new, disabled** |
| `world_events` | `world_events` | **new, disabled** |
| `general` | — (undeclared fallback) | classification debt, not a home |

The three new watches follow the INT-007 discipline exactly: deterministic
rules tuned on real headlines from their feeds (fetch-verified 2026-11-18),
denial/commentary exclusions from day one, per-poll and per-day caps, and
`enabled=False` until each passes its own live proof of the §5 shape.
Sources: YouTube Official Blog + Meta Newsroom (`platforms_policy`);
Python Insider + GitHub Blog (`fleet_tools`); Al Jazeera (`world_events` —
BBC World was first choice but its feed could not be verified from the
build environment, so it is not shipped on faith). Ops:
`python -m intelx.watches.run_once --domain <id>` polls a whole domain.
Domains are also the subscription unit for the Universe intel feed
(TASK-INT-014).

## 7. Alert policy: instant for big breaks, one digest for the rest — TASK-INT-015 (2026-11-18)

Owner decision 2026-11-18: instant alerts for big breaks, a digest for
everything else — replacing the v1 behaviour where every watch alert
rode the same digest terms. Each watch now declares
`instant_min_score`: an alert scoring at or above it is **instant-class**
(`alert_class: "instant"`, `severity: "high"` — the fleet's existing
severity vocabulary — `quiet_hours_exempt: true`, and a copy in the
instant outbox); below it, alerts are **digest-class**, byte-identical
in contract to v1. A watch with no bar (`None`) never alerts instantly.

The bars are derived, not picked: each is the score at which the item
carries the watch's heaviest rule **plus independent corroboration** —
`ai_model_releases` 6 = release_language(3) + model_name_with_version(3);
`crypto_market_structure` 6 = any two weight-3 structure rules;
`india_tech_regulatory` 6 = regulator_action(3) + payments_structure(3);
`platform_policy` 6 = policy_surface(3) + change_language(2) +
platform_name(1); `fleet_tools` 7 = security_event(3) +
python_version(2) + release_event(2); `world_events` 5 =
infra_outage(3) + impact_scale(2) (an outage *with* impact — a bare
outage mention stays digest). `PollResult.alerted_instant` counts the
instant class per poll, so the policy is observable, not implicit.

Downstream follow-up (PRO-001's lane, stated plainly): the instant
outbox is a new file for a fast-lane drainer to deliver from; until one
reads it, instant-class alerts still reach the owner through the main
outbox exactly as before — the policy change can make delivery faster,
never slower or lost.

**Fast lane landed (TASK-INT-016):** FRIDAY's PRO-002 drainer now
tails `instant_outbox.jsonl` on a short cadence
(`FRIDAY_PROACTIVE_INTELX_INSTANT_WATCH_INTERVAL_SECONDS`, default
15s) through the SAME drainer state as the main lane — the persisted
`dedupe_key` record is shared, so an instant envelope is delivered
exactly once across both lanes, by whichever reaches it first. The
fast lane has its own silent baseline, honours the envelope's
`quiet_hours_exempt` flag, and runs under the same
`FRIDAY_PROACTIVE_INTELX_WATCH` kill switch (code default OFF;
enabling it in production remains a separate coordinator step).
