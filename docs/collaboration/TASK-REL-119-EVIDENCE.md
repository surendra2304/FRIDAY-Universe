# TASK-REL-119 — scripts/live_probe.py: public-gateway live probe, one command per agent (evidence)

- **Task:** Reliability: scripts/live_probe.py — one command per agent hitting the gateway health endpoint + one real request (SPEED ROUND 2 5b).
- **Owner:** Muse 4. **Claim:** hub #2045 comment 7226298299, 2026-11-28 ~00:42 IST.
- **Board verified:** AVAILABLE, owner null, P1, on live main `69acab99` (board blob `f7589962…` read via git blob API before editing).
- **Branch:** `muse4/task-rel-119-live-probe` from main `69acab99` (verified via API; branch head == main at claim).
- **Live-proof route (coordinator watch235):** public gateway `https://friday-universe.duckdns.org` health endpoints + one real request per agent.

## Correction to the board acceptance — read first

The acceptance says "Build scripts/live_probe.py … New file only". That file
**already exists on main**: TASK-REL-104 built it and PR #2105 merged it
2026-11-27 (merge `e9b91a9f`, head `1d1b241b`; board REL-104 record: MERGED,
owner muse_6, "live run owed as follow-up"). REL-119 **is** that follow-up:
REL-104's own checkpoint-2 doc §5 says "Live run: once a route is settled,
run the script from a host with VCN or public-ingress access and file the
JSON output as evidence". No new file was created here, because creating a
second probe script would duplicate a merged tool. What this PR does instead,
in the one file the task names:

1. Adds `--public` mode to `scripts/live_probe.py` (the REL-104 script cannot
   run from this VM: its mesh-ping / task-execute legs need `INFERENCE_API_KEY`,
   which this worker does not hold and must not request — and, verified live
   below, its `/v1/health` gate 401s through the public ingress without a key).
2. Extends the hermetic suite `tests/test_live_probe.py` with 5 public-mode
   tests (13/13 pass locally, §6).
3. Files this doc with the real live-run output (§3–§5).

## Verdict

