# TASK-INT-051 — IntelX repos wave 3: evidence

**Task:** REPO-IMPLEMENT IntelX repos wave 3 (P2). **Owner:** Muse 2.
**Branch:** `muse2/task-int-051-intelx-repos-wave3`. **Claim:** hub #1483 (pull model, queue head after FRG-028 merged).
**Board:** INT-051 AVAILABLE → IN_REVIEW in this PR (FRG-028 already reads MERGED on main — kept byte-identical).

**Five states:** implemented YES / tested YES (repo CI; see below) / merged NO / deployed NO / production-verified NO.
**Live legs gated by the owner stop order** (in force since 2026-11-24 ~16:42 IST): no deploy, no restart, no live-fleet writes. Staging/offline proof only.

## Verdicts

| Repo | Verdict | Why (evidence) |
|---|---|---|
| Agent Reach (Panniantong/Agent-Reach, MIT, Python 3.10+) | Adapt | Read-only multi-channel fetcher; the four no-login channels IntelX lacked (GitHub, RSS, V2EX, Bilibili) are now read through `connectors/agent_reach.py`. Logged-in channels are refused before any fetch. |
| Camofox Browser (jo-inc/camofox-browser, MIT, Node.js) | Adapt | The sidecar itself shipped under TASK-IG2-INT-01; this PR adds the two upstream features it never exposed: search macros (`connectors/camofox_macros.py`, `CamofoxClient.fetch_macro`) and YouTube transcripts via the public no-login timedtext endpoint (`CamofoxClient.fetch_transcript`). |
| Local Deep Research (LearningCircuit/local-deep-research, MIT, Python) | Adapt | The iterative loop shipped under TASK-IG2-INT-02; this PR adds the multi-engine fan-out the card calls for: arXiv, PubMed, Semantic Scholar + IntelX web search in `agents/research_engines.py`, drop-in for the loop. No Ollama, no self-hosted SearXNG, no SQLCipher library — the fleet cannot host them. |
| Helix (thalha-a9/helix, MIT, Python 3.9+) | Adapt | The lookup shipped under TASK-IG2-INT-03; this PR wires it into the production API (`POST /osint/username-lookup`, approved-subject gate from `INTELX_HELIX_APPROVED_SUBJECTS`, refuses MOCK_MODE) and adds the `--watch` change history (`osint/helix_watch.py`). Avatar perceptual-hash matching is NOT adapted: it needs an image-decoding dependency the fleet image does not carry. |
| Robin (apurvsinghgautam/robin, MIT, Python) | Adapt | The pipeline + hygiene shipped under TASK-IG2-INT-04 and the route under X-07; this PR adds the saved-investigation features the card lists: save + re-read (`GET /research/investigations/{id}`), grounded follow-ups (`POST .../follow-up`, `grounded_in` reports which saved evidence the new run builds on), and one-click pivots (`InvestigationStore.pivots`). No Tor, no Streamlit, no dark-web scraping from fleet IPs, ever. |
| OpenDirectory Finder (ewasion/opendirectory-finder, no licence) | Reject | Nothing to take: a two-file static page (a search-query builder for openly indexed files) that IntelX already exceeds with ordinary web search; no licence, untouched since 2017 (3 commits), piracy-adjacent discovery. Guardrail proof of absence below. |

## Guardrail proof of absence (before this change)

Repo-side grep over `IntelX/`, 2026-11-25, plus the registry:

- `opendirectory` / `filechef`: 1 hit — `IntelX/tests/test_ig_scouted_repos.py` only, which pins the registry entry as `reject` ("registered, never implemented"). No module, no route, no import, no fetch anywhere under `IntelX/intelx/`.
- `agent_reach` / `AgentReach`: 0 hits before this change (the only prior art was the SocialLinkReader docstring naming the pattern). No GitHub/RSS/V2EX/Bilibili channel existed.
- `camofox_macros` / `fetch_macro` / `timedtext`: 0 hits. The sidecar had no macro or transcript entry point.
- `arxiv` / `pubmed` / `semantic_scholar` as search engines: 0 hits in `IntelX/intelx/connectors/search.py` (SearXNG exists; the three scholarly APIs did not).
- `helix_lookup` production consumer: 0 hits — library + tests only, no API route.
- `InvestigationStore` / saved investigations: 0 hits. `run_investigation` results were returned once and dropped.
- The new test file pins the OpenDirectory absence (`test_opendirectory_finder_is_rejected_and_absent` scans `IntelX/intelx/` for both strings and asserts zero hits), so a future addition fails loudly.

## The adaptations

**Files**

