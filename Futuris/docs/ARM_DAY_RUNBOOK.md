# ARM-DAY RUNBOOK — Futuris: flip the OpenBB switch (TASK-IG-FUT-01)

Purpose: when the 12 GB ARM server lands, activating the real OpenBB
Platform data path in Futuris is a **configuration flip, not a build**.
Everything host-side is already done (PR #496 adapter + the 2026-11-16
host-side completion in PR #778: `FUTURIS_OPENBB_PROVIDER` config,
SDK-present contract tests, `GET /v1/market-data/providers` readiness
surface, `openbb` pyproject extra). This runbook is the exact flip
sequence. (It lived in the IG lane workspace until the post-#778
follow-up PR landed it here, so ARM day does not depend on a
workspace file.)

Ground facts (measured, `Futuris/docs/DATA_BACKBONE_IGFUT01.md` §2):
`from openbb import obb` on openbb 5.0.0 = **210.9 s import, 995.6 MB
peak RSS**; the full install is ~1.1 GB / ~190 packages; resolution is
version-sensitive (a 4.7.1/1.5.2 pin conflict was hit during
evaluation). Futuris's current cap is MemoryMax 180 MB on a 956 MB
host — that is why none of this may run before ARM.

## Preconditions

- [ ] ARM server provisioned (12 GB), Futuris deployed and healthy on
      it (or Futuris's memory cap raised on a host with the headroom).
- [ ] FREE-only rule: only keyless OpenBB extensions (default
      `yfinance`). A keyed extension (e.g. `fmp`) needs the owner's
      explicit decision + the key in the server-side unit env — never
      in the repo.
- [ ] NEVER run any step of this runbook on the current 956 MB hosts.

## Step 0 — Measure FIRST, in a scratch venv (decides the cap)

The order inside this step is the whole point, so it is spelled out:
**snapshot → install into a SCRATCH venv only → measure with the
scratch venv's interpreter → set the cap from the measurement.**
Step 1 is the first moment anything is installed into the fleet venv.

Why: on a fresh ARM host `openbb` is not installed anywhere yet, so
the measurement import below can only run in a venv that already has
it — and installing into the fleet venv before measuring would put
the unmeasured ~1 GB import one stray import away from Futuris's
service env before its cap has been raised to fit it. Do NOT run the
measurement with the fleet venv's `python`, and do NOT "fix" a failed
measurement import by installing into the fleet venv — create the
scratch venv (0.2) instead.

```bash
# 0.1 Snapshot the fleet venv BEFORE anything changes (rollback base).
/opt/friday_universe/venv/bin/pip freeze > /tmp/pre-openbb-freeze.txt

# 0.2 Create a SCRATCH venv (NOT the fleet venv) and install the
#     declared set there, only there.
/usr/bin/python3 -m venv /tmp/openbb-measure-venv
/tmp/openbb-measure-venv/bin/pip install 'openbb>=5.0,<6.0' 'openbb-yfinance'

# 0.3 Measure with the SCRATCH venv's interpreter.
/usr/bin/time -v /tmp/openbb-measure-venv/bin/python -c "from openbb import obb" 2>&1 | grep -E "Maximum resident|Elapsed"
```

Record import time + peak RSS. Set Futuris's MemoryMax on ARM to at
least **peak-RSS + 1 GB** (starting recommendation: 2.5 GB, given the
~1 GB import peak + ~190 MB base footprint). Only after the cap is
decided do you proceed to Step 1.

## Step 1 — Install the declared set

```bash
# fleet venv on the ARM host
pip install 'futuris[openbb]'        # extra: openbb>=5.0,<6.0 + openbb-yfinance
pip freeze | grep -i openbb          # record the resolved set
```
Pin the resolved set into `Futuris/requirements.lock` via a small PR
the same day (the design doc recorded a ResolutionImpossible in this
tree's history — the resolved set is the deliverable, not the floor).

## Step 2 — Prove presence without starting anything

```bash
python -c "from futuris.market_data.providers.openbb_sdk import sdk_available; print(sdk_available())"
# must print True. (find_spec probe — does NOT import the SDK.)
```

## Step 3 — Config flip (Futuris unit env, server-side)

Confirm the exact unit name first (`systemctl list-units | grep -i futuris`).
In the Futuris service env:

```ini
FUTURIS_MARKET_DATA_PROVIDERS=yahoo_chart,stooq,openbb_sdk
FUTURIS_OPENBB_PROVIDER=yfinance
```

Week-1 posture: `openbb_sdk` LAST (breadth behind the proven free
providers). Promote it only after a week of `attempts` evidence
(Step 5.4). Restart Futuris only:

```bash
sudo -n systemctl restart <Futuris unit>
```

## Step 4 — Verify the flip (in this order)

1. **Readiness surface:**
   `GET /v1/market-data/providers` → the `openbb_sdk` entry must show
   `"available": true`. If it still shows `false` with the
   not-installed detail, the install landed in a different venv than
   the unit runs — stop and fix that, nothing else is meaningful yet.
2. **Force the real SDK path once:** temporarily set
   `FUTURIS_MARKET_DATA_PROVIDERS=openbb_sdk`, restart Futuris, then
   `GET /v1/market-data/ohlcv?symbol=BTCUSDT&days=30&interval=1d` →
   must return `status="ok"`, `provider="openbb_sdk"`,
   `source="market_data:openbb_sdk:yfinance"`,
   `evidence_class="LIVE"`, real bars. This also pays the one-time
   router build (~Step 0's import time) as a warm-up, so no forecast
   or user call ever pays it. Then restore the Step-3 ordering and
   restart again.
3. **Memory:** after the warm-up fetch,
   `systemctl show <Futuris unit> -p MemoryCurrent -p MemoryPeak` —
   peak must sit under MemoryMax with headroom; if not, raise the cap
   (ARM has the room) before proceeding.
4. **Health:** Futuris `/health` 200; fleet 10/10.

## Step 5 — Forecast-input gate (before unattended consumption)

1. Re-run the FUT-004/FUT-006 forecast-input scorecards with backbone
   inputs (design doc §6 step 4) before any unattended forecast path
   consumes `openbb_sdk` data.
2. For the first week, read the `attempts` array on `/ohlcv`
   responses daily: it records which provider actually served each
   fetch and why the others didn't.
3. Board follow-up: append the verification evidence to
   TASK-IG-FUT-01 via a board PR (deployed ≠ production-verified —
   the flip is production-verified only after steps 4.2 + 5.1 pass).

## Step 6 — statsforecast co-verification (same host move, separate engine)

The production forecast path returns `statsforecast_unavailable`
today. On ARM, confirm `statsforecast` imports inside Futuris's cap
and a forecast call stops returning the unavailable marker. Verify —
do not assume the host move fixed it; it is a different dependency
with its own footprint.

## Rollback (any step fails)

1. Remove `openbb_sdk` from `FUTURIS_MARKET_DATA_PROVIDERS`; restart
   Futuris. The backbone is byte-for-byte the behaviour flying today
   (yahoo_chart + stooq) — the provider imports the SDK only inside
   its fetch and is only built when configured.
2. If the install itself destabilised the shared venv (pin
   conflicts): uninstall the `openbb-*` packages and restore against
   `/tmp/pre-openbb-freeze.txt` from Step 0.
3. No code rollback exists or is needed: nothing in the flip touches
   repo code.
