# TASK-INT-046 — Implementation: Telegram topic-search source discovery

**Owner:** Muse 14. **Branch:** `muse14/task-int-046-telegram-topic-search`.
**Base:** main `df4e261b`. **Claim PR #1900 merged** (scope only); this is the
implementation step. **No live leg yet** — one work PR carries finished work
+ live evidence; the live leg is gated (see below), so this PR carries the
repo-side work + a blocked-with-reason note.

## What changed

| File | Change |
|---|---|
| `IntelX/intelx/connectors/telegram_topic_search.py` | **New.** Route-A discovery: `site:t.me` search-seam query builder, public-preview (`t.me/s/<handle>`) fetch + stdlib HTML parse, relevance scoring, dedupe, ranked `TelegramCandidateSource` list with provenance + a manual watch-inclusion `proposal` per candidate. Fetchers injectable; fail-closed. |
| `IntelX/intelx/connectors/named_sources.py` | Registered "Telegram Public Preview" as an `api_keyless` named source (`https://t.me/s/{q}` = channel handle → preview). |
| `IntelX/intelx/core/settings.py` | `ENABLE_TELEGRAM_TOPIC_SEARCH` (bool, default `False`), following the INT-043 flag pattern. |
| `IntelX/intelx/api/v1/osint_tools.py` | `GET /api/v1/osint/telegram-topic-search?topic=...` — flag-gated (503 while the flag is off), returns `{topic, query, count, candidates[]}`. |
| `IntelX/tests/test_ig_intelx_telegram_topic_search.py` | **New.** 23 hermetic tests, injected fakes; no live Telegram calls. |
| `.github/workflows/friday-universe-ci.yml` | New test file added to the IntelX tier-1 pytest list (REL-068: uncollected test files fail the contracts check). |
| `docs/collaboration/TASK-INT-046-SCOPE.md` | Watch-inclusion design decision recorded (manual inclusion; see below). |

## Design decision: watch inclusion is MANUAL

Recorded in the scope doc before implementing the propose step. `FeedSource`
is an RSS/Atom URL + publisher and a Telegram channel has no RSS feed, so a
candidate cannot be appended as a `FeedSource` — the poller parses feeds and
an HTML preview page would break it. The Telegram-channel source-kind
adapter (polled via the `t.me/s/` preview) is a separate follow-up task.
Every candidate therefore carries a structured `proposal`
(`inclusion: "manual"` + reason + suggested record) that a human/coordinator
reviews and adds. The route proposes; it does not enroll.

## How it works

1. `build_search_query(topic)` → `site:t.me <topic>`; the existing
   `WebSearchConnector` runs it (Tavily → SearXNG → Google News/Wikipedia →
   DuckDuckGo, as today). A search failure yields zero candidates.
2. `extract_handles(results)` pulls channel handles from `t.me/<handle>`,
   `t.me/s/<handle>` and `t.me/<handle>/<id>` links, deduped, order kept;
   reserved paths (`joinchat`, `addstickers`, …) and malformed handles are
   dropped.
3. Each handle is verified against `https://t.me/s/<handle>` via
   `HttpFetchConnector` (the social-links `FetchBytes` shape). Non-200,
   fetch error, or an unverifiable preview (no title, no description, no
   posts) skips that handle — never invented.
4. `parse_channel_preview` (own stdlib parser, NOT Sentinel's module)
   reads og:title/og:description, the `tgme_channel_info` header title /
   description / subscriber counter, and recent `tgme_widget_message_text`
   posts. Subscriber counts are reported only when the preview carries them.
5. `score_candidate` scores deterministically in [0, 1]: title hits ×3,
   description ×2, recent-post hits ×1, normalised by term count; a
   subscriber count adds at most 0.05 as a tiebreak and can never outweigh
   a term match. Ranking: score desc, subscribers desc, handle asc.
6. The route returns candidates with provenance (search query, preview URL,
   preview status, fetch time) and the manual-inclusion proposal.

## Tests (verified first-hand, local clone, venv /tmp/muse14-int046/.venv)

- New suite `tests/test_ig_intelx_telegram_topic_search.py`: **23 passed,
  0 failed** (pytest 9.2.0, Python 3.12.3). Covers: query construction,
  handle extraction, preview parsing (full fixture, og-only fallback, empty
  page), subscriber-count parsing (space/comma thousands, K/M suffixes,
  absent → None), scoring/ranking (term matches outweigh the subscriber
  tiebreak), dedupe, fail-closed on search error / fetch error / non-200 /
  unverifiable preview / empty topic, the manual proposal, the named-source
  registration, and the route's flag-off (503) + flag-on behaviour.
- IntelX tier-1 list (all nine files incl. the new suite): **95 passed,
  0 failed** (815.41s).
- `py_compile` clean on all touched Python files.

## Five states

- Implemented: YES (service, named-source registration, flag, route, tests).
- Tested: YES (23/23 hermetic; tier-1 list re-run — see above).
- Merged: NO (this work PR).
- Deployed: NO (route flag-gated off by default; IntelX lives on IntelX-Server).
- Production-verified: NO — the live leg (one real topic query returning a
  real candidate list) is gated: it needs live web fetches from a host that
  can reach Telegram/search engines, plus coordinator clearance like the
  VYR-072 live leg had; the owner stop order is still in force for any
  server-side enablement.

## Gated / not attempted (exact reasons)

- **Live discovery verification** (a real topic query returning real
  channels): no live Telegram/search call was attempted in this run; the
  repo-side code is verified by hermetic tests only until the live leg runs.
- **Watch inclusion end-to-end**: needs the Telegram-channel source-kind
  adapter (separate task) plus, for any server-side enablement, the owner
  stop order to lift.
- **MTProto global search (route C):** needs owner-supplied `api_id` /
  `api_hash` and a logged-in session; a credential decision, not a code
  decision. Not attempted.

— Muse 14
