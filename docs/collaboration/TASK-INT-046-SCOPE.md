# TASK-INT-046 — Scope: Telegram topic-search source discovery for the standing watches

**Owner:** Muse 14. **Claim:** hub #1483 comment 7175223802 (~03:03 IST 2026-11-26).
**Branch:** `muse14/task-int-046-telegram-topic-search`. **Base:** main `489a1b3b`.
**Queue:** INT-043 (head, live leg parked by the owner stop order) → INT-046 → TASK-VYR-072-FIX-01.

**Acceptance (board, verified first-hand on main 489a1b3b):** "A topic query returns a
candidate-source list (relevant public Telegram channels/groups/resources) that IntelX can
propose for watch inclusion. Distinct from Sentinel's known-channel monitoring (TASK-IG-SEN-03)."

## Finding 1: IntelX has no Telegram client at all — discovery must be built, not wired up

Verified first-hand on main `489a1b3b` (repo-wide search, 2026-11-26 ~03:10 IST):

- No Telethon, Pyrogram, MTProto, `TELEGRAM_API_*` setting, or `t.me` handling anywhere in
  `IntelX/` code. The word "telegram" occurs in IntelX only twice: as a platform string in
  the IntelBase email-lookup platform list (`IntelX/app/agents/real_intelx_osint.py:685`)
  and in a comment in `IntelX/intelx/ingestion/headline_watch.py:81`.
- There is therefore no existing Telegram seam to consume. The work is a new, small,
  credential-free discovery service built on seams that already exist — not a client
  integration and not a credential request.

## Finding 2: the Sentinel precedent (SEN-03) is the pattern — and the boundary

`Sentinel/sentinel/integrations/threat_feeds/telegram_channels.py` (TASK-IG-SEN-03) already
monitors **known, configured** public channels by fetching the public web preview
`https://t.me/s/<channel>` and parsing message blocks with a small HTML parser — no Telegram
account, no API key, no bot, nothing posted or joined; fail-closed on any fetch/parse failure.

INT-046 is the other half of that pattern and is distinct by design:

| | SEN-03 (Sentinel) | INT-046 (IntelX, this task) |
|---|---|---|
| Input | a configured channel list | a topic query |
| Output | matches in known channels | a candidate-source list of channels/groups for a topic |
| Question answered | "did something happen in channels we already watch?" | "which public channels should a watch consider?" |

INT-046 must implement its own preview parsing in IntelX (it must not import Sentinel's
module — different package, different failure domain); it may follow the same public-preview
approach, which is the only credential-free way to verify a candidate channel exists and
what it is about.

## Finding 3: the seams the discovery service composes with

All verified first-hand on main `489a1b3b`:

1. **Search** — `IntelX/intelx/connectors/search.py`: `WebSearchConnector` routes
   Tavily (keyed, `TAVILY_API_KEY` / `INTELX_TAVILY_API_KEY` in
   `IntelX/intelx/core/settings.py:336`) → Google News RSS / Wikipedia → DuckDuckGo HTML
   (keyless fallback). A `site:t.me <topic>` query through this seam returns candidate
   channel pages with no new credential. This is the discovery route.
2. **Read-only fetch** — `IntelX/intelx/connectors/social_links.py` (`SocialLinkReader`):
   read-only GETs only, injectable fetchers for hermetic tests, composed with
   `HttpFetchConnector` (SSRF guard, robots.txt, byte caps). Its `classify_social_url`
   knows youtube/reddit/instagram/web — it has no telegram host, so the Telegram preview
   reader is a new small module in this style, not an edit to the social-link classifier.
3. **Named-source registry** — `IntelX/intelx/connectors/named_sources.py`: the
   `NamedSource` registry (`api_keyless` / `api_keyed` / `seed_site`) plus
   `seed_search_url` is the pattern for registering a discoverable source with its access
   note and search-URL template. Telegram public preview registers here as `api_keyless`.
4. **Watches** — `IntelX/intelx/watches/engine.py`: `WatchDefinition.sources` is a
   `tuple[FeedSource, ...]` and `FeedSource` is an RSS/Atom URL + publisher; the poller
   parses feeds. A Telegram channel has no RSS feed, so **"propose for watch inclusion"
   cannot mean "append a FeedSource"** — it needs either a new Telegram-channel source
   kind polled via the `t.me/s/` preview (same credential-free pattern as SEN-03) or a
   decision that inclusion stays a manual step until that adapter exists. This is a design
   decision for the implementation step, recorded here so it is not discovered late.
5. **Routes** — `IntelX/intelx/api/v1/osint_tools.py` (`osint_tools_router`, e.g.
   `GET /osint/social-link`) and `IntelX/intelx/api/v1/feeds.py` are the mount points.
   Planned surface: `GET /api/v1/osint/telegram-topic-search?topic=...` returning the
   candidate list with provenance per candidate.
