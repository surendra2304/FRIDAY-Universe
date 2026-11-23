# TASK-OBS-016 — S2 IntelX + Futuris DEGRADED: root cause filed (2026-11-23)

**Task:** TASK-OBS-016 (P1, owner muse_4) — diagnose the IntelX + Futuris DEGRADED
states on S2 from the ORCH-014 G1 re-probe, fix or file the root cause for each.

**Claim:** branch `muse4/task-obs-016-s2-degraded-diagnosis` from main `f0bb67cb`;
claim PR #1486; hub claim on #1483, comment 7097043322.

**Origin:** ORCH-014 G1 evidence (Muse 13, #35 comment 7091440321, 09:36 IST):
`/api/agents/status` re-probed twice (09:42:46, 09:44:11 IST), 0 UNREACHABLE, but
IntelX + Futuris DEGRADED — pre-existing, outside G1 scope.

## Verdict up front

Both DEGRADED states are the **same by-design honest outcome, not a fault**: each
service's `/health` is a REL-004 §2.2 capability report that returns HTTP 503 while
any *required* capability is not `ok` — and in both services the one non-ok entry is
a capability that **has no live probe by design**. No code fix in either health
endpoint is correct: REL-004 §2.4 forbids reclassifying a required capability as
optional to get a green status, and both services' contract tests assert 503 in
exactly this state. Each state clears only when its probe is built — and both
probes already have owned, claimed lanes (INT-020, FUT-019). No live step was taken
on either service; this is a diagnose-and-file outcome.

Per the coordinator's F1 call (#1483 comment 7096978376): healthy for validation =
returns 200, OR returns the same non-200 it returned at baseline (honest
degradation, no regression). These 503s are the baseline — the OBS-019 CD gate
already treats them as non-failing (proof run 45138070415, S2 job success while
both 503s persisted).

## Live evidence this run (2026-11-23 ~15:20–15:25 IST)

### IntelX — S2 `127.0.0.1:8005/health` (direct loopback via bridge `run_shell`)

HTTP 503 in 0.11 s. Body (abridged, `observed_at` 2026-11-23T09:50:52Z):

- `status: degraded`, `service: intelx`, `version: 2.0.0`, `mock_mode: false`,
  `database: connected`
- `capabilities.research`: `unknown`, detail `NO_LIVE_PROBE` —
  "no live research probe exists; research ability is not verified by this endpoint"
- `capabilities.model_provider`: `unknown`, detail `CONFIG_ONLY` —
  "provider config present; no live probe"
- `dependencies.database`: `ok` — live `check_database_health()` round-trip
  (SELECT 1 / SELECT 1 FROM DUAL)
- `dependencies.storage`: `ok` — writable data-dir probe (tempfile write, as /readyz)

Process is up, serving, database connected, storage writable, provider configured.
The only non-ok entries are the two unprobed capabilities.

### Futuris — public ingress `https://friday-universe.duckdns.org/futuris/health` (Caddy → S2 `10.0.0.120:8004`)

HTTP 503. Body (abridged, `observed_at` 2026-11-23T09:54:51Z):

- `status: degraded`, `service: futuris`, `agent: futuris`, `version: 2.0.0`
- `capabilities.storage`: `ok` — "live schema inspection: 13/13 required tables present"
- `capabilities.forecasting`: `unknown`, detail `NO_MODEL_PROBE` —
  "no forecasting-model probe exists; storage readiness is not forecasting ability"
- `dependencies.database`: `ok` — live round-trip + all required tables present
- `storage`: `ready: true`, `expected: 13`, `present: 13`, `missing: []`, `error: null`

Process is up, serving, schema complete, database connected. The only non-ok entry
is the unprobed forecasting capability.

### FRIDAY `/api/agents/status` re-probe — S1 loopback `127.0.0.1:10000` (2026-11-23 15:29:44 IST)

Single live probe via bridge `run_shell` (returned in 2.3 s):

- overall `status: degraded`, `scope: health_capability_report`, `agent_count: 9`
- counts: `ONLINE: 1, REACHABLE: 6, DEGRADED: 2, UNREACHABLE: 0, OFFLINE: 0`
- `intelx`: `DEGRADED`, 94 ms, endpoint `http://10.0.0.120:8005` —
  "IntelX DEGRADED: research unknown (NO_LIVE_PROBE); model_provider unknown (CONFIG_ONLY)"
- `futuris`: `DEGRADED`, 36 ms, endpoint `http://10.0.0.120:8004` —
  "Futuris DEGRADED: forecasting unknown (NO_MODEL_PROBE)"
- All others `REACHABLE` (Inference :8001, Stratex :18003, Cortex :8009, Forge
  :8006, Sentinel :8008, VyralX :8010) or `ONLINE` (Memora :8002).

FRIDAY's own details name the exact root causes found in the `/health` bodies
above. Same picture as the G1 re-probe (09:42/09:44 IST): 0 UNREACHABLE, the same
two DEGRADED — unchanged in ~6 hours, pre-existing.

## Root cause — code (main `f0bb67cb`)

### IntelX: `IntelX/intelx/api/v1/health.py` (TASK-REL-067, REL-004 §2.2)

`health()` builds the capability report and returns HTTP 200 iff `status == "ok"`,
else 503. `_capability_report()` derives `ok` iff every required entry is `ok`.
`research` is required and, in live mode, is unconditionally
`unknown / NO_LIVE_PROBE`; `model_provider` is `unknown / CONFIG_ONLY`. The
docstring states it plainly: "/health is degraded / 503 even with the database
and storage ready, because research is required and has no live probe
(unknown / NO_LIVE_PROBE …). That is the contract's outcome (§2.4 forbids
reclassifying a required capability as optional to get a green status); it clears
only when a research probe is built."

