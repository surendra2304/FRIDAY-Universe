# ARM-DAY RUNBOOK — Futuris: flip the OpenBB switch (TASK-IG-FUT-01)

Purpose: when the 12 GB ARM server lands, activating the real OpenBB
Platform data path in Futuris is a **configuration flip, not a build**.
Everything host-side is already done (PR #496 adapter + the 2026-11-16
host-side completion: `FUTURIS_OPENBB_PROVIDER` config, SDK-present
contract tests, `GET /v1/market-data/providers` readiness surface,
`openbb` pyproject extra). This runbook is the exact flip sequence.

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

## Step 0 — Re-measure on the ARM interpreter (decides the cap)

> **⚠️ ORDER MATTERS — MEASURE FIRST, INSTALL INTO FUTURIS LAST.**
> **Do NOT `pip install` OpenBB into Futuris's / the fleet venv in
> this step, and do NOT try to measure the import in that venv
> first.** On a fresh ARM host OpenBB is not in that venv yet, so
> the measurement there would simply fail — and installing it there
> just to make the measurement work would put the ~1.1 GB install
> into the production env *before* its memory cap is decided, which
> is exactly what this step exists to prevent.
>
> The only install allowed in Step 0 is into a **throwaway scratch
> venv** (Step 0b). The install into Futuris's env is **Step 1
> only**, and Step 1 is **blocked** until Step 0 is complete:
> measurement recorded **and** MemoryMax decided from it.
>
> Do the four sub-steps below in order — 0a, then 0b, then 0c,
> then 0d. Do not reorder them.

**Step 0a — Snapshot the untouched Futuris / fleet venv (rollback
snapshot). Run this BEFORE any install, anywhere:**

```bash
# in the fleet venv on the ARM host — read-only, installs nothing
pip freeze > /tmp/pre-openbb-freeze.txt        # rollback snapshot
```

**Step 0b — ONLY IF OpenBB is not already present: install it into
a scratch venv, never into Futuris's env:**

```bash
python3 -m venv /tmp/openbb-measure-venv
/tmp/openbb-measure-venv/bin/pip install 'openbb>=5.0,<6.0'
```

(Skip 0b only if OpenBB is already importable on this host without
installing anything — e.g. a scratch venv from an earlier
measurement still exists; in that case use that venv's `python`
in Step 0c instead of the path shown. Never skip it by installing
into Futuris's env instead.)

**Step 0c — Measure the import in the SCRATCH venv (not in
Futuris's venv):**

```bash
/usr/bin/time -v /tmp/openbb-measure-venv/bin/python -c "from openbb import obb" 2>&1 | grep -E "Maximum resident|Elapsed"
```

**Step 0d — Record and decide the cap. Step 0 is not done until
this is written down:**

Record import time + peak RSS. Set Futuris's MemoryMax on ARM to at
least **peak-RSS + 1 GB** (starting recommendation: 2.5 GB, given the
~1 GB import peak + ~190 MB base footprint).

**GATE: Do not proceed to Step 1 until 0a–0d are all done.**

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