6. **Settings** — no Telegram setting exists. A feature flag following the INT-043 pattern
   (e.g. `ENABLE_TELEGRAM_TOPIC_SEARCH`, default `False`) gates the route until the live
   leg proves it.

## Discovery routes evaluated

- **A. Web search `site:t.me` + `t.me/s/` verification (primary).** Credential-free,
  implementable repo-side now: query the existing search seam, take candidate handles,
  fetch each channel's public preview, score by topic relevance (title/description keyword
  match, subscriber count when the preview carries it, recent-post relevance), return a
  ranked candidate list with provenance (search result + preview URL + fetch time).
  Limits: search-engine coverage of Telegram, preview rate limits, subscriber counts not
  guaranteed in the preview.
- **B. Public channel directories (tgstat, telemetr, …).** Third-party services with their
  own terms and rate limits. Not the primary route; evaluate only if route A proves too
  thin, and record the terms check before using one.
- **C. MTProto client (Telethon) global search.** Needs `api_id`/`api_hash` plus a logged-in
  account/session — owner credentials and clearance. **Gated; not attempted in this run.**
- **D. Bot API.** No global search method exists. Not viable.

## Repo-side work (this task)

1. New module `IntelX/intelx/connectors/telegram_topic_search.py`: candidate discovery
   (route A) — search-seam query builder (`site:t.me`), preview fetch + parse, relevance
   scoring, dedupe, ranked `TelegramCandidateSource` list with provenance. Fetchers
   injectable; fail-closed (a fetch/parse failure yields zero candidates from that source,
   never invented ones).
2. Register Telegram public preview in `named_sources.py` as an `api_keyless` named source.
3. Route `GET /api/v1/osint/telegram-topic-search` in `osint_tools.py` (flag-gated,
   default off), returning the candidate list.
4. Record the watch-inclusion design decision (new Telegram-channel source kind vs manual
   inclusion) in this doc before implementing the propose step.
5. Tests: new `IntelX/tests/test_ig_intelx_telegram_topic_search.py` — hermetic, injected
   fetchers: query construction, preview parsing (real `t.me/s/` fixture shape), dedupe,
   ranking, fail-closed on fetch failure, flag-off route behaviour. No live Telegram calls
   in tests.

## Design decision: watch inclusion — MANUAL (recorded before implementation)

**Decision: inclusion stays a manual step in this task; no new Telegram-channel
source kind is built here.**

- `WatchDefinition.sources` is a `tuple[FeedSource, ...]` and `FeedSource` is an
  RSS/Atom URL + publisher (`IntelX/intelx/watches/engine.py:74`). A Telegram
  channel has no RSS feed, so a `t.me/s/<handle>` URL cannot be appended as a
  `FeedSource` — the poller parses feeds, and an HTML preview page would break
  it. "Propose for watch inclusion" therefore cannot mean "append a FeedSource".
- The alternative — a new Telegram-channel source kind polled via the `t.me/s/`
  preview (same credential-free pattern as SEN-03) — needs a new source-kind
  type, a poller path, and a watch-definition change. That is a separate
  adapter task with its own acceptance, not part of INT-046.
- What INT-046 delivers for "propose": every candidate carries a structured
  `proposal` (channel handle, preview URL, title, description, relevance
  score, provenance, `inclusion: "manual"` + the reason, and the suggested
  watch-source record a human/coordinator would add). The route returns
  candidates with proposals; a human reviews and adds the channel manually
  (or a follow-up task builds the adapter). Nothing in this task pretends
  the channel is already a watch source.

## Gated items (not attempted; exact reason each)

- **Live discovery verification** (a real topic query returning real channels): needs live
  web fetches from a host that can reach Telegram/search engines, or MTProto credentials.
  No live Telegram call was attempted in this run; the repo-side code is verified by
  hermetic tests only until the live leg runs.
- **Watch inclusion end-to-end** (a discovered channel feeding a standing watch): needs
  the Telegram-channel source-kind adapter (see Finding 3.4) plus, for any server-side
  enablement, the owner stop order to lift — enabling anything on IntelX-Server is a
  server move.
- **MTProto global search (route C):** needs owner-supplied `api_id`/`api_hash` and a
  logged-in session; a credential decision, not a code decision.

## Five states

- Implemented: NO (scope only in this PR; the service, route, and tests are the
  implementation step).
- Tested: NO (no tests yet; hermetic suite listed above is the test step).
- Merged: NO (this work PR, when filed).
- Deployed: NO (IntelX lives on IntelX-Server; the route is flag-gated off by default).
- Production-verified: NO (one live topic query returning a real candidate list is the
  live leg; gated as above).

— Muse 14
