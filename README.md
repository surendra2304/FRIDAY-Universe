# FRIDAY Universe v3.0

**Multi-Agent Intelligence Platform — 9 Agents · 3 Layers · 60+ Real Engines · 257 Tests**

Inspired by Tony Stark's FRIDAY, this is a production-grade multi-agent system where each agent genuinely works in its domain — not stubs, but real algorithms.

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn httpx pydantic pytest requests numpy scipy matplotlib pandas

# Copy environment template
cp .env.example .env

# Start the API server (all 54+ endpoints)
export PYTHONPATH=FRIDAY/apps/core/src:Inference/app:Inference:Memora:Stratex:Forge/app/services:Sentinel/app/services:IntelX/intelx/services:Futuris/futuris/core:VyralX/app/services
python3 -m uvicorn friday_core.real_api_server:app --host 0.0.0.0 --port 8000

# Or use Docker
docker compose up -d --build
```

## Architecture

```
┌──────────────────────────────────────────┐
│          Universe Orchestrator            │
│    (Unified coordination across layers)   │
├──────────────────────────────────────────┤
│  LAYER 3 — Deep (Advanced Algorithms)     │
│  Recommenders · Sentiment · Security      │
│  Vuln Mgmt · Threat Forecast · Forecast   │
│  Audience Intelligence                    │
├──────────────────────────────────────────┤
│  LAYER 2 — Advanced (Scientific Computing)│
│  K-means · Black-Scholes · VaR · Causal   │
│  Knowledge Graph · ATT&CK · Quantum       │
├──────────────────────────────────────────┤
│  LAYER 1 — Basic (Working Engines)        │
│  Bayesian · TF-IDF · RSI/MACD · AST       │
│  Threat Detection · Indicator Correlation │
│  SMA/SES/Holt/ARIMA · Content Prediction  │
├──────────────────────────────────────────┤
│  9 Agents: Cortex Inference Memora         │
│  Stratex Forge Sentinel IntelX            │
│  Futuris VyralX                            │
└──────────────────────────────────────────┘
```

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/decision/decide` | Weighted decision engine |
| POST | `/api/deep/security-scan` | Deep code security scan |
| POST | `/api/deep/sentiment` | Sentiment analysis |
| POST | `/api/deep/forecast` | Time series forecast |
| POST | `/api/workflow/deep/security` | Deep security workflow |
| GET | `/api/dashboard` | Full dashboard data |

**54+ endpoints total** — see `README_UNIVERSE.md` for the complete list.

## Tests

```bash
# Run all 257 tests
bash scripts/run_all_real_tests.sh

# Or individual suites
python3 -m pytest tests/test_real_functional_engines.py -v    # 43 tests
python3 -m pytest tests/test_real_deep_engines.py -v           # 42 tests
python3 -m pytest tests/test_real_http_api.py -v               # 14 tests
```

| Suite | Tests | Status |
|-------|-------|--------|
| Basic + Advanced + Deep Engines | 147 | ✅ |
| Orchestrator + Prod Server | 26 | ✅ |
| Realtime Pipeline | 19 | ✅ |
| HTTP API (All) | 41 | ✅ |
| Dashboard HTTP | 4 | ✅ |
| **Total** | **257** | **✅ All passing** |

## Agents

| Agent | Domain | Layers | Key Engines |
|-------|--------|--------|-------------|
| Cortex | Decision Intelligence | 3 | Decision, Recommender, Predictive Analytics |
| Inference | Reasoning | 2 | Bayesian, Causal, Argumentation |
| Memora | Memory | 2 | TF-IDF, Knowledge Graph, SuperMemo |
| Stratex | Trading | 3 | RSI/MACD, Black-Scholes, Sentiment, Patterns |
| Forge | Code | 3 | AST, Auto-Repair, Security Scanner |
| Sentinel | Security | 3 | Threat Detection, Vuln Mgmt, Compliance |
| IntelX | Threat Intelligence | 3 | Correlation, DarkWeb, Forecast, Disinfo |
| Futuris | Forecasting | 3 | ARIMA, Quantum, Ensemble, Stress Test |
| VyralX | Content | 3 | Prediction, Audience, Growth, Moderation |

## Security

- All credentials loaded via `os.getenv()` — never hardcoded
- `.env.example` provided as template
- `.gitignore` excludes `.env`, `*.key`, `*.pem`, CREDENTIALS files
- Secret redaction in all error envelopes and logs
- See `CONTRIBUTING.md` for security reporting guidelines

## License

MIT — see [LICENSE](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

**Built with real code, real algorithms, real results.**
