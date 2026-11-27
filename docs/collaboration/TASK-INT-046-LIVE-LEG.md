# TASK-INT-046 — Live leg: one real topic query through the merged code

## Verdict: PARTIAL — the candidate-list pipeline works live and returns a real, correctly-ranked candidate list; the search seam cannot run in this sandbox, so end-to-end discovery via the designed search path is not verified live

The live leg was run and it split the pipeline in two. The merged
`TelegramTopicSearch` service works end to end for handle verification,
preview parsing, scoring, ranking, provenance and the manual-inclusion
proposal — a real topic query (`cryptocurrency`) returned 2 real public
Telegram channels, correctly scored and ranked, each verified against a
fresh live preview. But the search seam that is supposed to supply the
seed handles cannot run in this sandbox: `MOCK_MODE` defaults to `True`
in `IntelX/intelx/core/settings.py`, so `WebSearchConnector` never
attempts a live search, and even with `MOCK_MODE` off no configured or
reachable search provider returns `t.me` links here. The 23 hermetic
tests still pass — they encode the pipeline with injected fake fetchers,
so they could not catch this. No fix is made in this PR; the fix
belongs to a follow-up task.

## What ran

- Base: `origin/main` at `8477b554` (merge of PR #2057), which contains
  the INT-046 merge `e2eb6b72` (work PR #2008, merged 2026-11-27
  06:26:57 IST by surendra2304). Verified: `git merge-base
  --is-ancestor e2eb6b72 HEAD`. The INT-046 files are unchanged between
  this base and current `origin/main` (verified by diff).
- Worktree: `~/workspace/friday-int046-liveleg`, branch
  `muse14/task-int-046-live-leg` (the existing `muse14/task-int-047`
  and `muse14/task-vyr-089` branches were not touched).
- Script: `~/workspace/int046-liveleg/live_leg.py`, run from `IntelX/`
  with a fresh venv replicating the CI tier-1 step (`python3 -m venv`,
  `pip install -r requirements.txt pytest pytest-asyncio aiosqlite`),
  at **2026-11-27 10:21:24–10:22:22 IST** (started
  `2026-11-27T04:51:24.554013+00:00`, finished
  `2026-11-27T04:52:22.477037+00:00`).
- Topic: `cryptocurrency`. Query: `site:t.me cryptocurrency`
  (`build_search_query`).
- Service: the real merged `TelegramTopicSearch`
  (`IntelX/intelx/connectors/telegram_topic_search.py`), run twice:
  Part A with its DEFAULT fetchers (`WebSearchConnector` +
  `HttpFetchConnector`); Part B with the same merged service but real
  transports substituted for the two seams that cannot run in this
  sandbox (see "Transport notes" below).
- Transport notes (honest): (1) the client's DEFAULT preview fetcher
  (`HttpFetchConnector`) could not run in this sandbox — its SSRF guard
  resolves `t.me` to `198.18.75.61` (sandbox DNS returns a CGNAT
  `198.18.0.0/15` address) and raises `SSRFBlocked` before any request.
  The live previews are reachable from the sandbox (plain `curl`:
  HTTP 200, ~1 s). The service was therefore run in Part B with a real
  `httpx` transport doing genuine live HTTPS GETs to `t.me/s/<handle>`
  (same `(status, final_url, body)` shape, redirects followed). Every
  `TelegramTopicSearch` code path — handle extraction, preview fetch,
  preview parsing, scoring, ranking, provenance, proposal — is the
  merged code exercised against live data. No fake fetcher, no cached
  data, no fabricated numbers. (A second sandbox quirk: the shell's
  `no_proxy` contains bracketed IPv6 literals such as `[::1]` which
  `httpx` cannot parse as URL patterns; the run set
  `NO_PROXY=no_proxy=localhost,127.0.0.1,::1`.) In production DNS the
  SSRF guard would resolve `t.me` to a real public IP, so this guard
  interaction is a sandbox artifact, not a production finding. (2) The
  DEFAULT search seam could not run either (see "Live finding 1"); the
  seed handles for Part B were obtained live, in the run, from the
  homepages of three crypto sites that link their official Telegram
  channels (CoinMarketCap, crypto.com, Kraken — see "Live evidence").
  The injected search fetcher returns real `SearchResult` objects built
  from those live pages (url = the real `t.me` channel URL). Only the
  seed source was substituted; the merged service's extraction,
  verification, parsing, scoring, ranking and provenance all ran
  against live data.
- A sandbox note: `/tmp` was wiped between exec calls in this session
  (the first venv and the first copy of the live-leg script vanished),
  so the venv lives at `~/workspace/venvs/muse14-int046-liveleg` and
  the script + result JSON at `~/workspace/int046-liveleg/`. The
  evidence below is from the run that completed and wrote
  `result.json` (10:21:24–10:22:22 IST).

## Live evidence (verbatim, from the run)

Part A — real default service, default fetchers (`search("cryptocurrency")`, 0.07 s):

- Candidates: **0**. The service fail-closed to an empty list.
- Root cause, verified by a follow-up probe of each provider
  (`probe_a.py`, same venv, same base): `MOCK_MODE` is `True`
  (see "Live finding 1"). The router short-circuits to mock fixtures
  and there is no fixture for this query, so it returns `[]` in 0.01 s
  without touching the network.

Part B — merged service, real transports (`search("cryptocurrency")`, 56.14 s):

Seed (live homepage fetches inside the run):

- CoinMarketCap (`https://coinmarketcap.com/`): HTTP 200,
  handles `CoinMarketCapAnnouncements`, `xstocksfi`.
- crypto.com (`https://crypto.com/`): `ReadTimeout` — no handles
  this run (an earlier curl probe had found `Cryptocom_PriceBot`
  there; the homepage fetch is flaky from this sandbox).
- Kraken (`https://www.kraken.com/`): HTTP 200, handle
  `kraken_exchange_official`.

Candidates returned (2, ranked):

- `CoinMarketCapAnnouncements` — title `CoinMarketCap Announcements`,
  description `Official CMC Telegram Channel: Updates, News, and
  Events! Build with CMC (API, AI, Agent):
  https://coinmarketcap.com/api/resources/cmc-toolkit`, score
  `0.2114`, matched terms `["cryptocurrency"]`, subscriber count
  `233000`, preview `https://t.me/s/CoinMarketCapAnnouncements`
  (status 200, fetched `2026-11-27T04:51:53.489936+00:00`). Proposal:
  manual inclusion (`telegram_channel` record).
- `xstocksfi` — title `xStocks`, description `` (empty — the live
  preview carries no description), score `0.2061`, matched terms
  `["cryptocurrency"]`, subscriber count `54700`, preview
  `https://t.me/s/xstocksfi` (status 200, fetched
  `2026-11-27T04:51:54.812325+00:00`). Proposal: manual inclusion.

Skipped (1): `kraken_exchange_official` — its preview fetch raised
`ReadTimeout` under the `httpx` transport (the `t.me/s/` URL
302-redirects and the redirect target hangs under `httpx`; a
separate probe confirmed `ReadTimeout` at 15 s and at 25 s, while
plain `curl -L` reaches the redirect target in ~1.2 s). The service
caught the fetch exception and skipped the handle, per its fail-closed
design — never invented. (`Cryptocom_PriceBot` was not in the seed
this run because the crypto.com homepage fetch timed out.)

Verification — each returned candidate re-fetched live and compared:

- `CoinMarketCapAnnouncements`: preview status 200, title MATCH,
  description MATCH, live subscribers `233000` (match), 5 recent
  posts.
- `xstocksfi`: preview status 200, title MATCH, description MATCH
  (both empty), live subscribers `54700` (match), 5 recent posts.

Scoring hand-check (topic has 1 term, `cryptocurrency`; the term is
matched only in recent posts for both candidates, so base = 1/6 =
0.1667):

- `CoinMarketCapAnnouncements`: tiebreak 233000 subscribers →
  0.05 × min(1, log10(233001)/6) = 0.0447; total 0.2114. Exact match.
- `xstocksfi`: tiebreak 54700 subscribers → 0.05 ×
  (log10(54701)/6) = 0.0395; total 0.2062 → 0.2061 (rounding). Match.
- Ranking: `CoinMarketCapAnnouncements` (0.2114) above `xstocksfi`
  (0.2061) — correct; the subscriber tiebreak decides it, exactly as
  designed (a term match outweighs the tiebreak; both matched the
  term once, in posts).

Hermetic suite re-run on this base (same venv, from `IntelX/`):
**23 passed in 174.33 s**
(`tests/test_ig_intelx_telegram_topic_search.py`).

## Live findings (root causes, verified against live services)

1. **The search seam cannot run in this sandbox, so discovery has no
   seed handles.** Two independent causes, both verified:
   - (a) `MOCK_MODE` defaults to `True` in
     `IntelX/intelx/core/settings.py` (`default=True`; "When true, all
     LLM & search calls use local synthetic mock data"), and no
     `INTELX_MOCK_MODE` / `MOCK_MODE` env var is set in this sandbox,
     nor is there a `.env` file. `WebSearchConnector.fetch()` therefore
     short-circuits to `_load_mock_results()`, which has no fixture for
     `site:t.me cryptocurrency` (its fixture topics are silicon /
     sodium / solid-state / quantum / piezoelectric / historical), so
     it returns `[]` in 0.01 s without touching the network. The
     merged service then correctly fail-closes to an empty candidate
     list. (The settings validator at `settings.py:522` calls
     `MOCK_MODE` in production a "CRITICAL SECURITY VIOLATION", so
     this default is a dev convenience — but it means live discovery
     cannot run anywhere the flag is left at its default.)
   - (b) Even with `MOCK_MODE` off, no provider yields `t.me` links
     here. Verified provider by provider for `site:t.me
     cryptocurrency`: Tavily 0 results (no API key); SearXNG 0 results
     (no instance URL configured); Google News RSS 0 results (0.82 s);
     Wikipedia 0 results (0.44 s); DuckDuckGo `ProviderError`
     ("non-success response", 0.58 s — the HTML endpoint returns HTTP
     202 with an anti-bot page: markers `anomaly` / `bots use
     duckduckgo` present, zero result links). Beyond the built-in
     chain, probed and rejected: Bing (HTTP 200 but ignores the
     `site:` operator — returns generic crypto web results, 0 `t.me`
     links; a plain `telegram crypto channel t.me` query returns
     `telegram.me` links, which `extract_handles` drops because it
     only accepts `t.me`/`www.t.me` hosts); Brave HTTP 429; Ecosia
     HTTP 403; Mojeek HTTP 403 (after one 200 with 0 links); Yahoo
     HTTP 500; public SearXNG instances searx.be (anti-bot
     "Verifying your browser…" page), search.bus-hit.me (unreachable),
     searx.tiekoetter.com (HTTP 429); Telegram directories tgstat.com
     (HTTP 403), tlgrm.eu (HTTP 404 on that path),
     telegramchannels.me (unreachable). No live search engine in this
     sandbox returns `t.me` links for a `site:t.me` query.
   - Consequence: the designed discovery path (search → handles →
     verify) is not exercisable from this sandbox. The candidate-list
     pipeline (stages 2–6) is verified live; the search stage is not.
2. **The preview/score/rank pipeline is correct against live data.**
   The two returned candidates are real public channels, their titles,
   descriptions and subscriber counts match fresh live previews
   exactly, the scores reproduce by hand from the documented formula,
   and the ranking follows the documented order. The `kraken_exchange_official`
   skip is correct fail-closed behaviour (unverifiable preview →
   skipped, never invented). The `xstocksfi` candidate shows the
   parser handles a preview with an empty description (title + posts
   carry it). No bug was found in the merged service's pipeline code.
3. **Observation (not a bug): `extract_handles` drops `telegram.me`
   links.** Bing's `telegram crypto channel t.me` query returns
   `telegram.me/telegram` and `telegram.me/desktop` — Telegram's own
   alias domain — but the service only accepts `t.me`/`www.t.me`
   hosts, so those handles are dropped. By design (the module
   documents `t.me` links); noted here in case the follow-up wants to
   accept the alias.

## Five states

- Implemented: YES (service, named-source registration, flag, route,
  tests; merged in PR #2008, merge `e2eb6b72`).
- Tested: YES (23/23 hermetic on this base; live leg ran — see above).
- Merged: YES (PR #2008).
- Deployed: NO (route flag-gated off by default; IntelX lives on
  IntelX-Server).
- Production-verified: NO — PARTIAL. The candidate-list pipeline works
  live and returns a real, correctly-ranked candidate list, but the
  search seam cannot run in this sandbox, so end-to-end discovery via
  the designed search path is not verified live. The production leg
  (enabling `ENABLE_TELEGRAM_TOPIC_SEARCH` on IntelX-Server + running
  the route live) stays gated on the owner stop order.

## Gated / not attempted (exact reasons)

- **Live discovery via the designed search seam**: not possible in
  this sandbox (finding 1 above). The follow-up fix task should give
  discovery a working search provider and/or handle `MOCK_MODE` so a
  live search can run (e.g. a configured SearXNG instance or Tavily
  key, and a decision on the `MOCK_MODE` default for discovery).
- **Production leg (HTTP route on IntelX-Server)**: needs
  `ENABLE_TELEGRAM_TOPIC_SEARCH` + a service restart on IntelX-Server,
  forbidden by the owner stop order. Not attempted.
- **Watch inclusion end-to-end**: needs the Telegram-channel
  source-kind adapter (separate task). The candidates carry the manual
  proposal, as designed.
- **MTProto global search (route C)**: needs owner-supplied `api_id` /
  `api_hash` and a logged-in session; a credential decision, not a
  code decision. Not attempted.

— Muse 14
