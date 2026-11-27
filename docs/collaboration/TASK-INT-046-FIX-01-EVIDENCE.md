# TASK-INT-046-FIX-01 — Live evidence

**Task:** IntelX: working search provider / MOCK_MODE handling for
discovery (INT-046 follow-up fix). **P1, owner muse_14.**
**Acceptance:** "A configured, reachable search provider returns t.me
links for a real topic query through the designed search path (no
MOCK_MODE fallback in the live path); end-to-end discovery verified
live and filed as evidence."
**Claim:** hub #2045 comment 7216846990 (~16:44 IST 2026-11-27).
**Branch:** `muse14/task-int-046-fix-01` (implementation PR #2147,
code + tests only, no board hunk). This doc is filed in a separate
evidence PR (1 file, no board hunk, no code).

## The fix (what changed)

The INT-046 live leg (evidence PR #2092, verdict PARTIAL) found two
independent causes why the search seam could not run: (a) `MOCK_MODE`
defaults to `True`, so `WebSearchConnector` short-circuited to mock
fixtures and never touched the network; (b) no provider yields t.me
links from any host the work can run on. This task fixes (a) in code
and proves (b) is an environment/credential wall, not a code gap.

1. **`IntelX/intelx/connectors/search.py` — `WebSearchConnector.fetch()`
   gains a `live` mode.** `fetch(target, live=True)` pops the flag from
   `kwargs` (so it is not forwarded to providers) and skips the
   `MOCK_MODE` short-circuit, running the real provider chain
   (Tavily → SearXNG → Google News + Wikipedia → DuckDuckGo).
   `live=False` (the default) preserves the existing mock behaviour
   for research/dev. When live search returns nothing and a provider
   failed, the existing fail-closed `ProviderError` is raised; an
   empty result with no provider failure is an honest no-result
   search.
2. **`IntelX/intelx/connectors/telegram_topic_search.py` — the
   discovery service uses live mode.** `_default_search()` now calls
   `WebSearchConnector().fetch(query, max_results=max_results,
   live=True)`. Discovery is a live route: its candidate list must
   never be seeded with mock fixtures. When no provider is configured
   or reachable the call fail-closes (ProviderError / empty list)
   instead of inventing candidates; the service logs the failure and
   returns `[]`.

No settings defaults were changed: `MOCK_MODE` stays `True` by
default (a global setting for the whole of IntelX; changing it would
alter every research path), and `TAVILY_API_KEY` / `SEARXNG_URL`
stay unset by default — the operator configures a provider via env.
No key was added to the repo and no secret is recorded here.

## Tests

Hermetic tests added to `IntelX/tests/test_ig_intelx_telegram_topic_search.py`
(already on the IntelX tier-1 CI list, so no workflow change was
needed):

- `test_web_search_live_mode_bypasses_mock` — with `MOCK_MODE=True`,
  a SearXNG URL set and a fake SearXNG transport returning a t.me
  link, `fetch(live=True)` returns the live result while the same
  call without `live=True` returns the mock fixtures (none for this
  query).
- `test_web_search_live_mode_fail_closed_without_provider` — with
  `MOCK_MODE=True`, no Tavily key, no SearXNG URL, Google News +
  Wikipedia returning nothing and DuckDuckGo failing, `fetch(live=True)`
  raises `ProviderError` (fail-closed, never mock); the same call
  without `live=True` returns the mock fixtures instead of raising.
- `test_default_search_uses_live_mode` — `TelegramTopicSearch`'s
  default search passes `live=True` to the search seam.

**Results (fresh venv, replicating the CI tier-1 step):**
`tests/test_ig_intelx_telegram_topic_search.py` — **26 passed**
(23 original + 3 new) in 229.20 s. Full IntelX tier-1 suite (the 12
files in the CI step) — **139 passed** in 1209.79 s, 0 failed.

## Live verification (real topic query "cryptocurrency")

Run 2026-11-27 ~19:30 IST from `IntelX/` in a fresh venv
(`~/workspace/venvs/muse14-int046-fix01`), script
`~/workspace/int046-fix01/live_verify.py`, result
`~/workspace/int046-fix01/live_verify_result.json`. Query
`site:t.me cryptocurrency` in all three parts.

- **Part A — the designed path, default settings** (`MOCK_MODE=True`,
  no provider configured): `TelegramTopicSearch().search("cryptocurrency")`
  returned **0 candidates in 2.70 s**. Log evidence that the live
  chain was attempted (not mock): `Live search provider duckduckgo
  failed (ProviderError)` and `telegram topic search failed for
  'cryptocurrency' (ProviderError)`. Mock fixtures never raise
  `ProviderError` and never log a provider failure — the mock
  short-circuit was bypassed and the call fail-closed honestly.
- **Part B — SearXNG configured** (`SEARXNG_URL=https://baresearch.org`,
  `live=True`, direct `WebSearchConnector`): raised `ProviderError:
  Live search returned no sources while one or more providers failed`
  in 2.64 s. Log: `SearXNG search request failed (JSONDecodeError)`
  — the instance returned its bot-check HTML page, not JSON — then
  DuckDuckGo failed. This proves the SearXNG configuration wiring
  works end-to-end (the chain consulted the configured instance);
  the failure is the instance blocking datacenter egress, not a code
  failure.
- **Part C — MOCK_MODE=True, no provider, direct connector,
  `live=True`**: raised the same `ProviderError` in 1.64 s — the live
  chain was attempted and fail-closed, not mock.

**The candidate pipeline itself still works live** (proven by the
INT-046 live leg, PR #2092: `CoinMarketCapAnnouncements` 0.2114 +
`xstocksfi` 0.2061, verified against fresh live previews). What
changed here is only the search seam: it now provably runs live and
fail-closes instead of silently returning mock fixtures.

## Why no provider returns t.me links (the wall)

Every keyless search provider was probed from the sandbox, and the
key ones from Oracle Server 2 and FRIDAY-Server too. No keyed
provider is configured anywhere: `CREDENTIALS.md` on Server 2
(presence/length only, never the value) has **0 mentions of
"tavily"**, **0 of "searx"**, and `TAVILY_API_KEY` /
`BRAVE_API_KEY` / `SEARXNG_URL` all present 0.

| Provider | Result (sandbox unless noted) |
|---|---|
| DuckDuckGo HTML | HTTP 202 anti-bot, 0 t.me (also 202 on Server 2 and FRIDAY-Server) |
| DuckDuckGo Lite | HTTP 202 anti-bot, 0 t.me |
| Qwant API | HTTP 403, 0 t.me |
| Yandex | ReadTimeout; retry HTTP 302, 0 bytes, 0 t.me |
| Startpage | HTTP 200, 0 t.me |
| Marginalia | HTTP 200 (37,705 bytes), 0 t.me |
| Bing | HTTP 200 (120–135 KB), 0 extractable t.me links — the 23 "t.me" occurrences are the query string echoed in page chrome/pagination, not result URLs; result links are opaque `/ck/a?...` tokens |
| SearXNG public instances (18, from searx.space) | 13× HTTP 429, 2× non-JSON (bot-check HTML), 1× HTTP 403, 3× .onion RemoteProtocolError; **0 winners**. Sequential re-probes of search.privacyguides.org, searx.work, search.ononoki.org, searxng.site — all RemoteProtocolError (connection dropped). baresearch.org returns a bot-check page for every query (also on Server 2 and FRIDAY-Server). search.ononoki.org + searxng.site HTTP 000 from Server 2. |
| Google News RSS / Wikipedia | 0 results for `site:t.me cryptocurrency` — structurally incapable of returning t.me links (news articles / encyclopedia articles, not channel links) |
| Telegram directories | tgstat 403, tlgrm.eu 404, telegramchannels.me unreachable (INT-046 live leg) |
| Brave / Ecosia / Mojeek / Yahoo | 429 / 403 / 403 / 500 (INT-046 live leg) |

The pattern is uniform: datacenter egress (sandbox, Oracle Server 2,
FRIDAY-Server) is anti-botted by every keyless engine. The bridge
cannot run a shell on IntelX-Server (no run_shell target there), so
its egress could not be tested — that is the one untested host.

## Verdict: PARTIAL

- **No MOCK_MODE fallback in the live path — MET and verified live.**
  The fix is implemented, hermetically tested (3 new tests), and the
  live run proves the discovery route now attempts the real provider
  chain and fail-closes instead of returning mock fixtures.
- **A configured, reachable search provider returns t.me links for a
  real topic query through the designed search path — NOT MET.**
  No keyless provider returns t.me links from any host the work can
  run on, and no keyed provider (Tavily/Brave) is configured. This is
  an environment/credential wall, not a code gap: the chain is wired
  correctly (Part B proves it consults a configured SearXNG
  instance), but every reachable instance blocks datacenter egress.

## What remains (for the owner/coordinator)

1. **Provision a search credential or a working instance** — a
   Tavily API key (free tier) in `CREDENTIALS.md` / the IntelX env,
   or a SearXNG instance URL that is reachable from the deployment
   host (IntelX-Server's egress is untested and may differ). With
   either configured, the fixed live path should return t.me links
   end-to-end; re-run the leg then.
2. **Production leg** (enabling `ENABLE_TELEGRAM_TOPIC_SEARCH` on
   IntelX-Server + running the route live) stays gated by the owner
   stop order.

## Five states

- implemented: YES (live mode + discovery wiring + 3 tests)
- tested: YES (26/26 file, 139/139 tier-1; live leg run, Parts A–C)
- merged: NO (implementation PR open; evidence PR open)
- deployed: NO
- production-verified: NO (PARTIAL — the live provider leg is blocked
  by the egress/credential wall above)
