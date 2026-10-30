# FRIDAY agent integrations: Jarvis, Robin, Cloud9, and Drive

Status: implementation and test coverage are in this branch; exact source limits below are intentional. This document replaces the old “standalone modules only” note.

## Source inspection and scope

- **Jarvis AI Assistant** — [saipradeep77964/jarvis-ai-assistant](https://github.com/saipradeep77964/jarvis-ai-assistant), `main` at `6d5fc666842165aaa117804e900f399e0bec0a12`. Inspected all Python files in `Jarvis_Setup_Package.zip` (brain, actions, market, voice), its index and its setup/UI files. Its relevant behavior is now implemented in FRIDAY's own engines, with stricter permission boundaries; upstream installers and 3D HTML are not copied.
- **Robin** — [apurvsinghgautam/robin](https://github.com/apurvsinghgautam/robin), `main` at `b5d4f5f509fac39d65d3a28fd1d78b56efbeeaf4`. Inspected the investigation pipeline, 16-engine search list, scraper, prompts, store and MCP server. Reimplemented as IntelX modules and mounted in both FRIDAY HTTP applications.
- **Cloud9 Trading Mastery** — [Trading Mastery](https://www.cloud9markets.com/academy-trading-mastery.html), page retrieved 2026-10-26. The public page exposes 21 lesson headings (risk, sizing, stops, R/expectancy, structure, candles, volume, trends, psychology, journaling, MAs, RSI, breakouts, correlation and backtesting) but gates lesson bodies behind an access code. Stratex implements transparent calculations and review tooling from the visible curriculum; it does **not** claim to reproduce or know the gated lessons or their unsupported marketing claims.
- **Google Drive folder** — `16-w2LiHKi1WZxRmvInuVSY3gMU5fHU8j`; read the files through the connected Drive app. It contains the editable 200 AI Business Ideas DOCX (`1XcmTc8jVdlPPwXVK5XX0povCpTtrQ0qz`), the Grok Bot Business Playbook PDF (`1pcyI_2R58NaETE6UVe5E9X6RY60X4Nj3`), and three JARVIS setup guides (`1Z1dgQBuyk0WqDlhFAQLeQQdU1Oy2iKEk`, `16nLlHVIuQ_q4KAJibu3158kOaAMsMuGm`, `1C1XfM4Nj_YXslpeqCbaZkSj9w57_ASV5`). The business playbook describes 20 categories × 10 ideas, buyer interviews and human-reviewed pilots; Grok describes lead review, daily ad reporting, weekly ops, reusable skills/routines and approval boundaries; the JARVIS guides describe a local computer/voice setup and a later smart-room layer.

The 200-card source is **not copied wholesale into Git**. FRIDAY includes a bounded importer for the extracted DOCX text; an operator must import it once to make individual cards searchable. The source's categories and principles are available without importing. The Drive JARVIS guides refer to `adewaskar/jarvis`, which is distinct from the Jarvis AI Assistant ZIP above.

## Jarvis capabilities now wired into FRIDAY

`friday_core.real_api_server.app` and `friday_core.real_deep_api_server.app` both mount `real_research_api` and call the existing Stratex/IntelX/CrossAgent engines.

### Assistant and safe desktop actions

- `POST /api/assistant/respond` runs local deterministic dispatch first: market/research/status intents, time/date, a configured mail-cache brief, web search/YouTube/site opening, allowlisted app launch, and volume controls. Unknown text can use the injected Groq provider with model failover and retry-after cooldown.
- `POST /api/assistant/actions/approve` executes a *prepared* local action once, and only with `X-FRIDAY-Operator: $FRIDAY_LOCAL_ACTION_TOKEN`. A declined action is consumed. App launches require a `FRIDAY_ALLOWED_APPS` JSON argv allowlist. `FRIDAY_MAIL_CACHE` is an explicitly configured local text cache; without it the agent says the unread count is unknown.
- WhatsApp creates a URL-encoded draft for an explicit phone number and message; it does not resolve contacts or send messages. No shell commands from model output, arbitrary URLs, payments, system setting changes or trading orders are executed.
- `GET /api/assistant/vitals` returns measured host data where available (Linux `/proc`, optional `psutil`, disk, load, battery); unavailable measurements stay `null`. It also requires the operator token.
- The API has no shared conversation history. The local CLI gets a process-private, bounded six-message session.

### Live markets and voice

- `POST /api/trading/watchlist` retrieves the Jarvis default watchlist (Nifty, Sensex, selected Indian/US names and BTC-USD) from the Yahoo Finance chart endpoint, applies a short/medium average momentum analysis, returns per-symbol errors rather than false quotes, and attaches Cloud9-style OHLCV context when available. Cache TTL, URL, response size and timeout are bounded.
- Unknown assistant market queries use live retrieval only when `FRIDAY_LIVE_MARKETS=1`; otherwise they ask for supplied data or state that live lookup is disabled.
- `POST /api/assistant/voice` accepts bounded mono PCM WAV, requires `allow_cloud_transcription: true`, sends audio to Groq Whisper, passes recognized text through the same FRIDAY assistant and optionally returns native WAV synthesis. The host CLI supports continuous microphone capture and native speech output. If both `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` are configured, the CLI can use the Drive guide's optional ElevenLabs PCM voice adapter; cloud synthesis is separately consent-gated on the HTTP route:

  ```sh
  PYTHONPATH=.:FRIDAY/apps/core/src python3 -m VyralX.app.agents.real_assistant_voice --allow-cloud
  ```

  Install the host's microphone backend (`SpeechRecognition`/PyAudio) and `espeak-ng`/`espeak` or macOS `say` as appropriate. `--allow-cloud` is explicit CLI consent: captured voice goes to Groq Whisper, unknown queries may go to Groq chat, and when configured the spoken response may go to ElevenLabs. The HTTP route requires `allow_cloud_transcription: true`; `allow_cloud_synthesis` is a separate false-by-default opt-in. Without ElevenLabs, the host uses native WAV TTS. A native microphone service is not installed into the FRIDAY server.

- Set `GROQ_API_KEY` to opt into Groq. The assistant uses `llama-3.3-70b-versatile` then `llama-3.1-8b-instant` by default. The HTTP transport is implemented and mocked in tests; a live provider call requires the operator's credential and allowed outbound network.

## Cloud9 curriculum → Stratex risk coach

`TradingEngine.coach_engine()` attaches the coach and local SQLite trade journal to the existing Stratex state directory. Routes:

- `GET /api/trading/coach/curriculum`
- `POST /api/trading/coach/review` — OHLCV structure, SMA context, Wilder RSI, ATR, local swing levels, candle shape, relative volume and an explicitly qualified breakout state.
- `POST /api/trading/coach/position-plan` — user-supplied side, entry, stop, target, equity, risk budget, lot size, fees and slippage; quantity is capped by the notional multiple.
- `POST /api/trading/coach/expectancy` and `/correlation`
- `POST /api/trading/coach/journal` and `GET /api/trading/coach/journal/review` — persistent outcomes, R multiples, adherence and possible loss-triggered size escalation. Journal access is operator-token protected.

Existing Stratex strategies (`sma_cross`, `rsi_reversal`, `macd_cross`, `bollinger_breakout`, `jarvis_momentum`) now produce bar-timestamped signals and run through one causal long-only backtester: signal at close, fill next open, entry/exit fees and slippage, optional percentage stop/target, stop-first assumption if both touched in one bar, gap-aware stop fills and isolated per-run trades. This is simulation only; no broker, exchange or live order path is wired.

Risk sizing is a calculation of the inputs, not a recommendation. A 1% value is an application default, not a Cloud9 prescription. No pattern, RSI reading, breakout, correlation or backtest promises an outcome. The backtester does not model shorting, borrow costs, dividends, taxes, funding, halts or guaranteed stop fills.

## Robin → IntelX full investigation and agent workflow

The new `IntelX/intelx/services/real_research_transport.py`, `real_investigation_pipeline.py`, `real_robin_config.py` and `real_robin_llm.py` back the existing threat-intel engine. The default federated search list is Robin's 16 onion-engine endpoints from the inspected revision; `INTELX_SEARCH_ENGINES` can override it, and `INTELX_SEARCH_ENGINES=off` disables it. Endpoints are volatile and may be dead.

- `POST /api/threat/investigations` runs refine → search → relevance filter → scrape → IntelX IOC/report ingestion → grounded/extractive summary → pivots → persisted case. `preset` and `user_chose_preset: true` are required before a search. Presets: `threat_intel`, `ransomware_malware`, `personal_identity`, `corporate_espionage`.
- For stage-by-stage operation: `POST /api/threat/robin/search`, `/api/threat/robin/{search_id}/filter`, `/api/threat/robin/{search_id}/scrape`; `GET /api/threat/robin/health` and `/models`.
- Saved cases: `GET /api/threat/investigations`, `GET /api/threat/investigations/{id}`, `POST .../{id}/followup`, `GET .../{id}/export`, and operator-protected `DELETE .../{id}`.
- Existing `POST /api/threat/research` still ingests caller-provided evidence through IntelX and stores an unverified report summary in Memora.
- `friday_core.real_research_mcp` provides the nine Robin-named MCP tools (`robin_refine`, search, filter, scrape, investigate, list models, health, list investigations, save investigation) and a saved-case JSON resource.
- When no `use_cloud_model: true` is supplied, the lifecycle stays local and uses deterministic refinement/relevance plus a source-quoted extractive report. Explicit cloud mode uses the configured Groq analyzer for rewriting, filtering, report, pivots and follow-up; source excerpts are sent to the configured provider. Cloud errors/cooldowns fall back to local processing.
- All search and fetch traffic goes through a SOCKS5 proxy with remote DNS (`TOR_SOCKS_HOST`, `TOR_SOCKS_PORT`, default `127.0.0.1:9050`). There is no direct-network fallback. Scraping follows and revalidates each redirect, caps response bytes and reads HTML/plain text only (no attachments/media). Clearweb result fetching is disabled unless the investigator explicitly selects `allow_clearweb: true`; even then it uses Tor, blocks IP literals/local suffixes, and restricts ports to 80/443.
- Prompt-injection text in pages is treated as untrusted data. Search/filter host caps, result/page/text/concurrency bounds and session expiry are applied. Raw scraped text is used in the current response/session but is not written into new saved cases; saved reports preserve summaries and source citations. Existing older local case databases are not rewritten automatically.

`GROQ_API_KEY` enables the optional model path. The full investigation schema defaults `use_cloud_model` to false; setting it true is explicit data-transfer consent. Tor health and live onion engine behavior are mocked in tests; a real local Tor daemon and reachable search engines are required to run the network flow.

## Drive business playbooks → FRIDAY business operations

`friday_core.real_business_ops_engine` implements the three source workflows as deterministic, read-only operations over caller-uploaded snapshots:

- `POST /api/business/workflows/lead_review/run`: new/follow-up/waiting/won/not-fit/unclear classification, duplicate/missing-field flags, do-not-contact exclusion and evidence-bounded follow-up drafts.
- `POST /api/business/workflows/daily_ad_report/run`: CTR/CPC/CPL/CPA/ROAS derived only when denominators/data exist; comparison/budget threshold flags, date range, timezone, attribution window and source links. Missing values remain unavailable. The playbook's example 25% spend and 20% CPL thresholds are configurable heuristics, not universal rules.
- `POST /api/business/workflows/weekly_ops_sweep/run`: overdue tasks, stalled leads, campaign flags, failures/missing fields and up to three source-linked priorities.
- `GET /api/business/catalog` returns the 20 Drive sectors and playbook principles. `POST /api/business/ideas/import` accepts extracted DOCX text (up to 2 MB) and parses numbered cards to a local SQLite index; `POST /api/business/ideas/search` ranks imported cards with transparent token overlap; `POST /api/business/ideas/score` scores user-assessed readiness dimensions and outputs the source's first-14-day validation plan. It never represents the checklist score as probability of success.
- Skills and local routines persist in SQLite: `POST/GET /api/business/skills`, `POST/GET /api/business/routines`, `GET .../{routine_id}/next-run`, `POST .../{routine_id}/run`. Upload source snapshots with `POST /api/business/snapshots/{source_id}`. Each skill's `sources` list names the snapshot IDs required by its routine; snapshots have an explicit observation time/source link and a configurable max age. Missing/stale sources create blocked runs, not fabricated reports.
- To let routines run on schedule while the FRIDAY server process is alive, set `FRIDAY_ENABLE_ROUTINES=1` (optional poll interval `FRIDAY_ROUTINE_POLL_SECONDS`, 5–300 seconds). The local scheduler claims each due wall-clock slot transactionally across workers. This is not Grok Bot's cloud scheduler and does not run when the FRIDAY process is stopped. No CRM/ad/email connector is fabricated: integrations must supply current snapshots. All mutating operations remain human-reviewed; routine output is in-app only.

Desktop actions/vitals, business snapshot/routine/skill/customer-data routes, IntelX ingestion, live Robin search/scrape and saved-case access/mutation are protected by `X-FRIDAY-Operator: $FRIDAY_LOCAL_ACTION_TOKEN`. Lead drafts are never sent; reports never edit records, change budgets, assign tasks or delete anything. Market analysis, assistant text, voice (with separate consent) and public curriculum/catalog routes remain callable through the existing server boundary.

## Setup and request examples

Configure secrets and local Tor at the server, not in the browser. Example business snapshot upload:

```json
{
  "payload": {
    "leads": [{"id":"L-1","name":"Asha","interest":"demo","status":"active",
                "last_activity_at":"2026-10-01T12:00:00Z","source_link":"https://crm.example/L-1"}],
    "as_of":"2026-10-26T12:00:00Z"
  },
  "observed_at":"2026-10-26T12:00:00Z",
  "source_link":"https://crm.example/export"
}
```

Example full Robin investigation (the selected domain is mandatory):

```json
{
  "query":"ransomware leak organization name",
  "preset":"ransomware_malware",
  "user_chose_preset":true,
  "use_cloud_model":false,
  "max_results":30,
  "max_scrape":10
}
```

`FRIDAY_ALLOWED_APPS` is a JSON object from friendly name to an argv list (for example `{"code":["code"]}`); never put shell fragments in it. `FRIDAY_MAIL_CACHE` points to a local text file. The Yahoo feed and Groq/Tor transport are not reachable from this coding sandbox's outbound allowlist, so live requests were not asserted against external systems.

## Verification

- Deep integration layers 12–15 exercise upstream-style Jarvis actions/voice/model failover/live-market transport; Robin redirects, SOCKS remote-DNS, search/filter/scrape, model privacy opt-in, case persistence/follow-up/MCP; Cloud9 risk/expectancy/journal/correlation/causal backtests; Drive DOCX card parser, lead/ad/weekly operations, skills, scheduled snapshot execution and operator auth.
- Actual main and deep FRIDAY FastAPI apps are imported and posted through in tests.
- Regression group: `tests/test_real_functional_engines.py`, `test_real_cross_agent_integration.py`, `test_real_http_api.py`, `test_real_deep_http_api.py`, `test_real_deep_workflow_http.py`.
- Outcomes for the current code must be reported from the latest test run, not copied from older commits.

## Operational boundary

The existing FRIDAY servers already have broad CORS settings and legacy routes; deploy them behind an authenticated gateway and restrict network exposure. The new operator endpoints fail closed unless the local token is configured, but this integration does not retrofit authentication onto unrelated pre-existing routes. SQLite state is local, not encrypted at rest: restrict filesystem access and retention, especially for journals, reports and uploaded snapshots.

Not implemented/claimed: Cloud9's gated lesson bodies or trading outcomes, a licensed/connected Yahoo production feed, Gmail unread-mail OAuth, WhatsApp sending/contact lookup, a copied holographic Jarvis web UI, smart-home/BroadLink device drivers, a Tor service installation, live crawls in this sandbox, proprietary Drive connectors in the deployed server, live brokerage execution, unattended external sends, or a verified 200-card index until the operator imports the Drive document's extracted text.

## Extended workplace and verified coverage

The additive `/v2` contract preserves all existing routes and now includes a
browser workplace at `/v2/assistant`, voice/speech adapters, approval-gated room
services, grounded quote-validated investigations, Cortex business analysis,
and persistent validated routines. See [capability-coverage.md](capability-coverage.md)
for the source-to-code matrix, deployment configuration and verification limits.