Contract test `IntelX/tests/test_intelx_health_contract.py` asserts 503 with
`research` unknown / `NO_LIVE_PROBE` when the database and storage are healthy.

S2 parity: `search_code` on S2 (`/opt/friday_universe`, branch
`muse10/task-mem-023-three-section-proof-run2` @ `c9223600`) finds `NO_LIVE_PROBE`
in `IntelX/intelx/api/v1/health.py` at lines 100, 129, 234 — the same contract as
main. The live 503 body above is the S2 runtime proving it.

Note: FRIDAY's `ask_intelx` reads `/healthz` (process liveness, always `ok` when
the process serves), not `/health` — so FRIDAY's IntelX display is unaffected.

### Futuris: `Futuris/futuris/api/app.py` — `_health_payload()` / `health_check()` (TASK-REL-067)

Same pattern: `forecasting` is required (§3) and "has no model probe anywhere in
the surveyed code, so it reports `unknown` with detail `NO_MODEL_PROBE` until one
is built; storage readiness is not forecasting ability and must never be
presented as such. `forecasting` is required (§3), so the top-level status is
`degraded` (HTTP 503) until a forecasting probe exists — that is the contract's
honest outcome, not a bug."

Contract test `Futuris/tests/test_futuris_health_contract.py` asserts 503 with
storage `ok` and forecasting `unknown / NO_MODEL_PROBE` when storage is ready.

## Fix lanes (already owned and claimed — not this task)

- **IntelX research probe → TASK-INT-020** (Muse 7, CLAIMED,
  `muse7/task-int-020-intelx-research-runs`): prove research-with-sources through
  FRIDAY chat, 3 consecutive live runs. Its known blocker is
  `synthesis_entailment_unverified` (`IntelX/intelx/api/grounded_live_research.py:423`;
  G1 evidence calls it the INF-026/INT-020-lane blocker). When INT-020 lands, the
  IntelX `/health` research entry can report a live verdict and the 503 clears.
- **Futuris forecasting probe → TASK-FUT-019** (Muse 12, CLAIMED):
  forecast-everything proof. A forecasting-model probe is the OBS-016 follow-up
  that proof enables; until one exists, Futuris `/health` stays honestly 503.

No fix is filed here because there is nothing to fix in the health endpoints —
the 503s are the contract working as designed. Filing a "fix" that reclassified
either capability would violate REL-004 §2.4 and falsify the fleet's health
signal.

## Side findings (noted, not in scope)

- **S1 units masked:** `oracle_check_service` on Server 1: `IntelX.service`
  masked, failed (timeout, Main PID killed, since Fri 2026-11-20 23:56:31 IST);
  `Futuris.service` masked, inactive (dead). The services live on S2, so S1's
  masked units are consistent with the fleet layout — noted, no action taken.
  `oracle_get_logs` on S1 returns "No entries" for both (journal rotated).
- **Fleet not uniform:** S2 git is on `muse10/task-mem-023-three-section-proof-run2`
  @ `c9223600`, not main — the OBS-013 live leg's both-on-main precondition is
  still unmet. The S2 IntelX health code matches main's contract (verified above).
- **Bridge tooling caveat:** several bridge calls wedged this run (direct `run_shell`
  probes combining curl + `ss` + `ps`, `oracle_get_logs` for intelx, one
  `oracle_check_service` retry) — each hung >5 min with no output and had to be
  killed locally. Single-target calls returned in ~2 s. Live evidence above was
  obtained through the fast paths (direct `:8005` curl, public-ingress
  `/futuris/health`). The wedged calls were read-only; nothing was half-applied.

## States

- implemented: YES — diagnosis + this evidence doc
- tested: YES — both `/health` endpoints probed live this run; code read on main
  and (IntelX) on S2
- merged: NO — work PR follows (claim PR #1486 open, CI 9/9 green)
- deployed: NO — no code change; none is correct for this task
- production-verified: PARTIAL — both services re-probed live with root cause
  filed, and FRIDAY's `/api/agents/status` re-confirms the same two DEGRADED
  with 0 UNREACHABLE; the 503s clear only when INT-020 / FUT-019 land their probes

— Muse 4, 2026-11-23 ~15:25 IST
