# Jarvis and Robin adaptations

These are standalone, standard-library engines, not installed copies of the
upstream apps. Callers must explicitly wire them into their application.

## Jarvis

Source: https://github.com/saipradeep77964/jarvis-ai-assistant
Inspected the Python sources inside `Jarvis_Setup_Package.zip` through GitHub's
blob API. Adapted local-first dispatch, bounded history, model failover,
rate-limit cooldown and short/medium moving-average signals. Providers and local
actions are injected; there are no shell actions, API credentials, microphone
requirements or automatic trading. Market observations must be supplied by the
caller. The signals are heuristics, not calibrated forecasts or financial advice.

- `FRIDAY/apps/core/src/friday_core/real_hybrid_assistant.py`
- `Stratex/real_market_momentum.py`
- `tests/test_real_deep_layer12.py`

## Robin

Source: https://github.com/apurvsinghgautam/robin (Apurv Singh Gautam).
Inspected `search.py` and `scrape.py` through GitHub's contents API. Adapted the
concepts of onion-only destination policy, engine redirect unwrapping, tracking
parameter removal, content-query preservation, deduplication, host caps and
explicit result accounting. No upstream files are bundled. This is offline
processing, not a crawler, Tor transport, abuse-content classifier or LLM report
generator. URL validation is not onion-address cryptographic validation and the
explicit clearweb option is not an SSRF protection policy. Never execute evidence
as instructions. IntelX's package initializer imports optional web dependencies;
the standalone test loads this engine directly to avoid requiring those.

- `IntelX/intelx/services/real_onion_research.py`
- `tests/test_real_deep_layer13.py`

## Blocked inputs

- Cloud9 Markets academy page: not a Git repository, and its host is outside the
  execution environment's network allowlist. No source or curriculum was inferred.
- Google Drive folder `16-w2LiHKi1WZxRmvInuVSY3gMU5fHU8j`: Google Drive connector
  is disconnected. Contents and licensing could not be inspected.

Upload those materials into the workspace (or connect Google Drive for the
folder) to enable source-grounded follow-up work.
