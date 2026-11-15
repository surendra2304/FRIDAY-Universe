"""TASK-INF-004 isolated harness: cost of OpenRouter free-model discovery
in the gateway's fallback pattern.

Production pattern being simulated (app/providers/gateway.py
_execute_dynamic_fallback): for EVERY fallback, the gateway constructs a
fresh OpenRouterProvider via get_provider("openrouter", api_key=...) —
never memoised — and calls get_best_free_model(capability), which calls
fetch_available_free_models().

The stub transport reproduces the production-measured cost of
GET https://openrouter.ai/api/v1/models from Server 1 (850,791 bytes,
0.59–1.10s; 0.8s used here). No real network, no real providers.

Scenario: 10 sequential fallbacks (fresh instance each), then report the
number of catalogue fetches and total discovery wall time.
"""
import asyncio, os, sys, time

os.environ.setdefault(
    "DATABASE_URL",
    "oracle+oracledb://INFERENCE:placeholder@adb.example.com:1522/?service_name=TEST",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.providers.openrouter as openrouter_module
from app.providers.openrouter import OpenRouterProvider

FETCH_LATENCY_S = 0.8
FALLBACKS = 10

CATALOGUE = {
    "data": [
        {"id": "nvidia/nemotron-3.5-lightning:free", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "meta-llama/llama-3.3-70b-instruct:free", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "paid/model-x", "pricing": {"prompt": "0.001", "completion": "0.002"}},
    ]
}


class _Resp:
    status_code = 200

    def json(self):
        return CATALOGUE


class _StubClient:
    def __init__(self):
        self.calls = 0

    async def get(self, url, headers=None, timeout=None):
        self.calls += 1
        await asyncio.sleep(FETCH_LATENCY_S)
        return _Resp()


async def main():
    stub = _StubClient()

    async def _get_shared_client():
        return stub

    openrouter_module.get_shared_client = _get_shared_client
    if hasattr(openrouter_module, "_DISCOVERY_CACHE"):
        openrouter_module._DISCOVERY_CACHE.clear()

    start = time.perf_counter()
    models = []
    for _ in range(FALLBACKS):
        provider = OpenRouterProvider(api_key="bench-key")  # fresh, as the gateway does
        models.append(await provider.get_best_free_model("general"))
    elapsed = time.perf_counter() - start

    print(f"fallbacks simulated : {FALLBACKS} (fresh provider instance each)")
    print(f"catalogue fetches   : {stub.calls}")
    print(f"discovery wall time : {elapsed:.2f}s")
    print(f"per-fallback cost   : {elapsed / FALLBACKS:.2f}s")
    print(f"models selected     : {sorted(set(models))}")


if __name__ == "__main__":
    asyncio.run(main())
