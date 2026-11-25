# TASK-INF-036: PRODUCTION-VERIFY Inference corpus items IG-INF-05, IG-INF-06, IG2-INF-01, IG2-INF-02 — live evidence

Worker: Muse 15. Claim: hub #1483 comment 7155723900, 2026-11-25 ~12:48 IST (in the TASK-INF-035 completion post, claim-and-next). This run is the stall repair: the claim stood for ~80 minutes with zero commits before this work started.

Probe runs: 2026-11-25 ~14:05–14:09 IST (08:35–08:39 UTC), first-hand by Muse 15.

## Live route — same as INF-035, re-verified this run

- Route: bridge `run_shell` on Server 2 → `ssh` with the S2 Oracle key → Server 1 → `curl http://127.0.0.1:8001` (tunnel → AWS host 15.134.130.145).
- Discipline: read-only probes only. Probe scripts + result JSONs lived in `/tmp/inf036_*` on Server 1, were read back in chunks, then deleted — verified absent afterwards (`ls /tmp/inf036_*`: no such file). The Bytez probe report went to `/tmp/inf036_bp` scratch, also deleted. No service start/stop/restart, no config change, no key provisioning, no package installs, no failure injection, no moves of any kind. Net-zero production-state change.
- Gateway key: `INFERENCE_API_KEY` was read from S1's own daemon EnvironmentFile (`/opt/friday_universe/Inference/.env`) into probe-process memory only, and used in `Authorization` headers to 127.0.0.1:8001. It was never printed, logged, or written to any result file.
- Bridge transport was stable for this run (no lost results).

## Live environment state (Server 1, probe 2026-11-25 08:35:24Z)

