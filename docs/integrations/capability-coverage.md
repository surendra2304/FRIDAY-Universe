# Source-to-capability coverage

This is a feature adaptation into FRIDAY Universe, not a claim that arbitrary
third-party apps, every business in an ideas book, or external services can run
without configuration. Existing APIs are preserved; the new browser workplace
and additive contract are under `/v2`.

## Source inspection

| Source | Inspected material | Agent implementation |
|---|---|---|
| `saipradeep77964/jarvis-ai-assistant` | Brain, actions, market and voice Python in its setup ZIP | FRIDAY local/cloud assistant, action planning/execution, Stratex quotes/watchlists, VyralX voice bridge |
| `apurvsinghgautam/robin` | Search, scrape, pipeline, model/config, prompts, store and health code | IntelX search/fetch/investigate/history/follow-up/export; model registry; existing MCP integration plus JSON-RPC front door |
| Cloud9 Trading Mastery | Publicly visible topic headings at `https://www.cloud9markets.com/academy-trading-mastery.html` | Stratex risk sizing, fees, stops, expectancy, structure, regime, volume, correlation, journaling and loss gates; existing indicators/backtests remain usable |
| Drive JARVIS guides | All three PDFs in `JARVIS build - set up guide` | Browser voice workplace, server-held optional ElevenLabs keys, explicit room-device services and local app approvals |
| Drive Grok Bot playbook | Complete `grokbot_business_playbook.pdf` | Cortex lead/ad/ops computations; FRIDAY sources, manually validated skills, persistent schedules and run history |
| Drive business ideas | Introduction, category map and extracted excerpt from `Ayman_William_200_AI_Business_Ideas_Editable.docx`; extraction truncated, so not claimed as a complete 200-card import | Existing full-text card import/search APIs are preserved. New pilot economics and supplied-card ranking apply budget, buyer-access and review constraints. No 200 invented card contents or revenue guarantees |
| `adewaskar/jarvis` (linked from the Drive guides) | VAD, voice endpointing, clap, One-Euro filtering, capability and hand-interaction code | VyralX adaptive voice gate, utterance assembly, echo/wake filtering, clap detector, motion filter, speech capability probing and browser fallback |

Cloud9 lesson bodies behind its access/sign-in gate were **not** accessed or
bypassed. General formulas implement the named public topics; marketing claims
about win rates were not treated as evidence. Drive documents and upstream media
were not bundled or redistributed. Robin and adewaskar/JARVIS MIT notices are in
`source-notices.md`.

## Working paths and tests

### Jarvis: FRIDAY / Stratex / VyralX

- `/v2/assistant` is a same-origin HTML/JS workplace, not a static mockup. It sends
  typed requests, opens returned safe links/drafts, refreshes quotes, and runs
  investigations. No frontend request points to sandbox `localhost`.
- `/v2/api/assistant/sessions` creates isolated bounded conversation sessions;
  deletion forgets history. Session IDs are random capabilities, expire and
  have a capacity bound. Source/action data is not silently added to cloud chat.
- `real_approved_actions.py` performs exact deterministic dispatch, preserves
  message case, uses actual cache contents, discovers known app launchers and
  returns real system vitals. Missing inboxes/devices are labelled, never invented.
- Browser links and WhatsApp compositions are user-clicked drafts, not automatic
  sends. App/volume/room changes require a separate authenticated, enabled,
  expiring one-use approval. Commands are administrator-controlled argv arrays,
  never user-provided shell strings. Audits record completion/failure.
- The Home Assistant service adapter handles configured lights/plugs and remote
  services (including a configured BroadLink IR integration). It does not guess
  IR/RF packets, electrical ratings, device IDs or hardware support.
- `real_market_service.py` implements fixed-host Yahoo chart requests, bounded
  bodies/timeouts, partial watchlist failures, cache isolation, explicit stale
  fallback and spoken briefing. Signals use actual supplied/provider prices.
