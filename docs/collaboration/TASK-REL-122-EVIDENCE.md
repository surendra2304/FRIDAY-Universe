# TASK-REL-122 — scripts/live_probe.py: one command per agent (gateway health + one real request), output filed as evidence

- **Task:** Reliability: scripts/live_probe.py — one command per agent (gateway health + one real request), output filed as evidence. Sequel to REL-120; the keyed live run REL-119 left owed.
- **Owner:** Muse 2. **Claim:** hub #2045 comment 7235790173, 2026-11-28 ~12:43 IST.
- **Board verified:** AVAILABLE, owner null, P2, on live main `85415d37`.
- **Branch:** `muse2/task-rel-122-live-probe` from main `85415d37` (verified via API; branch head == main at claim).

## Verdict

**IMPLEMENTED + LIVE-RUN COMPLETE IN BOTH MODES, 7/10 agents pass keyed, 5/10 pass public — and the failures are the finding, not a probe failure.** The keyed run is the new evidence: leg A (mesh ping, genuinely per-agent) passes for 7 agents and fails for the same three degraded agents REL-119 found (stratex, futuris, intelx); leg B (one real request per agent) passes for all 10, each returning the content receipt `OK` from `openai/gpt-oss-20b` via groq, receipt target `inference` as the code-read caveat says. The public run re-confirms REL-119's picture (same three 503-degraded, forge's `/status` still self-reports `unhealthy`) plus two transient ingress transport drops that both answer 200 on direct re-read. The script exits 1 in both modes, as designed, when any agent fails a leg.

This PR also carries a real script fix the live run forced: the checked-in script could not run keyed mode at all against the current gateway — its gate and inference health leg sent no key for `GET /v1/health`, and the live gateway now 401s that endpoint without one. The fix sends the key on those two calls whenever one is set (§1).

## §1 — The fix (why the keyed run needed a code change first)

The REL-104 docstring said `GET /v1/health` needs no key. That no longer holds live. First keyed attempt (old script, run on Server 1, 12:55 IST):

- Gateway gate `GET /v1/health` → **401** `UNAUTHORIZED: missing API key`
  (correlation `98f95228-c1a6-4845-8390-84624791ea34`), exit 2, no per-agent
  probes run.
- Direct check from Server 1 in the same session: `GET /v1/health` with no
  key → 401 (0.50 s); with the key → **200 healthy** (0.70 s);
  `POST /v1/mesh/ping/friday` with the key → **200, reachable true, peer
  200** (1.54 s). Key valid, gateway healthy, mesh ping works — only the
  script's keyless gate was in the way.

Change in `scripts/live_probe.py` (no other behaviour touched):

- The gateway gate in `main()` (keyed mode) now passes `api_key` to
  `GET /v1/health` instead of `None`.
- Inference's leg A in `probe_agent()` now passes `api_key` to
  `GET /v1/health` instead of `None`.
- Sending the key is harmless when an endpoint does not need it (an extra
  header an open endpoint ignores), and when no key is set the script
  still sends none — the no-key path is unchanged.
- Docstring updated: the "needs no key" line now records the live 401/200
  finding (verified 2026-11-28).

Tests in `tests/test_live_probe.py` (2 new, 15/15 pass locally, §6):

- `StubGateway` gains a `require_key_for_health` knob: with it on,
  `/v1/health` 401s when the `X-Inference-API-Key` header is absent.
- `test_v1_health_with_key_passes_when_key_required` — key set, code 0,
  gate 200, 10/10 pass.
- `test_v1_health_without_key_exits_2_when_key_required` — no key, code 2,
  gate 401, no per-agent probes. This is the exact live failure, hermetic.

## §2 — Probe method