**IMPLEMENTED + LIVE-RUN COMPLETE, 7/10 agents pass, 3 degraded — and the
degradation is the finding, not a probe failure.** The public probe works
end to end with no key: gateway gate `GET /health` 200 healthy, all 10
leg-B real requests 200. Three agents fail leg A with persistent 503
`degraded` health, confirmed on three separate reads ~19:15Z, ~19:23Z and
~19:25Z (full run, 3-agent recheck, full-body re-fetch): **stratex,
futuris, intelx**. All three are degraded in the same way on every read —
a capability the endpoint itself marks `unknown`, not a transient blip —
and the deploy workflow already records Futuris/IntelX 503s as pre-existing
(`deploy-monorepo.yml`, TASK-OBS-019 baseline: "Futuris :8004 / IntelX :8005
were already failed … on a healthy deploy"). No re-run was done to hide
this: the script exits 1, as designed, when any agent fails a leg.

## §1 — What was built (`--public` mode)

Stdlib-only addition to `scripts/live_probe.py` (no new dependencies, no
daemon/timer/service, keyed REL-104 mode untouched — its 8 hermetic tests
still pass unmodified):

- **Leg A (health, genuinely per-agent):** `GET /{agent}/health` on the
  public gateway. Pass = HTTP 200 **and** the body self-reports
  `status`/`overall` of `healthy`/`ok`. A 503 `degraded` fails the agent.
- **Leg B (one real request per agent):** `GET` of one genuine read-only
  endpoint of that agent's own app (`PUBLIC_REAL_REQUEST` in the script).
  Pass = HTTP 200; the body's own status (when JSON carries one) is
  recorded, so a 200 that self-reports unhealthy stays visible.
- **Gateway gate:** `GET /health` on the public base; unreachable/unhealthy
  → exit 2 with no per-agent probes (same semantics as keyed mode).
- **Exit codes:** 0 all pass, 1 any agent fails a leg, 2 gateway down.
  `--agents` subsets and `--health-only` work in public mode too.
- **No key anywhere in public mode:** no `INFERENCE_API_KEY` read, no
  `Authorization` header sent, nothing secret in the output.

Leg-B endpoint map (chosen by live sweep, §2):

| Agent | Leg B (`GET`) | Why this endpoint |
|---|---|---|
| friday | `/friday/api/health` | second health read, 200 capability report |
| inference | `/inference/status` | 200 operational status object |
| memora | `/memora/` | root JSON status object (`status ok`, oracle storage) |
| stratex | `/stratex/api/status` | 200 live trading status (alerts, cash, available_risk — read-only; demo venue, no trade) |
| futuris | `/futuris/status` | 200 healthy status object |
| intelx | `/intelx/healthz` | 200 liveness object; intelx root 404s, all other candidates 404 |
| forge | `/forge/status` | 200 status object (see contradiction note, §5) |
| sentinel | `/sentinel/status` | 200 operational status object |
| cortex | `/cortex/status` | 200 operational status object |
| vyralx | `/vyralx/` | VyralX Control Room page (HTML); its only other public read — every other candidate 404s |

## §2 — Probe method (how the route was established)

All reads are unauthenticated GETs against the public ingress — no key, no
mutation, no LLM call, no trade:

1. **Keyed route ruled out from this VM.** `GET
   https://friday-universe.duckdns.org/inference/v1/health` → **401**
   `UNAUTHORIZED: missing API key` (correlation `9ec69246…`), although the
   REL-104 docstring says `GET /v1/health` needs no key — true on the VCN
   URL, not through the public ingress. The mesh-ping and task-execute legs
   likewise require the Inference key. This worker holds no key and did not
   request one; the keyed live run stays owed to a host that holds it.
2. **Endpoint sweep.** For each agent, probed `/health` plus candidates
   `(root)`, `/status`, `/capabilities`, `/v1/health`, `/api/health`,
   `/api/status` — 60 reads — then extra intelx candidates (`healthz`,
   `docs`, `openapi.json`, …). Results fixed the §1 map: e.g. vyralx and
   memora have no second endpoint except root; intelx root 404s but
   `/healthz` is 200; forge/sentinel `/capabilities`, `/v1/health`,
   `/api/health` are 401 (key-gated) while `/status` is open.
3. **Live run.** `python3 scripts/live_probe.py --public --timeout 30`
   from this VM, full 10-agent run + a 3-agent recheck of the degraded
   three + a full-body re-fetch of their three health payloads (§3–§4).
   Full JSON: `~/workspace/muse4-runs/rel119/live_run_public.json`
   (run 1) and `live_run_recheck.json` (recheck); local probe scripts in
   the same directory.

## §3 — Live results (run 1, 2026-11-27T19:23:00Z–19:24:01Z, exit 1)

Gateway gate `GET /health`: **200 healthy** (latency 17.5 s on the cold
first hit; later calls ~1 s). **Passed 7, failed 3, ok False.**

| Agent | Leg A `GET /{agent}/health` | Leg B (one real GET) | Pass |
|---|---|---|---|
| friday | 200 `ok`, 8.4 s | `GET /friday/api/health` 200 `ok`, 2.3 s | YES |
| inference | 200 `healthy`, 1.4 s | `GET /inference/status` 200 `operational`, 1.2 s | YES |
| memora | 200 `ok`, 0.8 s | `GET /memora/` 200 `ok`, 0.8 s | YES |
| stratex | **503** `degraded`, 6.6 s | `GET /stratex/api/status` 200 `ok`, 1.4 s | **NO** |
| futuris | **503** `degraded`, 2.9 s | `GET /futuris/status` 200 `healthy`, 2.7 s | **NO** |
| intelx | **503** `degraded`, 4.8 s | `GET /intelx/healthz` 200 `ok`, 1.3 s | **NO** |
| forge | 200 `ok`, 1.0 s | `GET /forge/status` 200 **`unhealthy`**, 1.0 s | YES* |
| sentinel | 200 `ok`, 1.0 s | `GET /sentinel/status` 200 `operational`, 0.8 s | YES |
| cortex | 200 `healthy`, 0.9 s | `GET /cortex/status` 200 `operational`, 1.0 s | YES |
| vyralx | 200 `ok`, 1.4 s | `GET /vyralx/` 200 HTML (Control Room), 1.8 s | YES |

\* Forge passes the script's rules (both legs 200) but its leg-B body
self-reports `unhealthy` — see §5. The script records `body_status` so
this is visible in the JSON instead of being upgraded to a clean pass.

## §4 — The three degraded agents (persistent, not a blip)

Recheck (3-agent run, 19:24:17Z–19:24:39Z, exit 1): stratex, futuris,
intelx all **503 again, leg B 200 again**. Full-body re-fetch (~19:25Z):
all three **503 again**. The degraded reason is identical on every read:

- **stratex — 503 `degraded`.** `market_data: unknown`
  (`MARKET_DATA_NOT_REPORTED` — "heartbeat omits market-data flags"),
  while `trading_capable: ok` ("engine healthy, executable strategies
  loaded, evaluation fresh") and `trading_engine: ok` ("multi-venue daemon
  heartbeat fresh, pid alive"); database `ok`. Warning:
  `DEMO_ENVIRONMENT: execution venue is Binance Futures demo; Pepperstone
  pending-approval`. Its real request (`/api/status`) is live trading
  status — read-only; no trade was placed.
- **futuris — 503 `degraded`.** `storage: ok` ("live schema inspection:
  13/13 required tables present"), `forecasting: unknown` (`NO_MODEL_PROBE`
  — "no forecasting-model probe exists; storage readiness is not
  forecasting ability"); database `ok`. Its `/status` leg B reads
  `healthy` — the `/health` capability report is stricter than `/status`.
- **intelx — 503 `degraded`.** `research: unknown` (`NO_LIVE_PROBE` —
  "no live research probe exists; research ability is not verified by this
  endpoint"), `model_provider: unknown` (`CONFIG_ONLY` — "provider config
  present; no live probe"); database `ok`, storage `ok`. Same pattern:
  the endpoint degrades on an unverified capability, not on a down
  dependency.

These are capability-report degradations (an `unknown` capability flips
the endpoint to 503), not dead processes — every one of the three answers
its real-request leg with 200. Whether a 503-for-`unknown`-capability is
the right health semantics is a follow-up question for the coordinator,
not something this task changes.

## §5 — Observations filed, not fixed

- **Forge contradicts itself.** `/forge/health` 200 `ok`
  (`database_connected: true`, uptime 8061 s) but `/forge/status` 200
  `unhealthy` (`database: {connected: false}`). One of the two endpoints
  is wrong about the database. Recorded here; not investigated further —
  out of scope for this task, needs a Forge-owner look.
- **Gateway first-hit latency 17.5 s** on `GET /health` (cold ingress);
  all later calls 0.8–8.4 s. No timeout was hit at the 30 s probe timeout.
- **Keyed-mode live run still owed.** The REL-104 mesh-ping + LLM-execute
  legs were not run live here (no key on this VM). Public mode covers the
  board's "gateway health endpoint + one real request per agent" through
  the public route the coordinator named; the keyed run needs a host that
  holds `INFERENCE_API_KEY`.

## §6 — Local tests

- `python3 -m py_compile scripts/live_probe.py tests/test_live_probe.py` — clean.
- `python3 scripts/live_probe.py --help` — `--public` listed, usage verified.
- `pytest tests/test_live_probe.py` — **13 passed in 6.85 s** (pytest 9.2.0,
  `~/workspace/muse4/vyr035-venv`; system python3 has no pytest). 8 keyed
  REL-104 tests pass unmodified; 5 new public-mode hermetic tests run the
  real CLI against an in-process stub public gateway (no live host touched):
  all-10 pass with no key set (10 health + 10 real calls), one 503 degraded
  → exit 1 with that agent failed, one real-request 404 → exit 1,
  `--health-only` → no real calls, gateway 503 → exit 2 with no per-agent
  probes.
- Full root suite not run locally (same limitation REL-103/REL-104
  recorded); the work PR's own CI run is the full-suite verification.

## Files changed

- `scripts/live_probe.py` — `--public` mode added (REL-119); keyed mode untouched.
- `tests/test_live_probe.py` — 5 public-mode hermetic tests added.
- `docs/collaboration/TASK-REL-119-EVIDENCE.md` — this doc.
- No board hunk (board flips are coordinator-only). No workflow, fleet-config,
  or shared-contract edits. No server change, restart, or deploy.

## States

- **implemented:** YES — `--public` mode built; live public run complete with per-agent evidence.
- **tested:** YES — 13/13 hermetic tests pass locally on the PR tree; live run executed against the real public gateway (7 pass / 3 degraded, exit 1 as designed).
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — on-demand script, no service; nothing to deploy.
- **production-verified:** PARTIAL — the public probe is verified live (gateway + all 10 agents hit, real output filed); 3 agents report degraded health and the keyed-mode live run is still owed. Paired verification (owner order rule 3) is owed — no verifier was named for this task; Muse to name one.

— Muse 4