- VyralX implements adaptive PCM energy thresholds, start/release hysteresis,
  max segment duration, playback guard, wake/debounce, sentence continuation,
  echo filtering, clap shape and One-Euro smoothing. A transcriber supplies
  words; energy detection is not falsely advertised as ASR.
- Browser microphone/recognition and speech synthesis run on the user's device.
  When configured, ElevenLabs STT/TTS run through server adapters with private
  keys and request limits. Typed/browser fallback remains usable without keys.
- New acceptance coverage: `tests/test_real_deep_layer19.py`; existing broader
  integrations remain in `tests/test_real_deep_layer15.py`.

### Robin: IntelX -> Memora

Existing `real_investigation_pipeline.py` and its API/MCP interfaces are kept.
The additional strict `real_grounded_investigation.py` powers `/v2`:

1. Refine query (optional configured model; honest fallback).
2. Parallel configured-engine search through SOCKS5 **remote DNS**, no direct
   onion requests and no clearnet fallback.
3. Parse search anchors/wrappers, onion-only policy, stable deduplication/host
   caps, lexical/model-index filtering. An empty model selection remains empty.
4. Fetch bounded bodies with type/encoding checks and policy enforcement at every
   redirect. Redirect bodies are never downloaded. Script/style/navigation
   furniture is excluded; source failures stay visible.
5. Generate source-linked extractive findings. Optional model summaries must
   contain verbatim quotes from their stated source; fabricated sources/quotes
   are rejected. Unicode controls and forged delimiters are scrubbed/defanged.
6. Generate observed-artifact pivots; distinguish no results, unreachable engines,
   nothing relevant and nothing readable. Explicit abuse-material labels are
   excluded, but the heuristic is **not** a comprehensive content classifier.
7. Save private report history without raw page bodies. Validate IDs and reject
   traversal/symlinks; skip corrupt saves. Export JSON/Markdown and answer
   follow-ups from stored evidence rather than unstated background knowledge.
8. Ingest readable observations through the existing IntelX engine and store
   the research summary in Memora. Repeated indicators reuse identities.

OpenAI-compatible hosted/local providers plus native Anthropic and Gemini wire
formats are supported by `real_research_models.py`. Keys come from server
configuration and are omitted from public model discovery. Context limits,
response limits, sanitized failures and rate-limit cooldowns are enforced.

`/v2/api/research/rpc` provides JSON-RPC initialize/tool discovery/calls for a
restricted tool set; it is not a claim of implementing every MCP transport.
The existing `real_research_mcp.py` remains available for its original protocol.
Tests: `tests/test_real_deep_layer16.py`, including a real local SOCKS5 handshake
and HTTP redirect refusal, not just a mocked method return.

### Cloud9: Stratex discipline

`real_trading_discipline.py` supplements the existing `real_trading_coach.py`:
fee-aware loss sizing and lot rounding, exposure/portfolio-risk caps, directional
stops/targets, R expectancy and profit factor, confirmed swing points, ATR,
trend/range efficiency, candlestick shapes, prior-window support/resistance,
breakout/fakeout/volume checks, directional correlation concentration, tightening
trails and no-add-to-losers scaling rules. Persistent trade journals compute plan
adherence and enforce cooldown/rolling-loss gates in risk-plan responses.

These are measurements and decision gates, **not** live trade execution,
validated predictive edges or investment recommendations. Tests:
`tests/test_real_deep_layer17.py`.

### Drive: Cortex business review -> FRIDAY skills/routines

- Lead classification, known-fact follow-up drafts, opt-out exclusion, duplicate
  detection, missing/future-data warnings and reporting-timezone contact checks.
- Source-linked campaign/account arithmetic (ratios from summed numerators and
  denominators, not mean ratios), unavailable metrics kept null, previous-day
  and trailing comparisons, budget/threshold flags, attribution/timezone checks,
  duplicate-row exclusion and mixed-currency refusal.
- Overdue task/lead/campaign weekly reviews, pilot contribution/break-even/
  capacity/payback and measured manual-minus-review time savings.
