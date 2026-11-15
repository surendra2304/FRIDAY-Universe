# Futuris uncertainty presentation (TASK-FUT-008)

Audit of how Futuris presents forecasts to FRIDAY and to the owner, on fresh
main `ef3ca99` (2026-11-15), and the presentation layer added in response.

## The rule

Every forecast must carry, in plain language:

1. **Its horizon** — "over the next 24 hours", never a missing field or a
   raw `timedelta` string.
2. **Its method, honestly named** — a statsforecast model is named as a
   statsforecast model only when the statsforecast backend is installed in
   the deployment. While it is not installed, a stored forecast's label is
   reported as a *recorded label* that was not produced by a statsforecast
   run here. Heuristic rules are named as heuristic rules.
3. **A calibrated uncertainty range** — the numeric range, its actual level
   (the adapters build 90% prediction intervals, `z = 1.645` over residual
   std in `futuris/models/adapters.py`), and whether calibration for the
   target has been *measured* from resolved outcomes or is still
   *unmeasured*.

Implemented once in `futuris/presentation/uncertainty.py` (stdlib-only) and
attached as an additive `presentation` block on every surface below.
Existing fields are unchanged; consumers that ignore `presentation` keep
working.

## Audit findings (before)

| Surface | Horizon | Method | Uncertainty |
|---|---|---|---|
| `POST /v1/friday/forecast` (FRIDAY delegation) | **dropped entirely** — the response model had no horizon field, although the domain forecast has one | only `model_used: "seasonal_naive@v1:c8f93a"` — an opaque label | bounds present; level never stated; calibration honest since FUT-002 (`_honest_calibration`), but the bare `confidence: "MEDIUM"` meta-confidence label reads as event confidence |
| `POST /v1/friday/delegate` summaries | absent from the text FRIDAY relays | absent | absent — summary was target + status only |
| `POST /v1/friday/scenario` | absent | absent | probability honest since FUT-002 (base probability verbatim); the `HIGH_RISK`/`MODERATE_RISK`/`NOMINAL` label is sized purely off the delta with **no stated basis** |
| `GET /v1/friday/forecasts` | absent | only `model_version` label | **no range bounds at all** |
| `GET /v1/friday/calibration` | — | — | already honest (FUT-002: real resolved pairs, `trend: "unmeasured"`); left untouched, except the delegate summary no longer quotes the 0.0 sentinel ECE as a score when unmeasured |
| `POST /forecast` (owner quick surface) | echoed as the raw request string | only the version label | range present, level unstated, calibration state absent |
| `GET /trends` (owner) | **absent** | **absent** | bounds present, level unstated |
| `POST /simulate` (owner) | absent | deterministic linear propagation **unnamed** | probability honest since FUT-002 (`null` + status); no statement that the run has no spread |
| Canonical `GET/POST /v1/forecasts` | rendered as `str(timedelta)` — literally `"1 day, 0:00:00"` | only the version label | range present, level unstated, calibration state absent |
| `POST /v1/futuris/market/forecast` (Stratex) | `horizon_hours` present in sub-payloads | **the label sent to the Inference gateway was `statsforecast_garch_intelx`** — neither statsforecast nor GARCH ran; the persisted record has been honestly labelled `heuristic:telemetry_vol_rule@v2` since TASK-TRUST-001, but the outbound label was never corrected | `range_pct` is a deterministic rule bound (`-2.5×`/`+3.5×` multipliers), presented with no basis — reads as a statistical interval |

Already honest and deliberately **not** touched: the BLOCKED /
stale-telemetry / insufficient-data refusals (TASK-REL-018), the FRIDAY
calibration report (TASK-FUT-002), scenario probability semantics
(TASK-FUT-002), market confidence derivation (TASK-FUT-002).

## After — the same stub forecast, both responses

Stub: target `service:checkout:capacity_exceedance_24h`, 24h horizon,
prediction 128.5, range 100.2–156.8, probability 0.42, model label
`seasonal_naive@v1:c8f93a`, no resolved outcomes, synthetic inputs,
statsforecast **not** installed (the production reality until ARM).

**Before** — FRIDAY delegation response (excerpt, generated from main):

```json
{
  "prediction": {"point_estimate": 128.5, "lower_bound": 100.2,
                 "upper_bound": 156.8,
                 "probability_distribution": {"p10": 100.2, "p50": 128.5,
                 "p90": 156.8, "exceedance_probability": 0.42}},
  "confidence": "MEDIUM",
  "model_used": "seasonal_naive@v1:c8f93a"
}
```

No horizon anywhere in the payload. Canonical API `horizon` for the same
forecast: `"1 day, 0:00:00"`.

**After** — the same response gains (existing fields unchanged):

```json
{
  "horizon": "24 hours",
  "presentation": {
    "horizon_text": "24 hours",
    "method": "Seasonal naive (recorded model label)",
    "interval_level_pct": 90,
    "uncertainty_range": {"lower": 100.2, "upper": 156.8, "level_pct": 90},
    "calibration_status": "unmeasured",
    "summary": "Forecast for service:checkout:capacity_exceedance_24h over the next 24 hours: most likely value 128.5. The 90% prediction range is 100.2 to 156.8 — if the model is well calibrated, the actual value should fall inside that range about 90 times out of 100. Method: Seasonal naive (recorded model label) — the stored forecast is labelled Seasonal naive, which repeats the most recent seasonal cycle. The statsforecast backend is not installed in this deployment, so this number was not produced by a statsforecast run here and cannot be recomputed until the backend is installed. Estimated probability of the event in this horizon: 42%. Calibration for this target is unmeasured — no resolved forecasts have been checked against outcomes yet — so treat the range as the model's own estimate, not a proven track record. Its inputs are synthetic/demo data, not live measurements — do not treat it as a reading of the real system. The 'medium' confidence label describes trust in the model's calibration and data quality — it is not the probability of the event."
  }
}
```

In a deployment where statsforecast **is** installed, the same label reads
`Seasonal naive (statsforecast)` — the naming follows the backend's actual
presence, checked at runtime via `STATSFORECAST_AVAILABLE`.

## Coordination

- **FUT-004** (walk-forward evaluation harness) is the instrument that will
  *measure* the empirical coverage these presentations cite as unmeasured;
  nothing here pre-empts its verdicts — the presentation reads calibration
  only from stored resolved-outcome metrics.
- **FUT-006**: no file overlap intended. This change touches
  `futuris/presentation/**` (new), `futuris/api/routers/{friday,forecasts,
  market}.py`, `futuris/api/app.py` (quick surfaces only) and adds one test
  file; flagged on issue #35 so merges can be sequenced if FUT-006 lands in
  the same files first.