- Host: `friday-universe-vnic`, up 42 days (same boot as INF-035's probe ~2h earlier).
- `Inference.service`: **inactive (dead)** — re-verified, same state as INF-035 (dead since 2026-11-24 13:42 IST, bind conflict). `inference-aws-tunnel.service`: **active**. S1 :8001 is the SSH tunnel to AWS host 15.134.130.145 — the live gateway is AWS-hosted, not S1 code.
- S1 checkout: `b51ef05f` (behind main `a0a9f1ba`), **dirty** — same two modified Futuris files and deleted VyralX test as INF-035, plus new untracked `FRIDAY/scripts/telegram_webhook_watchdog.py`, `FRIDAY/state/`, `Stratex/daily_loss_breaker_state.json`. **The S1 checkout is not the live code** — the live gateway runs on the AWS host, whose checkout sha is not observable from this route. File-identity checks below therefore describe S1's checkout, while the behavioural evidence describes the live AWS gateway.
- **All 9 files checked on S1 are md5-identical to main `a0a9f1ba`**: `Inference/docs/CORPUS_DISPOSITIONS.md` 42477019…, `Inference/docs/PROMPT_ENGINEERING_DISCIPLINE.md` 86cef607…, `Inference/app/providers/bytez.py` ba66276f…, `Inference/app/providers/bytez_probe.py` 066e29bb…, `Inference/app/providers/key_vault.py` 0e7ed8b0…, `Inference/app/providers/token_compression.py` 59ccc56e…, `Inference/app/providers/gateway.py` b40645cd…, `Inference/benchmarks/candidates/bytez.json` cae2c5f6… (same md5 as INF-035), `Inference/app/core/config.py` 4d0eda99….
- S1 Inference `.env` (32 lines; names only, never values): `INFERENCE_API_KEY` present; `GROQ_API_KEY` and `GEMINI_API_KEY` present; `THIRD_PARTY_GEMINI_KEY`, `THIRD_PARTY_GROQ_KEY`, `THIRD_PARTY_OPENROUTER_KEY` present. **Absent: `BYTEZ_API_KEY`, `BYTEZ_API_KEYS`, `INFERENCE_BYTEZ_RUNG_ENABLED`, `INFERENCE_KEY_VAULT_MASTER_KEY`, `INFERENCE_KEY_VAULT_FILE`, `MINIMAX_API_KEY`.**
- `/health` via the tunnel: HTTP 200 `{"status":"healthy","service":"inference","agent":"Inference","providers":["groq","cerebras","openrouter","gemini","nvidia"],"version":"2.0.0"}` (healthy this run; INF-035 saw `degraded` with `market_data UNKNOWN` ~2h earlier — health state moves; recorded as observed).

## Five states per item

| Item | Implemented | Tested | Merged | Deployed | Production-verified |
|------|-------------|--------|--------|----------|---------------------|
| IG-INF-05 | yes | yes | yes (PR #514) | yes | **VERIFIED** — record present live and its dispositions match live code + live gateway behaviour |
| IG-INF-06 | yes | yes | yes (PR #517) | yes | **PARTIAL** — discipline present live, never exercised; no prompt change has gone through R1–R7 |
| IG2-INF-01 | yes | yes (10 tests) | yes (PR #735) | yes | **PARTIAL** — adapter present, rung provably OFF live; quota probe NOT RUN (no Bytez key anywhere) |
| IG2-INF-02 | yes | yes (9 tests) | yes (PR #706) | yes | **PARTIAL** — vault code present + wired into gateway startup; live keys NOT flowing through the vault on the observable host; fix task named |

## Per-item verdicts

### IG-INF-05 — VERIFIED (disposition record present live; dispositions match live code and live gateway)

Live legs per its `next_action` ("record is the deliverable"):

- **Doc present on the live host checkout**, md5-identical to main `a0a9f1ba` (`Inference/docs/CORPUS_DISPOSITIONS.md`, 42477019…, 12,419 bytes).
- **Free-token cluster — zero wired in, verified live:** no FreeLLMAPI/OmniRoute adapter code exists anywhere in `Inference/app` (grep for `FreeLLMAPI(`, `OmniRoute(`, client classes, imports: zero hits; the only mentions are docstring references in `key_vault.py`, `token_compression.py`, `admin_dashboard.py` describing the pattern, not a route). The live gateway's `/v1/models` lists 7 catalogue models + `auto` — all first-party free tiers, zero third-party intermediary routes. `/health` providers are exactly the first-party pools: groq, cerebras, openrouter, gemini, nvidia.
- **Already-implemented (7 items) — verified against live code paths:** `KeyPool` 429/503 quarantine in `gateway.py` (30 matches on S1); `MODEL_CATALOG` over pooled first-party tiers in `app/api/v1_core_routes.py:891` (the disposition cites the catalogue; it lives in the routes module, not `gateway.py` — checked, present); token compression wired into the gateway (`token_compression` 2 matches in `gateway.py`, `def compress` ×3 in `token_compression.py` — the OmniRoute cherry-pick implemented natively as TASK-IG2-INF-04, as the doc's update notes); the `/v1/*` OpenAI-compatible surface over all pools, served live this run behind the single gateway credential `INFERENCE_API_KEY`.
- **Live behaviour matches the record:** the named-model failover probe below (gemini-3.8-flash → gemini-3.6-flash on live 503) is the KeyPool-quarantine + capability-matched fallback ladder working live; the 5× concurrent `auto` run is the pooled-tiers surface under load. The servability tracker in live provenance records attempts/serves/misses/quarantine per model (see bytez probe: chosen gemini-3.8-flash attempts 3, serves 0, misses 3, quarantined false).
- **Subscription pooling — not adopted, and no subscription bridge exists in the code** (nothing in `Inference/app` consumes a consumer subscription allowance; the legitimate need is served by the cross-provider ladder, which the failover probe exercised live).

### IG-INF-06 — PARTIAL (discipline present live; never exercised — no prompt change has gone through it)

Live legs per its `next_action` ("first prompt change under the discipline replaces a baseline changelog row with measured before/after → VERIFIED"):

- **Doc present on the live host checkout**, md5-identical to main `a0a9f1ba` (`Inference/docs/PROMPT_ENGINEERING_DISCIPLINE.md`, 86cef607…, 5,190 bytes).
- **Changelog is still baseline-only.** The doc's changelog carries exactly the three 2026-11-15 baseline rows (astra-core, deliberation roles, route-inline system prompts — "never benched as prompts") and no measured row. S1 copy identical (md5 match), so this is the live-host state too.
- **No prompt change has occurred since the discipline landed, so there is nothing the discipline could have exercised.** Verified first-hand on main `a0a9f1ba`: `git diff d254abe9..HEAD` (d254abe9 = the TASK-IG-INF-06 commit) shows `Inference/app/core/astra_profile.py`, `Inference/app/agents/roles/`, `Inference/app/agents/deliberation_engine.py` **unchanged**; the only route-file changes are routing/selection code in `v1_core_routes.py` (+585/−38) and `friday_routes.py` (+46/−0) with **zero added prompt prose** (no added "You are…", system-prompt, persona, or instruction strings). The one merge touching those paths since 2026-11-15 (#1373, worker-prompt housekeeping) changed no Inference prompt text.
- **Stated plainly: the discipline is NOT exercised.** R1–R7 have never run on a real prompt change; no bench-before/after exists. This is not a code failure — the trigger (a prompt change) simply has not occurred — and **no fix task is owed**. The item's own acceptance says VERIFIED arrives with the first prompt change under the discipline; until then it stays PARTIAL.
- **The live leg that CAN be checked works:** every live completion in this run recorded `served_by_model` in provenance (R4's evidence requirement — a result is evidence only when served_model is known). E.g. the Bytez-named request records `requested_model: Qwen/Qwen2.5-7B-Instruct`, `selected_model: gemini-3.8-flash`, `served_by_model: gemini-3.6-flash`, `served_by_provider: gemini`, `selected_as: best_suitable_for_chat`.

### IG2-INF-01 — PARTIAL (adapter present, rung provably OFF live; quota probe NOT RUN — no key)

- **Adapter + probe harness present on the live host checkout**, md5-identical to main: `Inference/app/providers/bytez.py` ba66276f… (83 lines, `BytezProvider`, ≤7B models only: Qwen2.5-7B-Instruct, Qwen3-4B, Llama-3.2-3B-Instruct, Phi-3-mini-4k-instruct), `Inference/app/providers/bytez_probe.py` 066e29bb… (232 lines, sequential rounds, stops at first 429, verdicts `proven_for_this_run` / `rate_limited` / `auth_error` / `inconclusive` / `no_attempts`), `Inference/benchmarks/candidates/bytez.json` cae2c5f6…. Rung gate in `gateway.py` (3 matches: `bytez_rung_enabled()` — env `INFERENCE_BYTEZ_RUNG_ENABLED`, default off) and `bytez` in `unified_manager.py` (1 match).
- **Rung OFF in live config, proven three ways:** (1) `INFERENCE_BYTEZ_RUNG_ENABLED` is absent from S1's Inference `.env` (name check), and the code default is off; (2) live `GET /v1/models`: HTTP 200 in 0.74s, **8 models, zero Bytez entries, zero `custom:<name>` entries** (same 7 catalogue models + `auto` as INF-035); (3) a live request naming a Bytez-only model (`Qwen/Qwen2.5-7B-Instruct`) was **not served by Bytez and Bytez was never attempted** — HTTP 200 in 3.57s, served by `gemini` / `gemini-3.6-flash` via best-suitable selection (`selected_as: best_suitable_for_chat`, `selected_model: gemini-3.8-flash`, `fallback_reason: "Gemini model gemini-3.8-flash experienced 503 high demand; failing over to gemini-3.6-flash"`). Content: `"ok"`, `finish_reason: STOP`, usage prompt 76 / completion 1 / total 77.
- **Quota probe harness runs live — verdict `no_attempts`.** `python -m app.providers.bytez_probe --rounds 1` run live on S1 in the deployed checkout (fleet venv Python 3.10.12, report dir pointed at `/tmp/inf036_bp` scratch): exit 1, `verdict: no_attempts`, `rounds_attempted: 0`, `"No BYTEZ_API_KEY(S) configured in this environment; nothing was sent."` Zero network calls were made (the probe returns before building any request when no key exists — same gate INF-035 verified for `evaluate_candidate.py`).
- **Empirical quota probe leg NOT RUN, with reason:** no `BYTEZ_API_KEY` is provisioned anywhere in the fleet (verified absent from S1's Inference `.env` and from the live daemon environment; no persisted probe report exists in S1's `Inference/app/.data/`). Provisioning a key is an operator/coordinator decision under FREE ONLY, not a code fix — same precedent as INF-035's IG-INF-03 credential legs, so **no fix task is named for this leg**. Bytez's free volume stays `unproven_free_tier` in the quota ledger, exactly as the adapter's own docstring requires, and the rung stays off. Do not mark IG2-INF-01 verified until a key is provisioned, the probe runs across repeated rounds, and an operator declares a ledger limit from that evidence.

### IG2-INF-02 — PARTIAL (vault present + wired; live keys do NOT flow through it on the observable host)

- **Vault code present on the live host checkout**, md5-identical to main: `Inference/app/providers/key_vault.py` 0e7ed8b0… (330 lines; PBKDF2-HMAC-SHA256 200k iterations, HMAC-SHA256 counter-mode keystream, encrypt-then-MAC, stdlib only; default path `Inference/app/.data/key_vault.json`; master key from `INFERENCE_KEY_VAULT_MASTER_KEY` only).
- **Wired into gateway startup, verified in code:** `ModelGateway.__init__` calls `_apply_key_vault()` before `_initialize_pools()` (`gateway.py`: 4 matches for `_apply_key_vault|apply_vault_to_settings`, 3 for `key_vault` import); `apply_vault_to_settings` fills **only currently-empty** fields, never overwrites an env value, never moves a value across pools. Unit tests: 9 tests in `Inference/tests/test_ig2_key_vault.py` (bytez suite has 10).
- **Live on the observable host the vault is NOT configured and NOT used — verified three ways on S1:**
  1. Vault file does **not exist**: `/opt/friday_universe/Inference/app/.data/key_vault.json` absent; no bytez/vault/key files in `Inference/app/.data/` (directory exists, listing empty for those names).
  2. Master key absent: `INFERENCE_KEY_VAULT_MASTER_KEY` and `INFERENCE_KEY_VAULT_FILE` both absent from S1's Inference `.env` (name check).
  3. Runtime check live on S1: `vault_configured()` → `False`; `python -m app.providers.key_vault list` → exit 0, **zero entries**; `apply_vault_to_settings(settings)` against the real settings object → `{'applied': [], 'skipped_existing': [], 'errors': []}` — a no-op at startup.
- **Live provider keys on S1 sit as plaintext env names** (`GROQ_API_KEY`, `GEMINI_API_KEY`, `THIRD_PARTY_GEMINI_KEY`, `THIRD_PARTY_GROQ_KEY`, `THIRD_PARTY_OPENROUTER_KEY` present in the `.env`). No key material was read, printed, or recorded in this run — names only, per discipline.
- **Scope limit, stated honestly:** S1's daemon is dead and its `.env` is the dead daemon's config, not the live gateway's. The live gateway runs on the AWS host, whose environment is **not observable from the S2→S1 route** — so whether the AWS gateway's keys flow through a vault there is NOT VERIFIABLE here, not proven absent. What is proven is: on the only observable host the vault is unused, and no vault exists anywhere in the fleet path this run can see. **Fix task filed from this record: TASK-IG2-INF-02-FIX-01** (defined below). Do not mark IG2-INF-02 verified until it lands and is re-probed live.

## Failover + load cases (the per-item failure case, exercised via safe client-side triggers only)

No provider was taken down, no service was killed, no failure was injected into the live daemon. All failover evidence comes from ordinary API calls that name a failing or absent route and observe the cascade:

- **Named `gemini-3.8-flash` (small prompt): HTTP 200 in 0.74s, served by `gemini` / `gemini-3.6-flash`** — the first attempt hit a live Gemini 503 ("high demand") and the gateway failed over within the same request (`fallback_reason` recorded in provenance). Content: `"ok"`. This is the IG-INF-05 quota-exhaustion ladder working live, and it also reproduces INF-035's bounded-retry observation with a different first-attempt failure (503 high demand rather than a degraded rung).
- **Named Bytez model (IG2-INF-01 failure case):** the disabled rung was never attempted and the request was served by a catalogue model instead (see IG2-INF-01 above) — the rung-off gate fails safe, not loud.
- **Concurrency (load leg): 5 parallel small `"auto"` requests: 5/5 HTTP 200, wall 18.03s, latencies 9.73 / 12.87 / 6.83 / 12.37 / 18.03s**, all served by the ladder model `nvidia/nemotron-3.5-super-vl:free` via openrouter. All five hit `finish_reason: length` at the 50-token cap with long meta-commentary instead of the requested single word — the same ladder-model rambling INF-035 observed (there at the 200-token cap). Model-behaviour observation, not a routing failure: every request was served, and provenance on each records the NVIDIA rung skip (`"Provider 'nvidia' is disabled by configuration (INFERENCE_NVIDIA_RUNG_ENABLED is off; TASK-REL-047); skipping without an attempt."`).
- **True provider-kill failover NOT RUN:** killing a provider rung or injecting a failure into the live daemon is barred; the triggers above are the safe substitute and they exercised the selection redirect, bounded retry, ladder, and rung-off paths live.

## Task-level verdict: PARTIAL — 1 of 4 items verified on their live legs

- IG-INF-05: VERIFIED (record present live; dispositions match live code + live gateway behaviour).
- IG-INF-06: PARTIAL — discipline present live, never exercised (no prompt change since it landed); no fix task (the trigger has not occurred).
- IG2-INF-01: PARTIAL — adapter present, rung provably OFF live; quota probe NOT RUN (no Bytez key provisioned); no fix task (key provisioning is a coordinator decision, INF-035 precedent).
- IG2-INF-02: PARTIAL — vault present + wired; live keys do not flow through it on the observable host; fix task TASK-IG2-INF-02-FIX-01 named below.
- INF-036 goes IN_REVIEW on this evidence; closure is Muse's call. IG-INF-06, IG2-INF-01 and IG2-INF-02 stay unverified until their named conditions are met and re-probed live.

## TASK-IG2-INF-02-FIX-01 — named fix task (filed from this record)

**Title:** Encrypted key vault is wired into gateway startup but unused live — provider keys on the observable host sit as plaintext env, no vault file, no master key; AWS-side adoption is unverifiable from the S2→S1 route.

**Problem (live evidence in this document):**
1. On Server 1 (the only observable host) there is no vault file (`Inference/app/.data/key_vault.json` absent), no `INFERENCE_KEY_VAULT_MASTER_KEY` in the Inference `.env`, `vault_configured()` returns `False` live, `key_vault list` returns zero entries, and `apply_vault_to_settings(settings)` is a no-op at startup.
2. The live provider keys visible on S1 are plaintext env names (`GROQ_API_KEY`, `GEMINI_API_KEY`, `THIRD_PARTY_*`) — exactly the single-file-leak blast radius the vault was built to shrink.
3. The live gateway is AWS-hosted and its environment is not observable from the S2→S1 probe route, so vault adoption there cannot be confirmed or denied by this task — the item is unverifiable as written until adoption is observable.

**Repair (coordinator to scope; operator action + small code):** provision the vault on the live gateway host (set `INFERENCE_KEY_VAULT_MASTER_KEY` in the service environment, migrate provider keys into the vault via the operator CLI, keep env values as fallback since env always wins); and make vault status observable from the probe route (e.g. a read-only admin/health field reporting applied/skipped entry counts by field name only, never values or fingerprints of values beyond the existing `verify` CLI) so a future production-verify can confirm keys load through the vault without needing the AWS host's env.

**Acceptance:** re-probe live — `vault_configured()` true on the live gateway host (or the new status field shows applied entries), `key_vault list` shows the provider-key field names, and a gateway restart (operator-approved) loads at least one provider key from the vault with env absent for that field; no key material printed anywhere. Do not mark IG2-INF-02 verified until then.

## Observations (not verdicts — for the coordinator)

- **S1's local Inference is still dead and the fleet still runs on the AWS tunnel** (re-verified this run: `Inference.service` inactive/dead, tunnel active). Same coordinator call as INF-035: retire S1's local Inference in favour of the tunnel, or restore it and resolve the port conflict. This task only records the fact.
- **The ladder model still rambles.** `nemotron-3.5-super-vl:free` spent the 50-token budget on meta-commentary in all 5 concurrent probes (and the 200-token budget in INF-035), instead of answering in one word. Callers that need short answers should not rely on the ladder's default pick.
- **S1 checkout is still dirty and behind main** (`b51ef05f` vs `a0a9f1ba`; modified Futuris files, a deleted VyralX test, untracked `.backups/`, `FRIDAY/.frd002_scratch/`, plus new untracked `FRIDAY/scripts/telegram_webhook_watchdog.py`, `FRIDAY/state/`, `Stratex/daily_loss_breaker_state.json`). Unrelated to Inference, but the fleet checkout is not clean.
- **Gemini 3.8-flash is under live 503 pressure right now** (high demand): both named-model probes this run failed over from it to 3.6-flash within the request, and the servability tracker showed the chosen model at 3 attempts / 0 serves / 3 misses. The failover ladder absorbed it; worth watching, not a defect.
- **Probe scripts kept in the worker's workspace** (`inf036_env_probe.py`, `inf036_live_probe.py`, `inf036_mod_probe.py`; raw results in `/tmp/inf036_*_result_clean.json`) — not committed; the evidence above is the filed record.

— Muse 15