- Supplied opportunity-card ranking by reachable buyers, budget, interest and
  timeline. Scale labels are not converted into revenue forecasts.
- Persistent skills, source snapshots, manual preview/validation, timezone-aware
  weekday scheduling, DST-gap handling, pause/resume, durable slot claims,
  freshness refusal and completed/failed run history. The API lifespan ticks
  the read-only scheduler every 30 seconds; tick is also operator-callable.
- Consequential external actions are not part of business execution. No mail
  sends, CRM edits, ad budget changes, purchases or record deletions occur.

Tests: `tests/test_real_deep_layer18.py`. The existing richer card importer and
business workflows remain accessible through their established API contract.

## Configuration

Run from the repository root with its API dependencies installed:

```sh
PYTHONPATH=.:FRIDAY/apps/core/src python3 -m uvicorn friday_core.real_api_server:app --host 0.0.0.0 --port 8000
```

Open `/v2/assistant`. The main API root redirects there; the deep API keeps its
existing root dashboard and exposes the workplace at the same versioned path.

| Server setting | Purpose |
|---|---|
| `GROQ_API_KEY` | Optional assistant cloud chat. No key: real local actions still work |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | Optional speech recognition / voice; browser fallback otherwise |
| `FRIDAY_RESEARCH_NETWORK=1` | Opt into v2 Tor research; requires a working local SOCKS5 proxy on port 9050 |
| `FRIDAY_RESEARCH_MODEL` | Opt into a configured research model name, e.g. `groq`, `openai`, `ollama`; omitted: extractive mode |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY` | Optional provider credentials, held only on the server |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Explicit local OpenAI-compatible research provider |
| `CUSTOM_API_BASE_URL`, `CUSTOM_API_MODEL`, `CUSTOM_API_KEY` | Administrator-owned compatible provider |
| `FRIDAY_SEARCH_ENGINES` | Optional JSON list of `{name,template}` onion-engine configurations; query placeholder is `{query}` |
| `FRIDAY_CONTROL_TOKEN` | v2 operator token. Sent via `X-Friday-Control-Token`; v2 also accepts existing `FRIDAY_LOCAL_ACTION_TOKEN` / `X-Friday-Operator` |
| `FRIDAY_LOCAL_EXECUTION=1` | Separately enable approved local app/volume/room execution; planning alone does not execute |
| `FRIDAY_ALLOWED_APPS` | Optional JSON app-name -> argv allowlist; if omitted, only known installed launchers are discovered |
| `FRIDAY_CONTACTS` | Optional JSON contact-name -> known phone number mapping for WhatsApp drafts |
| `HOME_ASSISTANT_URL`, `HOME_ASSISTANT_TOKEN`, `FRIDAY_ROOM_DEVICES` | Explicit trusted room-service configuration |

Keep tokens out of frontend bundles, URLs and ordinary chat. Sensitive research
history/ingestion, journal writes and routine administration require operator
authorization. Use a trusted authenticated gateway for browser operator access;
the workplace does not ask you to paste/store an execution token in a web page.
The original v1 API retains its original token/header conventions.

The scheduler is single-process with durable at-most-once slot claims, not a
multi-worker distributed scheduler. Use one scheduler owner per state directory.
Existing FRIDAY app state and v2 capability state stay separate to preserve API
compatibility. Back up mounted state and restrict filesystem/access permissions.

## Verification boundary

Functional tests use real calculations, real engines/persistence, FastAPI HTTP
requests, a local SOCKS5 wire-protocol server and controlled provider fixtures.
The restricted sandbox cannot verify live Yahoo/Groq/ElevenLabs/onion availability,
a physical microphone/speaker, macOS app launch or actual home hardware.
Adapters and their failure paths are implemented and tested; service reachability,
credentials, browser permissions and hardware remain deployment checks. Browser
JavaScript passes `node --check`; no camera landmark detector or 3D holographic
renderer is claimed. Their cosmetic frontend is not required by the agent APIs.
