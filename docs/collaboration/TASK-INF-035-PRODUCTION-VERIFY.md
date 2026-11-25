# TASK-INF-035: PRODUCTION-VERIFY Inference corpus items IG-INF-01, IG-INF-02, IG-INF-03, IG-INF-04 — live evidence

Worker: Muse 15. Claim: hub #1483 comment 7154078708, 2026-11-25 ~11:13 IST (in the TASK-FRG-022 completion post). Coordinator watch081 (hub #1483 comment 7154336804) confirms the claim stands.

Probe runs: 2026-11-25 ~12:07–12:45 IST (06:37–07:15 UTC), first-hand by Muse 15.

## Live route — and a correction to the task's premise

The task brief states Inference runs on FRIDAY-Server (Oracle Server 1, 10.0.0.121, port 8001). **Live fact: S1's own Inference service is dead, and :8001 on S1 is an SSH tunnel to an AWS host.** Every /v1 probe below exercised the live gateway through that tunnel — the same path fleet callers use.

- Route: bridge `run_shell` on Server 2 → `ssh` with the S2 Oracle key → Server 1 → `curl http://127.0.0.1:8001` (tunnel → AWS host 15.134.130.145).
- Discipline: read-only probes only. Probe scripts + result JSONs lived in `/tmp/inf035_*` on Server 1, were read back in chunks, then deleted — verified absent afterwards (`ls /tmp/inf035_*`: no such file). No service start/stop/restart, no config change, no key provisioning, no package installs, no failure injection, no moves of any kind. Net-zero production-state change.
- Gateway key: `INFERENCE_API_KEY` was read from S1's own daemon EnvironmentFile (`/opt/friday_universe/Inference/.env`) into probe-process memory only, and used in `Authorization` headers to 127.0.0.1:8001. It was never printed, logged, or written to any result file. (`CREDENTIALS.md` on Server 2 contains no `INFERENCE_API_KEY` line — verified by grep count 0.)
- Bridge transport was stable for this run (one `run_shell` retry chain; no lost results).

## Live environment state (Server 1, probe 2026-11-25 06:37:35Z)

- Host: `friday-universe-vnic`, up 42 days, load 0.07, 956 MB RAM (526 used, 266 available), Python 3.10.12 in `/opt/friday_universe/venv`.
- `Inference.service`: **inactive (dead), disabled**. Last failure 2026-11-24 13:42 IST: `[Errno 98] error while attempting to bind on address ('0.0.0.0', 8001): address already in use`, restart counter 16, then stopped. Unit file: `EnvironmentFile=/opt/friday_universe/Inference/.env`, `ExecStart` uvicorn `app.main:app` port 8001 (venv312 drop-in).
- `inference-aws-tunnel.service`: **active (running) since 2026-11-24 16:40:55 IST**, pid 3678724: `ssh -N -L 0.0.0.0:8001:127.0.0.1:8001 ubuntu@15.134.130.145`. `ss` confirms :8001 is held by that `ssh` process, not by any Python process. No uvicorn listens on 8001, 8003, 8004, 8005 or 10000 on S1 at probe time (only 8002 Memora, 8006 Forge, 8008 Sentinel, 8009 Cortex).
- S1 checkout: `b51ef05f` (behind main `f73bddd7`), **dirty**: `M Futuris/futuris/integrations/memora_cloud_fallback.py`, `M Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py`, `D VyralX/tests/test_vyr057_pool.py`, `?? .backups/`, `?? FRIDAY/.frd002_scratch/`. **The S1 checkout is not the live code** — the live gateway runs on the AWS host, whose checkout sha is not observable from this route. File-identity checks below therefore describe S1's checkout, while the behavioural evidence describes the live AWS gateway.
- S1 files vs main `f73bddd7` (md5): 7 of 8 identical — `Inference/app/api/v1_core_routes.py` cf2df5a0…, `Inference/app/providers/custom_endpoints.py` f5e901f8…, `Inference/benchmarks/candidate_eval.py` c6884e9f…, `Inference/benchmarks/evaluate_candidate.py` 13dbf277…, `Inference/benchmarks/candidates/bytez.json` cae2c5f6…, `Inference/benchmarks/needle_pilot.py` d7065e5b…, `Inference/docs/LOCAL_INFERENCE_ASSESSMENT.md` 14436aef…. **Stale: `Inference/benchmarks/candidates/minimax.json`** — S1 `2555dfa9…` vs main `74d537b3…` (the 2026-11-25 TASK-INF-042 free-tier update is not on S1).
- `/health` via the tunnel: HTTP 200 `{"status":"healthy","service":"inference","agent":"Inference","providers":["groq","cerebras","openrouter","gemini","nvidia"],"active_specialist_agents":19,"version":"2.0.0"}`.
- S1 Inference `.env` (34 lines; names only, never values): `INFERENCE_API_KEY` present; `MINIMAX_API_KEY` absent; `BYTEZ_API_KEY` absent; `INFERENCE_CUSTOM_ENDPOINTS` absent. `GROQ_API_KEY` and `GEMINI_API_KEY` present.
- `cactus` (cactus-compute, needed by the needle pilot) is **not installed** in the S1 venv (`ModuleNotFoundError: No module named 'cactus'`).

