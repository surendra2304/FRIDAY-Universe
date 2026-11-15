# Futuris Market-Data Backbone — OpenBB Evaluation & Adapter (TASK-IG-FUT-01)

Owner IG-corpus idea (source video `DcsyTU1DsT9`): *"OpenBB-style open
financial-data/research platform as a data backbone candidate for
Futuris forecasting inputs."* Repo card verdict: **adapt** — adopt
selectively; the full platform is far too heavy for the current fleet.

This document is the evaluation, the verdict, and the contract of what
was built instead. All measurements were taken on 2026-11-15 in an
isolated venv (Python 3.12 sandbox; production is Python 3.10.12 —
package resolution and footprints are indicative, and every conclusion
below holds with wide margin).

## 1. What OpenBB is, in its own terms

OpenBB Platform v5 (Apache-2.0 since v5; earlier releases AGPL-3.0) is a
provider-agnostic data platform: data origins are wrapped once as
provider extensions, and consumers read **standardized models** through
one interface, receiving an `OBBject` envelope (results + provider
attribution). That standardization — not any single data source — is
the valuable idea for Futuris.

## 2. Measured cost of the full SDK

| Measurement | Result |
|---|---|
| `pip install openbb-core` (core only) | site-packages ≈ 55 MB total |
| `import openbb_core` | ~0 s, ~9 MB peak RSS |
| `import openbb_core.app.model.obbject` (the data-model layer) | ~51 MB peak RSS |
| `pip install openbb openbb-yfinance` | **site-packages ≈ 1.1 GB**, 27 `openbb-*` packages, ~190 packages total (incl. scipy, statsmodels, plotly, jupyter/ipykernel, flask) |
| First install attempt | **failed**: `ResolutionImpossible` (openbb 4.7.1 vs openbb-yfinance 1.5.2 pin conflict); a later resolution selected openbb 5.0.0 — resolution is version-sensitive |
| `from openbb import obb` (router build) | **210.9 s import time, 995.6 MB peak RSS** |

### 2.1 Import measurement

```
$ python -c "from openbb import obb"   # openbb 5.0.0, sandbox venv
import time: 210.9s
peak RSS:    995.6 MB
```

Building the OpenBB application object takes three and a half minutes
and peaks at ~996 MB of resident memory — **more than Server 1's entire
956 MB of RAM**, for the import alone, before a single byte of data is
fetched. Against Futuris's 180 MB MemoryMax this is not a tuning
problem; it is two orders of magnitude of headroom that does not exist.

## 3. The fleet budget it would have to fit

Ground truth from TASK-REL-048 (production, Server 1, 2026-11-15):

* Server 1 has **956 MB RAM total** for seven agents; swap is load-bearing.
* Futuris runs under **MemoryMax = 180 MB**; its measured total
  footprint is **186.1 MiB** — already over cap, kept alive by swap.
* ≈127 MB of that is Futuris's own forecast-adapter stack at boot.

## 4. Verdict

**The full OpenBB SDK cannot run inside Futuris on the current fleet.**
A ~1.1 GB dependency tree whose application object costs (per §2.1) a
large fraction of — or more than — the entire server RAM, inside a
service capped at 180 MB that is already over its cap, is not a close
call. Pin fragility (§2) adds operational risk on a 3.10 production
interpreter the SDK's current releases are not primarily built for.

**What is adopted now** is OpenBB's architecture, which is the part
that helps Futuris today:

* standardized OHLCV records + an OBBject-style result envelope with
  provider attribution (`futuris/market_data/models.py`);
* a bounded provider contract (`futuris/market_data/base.py`) with two
  keyless real-data providers over origins OpenBB itself wraps —
  Yahoo Finance chart API (`yahoo_chart`, the origin behind OpenBB's
  yfinance provider) and Stooq daily CSV (`stooq`);
* an `openbb_sdk` provider that imports the real SDK **lazily, only
  inside its fetch**, and reports `unavailable` while the SDK is not
  installed. On post-ARM hardware, installing the SDK and adding
  `openbb_sdk` to `FUTURIS_MARKET_DATA_PROVIDERS` lights up the real
  platform behind the identical interface — no consumer changes.

## 5. The backbone contract (what the Stratex lane consumes)

In-process:

```python
from futuris.market_data.service import MarketDataBackbone, to_observations

backbone = MarketDataBackbone.from_settings()  # FUTURIS_MARKET_DATA_PROVIDERS
result = await backbone.get_ohlcv("BTCUSDT", start, end, interval="1d")
observations = to_observations(result)  # -> futuris Observation list
```

Over HTTP (Futuris API): `GET /v1/market-data/ohlcv?symbol=BTCUSDT&days=90&interval=1d`

Semantics both ways:

* `status="ok"` ⇒ `bars` are real fetched data; `provider` and
  `source` name the origin (e.g. `market_data:yahoo_chart:BTC-USD`);
  the API labels the payload `evidence_class="LIVE"`, and
  `to_observations` feeds `futuris.connectors.provenance` so forecasts
  consuming backbone data are labelled from what actually fed them.
* `status="unavailable"` ⇒ `bars` is empty, `detail` says why, and
  `attempts` records every provider tried. **There is no synthetic
  fallback anywhere in this layer** (FUT-005 discipline): no invented
  bars, no interpolation of missing slots (Yahoo null bars are
  dropped), no resampling (Stooq refuses non-daily intervals rather
  than deriving them).
* Providers are tried in configured order; the first real answer wins.

## 6. Adoption path when hardware allows

1. Provision the ARM server (post-ARM milestone).
2. `pip install openbb openbb-yfinance` (pin the resolved set; re-run
   §2's measurements on the production interpreter first).
3. Set `FUTURIS_MARKET_DATA_PROVIDERS=yahoo_chart,stooq,openbb_sdk`
   (or lead with `openbb_sdk`).
4. Re-run the FUT-004/FUT-006 forecast-input scorecards with backbone
   inputs before any forecast path consumes them unattended.