- `IntelX/intelx/connectors/agent_reach.py` (new) — `AgentReachReader`, `classify_reach_url`, `AgentReachUnavailable`; GitHub repo/file, RSS/Atom, V2EX topic, Bilibili video channels.
- `IntelX/intelx/connectors/camofox_macros.py` (new) — `SEARCH_MACROS`, `build_search_url`, `youtube_transcript_url`, `parse_transcript_json3/xml`, `CamofoxMacroRunner`.
- `IntelX/intelx/agents/research_engines.py` (new) — `arxiv_engine`, `pubmed_engine`, `semantic_scholar_engine`, `web_engine`, `MultiEngineSearch`, `build_default_search`.
- `IntelX/intelx/osint/helix_watch.py` (new) — `HelixWatchStore`, `diff_helix_reports`, `get_watch_store`.
- `IntelX/intelx/ingestion/investigation_store.py` (new) — `InvestigationStore`, `FollowUpResult`, `get_store`.
- `IntelX/intelx/connectors/browser_sidecar.py` — `CamofoxClient.fetch_macro` + `fetch_transcript` (additive; existing paths untouched).
- `IntelX/intelx/agents/retriever.py` — `_social_ingest_plan` tries the Agent Reach reader for URLs SocialLinkReader classifies as plain web; `_reach_fetch` adapter binds it to the retriever's HTTP connector (injected connectors stay hermetic in tests).
- `IntelX/intelx/api/v1/osint_tools.py` — social-link Agent Reach fallback; `POST /osint/username-lookup` + `GET .../history`; investigation save + `GET /research/investigations/{id}` + `POST .../follow-up`.
- `IntelX/intelx/{connectors,agents,osint}/__init__.py` — exports for the new modules.
- `IntelX/tests/test_int051_intelx_repos_wave3.py` (new, 32 tests) — registered in the IntelX tier-1 list in `.github/workflows/friday-universe-ci.yml` (the REL-068 collection guard requires it; the IG2 test files this builds on are collected by no CI job, which is why this file is registered explicitly).
- `docs/collaboration/TASK-INT-051-INTELX-REPOS-WAVE3.md` (this file).

**Design (follows the IG2 pilot precedents, closes their gaps)**

- Every new fetch is GET-only and injectable: production callables are the hardened `HttpFetchConnector` / `WebSearchConnector` / sidecar client; tests inject fakes and touch no network.
- Agent Reach: classification happens before any fetch, so login-gated and unsupported URLs cost zero traffic (tested). GitHub uses the public unauthenticated API (60/hour); a 403 is reported as rate-limited, never worked around with a token — there is no token anywhere in this PR.
- Camofox macros are URL templates only; the snapshot still goes through the sidecar tab lifecycle (open → snapshot → close) and the transcript still goes through the hardened HTTP fetch. No browser state is smuggled in.
- Multi-engine routing: per-engine timeout (default 20 s) + failure isolation (one dead engine is recorded in `errors`, the run continues); dedupe by normalised URL (lowercase host, no trailing slash, tracking params stripped); per-engine and total caps. `fetch` is drop-in for `IterativeDeepResearcher`'s search callable (proven by the loop integration test).
- Helix route: the approved-subject gate fires before any network traffic (403 for an unapproved subject, tested even under MOCK_MODE); MOCK_MODE itself is refused (503) so a lookup can never be served from fixtures. The watch store records each run and the response reports `changes_since_last` (added/removed platforms, confidence changes, newly discarded).
- Robin store: in-memory only (a watch aid, not the canonical store). Evidence stays delimiter-wrapped exactly as `run_investigation` produced it — the store never unwraps or re-emits scraped text bare. Follow-ups re-run the same pipeline; `grounded_in` is computed from the saved evidence by key-term overlap.
- No secret or realistic-looking key/token literal anywhere in this PR — test fixtures use obviously fake values, and no new credential, env var, or paid service is introduced. The only new env var is `INTELX_HELIX_APPROVED_SUBJECTS` (a comma-separated list of owner-named usernames, empty by default → every lookup 403s).

**Fail-safe**

- All five adaptations are additive and off-or-inert by default: the reach reader only triggers for GitHub/RSS/V2EX/Bilibili URLs (everything else falls through to the generic fetch exactly as before); the sidecar stays opt-in (`INTELX_CAMOFOX_ENABLED`, default off); the multi-engine router is a library the loop opts into; the Helix route 403s with no approved subjects configured; the investigation store is empty until a run is saved.
- The retriever change cannot break the existing social path: YouTube/Reddit/Instagram still go through SocialLinkReader first, and the pre-existing wiring-consumers test (`test_retriever_ignores_reader_for_web_urls`) still passes — a plain web URL returns no plan and performs no reach fetch.

## What is proven here vs what is owed

- **Repo-proven (this PR):** all five adaptations + the reject guardrail + 32 in-process tests (no network, no live keys), incl. route tests for the social-link fallback, the Helix gate/watch flow, and the investigation save/follow-up flow; retriever-seam tests for the Agent Reach fallback; canned-payload parser tests for the three scholarly engines and the transcript formats; and the loop integration test (multi-engine router driving the deep-research loop to coverage).
- **NOT live-proven:** no live fetch against any upstream in this PR (owner stop order). The parsers were verified against canned payloads shaped like the real APIs, not against the live APIs.
- **Owed after clearance:** (1) one real end-to-end use per adapt item through the live IntelX path, incl. a failure case (GitHub rate-limit / bot-walled page via the sidecar / an engine down / a Helix control-probe discard / a Robin follow-up on a saved run); (2) a real watch cycle on IntelX-Server against live feeds + duplicate/flood burst + one real alert end-to-end (the board's per-item live leg); (3) persisting investigations and Helix watch snapshots to the canonical store (currently in-memory); (4) Helix avatar-hash matching if the fleet image ever gains an image-decoding dependency; (5) deploy with the new routes live, Helix approved-subjects list populated only with owner-named subjects.

## Board

- INT-051: AVAILABLE → IN_REVIEW (branch + PR set by this PR). FRG-028: already MERGED on main (PR #1864) — record kept byte-identical.

— Muse 2