**Keyed mode — run on Server 1, key never left the server.** The key is not
in Server 2's `/opt/friday_universe/CREDENTIALS.md` (grep count for
`INFERENCE` there is 0); it lives in Server 1's
`/opt/friday_universe/Inference/.env` — the `EnvironmentFile` of the live
`Inference.service` — exactly one `INFERENCE_API_KEY` line (43 chars; the
value is not recorded anywhere). The fixed script was copied to Server 1
`/tmp/live_probe_rel122.py` (sha256 verified identical to the PR tree,
`52033f4f…`), run there with the key extracted server-side from that `.env`
file into the process environment only, and the JSON output fetched back
over the bridge. All Server 1 scratch (`/tmp/live_probe_rel122.py`,
probe JSON/log/exit files, curl temp files) was removed afterwards; no
repo file, service, or config on either server was changed. The Server 1
checkout's own `scripts/live_probe.py` is byte-identical to main
(sha256 `1c8cfd54…`), so the pre-fix script on the server was the same code
the PR fixes. Full run launched in the background (10 LLM calls exceed the
bridge's ~120 s call window); health-only run first, in the foreground, to
validate the fix.

**Public mode — run from this VM, no key.** `python3 scripts/live_probe.py
--public --timeout 30`, full 10-agent run + a targeted 2-agent recheck of
the two transport failures + direct curl confirmation.

**Bridge tooling note.** The old bridge client
(`muse2/task-rel-064/bridge_mcp.py`) fails on this VM now: its
`resp.read()`-to-EOF dies with `IncompleteRead` because the bridge holds
the SSE stream open (endpoint itself is up — initialize returns 200,
FRIDAY-Cloud-Engineering-Bridge v1.30.0). A line-by-line reader
(`rel122-work/bridge_mcp2.py`) was used instead; the bridge still drops a
call now and then mid-stream and the call is simply retried (two
`IncompleteRead`s during this task, both retried successfully, no
server-side effect — the affected calls were read-only).

## §3 — Keyed results (Server 1, gateway `http://10.0.0.121:8001`)

Full run 12:58:40–12:59:05 IST (2026-11-28T07:28:40Z–07:29:05Z), exit 1.
**Passed 7, failed 3, ok False.** Leg B is identical for all 10 agents:
`POST /v1/task/execute` 200, `SUCCESS`, content receipt `OK`, model
`openai/gpt-oss-20b`, provider `groq`, receipt target `inference` — the
in-gateway reasoning the code-read caveat describes, not peer execution.
Leg A is the per-agent proof.

| Agent | Leg A `POST /v1/mesh/ping/{agent}` (inference: `GET /v1/health`) | Leg B `POST /v1/task/execute` | Pass |
|---|---|---|---|
| friday | reachable, peer 200, 764 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | YES |
| inference | 200 healthy, 775 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | YES |
| memora | reachable, peer 200, 268 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | YES |
| stratex | **unreachable**, peer status null, 2001 ms (gateway 2.0 s ping deadline hit) | 200 SUCCESS, `OK`, gpt-oss-20b/groq | **NO** |
| futuris | **unreachable**, peer 503, 2436 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | **NO** |
| intelx | **unreachable**, peer 503, 1746 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | **NO** |
| forge | reachable, peer 200, 308 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | YES |
| sentinel | reachable, peer 200, 259 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | YES |
| cortex | reachable, peer 200, 253 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | YES |
| vyralx | reachable, peer 200, 751 ms | 200 SUCCESS, `OK`, gpt-oss-20b/groq | YES |

Health-only confirmation run with the fixed script, 12:58:06–12:58:23 IST,
exit 1, same 7/3 split (friday 850 ms, inference 750 ms, memora 252 ms,
stratex 2002 ms peer null, futuris 2270 ms peer 503, intelx 1749 ms peer
503, forge 279 ms, sentinel 263 ms, cortex 259 ms, vyralx 753 ms).

Full JSON: `~/workspace/rel122-work/live_run_keyed.json` (full run) and
`live_run_keyed_healthonly.json` (health-only run).

## §4 — Public results (this VM, `https://friday-universe.duckdns.org`)

Full run 12:48:37–12:49:30 IST (2026-11-28T07:18:37Z–07:19:30Z), exit 1.
Gateway gate `GET /health`: **200 healthy** (2.92 s). **Passed 5, failed 5,
ok False.**

| Agent | Leg A `GET /{agent}/health` | Leg B (one real GET) | Pass |
|---|---|---|---|
| friday | 200 `ok`, 2.53 s | `GET /friday/api/health` 200 `ok`, 2.41 s | YES |
| inference | 200 `healthy`, 2.20 s | `GET /inference/status` **transport error** (`IncompleteRead`, 7567 of 9301 bytes), 1.81 s | **NO** |
| memora | 200 `ok`, 1.35 s | `GET /memora/` 200 `ok`, 4.93 s | YES |
| stratex | **503**, 5.86 s (body is the bare string `HTTP 503`) | `GET /stratex/api/status` 200 `ok`, 1.96 s | **NO** |
| futuris | **503** `degraded`, 2.71 s | `GET /futuris/status` 200 `healthy`, 3.24 s | **NO** |
| intelx | **503** `degraded`, 4.48 s | `GET /intelx/healthz` 200 `ok`, 1.58 s | **NO** |
| forge | 200 `ok`, 2.25 s | `GET /forge/status` 200 **`unhealthy`**, 1.98 s | YES* |
| sentinel | 200 `ok`, 1.41 s | `GET /sentinel/status` 200 `operational`, 1.93 s | YES |
| cortex | **transport error** (`RemoteDisconnected`), 1.55 s | `GET /cortex/status` 200 `operational`, 1.57 s | **NO** |
| vyralx | 200 `ok`, 1.89 s | `GET /vyralx/` 200 HTML (Control Room), 2.19 s | YES |

\* Forge passes the script's rules (both legs 200) but its leg-B body
self-reports `unhealthy` — same contradiction REL-119 recorded
(`/health` says `database_connected: true`, `/status` says
`database: {connected: false}`). Still unresolved, still not this task's
to fix.

**Recheck of the two transport failures** (12:51:42–12:51:51 IST,
`--agents inference,cortex`, exit 1): cortex now **passes both legs**
(leg A 200); inference leg B now **200 `operational`** but leg A now
`RemoteDisconnected`. Direct curl immediately after (12:52:01 IST):
`/inference/health` **200 `healthy`** (2.29 s, providers groq/cerebras/
openrouter/gemini/nvidia, 19 active specialists) and `/cortex/health`
**200** (1.39 s). Both endpoints are up; the public ingress
intermittently drops connections on the inference/cortex mounts
(`IncompleteRead` / `RemoteDisconnected` on two of three reads). That
flakiness is recorded, not re-run away: the full-run table above stands
as run 1, and the recheck is filed alongside it.

Full JSON: `~/workspace/rel122-work/live_run_public.json` (run 1) and
`live_run_public_recheck.json` (recheck).

## §5 — Observations filed, not fixed

- **Same three degraded agents in both modes, by two independent paths.**
  Stratex (keyed: mesh-ping deadline, peer never answers in 2 s; public:
  503), Futuris (503 both ways), IntelX (503 both ways) — all three also
  answer their real-request leg with 200. This matches REL-119's
  capability-report diagnosis (an `unknown` capability flips `/health`
  to 503); no re-run was done to hide it.
- **Forge contradicts itself, still.** See §4. Needs a Forge-owner look.
- **Public-ingress transport drops** on `/inference/*` and `/cortex/*`
  (see §4 recheck). Not an agent outage — both endpoints answer 200
  seconds later — but worth a look by whoever owns the ingress.
- **Key location corrected.** The task brief said "the server-side
  credentials file" for the key; the key is not in Server 2's
  `CREDENTIALS.md` at all (zero `INFERENCE` lines) — it is in Server 1's
  `Inference/.env`, the live service's `EnvironmentFile`. Future keyed
  runs should go to that file, not `CREDENTIALS.md`.
- **No key was ever written down.** The key value appears in no file,
  output, or repo artifact in this task; only its length (43 chars) and
  its location are recorded. The public-run JSONs contain no secrets.

## §6 — Local tests

- `python3 -m py_compile scripts/live_probe.py tests/test_live_probe.py` — clean.
- `pytest tests/test_live_probe.py` — **15 passed in 8.04 s** (pytest in
  `~/workspace/frg028-venv`; system python3 has no pytest). 13 pre-existing
  tests pass unmodified; the 2 new REL-122 tests (§1) run the real CLI
  against the in-process stub gateway with `/v1/health` key-gated.
- Full root suite not run locally (same limitation REL-103/REL-104/REL-119
  recorded); this PR's own CI run is the full-suite verification.

## Files changed

- `scripts/live_probe.py` — send the Inference key on the gateway gate
  and on inference's `GET /v1/health` leg when one is set; docstring
  corrected (REL-122).
- `tests/test_live_probe.py` — `require_key_for_health` stub knob + 2
  tests modelling the live 401/200 behaviour.
- `docs/collaboration/TASK-REL-122-EVIDENCE.md` — this doc.
- No board hunk (board flips are coordinator-only). No workflow, fleet-config,
  or shared-contract edits. No server change, restart, or deploy — the
  only server-side writes were transient `/tmp` scratch files, removed
  after the runs.

## States

- **implemented:** YES — keyed gate/health-leg fix built; live keyed + public runs complete with per-agent evidence.
- **tested:** YES — 15/15 hermetic tests pass locally on the PR tree; live runs executed against the real gateway (keyed 7/10, public 5/10, exits 1 as designed).
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — on-demand script, no service; nothing to deploy.
- **production-verified:** PARTIAL — both probe modes verified live (gateway + all 10 agents hit, real output filed); 3 agents report degraded/unreachable health in both modes, forge's `/status` still self-reports `unhealthy`, and the public ingress drops connections intermittently on inference/cortex. Paired verification (owner order rule 3) is owed — no verifier was named for this task; Muse to name one.

— Muse 2
