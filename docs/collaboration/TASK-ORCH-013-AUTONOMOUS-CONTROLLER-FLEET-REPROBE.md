# TASK-ORCH-013 — Autonomous-Controller + Fleet-Supervision Re-probe

**Date:** 2026-11-23 · **Worker:** Muse 13 · **Claim base:** main `1d6b43a7` ·
**Branch:** `muse13/task-orch-013-autonomous-controller-reprobe` ·
**Follow-up branch:** `muse13/task-orch-013-live-reprobe` from main
`d6a92978` (checkpoint-1 PR #1443 merged 07:54:21 IST, merge `d6a92978`)

**Assignment:** coordinator follow-up 7089274897 (2026-11-23 ~07:08 IST, on issue #35):
re-probe the autonomous-controller + fleet-supervision state live across all
agents; fix any code-default vs live-env drift found; file per-agent state
evidence. Renumbered from ORCH-012* — that id collides with the existing
MERGED TASK-ORCH-012 (Muse 4, PR #1334). Queue after claim: ORCH-013 →
CTX-005* → OBS-011* (OBS-011* assigned as position 3 in coordinator watch
7089537118 — voice worker /health route, fits the supervision lane).

**Board record:** rides in the coordinator's consolidated board PR per
7089274897 — deliberately NOT filed in this PR, so no duplicate
TASK-ORCH-013 record exists when the coordinator files it.

## 1. Precedent — what this re-probe re-checks

TASK-ORCH-011 (Muse 9, 2026-11-22, `docs/collaboration/TASK-ORCH-011-SUPERVISION-REPROBE.md`)
is the same scope, read-only. Its verdicts are the baseline; ORCH-013
re-verifies each one live and closes or carries each gap:

- **Supervision loop alive and honest** (2026-11-22 11:52 IST): `status:
  degraded`, snapshot 29 s old, `last_error: null`, 5-min interval,
  `agent_count: 9`. "Degraded" = not all peers ONLINE, not a loop failure.
- **Code default autonomy OFF, live process ON.** `config.py:213`
  `autonomous_mode` default `False`, `full_access_mode` default `False`,
  toggle runtime-only (`controller.py:275-289`, `autonomous_mode_persistence:
  "runtime_only"`); but the live FRIDAY process reported
  `autonomous_mode: true`, `full_access_mode: true`,
  `sensitive_actions_auto_approved: true` (11:43 and 11:52 IST), armed by
  the standing `FRIDAY_AUTONOMOUS_MODE=true` env flag + the TASK-FRD-023
  boot-arm (`server.py:637-641`). Daemon heartbeating, idle (0 queued,
  0 running); 50-entry action-history ring full with old entries — no
  autonomous goal work executing.
- **Guard tests 8/8 pass** on Server 1 venv, 27.32 s (ORCH-003 contracts).
- **Gaps G1–G6** (file/line in ORCH-011 §6): G1 supervision probe targets
  encode the old layout (4 agents permanently UNREACHABLE in
  `/api/agents/status` while alive elsewhere — IntelX/Futuris on Server 2,
  Sentinel on Server 1, VyralX on AWS); G2 Memora event consumer fails at
  the cursor every observed cycle; G3 autonomy ON in production needs a
  coordinator decision (no worker toggle); G4 Stratex/Forge probe flapping
  (known REL-023 pattern); G5 VyralX AWS leg is a supervision blind spot;
  G6 two supervision surfaces disagree (agent-watch log 10/10 healthy vs
  `/api/agents/status` degraded).
- **Deployed code byte-identical to main** for the four supervision-relevant
  files (sha256, ORCH-011 §5).

Interim live state since ORCH-011 (from TASK-CTX-004 live proof, Muse 13,
2026-11-23 06:36 IST, comment 7089047929): S2 checkout main `491a63e9`;
Cortex restarted 05:25:17 IST (PID 599993); supervisor ~06:41 IST: 148
cycles, 0 errors, `last_unconfigured: []`, `ai_universe` HEALTHY 147/148;
`ratio_check` live in `GET /v1/friday/self_healing`, streak 0, signal
present.

## 2. Method

1. **Code defaults on main** (this branch base): re-read
   `FRIDAY/src/friday/core/config.py` (autonomy defaults, env prefix),
   `FRIDAY/src/friday/autonomous/controller.py` (toggle, `get_status()`),
   `FRIDAY/src/friday/api/server.py` (FRD-023 boot-arm, supervision
   endpoints, Memora consumer loop), `FRIDAY/src/friday/ecosystem/fleet_client.py`
   (probe targets, budgets). Record file:line for every default.
2. **Live re-probe, read-only, via the bridge** (Server 1 + Server 2):
   `GET /api/autonomous/status` (twice, separated in time),
   `GET /api/agents/supervision`, `GET /api/agents/status`,
   per-agent `/health` + `/ready` at the **running** copies (6/4 layout:
   IntelX/Futuris Server 2, Sentinel Server 1, VyralX AWS — not the masked
   sleeping copies), Cortex supervisor state on Server 2 (cycles, errors,
   `last_unconfigured`), Memora consumer `last_result`, daemon heartbeat
   lines in the FRIDAY journal.
3. **Guard tests re-run** on the Server 1 venv:
   `tests/test_fleet_supervision_loop_contracts.py` (targeted run only —
   the bridge `run_workspace_test` path arg runs the whole repo).
4. **Drift triage.** Code-default vs live-env drift found here is fixed
   in this PR where the fix is code (probe targets, defaults, docs).
   Anything that would change a running service's mode, flag, or
   supervision posture — above all the G3 autonomy-ON question — is
   reported to Muse for a decision, not toggled by this worker.
5. **Per-agent evidence** filed in §4 below with timestamps; any agent
   presenting as ok while degraded is flagged with the exact degraded
   capability (REL-004 contract).

## 3. First step (this commit)

Design + baseline doc only. Live probe follows in this run; evidence lands
in §4 and in the work PR as it is captured.

## 4. Live evidence — re-probe 2026-11-23 07:43–07:52 IST (Muse 13)

### 4.0 Verdict

**Supervision loop alive and honest; 7 of 9 agents ONLINE in
`/api/agents/status`. The 2 UNREACHABLE are a stale-`.env` probe-target
defect, not dead agents — both verified alive by direct probe. Autonomy is
ON in production and now consistent with the code default (FRD-035 flipped
the default to `True` on 2026-11-22). Memora consumer healthy — G2 closed.
Guard tests 8/8. Deployed code byte-identical to main (5 files, sha256).**
No service mode, flag, or supervision posture was changed in this task; all
probes were read-only GETs / status reads / one targeted test run.

Probe-path correction (my own error, recorded honestly): the first S1 batch
curled `/friday/health`, `/friday/api/...` against port 10000 directly and
got the Next.js 404 page. Caddy strips the `/friday` prefix before proxying
to 127.0.0.1:10000 (`handle_path /friday*` in `/etc/caddy/Caddyfile`), so
the FastAPI routes are `/health`, `/api/autonomous/status`,
`/api/agents/supervision`, `/api/agents/status` on the raw port. All
readings below use the corrected paths. The 404s were a probe-path error,
not a live defect.

### 4.1 FRIDAY process (Server 1)

- `FRIDAY.service`: active, running, MainPID **2606173**, started
  **04:49:52 IST**, NRestarts 0. Unclaimed restart (Muse 6 already flagged
  the 04:29–05:40 IST window on the hub; no actor recorded).
- `GET /health` 200, `overall: healthy`, `friday_core`, python 3.10.12.
- Daemon heartbeats every ~5 min, `Autonomous daemon alive: 0 queued,
  0 running` (latest 07:41:40 IST). History ring full at 50 entries; no
  autonomous goal work executing.
- Live `.env` flags (`/opt/friday_universe/FRIDAY/.env`):
  `FRIDAY_AUTONOMOUS_MODE=true`, `FRIDAY_FULL_ACCESS_MODE=true`.

### 4.2 Autonomous status (×2, identical)

`GET /api/autonomous/status` 07:44 IST and 07:50:07 IST, identical:
`{"autonomous_mode": true, "full_access_mode": true,
"sensitive_actions_auto_approved": true,
"autonomous_mode_persistence": "runtime_only", "active_agent": null,
"active_directive": null, "history_count": 50}`.

Code defaults on this branch base (re-read first-hand):

| Check | File:line | Result |
|---|---|---|
| `autonomous_mode` default **ON** | `FRIDAY/src/friday/core/config.py:213-216` | `Field(default=True, "Enable owner-requested actions without confirmation prompts; enabled by default (TASK-FRD-035: aligned to the live env, owner standing order — agents autonomous). The FRIDAY_AUTONOMOUS_MODE env flag opts out.")` — flipped by FRD-035, commit `105359e9`, 2026-11-22T09:45:26Z. ORCH-011's `default=False` was correct at its probe time (11:43 IST, before the 15:15 IST merge); the default changed after ORCH-011. |
| `full_access_mode` default OFF | `FRIDAY/src/friday/core/config.py:218-222` | `Field(default=False, ...)` — unchanged. Live `true` comes from the `.env` flag only. Residual drift of the same class, narrower. |
| Toggle runtime-only | `FRIDAY/src/friday/autonomous/controller.py:275-289` | `enabled` property reads/writes the shared runtime setting; `get_status()` reports `"autonomous_mode_persistence": "runtime_only"` (`:305`). |
| Env flag arms daemon at boot (FRD-023) | `FRIDAY/src/friday/api/server.py:633-641` | `if get_settings().autonomous_mode: await autonomous_daemon.start()`. Two further `autonomous_daemon.start()` call sites exist at `:2237` and `:2275` (not traced in this task). |
| Settings read the flag from env | `FRIDAY/src/friday/core/config.py:79` | `env_prefix="FRIDAY_"`. |
| Audit doc stale | `docs/autonomy/AUTONOMY_AUDIT_2026-11-10.md` §5 | Still states "mode is off by default" and "a process restart returns to the config default (OFF); locked by test". Both are false since FRD-035. Addendum filed in this PR (see §6 G3). |

### 4.3 Supervision loop

- `GET /api/agents/supervision` 07:45 IST and 07:50 IST: `status:
  degraded`, `checked_at` 02:11:38Z / 02:16:38Z, `snapshot_age_seconds`
  251 / 209 (interval 300 s — snapshot fresh), `last_error: null`,
  `agent_count: 9`. Loop alive; "degraded" is the two stale-target peers,
  not a loop failure.
- `GET /api/agents/status` 07:45 IST: overall `degraded` — **7 ONLINE /
  2 UNREACHABLE**:
  - inference ONLINE 167 ms (`127.0.0.1:8001`); memora ONLINE 81 ms
    (`127.0.0.1:8002`); intelx ONLINE 77 ms (`10.0.0.120:8005`); futuris
    ONLINE 80 ms (`10.0.0.120:8004`); cortex ONLINE 78 ms
    (`10.0.0.120:8009`); forge ONLINE 170 ms (`127.0.0.1:8006`);
    sentinel ONLINE 105 ms (`10.0.0.121:8008`).
  - stratex UNREACHABLE — live probe target `http://127.0.0.1:8003`,
    `ConnectError: All connection attempts failed`.
  - vyralx UNREACHABLE — live probe target `http://10.0.0.120:8010`,
    `ConnectError: All connection attempts failed`.

### 4.4 Why the 2 UNREACHABLE are a stale-`.env` defect (G1, narrowed)

- Live `.env` URL overrides (S1, read-only grep):
  `INFERENCE_URL=http://127.0.0.1:8001`,
  `MEMORA_URL=http://127.0.0.1:8002`,
  **`STRATEX_URL=http://127.0.0.1:8003`**,
  `INTELX_URL=http://10.0.0.120:8005`,
  `FUTURIS_URL=http://10.0.0.120:8004`,
  `CORTEX_URL=http://10.0.0.120:8009`,
  `FORGE_URL=http://127.0.0.1:8006`,
  `SENTINEL_URL=http://10.0.0.121:8008`,
  **`VYRALX_URL=http://10.0.0.120:8010`**.
- The VAL-006 canonical map (`fleet_client.py:126-134`) is correct in
  code: stratex → `http://127.0.0.1:18003` (S1 SSH tunnel to AWS),
  vyralx → `http://16.176.9.247:8010` (AWS), sentinel →
  `http://127.0.0.1:8008`. But `configured_url()`
  (`fleet_client.py:248-259`) reads the `.env` value **first**; the map
  only applies when no env value is set. The VAL-006 deploy step (sync the
  live `.env` STRATEX_URL / SENTINEL_URL / VYRALX_URL to the map) was
  never applied — the `.env` still carries the pre-VAL-006 values for
  Stratex (port 8003 is the dashboard, not the engine — nothing listens
  there for the probe) and VyralX (the masked S2 copy, dead since Nov 19).
  Sentinel's `.env` value differs harmlessly (10.0.0.121:8008 vs map
  127.0.0.1:8008 — same service, ONLINE).
- Both agents verified alive by direct probe: Stratex engine online and
  healthy via the `:18003` tunnel (daemon balance 10557.95, demo env);
  VyralX AWS `/health` 200 from S1 in 0.49 s (§4.5).
- **Fix (deploy step, NOT a code change — needs Muse clearance):** set
  `STRATEX_URL=http://127.0.0.1:18003` and
  `VYRALX_URL=http://16.176.9.247:8010` in the S1 FRIDAY `.env`, then
  restart FRIDAY. No code change in this PR — the map is already correct.

### 4.5 Per-agent `/health` + `/ready` at the running copies

| Agent | Running copy | `/health` | `/ready` |
|---|---|---|---|
| Inference | S1 10.0.0.121:8001 | 200 healthy, providers groq/cerebras/openrouter | 200 ready, DB connected (oracle) |
| Memora | S1 10.0.0.121:8002 | 200 healthy, storage oracle, DB healthy | not probed (no `/ready` route asserted) |
| Stratex | S1 tunnel 127.0.0.1:18003 | 200 engine online, engine_healthy true, dashboard online, daemon_balance 10557.95, DEMO_ENVIRONMENT | not probed |
| IntelX | S2 10.0.0.120:8005 | 200 ok, mock_mode false | **404** — no `/ready` route on IntelX |
| Futuris | S2 10.0.0.120:8004 | 200 ok, storage 13/13 present | 200 ready, DB connected (oracle) |
| Cortex | S2 10.0.0.120:8009 | 200 healthy | 200 READY; required deps database/schema/redis UP; degraded: ai_universe, sentinel, intelx, futuris — each `UNKNOWN: no live readiness probe configured` (a probe-config gap in the `/ready` endpoint itself, distinct from the supervisor's live probes, which are HEALTHY — §4.6) |
| Forge | S1 10.0.0.121:8006 | 200 ok, uptime 11885.6 s, database_connected true | not probed |
| Sentinel | S1 10.0.0.121:8008 | 200 ok, kill_switch_active false | 200 READY, crypto_keys/database_wal/audit_integrity/event_bus checks pass |
| VyralX | AWS 16.176.9.247:8010 | **200 ok from S1** (`{"status":"ok","service":"vyralx","version":"0.2.0"}`, 0.49 s); **000 from S2** (twice, 8–12 s timeouts — S2 egress to that AWS IP fails) | not probed |
| VyralX (masked S2 copy) | S2 10.0.0.120:8010 | 000 from S1 — dead, as expected (stopped Nov 19) | — |

### 4.6 Cortex supervisor (Server 2, authenticated)

`GET /v1/friday/self_healing` with the `X-Friday-Api-Key` header (key
taken server-side from `Cortex/.env`, value never read or copied;
unauthenticated GET returns 401 — the endpoint is correctly auth-gated).
Observed ~07:47–07:48 IST:

- background: running, **cycles 280, errors 0**, `last_unhealthy: []`,
  `last_unconfigured: []`, `self_healing_enabled: true`.
- All subsystems CLOSED, 0 consecutive failures. ai_universe: 279
  successes / 1 failure, 20 samples. database/schema/redis/agents: 280/0.
  ingestion/tools: 0 samples ("no probe").
- `last_probes`: database, schema, redis, ai_universe, agents all
  HEALTHY (checked 02:17:38–39Z); ingestion/tools "no probe".
- `degraded: []`; `escalations: []`; escalation channel telegram
  configured, attempts 0, delivered 0.
- `ratio_check` live (thresholds 10/3, signal rates 1.0) — the CTX-004
  live proof continues to hold (cycles 148 at 06:41 IST → 280 now, no
  errors since the 05:25:17 IST restart).

### 4.7 Memora event consumer — G2 CLOSED

- `memora_event_consumer` in both supervision reads: `consumer_id:
  friday-cloud`, running true, `last_completed_at` 02:15:41Z and
  02:19:42Z, `last_result: {"status": "ok", "persisted": 0,
  "acknowledged": 0, "next_after_id": 1896, "has_more": false}` — the
  cursor is caught up, no new events, no error.
- 0 `Memora cursor read failed` / `Memora event consumption did not
  complete` lines in the 2-hour FRIDAY journal (ORCH-011 saw the failure
  repeating every few minutes). Two consecutive ok results + a clean
  2-hour journal close G2.

### 4.8 Guard tests re-run (Server 1 venv)

- Command (Server 1, `/opt/friday_universe/FRIDAY`):
  `/opt/friday_universe/venv/bin/python -m pytest
  tests/test_fleet_supervision_loop_contracts.py -q -p no:cacheprovider`
- Result: **8 passed in 9.12 s** (ORCH-011: 8/8 in 27.32 s). The 8 are
  the ORCH-003 contracts. Note: `test_enabling_autonomy_does_not_survive_a_settings_rebuild`
  now pins the *toggle*, not the default — its comment records "The code
  default is ON since TASK-FRD-035; this test pins the toggle, not the
  default" (suite env sets the flag false, so a rebuild reads False).

### 4.9 Deployed code vs main (sha256)

S1 checkout main `c1fac16b` (S2 checkout also main `c1fac16b`). All five
files byte-identical to the main blob:

| File | sha256 (S1 checkout == main) |
|---|---|
| `FRIDAY/src/friday/api/server.py` | `53174d62df2cc219d829ed9773a4ada552af3c24591bdf3bde9d95926c993fcd` |
| `FRIDAY/src/friday/autonomous/controller.py` | `0907d381b432dac27bcb8fb9dc18324afd540f224d2bc5fd905b415b8c304da9` (unchanged since ORCH-011) |
| `FRIDAY/src/friday/core/config.py` | `b4b1ee6b54707ed2dcc6ca388a8f222f717073efe813fd58538ddc32758d8aac` |
| `FRIDAY/src/friday/ecosystem/fleet_client.py` | `f08f3a987641148c66211c2dc4ee0f1dbcf9858ae3b4ac8c3774c8ac9a1b7ba4` |
| `FRIDAY/tests/test_fleet_supervision_loop_contracts.py` | `b60a8a418919084f1c207416e4ce792e3f36cccff4e3816cf62437051c46138a` |

### 4.10 Unclaimed restarts observed today

- **FRIDAY.service 04:49:52 IST**, PID 2606173 (Muse 6 flagged the
  04:29–05:40 window; no actor on the hub).
- **IntelX.service 07:37:19 IST**, PID 601626 — clean stop/start
  (journal `Stopped … Started`, NRestarts 0, watches re-armed, `/health`
  200 after). Found during this re-probe; **not caused by this worker**
  (all probes read-only; the restart predates the first IntelX probe).
  No hub post records the actor. Flagged to Muse in the status post.
- Futuris 04:22:25 IST (PID 599030), Cortex 05:25:17 IST (PID 599993 —
  the CTX-004 live-proof restart, known).

### 4.11 S2 unit-name note

Lowercase `systemctl` names (`intelx`/`futuris`/`cortex`) are not-found;
the units are `IntelX.service` / `Futuris.service` / `Cortex.service`
(capitalized) — all active/running. No defect; probe scripts must use the
capitalized names. (An early probe in this run reported the lowercase
names inactive — that was a naming error, corrected here.)

## 5. Acceptance

- [x] Autonomous-controller + fleet-supervision state re-probed live
      across all agents, with a recorded verdict — §4 above.
- [x] Code defaults verified against live env; every drift found is
      either fixed in this PR (code/docs) or filed as a gap with file/line
      and a coordinator decision requested — §6.
- [x] ORCH-011 gaps G1–G6 each re-checked: closed with evidence, or
      carried with fresh evidence — §6.
- [x] Per-agent state evidence filed with timestamps — §4.5.
- [x] No service mode, flag, or supervision posture changed without
      coordinator direction; all probes read-only unless a code fix lands
      in this PR. (One doc fix lands in this PR: the audit-doc addendum,
      §6 G3. The G1 .env fix is a deploy step awaiting Muse clearance.)

## 6. Gaps G1–G6 — re-check verdicts

- **G1 — NARROWED, carried.** The map is fixed (VAL-006) and deployed
  code == main, but the live `.env` overrides for Stratex and VyralX are
  still pre-VAL-006, so `/api/agents/status` reports both UNREACHABLE
  while both are alive (§4.4). IntelX / Futuris / Sentinel legs are
  CLOSED (all ONLINE via correct targets). Fix: set
  `STRATEX_URL=http://127.0.0.1:18003` and
  `VYRALX_URL=http://16.176.9.247:8010` in the S1 FRIDAY `.env` + restart
  FRIDAY — **deploy step, Muse clearance requested in the status post**;
  not done unilaterally (live env change + service restart).
- **G2 — CLOSED.** Memora consumer `last_result: ok` twice, cursor
  caught up, 0 journal failures in 2 h (§4.7).
- **G3 — CHANGED.** The autonomous_mode code-vs-live drift is closed by
  FRD-035 (default `True`, owner standing order cited, commit `105359e9`,
  merged 2026-11-22) — the coordinator decision ORCH-011 asked for on the
  mode itself is answered by that merge, not by this worker. Residual:
  `full_access_mode` default still `False` vs live `True` (env flag), and
  the 2026-11-10 audit doc still claims OFF-by-default. **Doc fix in this
  PR:** dated addendum appended to
  `docs/autonomy/AUTONOMY_AUDIT_2026-11-10.md` (original audit text
  untouched). **Still owed from Muse:** confirm `full_access_mode` ON is
  intended, and whether the audit's posture is superseded.
- **G4 — NOT REPRODUCED this run, carried under REL-023.** Single sweep:
  Forge ONLINE (170 ms), Stratex down is the G1 stale-target cause, not
  flapping. Multi-sweep flapping assessment still owed.
- **G5 — NARROWED.** VyralX AWS leg verified alive from S1 (200, 0.49 s)
  — the blind spot is closable by the same `.env` fix as G1. Note: S2
  cannot reach the AWS endpoint (000 twice); S2-side VyralX probing
  would still fail — whoever probes from S2 should use the S1 route or
  record the egress gap.
- **G6 — CHANGED FORM, carried as documented.** The agent-watch journal
  no longer emits per-agent healthy counts: the hourly pass now reports
  alerts evaluation only (`evaluated: 0, fired: 0, deliveries: 0` at
  06:00 and 07:00 IST). No disagreement is observable in that form;
  `/api/agents/status` is the authoritative surface, and its `degraded`
  verdict is fully explained by the two stale probe targets (§4.4).

— Muse 13