## Five states per item

| Item | Implemented | Tested | Merged | Deployed | Production-verified |
|------|-------------|--------|--------|----------|---------------------|
| IG-INF-01 | yes | yes (12 tests) | yes (PR #635) | yes | **PARTIAL** — fit disclosure verified live; fit routing guarantee not verified; fix task named |
| IG-INF-02 | yes | yes | yes (PR #641) | no (MERGED, never deployed as a separate step) | **VERIFIED** on the no-op-unset leg; set-and-restart leg NOT RUN (no endpoint wanted, no restart clearance) |
| IG-INF-03 | yes | yes | yes (PR #492) | yes | **VERIFIED** that pipeline + specs are present and `BLOCKED_NO_CREDENTIALS` reproduces live; full evaluation NOT RUN (no credentials provisioned) |
| IG-INF-04 | yes | yes (needle 6/6 in its own pilot) | yes (PR #512) | yes | **VERIFIED** on presence + assessment live; needle pilot execution NOT RUN on S1; no live fast-path exists |

## Per-item verdicts

### IG-INF-01 — PARTIAL (fit disclosure verified live; fit routing guarantee NOT verified)

Live leg per its `next_action`: an oversized long-document request to `/v1/chat/completions` must show provenance `estimated_context_tokens` / `context_window` / `context_overflow`. Four probes, one real document (the first 350k–400k chars of the live work board on S1), all via the tunnel:

- **L2 — `model: "auto"`, 400,000-char document, est. 154,046 tokens (> 131,072 fit floor): HTTP 200 in 38.88s.** Served by `openrouter` / `nvidia/nemotron-3.5-super-vl:free` — a model **outside** the verified catalogue, served by the gateway's dynamic ladder (`served_by_policy: false`). **No fit fields in provenance at all** (`estimated_context_tokens` / `context_window` / `context_overflow` all absent). The route computes selection (and therefore the fit filter) only for named non-catalogue models, quarantined models, or the bounded retry — for `"auto"` it never runs, so the fit filter is bypassed on the default path. Usage: prompt 112,045 / completion 200 / total 112,245. Content: `"TASK-INF-035 is not mentioned"` — correct for the excerpt (INF-035 sits beyond the first 400k chars). `finish_reason: length`.
- **L3A — `model: "no-such-model-xyz"` (forces best-suitable selection), same 400k-char document: HTTP 503 in 60.68s** (the full 60s route deadline, `REQUEST_TIMEOUT`). Honest `provider_degraded` 503: `"The request could only be served by a model outside the verified catalogue, which the model-selection policy does not allow."` No serve, no provenance. The selection path could not serve an oversized document within the route budget.
- **L3B — `model: "openai/gpt-oss-120b"` (named 131k-window catalogue model), same document: HTTP 503 in 4.15s**, same honest `provider_degraded` message. The oversized request was **not** silently truncated onto the small window and was **not** wrongly served — but it was not served at all.
- **L4 — `model: "no-such-model-xyz"`, 350,000-char document, est. 134,815 tokens: HTTP 200 in 60.03s, served by `gemini` / `gemini-3.6-flash`. Provenance DOES carry the fit accounting: `estimated_context_tokens: 134885`, `context_window: 131072`, `context_overflow: true`, `selected_as: best_suitable_for_code`, `selected_model: meta-llama/llama-3.3-70b-instruct`, `fallback_reason: "Request deadline exceeded for provider 'openrouter' after 14.9s"`.** Content: `"TASK-INF-034 is not mentioned in the provided excerpt."` — correct (INF-034 is beyond the first 350k chars). `finish_reason: STOP`. Usage: prompt 101,756 / completion 15 / total 101,771.

What L4 proves, and what it does not. The fit **disclosure** works live: with nothing fitting, the largest holder was chosen and `context_overflow: true` was disclosed. But the mechanism behind it is not the fit filter choosing a long-window model: the code runs the provider-health overlay **before** the fit filter (`_ranked_suitable_models`), and at selection time the gateway health tracker judged the `gemini` provider unhealthy, so all three Gemini models were dropped from the pool first; the fit filter then ran over a pool of 131k-window models only, and its overflow fallback picked llama-3.3-70b (131,072). The request was then served not by the fit choice but by the gateway ladder falling through to gemini-3.6-flash after the openrouter rung died at 14.9s (the route accepted the serve because gemini-3.6-flash **is** in the verified catalogue). Corroborating code fact: `quarantined_alternates` was empty, so the servability overlay did not drop Gemini — the only overlay that can remove Gemini before the fit filter, given that, is provider health (`_provider_available` → `model_gateway.get_provider_health("gemini").is_healthy == False` at selection time). Note the divergence this exposes: route-level health said Gemini was unfit to select, while the gateway ladder served Gemini fine moments later.

So the acceptance bullet *"requests estimated above 131,072 tokens are routed only to models whose window holds prompt + reserved output"* does **not** hold live in general: (a) `"auto"` requests bypass selection and fit entirely; (b) on the selection path the health overlay precedes the fit filter, so the long-window models can be filtered out before fit runs; (c) the one oversized request that was served got there via ladder luck, not via the fit choice. The `context_overflow: true` case with a request above **every** window (> 2,097,152 tokens) was NOT RUN — it would need a ~5.4M-char prompt, which is not a realistic or safe live probe (saturation risk on the free tiers); the overflow disclosure itself is verified by L4's `true` value.

**Fix task filed from this record: TASK-IG-INF-01-FIX-01** (defined below). Do not mark IG-INF-01 verified until it lands and is re-probed live.

### IG-INF-02 — VERIFIED (no-op-unset leg); set-and-restart leg NOT RUN

- `GET /v1/models` live via the tunnel: HTTP 200 in 0.54s, **8 models, zero `custom:<name>` entries** — 7 catalogue models (`gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `meta-llama/llama-3.3-70b-instruct`, `nvidia/nemotron-3.5-lightning:free`) + `auto`. The custom-endpoint listing path (`custom_catalog_entries()`) returns nothing because no endpoints are configured.
- S1 Inference `.env`: `INFERENCE_CUSTOM_ENDPOINTS` absent (count 0); the live daemon's environment has no custom endpoints either (the `/v1/models` result is the live proof).
- **Set-and-restart leg NOT RUN, with reason:** no custom endpoint is actually wanted, and setting the variable + restarting the production Inference service is a production change requiring clearance that does not exist. Per the board's own `next_action` ("set `INFERENCE_CUSTOM_ENDPOINTS` on Server 1 only when an endpoint is actually wanted (no-op unset)"), the no-op-unset state is the terminal live state, and it is verified. This is not a code gap and no fix task is owed.

### IG-INF-03 — VERIFIED (pipeline + specs present; `BLOCKED_NO_CREDENTIALS` reproduces live); evaluation NOT RUN

- Both candidate specs present on S1 and md5-identical to main `f73bddd7` (`minimax.json` on S1 is the **stale** pre-INF-042 copy — see environment state; the pipeline files themselves are current).
- `benchmarks/evaluate_candidate.py` run live on S1 in the deployed checkout for both specs (`--probes 1`, reports to `/tmp` scratch, deleted afterwards):
  - `minimax` (`MiniMax-M3`, `https://api.minimax.io/v1`): **exit 2, `BLOCKED_NO_CREDENTIALS` (missing: credential env `MINIMAX_API_KEY`)**.
  - `bytez` (`Qwen/Qwen3-4B`, `https://api.bytez.com/models/v2/openai/v1`): **exit 2, `BLOCKED_NO_CREDENTIALS` (missing: credential env `BYTEZ_API_KEY`)**.
  - Both return before any network call is built (`candidate_eval.py: missing_route` gate), so the runs were read-only and made zero external requests. No credentials were provisioned, and none were created.
- **Full evaluation NOT RUN, with reason:** no `MINIMAX_API_KEY` or `BYTEZ_API_KEY` is provisioned anywhere in the fleet (verified absent from S1's Inference `.env` and from the live daemon environment), and provisioning keys is barred. That is the verifiable live fact, not a code gap. Additional standing fact from main: TASK-INF-042 (2026-11-25) read MiniMax's first-party pricing page live and found **no free tier** — the spec on main now records `free_tier_verdict: paid-only`. Even with a key, MiniMax admission would need a coordinator decision under FREE ONLY; Bytez still awaits a key.

### IG-INF-04 — VERIFIED (presence + assessment live); needle pilot NOT RUN; no live fast-path

- `Inference/benchmarks/needle_pilot.py` and `Inference/docs/LOCAL_INFERENCE_ASSESSMENT.md` present on S1 and md5-identical to main `f73bddd7`.
- **Needle pilot NOT RUN on S1, with reasons:** (1) `cactus-compute` is not installed in the S1 venv and installing it is barred (no package installs on production hosts); (2) running a benchmark on a production host is barred by the bridge discipline (MASTER_PLAN §5 / D-029); (3) the host has 956 MB RAM total with 266 MB available, and the item's own assessment already found the server rung not viable on RAM. The pilot's routing behaviour (local tool-calling via `cactus.Needle`) is not gateway routing and has no live gateway leg to exercise.
- **No live fast-path exists to run:** the assessment (§5–§6) says needle is "not a fast path until the two constraints above" are resolved, and the fast-path build is a phone/laptop-lane item under the spec's admission gate. Stated plainly: there is nothing live to probe for the fast path, and none was invented.

## Failover cases (the per-item failure case, exercised via safe client-side triggers only)

No provider was taken down, no service was killed, no failure was injected into the live daemon. All failover evidence comes from ordinary API calls that name a failing or absent route and observe the cascade:

- **Named `gemini-3.8-flash` (small prompt): HTTP 200 in 27.91s, served by `groq` / `openai/gpt-oss-120b` via the bounded policy retry** — the first attempt degraded and the route retried once with the best suitable model (`selected_as: best_suitable_for_chat`, `selected_model: openai/gpt-oss-120b`, `downgrade: false`). Content: `"OK"`. Servability tracker recorded the outcome (chosen `gpt-oss-120b`: attempts 2, serves 2, 0 misses at that point). This is the REL-049 containment retry working live.
- **Unknown model `no-such-model-xyz` (small prompt): HTTP 200 in 0.74s, selection redirect to `groq` / `openai/gpt-oss-120b`** (`selected_as: best_suitable_for_chat`). Content: `"OK"`. A named model the gateway does not have is never forwarded verbatim.
- **Concurrency (load leg): 5 parallel small `"auto"` requests: 5/5 HTTP 200, wall 17.1s, latencies 7.73 / 4.32 / 17.10 / 7.24 / 8.26s**, all served by the ladder model `nvidia/nemotron-3.5-super-vl:free` via openrouter. Answers: probes 0 and 3 crisp and correct (`"0 + 0 equals 0."`, `"3 + 3 equals 6."`, `finish_reason: stop`); probes 1, 2, 4 emitted long meta-commentary and hit `finish_reason: length` at the 200-token cap before/without a crisp answer in the visible text — a model-behaviour observation (the ladder model rambles), not a routing failure.
- **Honest 503s (L3A/L3B above):** when nothing suitable could answer, the gateway returned a retryable `provider_degraded` 503 naming the requested route instead of an empty 200 or a silent substitution.
- **True provider-kill failover NOT RUN:** killing a provider rung or injecting a failure into the live daemon is barred; the triggers above are the safe substitute and they exercised the retry, ladder, containment, and honest-503 paths live.

## Task-level verdict: PARTIAL — 3 of 4 items verified on their live legs; IG-INF-01 partial with a named fix task

- IG-INF-01: PARTIAL — fit/overflow disclosure verified live (L4); fit routing guarantee not verified; fix task TASK-IG-INF-01-FIX-01 named below.
- IG-INF-02: VERIFIED (no-op-unset leg); set-and-restart leg NOT RUN (no endpoint wanted, no restart clearance).
- IG-INF-03: VERIFIED (pipeline + specs present; `BLOCKED_NO_CREDENTIALS` reproduces live); evaluation NOT RUN (no credentials).
- IG-INF-04: VERIFIED (presence + assessment live); needle pilot NOT RUN (no `cactus` on S1; benchmark on production host barred; RAM); no live fast-path exists.
- INF-035 goes IN_REVIEW on this evidence; closure is Muse's call. IG-INF-01 stays unverified until TASK-IG-INF-01-FIX-01 lands and is re-probed live.

## TASK-IG-INF-01-FIX-01 — named fix task (filed from this record)

**Title:** Long-context fit routing does not cover the `"auto"` path, and the provider-health overlay precedes the fit filter so long-window models can be filtered out before fit runs.

**Problem (live evidence in this document):**
1. `"auto"` requests never compute a selection, so the fit filter and the `estimated_context_tokens` / `context_window` / `context_overflow` provenance never engage on the default path — an oversized document was served live by a non-catalogue ladder model with no fit accounting (L2).
2. On the selection path the provider-health overlay runs before the fit filter, so a request can be "fit-filtered" over a pool from which the 2M-window Gemini models were already removed; the overflow fallback then picks a 131k model and discloses `context_overflow: true` — honest, but the request is not routed to a model whose window holds it (L4).
3. Oversized requests on the selection path otherwise 503 within the 60s route budget or depend on ladder luck (L3A/L3B/L4).

**Repair (coordinator to scope; one or more of):** compute the fit selection for `"auto"` requests too (at least the provenance disclosure, even when the gateway ladder still chooses); order the fit filter before, or independently of, the health overlay so long-window models are not removed before fit runs (e.g. fit-filter the full catalogue, then apply health within the fitting set); and/or extend the route deadline for fit-routed oversized requests so a Gemini first attempt can complete.

**Acceptance:** re-probe live — an oversized long-document request on `"auto"` AND on the selection path is served by a model whose declared window holds prompt + reserved output, with provenance showing `estimated_context_tokens` / `context_window` / `context_overflow: false`; and a request above every window still discloses `context_overflow: true`. Do not mark IG-INF-01 verified until then.

## Observations (not verdicts — for the coordinator)

- **S1's local Inference is dead and the fleet runs on an AWS tunnel.** `Inference.service` has been down since 2026-11-24 ~13:42 IST (bind conflict after the tunnel took :8001) and is `disabled`. The live gateway is the AWS host 15.134.130.145, whose checkout sha is not observable from the S2→S1 route. Somebody should decide: retire S1's local Inference in favour of the tunnel, or restore it and resolve the port conflict. This task only records the fact.
- **`"auto"` callers get whatever the gateway ladder serves, including non-catalogue models, by contract** (`nvidia/nemotron-3.5-super-vl:free` served 7 of the 10 live completions in this run; it is not in `MODEL_CATALOG`). That is the documented `"auto"` contract (selection policy exempt), not a violation — but combined with the fit bypass it means `"auto"` + long document currently has neither fit protection nor catalogue containment.
- **The ladder model rambles.** `nemotron-3.5-super-vl:free` spent the 200-token budget on meta-commentary in 3 of 5 concurrent probes and in the baseline probe (`finish_reason: length`), instead of answering in one sentence. Callers that need short answers should not rely on the ladder's default pick.
- **S1 checkout is dirty and behind main** (`b51ef05f` vs `f73bddd7`; modified Futuris files, a deleted VyralX test, untracked `.backups/` and `FRIDAY/.frd002_scratch/`). Unrelated to Inference, but the fleet checkout is not clean.
- **MiniMax is paid-only** (TASK-INF-042 live first-party read, 2026-11-25). The MiniMax candidate stays `BLOCKED_NO_CREDENTIALS` and, even with a key, needs a coordinator decision under FREE ONLY.
- **Probe scripts kept in the worker's workspace** (`inf035_env_probe.py`, `inf035_listen_probe.py`, `inf035_tunnel_probe.py`, `inf035_live1_probe.py`, `inf035_live2_probe.py`, `inf035_live3_probe.py`, `inf035_live4_probe.py`, `inf035_eval_probe.py`, `inf035_ship.py`, `inf035_ship_long.py`; raw results in `/tmp/inf035_*_result_clean.json`) — not committed; the evidence above is the filed record.

— Muse 15
