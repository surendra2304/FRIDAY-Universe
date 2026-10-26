# Jarvis / Robin: integrated agent capabilities

## Source inspection

- Jarvis: https://github.com/saipradeep77964/jarvis-ai-assistant at
  `6d5fc666842165aaa117804e900f399e0bec0a12`. Inspected the Python files in
  `Jarvis_Setup_Package.zip` through GitHub's blob API (brain, market, voice).
- Robin: https://github.com/apurvsinghgautam/robin at
  `b5d4f5f509fac39d65d3a28fd1d78b56efbeeaf4` (Apurv Singh Gautam).
  Inspected `search.py` and `scrape.py` through GitHub's contents API.

Algorithms are rewritten as standard-library engines; upstream applications,
installers and dependencies are not copied into this repository.

## Actual call paths

Both `friday_core.real_api_server.app` and
`friday_core.real_deep_api_server.app` mount `real_research_api`:

- `POST /api/assistant/respond` -> `CrossAgentEngine.assistant_reply`
  -> Jarvis local-first dispatch -> Stratex or IntelX -> structured response.
  Unknown questions optionally go to Groq, with model failover and cooldown.
- `POST /api/trading/momentum` -> existing `TradingEngine.analyze_momentum`
  -> short/medium averages and market signal on supplied observations.
- Existing `/api/trading/signals` and `/api/trading/backtest` accept strategy
  `jarvis_momentum`. Backtest execution uses prior-close signals at the next
  bar open, entry/exit fees, marked equity, drawdown and isolated per-run trades.
- `POST /api/threat/research` -> `CrossAgentEngine.research_threats`
  -> existing `ThreatIntelEngine.ingest_research` -> source deduplication/host
  limits -> unverified URL, IPv4, email and SHA256 observations -> persistent
  IntelX indicators and report -> Memora summary with returned memory ID.
  Repeated observations reuse indicator IDs; each report retains its sources.

Example market assistant request:

```json
{
  "query": "Jarvis, analyze market",
  "market": {
    "symbol": "TEST",
    "price": 120,
    "previous_close": 118,
    "closes": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118]
  }
}
```

Example research request:

```json
{
  "documents": [{
    "url": "http://example.onion/post",
    "title": "Observed posting",
    "text": "Unverified observation: 8.8.8.8"
  }],
  "per_host_limit": 3
}
```

A document can supply `engine_url` and a wrapped/relative `url` from that
engine. Robin-style extraction resolves the external onion destination before
policy validation, deduplication and indicator creation. Userinfo, ambiguous
hosts, deceptive onion suffixes and clearweb destinations are rejected.

## Deployment and limits

Set `GROQ_API_KEY` in the server environment to opt into the actual stdlib Groq
HTTP adapter. Do not put credentials in requests or source files. Without a key,
local agent dispatch works and unknown questions return an honest fallback.
The cloud transport has a timeout and response-size limit. Cloud tests mock
transport; live outbound Groq access is not available in this workspace.
Only the conversational query/history goes to the provider, not structured market
or research context. API history is disabled to prevent cross-user leakage;
model cooldown persists for each running cross-agent engine. Route mutations
are serialized within each router. This is not a distributed worker queue.

No shell commands, trade orders or arbitrary URL fetches are executed. Market
prices and research documents must be supplied by the caller. Onion URL policy
is not onion-address cryptographic validation. Observations are not confirmed
threats: persisted indicators carry low confidence and `unverified` tags.
No Tor transport, live market feed, abuse-content classifier, voice device loop
or full upstream application is claimed. These API routes inherit the servers'
existing access controls; do not expose the existing servers publicly without
an authenticated deployment gateway.

## Verification

- `tests/test_real_deep_layer12.py`: hybrid brain and momentum calculations.
- `tests/test_real_deep_layer13.py`: destination policy, extraction and accounting.
- `tests/test_real_deep_layer14.py`: real engines through HTTP, persistence/reload,
  Memora storage, idempotent indicators, cloud transport, local-first cooldown,
  causal signals, fees and repeatable backtests.

## Sources still blocked

- Cloud9 Markets academy: not a repository and outside the workspace network
  allowlist. No curriculum or proprietary trading logic was inferred.
- Drive folder `16-w2LiHKi1WZxRmvInuVSY3gMU5fHU8j`: connector lookup reported
  disconnected. No contents or license were inspected.

Upload those materials or connect Drive for source-grounded implementation.
