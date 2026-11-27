# TASK-REL-104 — CHECKPOINT 2 (implementation: scripts/live_probe.py)

- Task: `scripts/live_probe.py` — one command per agent: gateway health + one real request, output filed as evidence.
- Filed: 2026-11-27 ~14:30 IST, Muse 6. Branch `muse6/task-rel-104-live-probe`, base `06ff9ee6` (checkpoint 1 @ `b9602155` remote / `fe3a6ae8` local — same tree).
- Five states: implemented YES / tested YES (hermetic, stub gateway — see §4) / merged NO / deployed NO / production-verified NO (live run owed, §5).
- Files in this commit: `scripts/live_probe.py` (new), `tests/test_live_probe.py` (new), this doc.

## 1. What was built

`scripts/live_probe.py` (stdlib-only, `urllib`, no new dependencies): an
on-demand CLI, one command per agent, no daemon/timer/service.

- **Leg A — health, genuinely per-agent:** `POST /v1/mesh/ping/{agent_id}`
  for the 9 mesh peers (gateway pings that peer's `/health`, 2.0 s deadline,
  returns `reachable` / `status_code` / `latency_ms`); Inference itself via
  `GET /v1/health` (it is the gateway, not a peer).
- **Leg B — one real request per agent:** `POST /v1/task/execute` with a
  small read-only envelope per `target_agent` (`source_agent: live_probe`,
  `action: reason`, prompt "Reply with the single word OK.", priority low).
  The receipt is the content proof: result status, model/provider, latency,
  the gateway's `verification_evidence`, and a 120-char content receipt —
  not a bare 200.
- **Output:** one JSON evidence record (gateway health + one record per
  agent + passed/failed counts + the §2 caveat), printed to stdout and
  optionally written with `--output`. Exit 0 all pass, 1 any agent fails a
  leg, 2 gateway unreachable/misconfigured. `--agents` subsets,
  `--health-only` runs leg A only, `--gateway` overrides the base URL
  (default VCN `http://10.0.0.121:8001`; public ingress
  `https://friday-universe.duckdns.org/inference`).
- **Auth:** `X-Inference-API-Key` from the environment (default
  `INFERENCE_API_KEY`) — never a CLI argument, never printed. `GET
  /v1/health` needs no key; without a key the ping/execute legs fail or
  skip with an explicit reason, they never silently pass.

## 2. Code-read finding — checkpoint-1 open question §4.1 ANSWERED

**Forwarding vs in-gateway reasoning: IN-GATEWAY.** Verified first-hand on
live main `25612602` (`Inference/app/api/universal_task_routes.py`,
`execute_task`, lines 221–410): the handler never forwards to the peer.
It detects specialist requirements from `source_agent` / `action`
(Forge code, VyralX script, IntelX claims — otherwise general reasoning),
runs one LLM call in Inference (`UnifiedExecutionRequest`, `fast_lane`,
`max_tokens=2048`), and the receipt **always names `target:
"inference"`** (lines 356–374). `target_agent` in the envelope is a label,
not a dispatch target.

Consequence, stated in the script docstring and the output `caveat`: leg B
proves the gateway's real-request path per `target_agent` label; **leg A
(mesh ping) is the proof the path actually reaches each peer**. Do not read
a leg-B SUCCESS as peer execution. True per-agent execution would need
direct per-agent endpoints (each agent's own API) — follow-up, not this
task: the board acceptance is gateway health + one real request per agent,
and that is what the script does.

Other code facts verified first-hand on main `25612602` (not assumed):

- `POST /v1/mesh/ping/{agent_id}` (`mesh_routes.py:360-440`): requires the
  Inference key (`require_inference_api_key`); 404 for an unknown agent;
  returns `agent_id`, `target_url`, `reachable`, `status_code`,
  `latency_ms`, `authenticated_ping`.
- `require_inference_api_key` (`core/security.py`): accepts
  `X-Inference-API-Key` / `X-API-Key` / `X-Friday-API-Key` /
  `Authorization: Bearer`.
- `GET /v1/health` (`v1_core_routes.py:115`): no auth dependency; returns
  `status: healthy`, service, version, registered roles.
- `TaskEnvelope` (`universal_task_routes.py:32-42`): `task_id`,
  `source_agent` (default `friday`), `target_agent` (default `inference`),
  `action` (default `reason`), `payload`, `priority`. Prompt taken from
  `payload.prompt` (fallback question/query/task). Quota: per-source admit,
  estimated `max(100, len(payload)//4)` tokens per call — 10 tiny envelopes
  cost ~100 tokens each estimated.
- Cost guard: one-word prompt keeps the completion tiny; no LLM-heavy
  payloads; the script makes exactly 10 execute calls per full run.

## 3. Design deltas vs checkpoint 1 §3

- `source_agent` is `live_probe`, not the target agent: using the target as
  source would trigger the specialist prompts (Forge code-gen, VyralX
  script, IntelX claims) for a one-word probe — wrong work, wasted tokens,
  mislabelled source. `action: reason` + `source_agent: live_probe` takes
  the plain `system_architect` path.
- `GET /v1/health` is probed once up front as the gateway gate: if the
  gateway itself is down/unhealthy the run exits 2 with no per-agent
  probes (a dead gateway is not ten failed agents).
- Per-agent `pass` requires BOTH legs (or leg A alone under
  `--health-only`); a DEGRADED/ERROR execute fails that agent, recorded
  with the error — never upgraded to a pass.

## 4. Hermetic test evidence (this VM, no live host touched)

- `python3 -m py_compile scripts/live_probe.py tests/test_live_probe.py` — clean.
- `python3 scripts/live_probe.py --help` — arg parsing verified.
- `pytest tests/test_live_probe.py` — **8 passed in 4.21 s**
  (pytest 9.2.0, `~/workspace/voi026-venv`; system python3 has no pytest).
  The suite runs the real CLI against an in-process stub gateway that mimics
  the exact live response shapes (`/v1/health`, `/v1/mesh/ping/{id}`,
  `/v1/task/execute` with receipt): all-10 pass (exit 0, 10 execute calls,
  9 pings, receipt target `inference`, content receipt `OK`); one ping
  down → exit 1 with that agent failed; one execute ERROR → exit 1;
  `--health-only` → no execute calls; gateway 503 → exit 2, no per-agent
  probes; unknown agent → exit 2; no API key → execute SKIPPED, exit 1;
  `--agents friday,inference` subset → 1 ping (only friday is a peer).
- No live run in this checkpoint: no bridge route from this VM (standing
  position); the live leg is coordinator-side `run_shell` or per-sandbox
  registration (checkpoint 1 §4.2, still open).

## 5. Next

- Work PR with these 3 files (rule 1: checkpoint first, PR follows
  implementation); CI must go green; paired verifier assigned by the
  coordinator. Board flip rides the coordinator board PR (coordinator-only).
- Live run: once a route is settled, run the script from a host with VCN
  or public-ingress access and file the JSON output as evidence; if any
  peer is unreachable or any execute leg degrades, that is data — file it,
  do not re-run to hide it.
- This run also filed the paired VERIFIED verdict on PR #2100 (M1, VOI-030)
  as review 6085510230 (WATCH212 §4, due ~15:00 IST) — separate work,
  recorded on the hub status post, not in this checkpoint.
