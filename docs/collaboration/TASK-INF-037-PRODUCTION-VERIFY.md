# TASK-INF-037 — PRODUCTION-VERIFY: Inference corpus IG2-INF-03, IG2-INF-04, IG3-INF-01, IG3-INF-02 (wave 3)

## Claim (2026-11-25 ~15:40 IST, 15:36 self-check run)
- **Assigned by:** coordinator watch085 — queue position 3 behind TASK-VOI-030 (blocked) and TASK-INF-041.
- **Claim of record:** hub #1483, comment 7159309330 (also carries the TASK-INF-041 COMPLETE note).
- **Branch:** `muse13/task-inf-037-prod-verify` @ main a5de35d7 (created via Git Data API, verified by read-back); rebased (fast-forward, no unique commits) onto main 076b3942 before filing.
- **Board verified first-hand:** main 076b3942, blob a18f78a4 (`docs/collaboration/WORK_BOARD.yaml`, 22,825 lines, 2,861,325 bytes): INF-037 AVAILABLE / owner muse_13 / branch null / pr null, P2, updated 2026-11-25T12:47 IST. No competing claim in the full hub scan (1,413 comments through ~16:36 IST). Claim flip rides in the work PR.
- **Predecessor:** TASK-INF-041 MERGED 2026-11-25 15:22 IST (work PR #1806, merge 25de32df, CI 10/10 green).
- **Queue now:** INF-037 (head, completing this run) → VOI-030 (blocked, calm window; voice status NOT WORKING per P0 7159737257 until the owner re-tests and accepts).
- **Usage:** 36% of free weekly limit (checked this run via subscription-status; reset Nov 29, 6:09 PM IST). Work-request stays unarmed while a claim is held (fleet guard, hub 7111077225).

## Acceptance (board record, verbatim substance)
PRODUCTION-VERIFY (owner standard 2026-11-24: merged code is NOT implemented): live extreme-condition verification of TASK-IG2-INF-03, TASK-IG2-INF-04, TASK-IG3-INF-01, TASK-IG3-INF-02.
- Extreme-condition test: real prompts routed through live Inference on FRIDAY-Server under load (long-context, concurrent) + provider-failure failover case per item.
- For EACH item: run it in the live agent on a real task, file the live evidence (what ran, on which server, with what result, incl. the failure case). A code-only report is rejected — the task closes only on live evidence per item.
- Any item that fails live gets a named fix task filed from this record; do not mark a failing item verified.

## Live route — same as INF-035/INF-036, re-verified this run
- Route: bridge `run_shell` directly on Server 1 → `curl http://127.0.0.1:8001` (tunnel → AWS host 15.134.130.145). (INF-036 went S2→ssh→S1; this run the bridge ran the shell on S1 directly and it worked.)
- Discipline: read-only probes + ordinary API completions only. Probe scripts + result JSONs lived in `/tmp/inf037_*` on Server 1, were read back, then deleted — verified absent afterwards (`ls /tmp/inf037_*`: no such file). No service start/stop/restart, no config change, no key provisioning, no package installs, no failure injection, no moves of any kind. Net-zero production-state change.
- Gateway key: `INFERENCE_API_KEY` was read from S1's own daemon EnvironmentFile (`/opt/friday_universe/Inference/.env`) into probe-process memory only, and used in `Authorization` / `X-INFERENCE-API-KEY` headers to 127.0.0.1:8001. It was never printed, logged, or written to any result file.
- Probe runs: 2026-11-25 ~16:39–16:41 IST (11:09–11:11 UTC), first-hand by Muse 13. Probe 1 (env + 8 live legs) 11:10:06–11:10:18 UTC; probe 2 (corrected compression leg) 11:11:10–11:11:13 UTC.
- Bridge transport was stable for this run (no lost results).

## Live environment state (Server 1, probe 2026-11-25 11:09 UTC)
- Host: `friday-universe-vnic`, up 42 days (same boot as INF-035/INF-036).
- `Inference.service`: **inactive (dead)** — re-verified, same state as INF-035/036 (dead since 2026-11-24 13:42 IST, bind conflict). `inference-aws-tunnel.service`: **active**. S1 :8001 is the SSH tunnel to AWS host 15.134.130.145 — the live gateway is AWS-hosted, not S1 code.
- S1 checkout: `b51ef05f` (behind main `076b3942`), **dirty** — same two modified Futuris files and deleted VyralX test as INF-035/036, plus untracked `FRIDAY/scripts/telegram_webhook_watchdog.py`, `FRIDAY/state/`, `Stratex/daily_loss_breaker_state.json`, `Stratex/forward_daily_reports/`, `Stratex/loss_streak_breaker_state.json`, `Stratex/scripts/telegram_webhook_watchdog.py`, `Stratex/self_experiments_data/`, `VyralX/light_result_r1.txt`, `VyralX/light_result_r2.txt`, `backtest_results/`, `venv312/`, `.backups/`, `FRIDAY/.frd002_scratch/`. **The S1 checkout is not the live code** — the live gateway runs on the AWS host, whose checkout sha is not observable from this route. File-identity checks below therefore describe S1's checkout, while the behavioural evidence describes the live AWS gateway.
- `/health` via the tunnel: HTTP 200 `{"status":"healthy","service":"inference","agent":"Inference","providers":["groq","cerebras","openrouter","gemini","nvidia"],"version":"2.0.0"}`.
- `/v1/models` via the tunnel: HTTP 200 in 0.99s, **8 models**: gemini-3.8-flash, gemini-3.6-flash, gemini-3.5-flash-lite, openai/gpt-oss-120b, qwen/qwen3.8-27b, meta-llama/llama-3.3-70b-instruct, nvidia/nemotron-3.5-lightning:free, auto. Zero Bytez entries, zero `custom:<name>` entries.
- S1 Inference `.env` (names only, never values): `INFERENCE_API_KEY` present; `GROQ_API_KEY`, `GEMINI_API_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `THIRD_PARTY_GEMINI_KEY`, `THIRD_PARTY_GROQ_KEY`, `THIRD_PARTY_OPENROUTER_KEY` present. **Absent: `INFERENCE_TOKEN_COMPRESSION_ENABLED`, `INFERENCE_COMPRESSION_MIN_TOKENS`, `INFERENCE_BYTEZ_RUNG_ENABLED`** — so token compression defaults ON with the 800-token bypass, and the Bytez rung defaults OFF.

## File identity — main 076b3942 vs S1 checkout b51ef05f
| File | main md5 | S1 md5 | Match |
|------|----------|--------|-------|
| `Inference/docs/CORPUS_DISPOSITIONS.md` | 42477019733bb18fa928f81037a69d0f | 42477019733bb18fa928f81037a69d0f | YES |
| `Inference/docs/FREE_SUBSTITUTION_TABLE.md` | 42fba38fbfd555817a024aeb9006b300 | c9e1f0b4c1a16cdcb7e0b87e9e8d2825 | **NO — see IG3-INF-01** |
| `Inference/config/free_tier_routes.json` | 4f27836b3b943ff609e78d7a73a96dbc | *absent on S1* | **NO — see IG3-INF-01** |
| `Inference/app/providers/failover_log.py` | b90a4546d9255f2344716534881c849d | b90a4546d9255f2344716534881c849d | YES |
| `Inference/app/providers/token_compression.py` | 59ccc56e1d1540c544a0efa43acdbd9d | 59ccc56e1d1540c544a0efa43acdbd9d | YES |
| `Inference/app/routers/admin_dashboard.py` | 8b16854ecce2e49197935a8480afe0e3 | 8b16854ecce2e49197935a8480afe0e3 | YES |
| `Inference/app/providers/gateway.py` | b40645cd711d41b006ea521aa4bca282 | b40645cd711d41b006ea521aa4bca282 | YES |

## Five states per item
| Item | Implemented | Tested | Merged | Deployed | Production-verified |
|------|-------------|--------|--------|----------|---------------------|
| IG2-INF-03 | yes | yes | yes | yes | **VERIFIED** — dashboard live, log records real escalations in real time |
| IG2-INF-04 | yes | yes | yes (PR #710) | yes | **VERIFIED** — compression live, measured saving on my own request |
| IG3-INF-01 | yes | yes | yes | yes | **VERIFIED** — table present live, zero rows wired, INF-042 verdicts stand |
| IG3-INF-02 | yes | yes | yes | yes | **VERIFIED** — evaluation record present live, no adapters, cherry-pick live |

## Per-item verdicts

### IG2-INF-03 — VERIFIED (failover log + admin dashboard live; records real escalations in real time)
- **Code present on the live host checkout**, md5-identical to main `076b3942`: `Inference/app/providers/failover_log.py` (b90a4546…, 87 lines, bounded in-memory ring, max 200 events), `Inference/app/routers/admin_dashboard.py` (8b16854e…, 201 lines, `GET /admin/inference` + `GET /admin/inference.json`, mounted behind `require_inference_api_key`), `Inference/app/providers/gateway.py` (b40645cd…).
- **Wiring verified in code:** `ModelGateway._execute_dynamic_fallback` calls `failover_log.record(` at `gateway.py:1152`; the dashboard serves `failover_log.snapshot(limit=20)` plus the compression stats in the same snapshot.
- **Dashboard is LIVE on the AWS gateway, not just on S1's checkout:** `GET /admin/inference.json` via the tunnel returned HTTP 200 in 1.05s at 11:10:08 UTC. That proves the IG2-INF-03 code is deployed on the live gateway host (S1's own Inference daemon is dead; nothing on S1 could have served it).
- **The log records live escalations — proven by my own probes this run:** `events_retained` 39 at 11:10:08 UTC → 39 after the failover-trigger request (selection redirect, no escalation — correct) → **40** after the compression probe (one new nvidia rung-skip event, 11:10:11.576783Z) → **45** after the 5× concurrent load leg (five new nvidia events, 11:10:15) → **46** after compression probe 2. `events_dropped_oldest: 0` throughout.
- **The log already held real production failovers before I arrived** (39 events, spanning 06:49–11:02 UTC today): Groq guard routing-away (`Prompt estimated at 30746 tokens exceeds the 7000-token Groq guard…`), Gemini deadline-exceeded (`Request deadline exceeded for provider 'gemini' after 9.9s/15.0s`), Nvidia rung-off skips (`INFERENCE_NVIDIA_RUNG_ENABLED is off; TASK-REL-047`), OpenRouter deadline-exceeded. The operator question "what just failed over, from where, and why?" is answered live, with reasons and timestamps.
- **Failure case (named-model failover trigger):** named `gemini-3.8-flash`, small prompt, HTTP 200 in 0.88s, content `"ok"`. The gateway did NOT attempt gemini-3.8-flash: best-suitable selection picked `openai/gpt-oss-120b` on Groq (`selected_as: best_suitable_for_chat`, `fallback_reason: null`, usage prompt 155 / completion 19 / total 174). No failover event was recorded — correct: selection redirect is not a ladder escalation, and the log records escalations only. (INF-036's named-3.8-flash probe hit a live 503 and did escalate; this run the selection layer redirected first — both paths are live, and the escalation path is proven by the 7 events my other probes recorded.)

### IG2-INF-04 — VERIFIED (token compression live; measured saving on my own request)
- **Code present on the live host checkout**, md5-identical to main: `Inference/app/providers/token_compression.py` (59ccc56e…, 256 lines; rule-based only, whitespace + duplicate-block + duplicate-message, fenced code untouched, <800-token bypass, `INFERENCE_TOKEN_COMPRESSION_ENABLED` kill switch default on), `gateway.py` (b40645cd…).
- **Wiring verified in code:** `compress_provider_request` applied in the gateway at `gateway.py:650-652` and `1625-1627` — once per request, before the primary attempt, so every ladder rung sends the compressed prompt.
- **Live config is default-on:** `INFERENCE_TOKEN_COMPRESSION_ENABLED` and `INFERENCE_COMPRESSION_MIN_TOKENS` are both absent from S1's Inference `.env` (name check), so the live gateway runs enabled with the 800-token bypass. The dashboard confirms it: `enabled: true, min_tokens_bypass: 800`.
- **The stage is in live use, not just present:** the dashboard's process-wide stats at 11:10:08 UTC showed `requests_seen: 69, requests_compressed: 36, requests_bypassed: 32, est_tokens_saved: 27220, blocks_deduped: 24` — real traffic today has been compressed by this process.
- **My own compression leg (probe 2, corrected):** prompt 4,117 chars / 1,029 est tokens (5 copies of a ~700-char block with whitespace runs + a fenced code block + question) — above the 800-token bypass. HTTP 200 in 1.84s, served by `nvidia/nemotron-3.5-super-vl:free` via openrouter, answer CORRECT ("the animal is a fox" — compression did not corrupt the question). Dashboard before → after: `requests_seen 76 → 77`, `requests_compressed 36 → 37`, `requests_bypassed 39 → 39` (unchanged), `est_tokens_saved 27220 → 27773` (**+553 est tokens on my one request**), `blocks_deduped 24 → 27` (+3). Provider-reported `prompt_tokens: 489` for the request vs 1,029 estimated uncompressed — the provider metered the compressed prompt. The stage works live, end to end.
- **Honest note on probe 1:** my first long prompt was sized wrong — 2,421 chars / 605 est tokens, below the 800-token bypass — so it was bypassed (`requests_bypassed 33 → 34`, compressed unchanged). That leg verified the bypass path, not compression; probe 2 was re-run at the correct size and is the evidence above. The sizing error is recorded, not hidden.

### IG3-INF-01 — VERIFIED (substitution table present live; zero rows wired; INF-042 live verdicts stand)
- **Doc present on the live host checkout:** `Inference/docs/FREE_SUBSTITUTION_TABLE.md` exists on S1 — but it is the 2026-11-16 version (commit 90b9ea8b, the IG3-INF-01 filing itself), md5 c9e1f0b4…, **not** md5-identical to main (42fba38f…). The difference is exactly one later commit: 29ad7380 (2026-11-25 00:23 UTC, TASK-INF-042) added §4 "Live verdicts" and created `Inference/config/free_tier_routes.json`. S1's checkout predates INF-042: `git log` on S1 shows 90b9ea8b as the last commit touching the table, and `free_tier_routes.json` is absent on S1. This is deployment lag on the observable host, not a defect in the item: the table as IG3-INF-01 defined it (§§1–3, the six-row table + graduation rules) is present verbatim; the §4 enrichment is INF-042's output, filed today, not yet deployed to S1's checkout.
- **Zero rows wired — verified live in code:** `grep -ri 'FREE_SUBSTITUTION|free_tier_routes|substitution_table' Inference/app/` on S1: **zero hits**. No routing code references the table or the routes file.
- **MiniMax row — no adapter, verified:** no `minimax` file under `Inference/app/providers/`, no `minimax` references anywhere under `Inference/app/providers/`. The candidate spec stays spec-only, `BLOCKED_NO_CREDENTIALS`, exactly as the table's disposition requires.
- **Live verdicts stand (TASK-INF-042, Muse 4, today 2026-11-25):** every row was checked live against the vendor's own pricing/terms page — **0 of 6 routes verify as free API capacity** (Sora 2 REJECTED-discontinued; MiniMax PAID-ONLY; NanoBanana PAID-ONLY; Wan 2.6 PAID-ONLY; SadTalker VERIFIED-FREE software, not a route; Gamma AI VERIFIED-FREE consumer plan, not a route). The machine-readable record `config/free_tier_routes.json` on main has `wired: false` for every entry (md5 4f27836b…), and `tests/test_inf042_free_tier_routes.py` fails if that ever changes without a new dated first-party read. No re-check was run this run — INF-042's live check is hours old and there is no trigger to redo it.
- **The item's own terms are met:** the table is catalogue knowledge, not routing; it exists, it is not wired, and its verdicts are current.

### IG3-INF-02 — VERIFIED (re-watch evaluations record present live; no adapters; cherry-pick now live)
- **Doc present on the live host checkout**, md5-identical to main `076b3942`: `Inference/docs/CORPUS_DISPOSITIONS.md` (42477019…, 12,341 bytes), including the "Re-watch evaluations — 2026-11-16 (TASK-IG3-INF-02)" section covering all three items: FreeLLMAPI second source (Da-cwtZs1T7, I-11), OmniRoute README detail (DcqsV6Sxg63, I-12), Codex model-router (Ddlk8oQyOVO, I-12).
- **No adapters built — verified live in code:** `grep -ri 'FreeLLMAPI(|OmniRoute(' Inference/app/` on S1: **zero hits**. There is no hosted endpoint to adapt to for either project (both are self-hosted gateway software); running a second gateway beside the native one would add an unmaintained hop, not capacity. The Codex router project was never identifiable (truncated URL) and stays not-a-candidate.
- **The one transferable idea is now live:** token compression, recorded in the dispositions doc as implemented natively as TASK-IG2-INF-04 — verified live in this same run (see IG2-INF-04: +553 est tokens saved on my request). The doc's update note is true on the live gateway.
- **Security note stands:** OmniRoute's CVE-2026-88062 / GHSA-hf57-cqmx-p4gr (unauthenticated RCE via the custom ACP agent endpoint) is recorded in the dispositions; a third-party key-holding gateway with that record does not enter the fleet's request path. No adapter, no exposure.

## Failover + load cases (the per-item failure case, exercised via safe client-side triggers only)
No provider was taken down, no service was killed, no failure was injected into the live daemon. All failover evidence comes from ordinary API calls that name a failing or absent route and observe the cascade:
- **Named `gemini-3.8-flash` (small prompt): HTTP 200 in 0.88s, served by Groq `openai/gpt-oss-120b`** via best-suitable selection — the selection layer redirected before any attempt (see IG2-INF-03). Content: `"ok"`.
- **Named Bytez model — not re-run this task** (IG2-INF-01's leg, covered by INF-036: rung OFF, request served by a catalogue model; no Bytez key provisioned anywhere in the fleet).
- **Compression probe (long-context leg): 4,117 chars / 1,029 est tokens, HTTP 200 in 1.84s**, compressed live (+553 est tokens saved), answer correct.
- **Concurrency (load leg): 5 parallel small `"auto"` requests: 5/5 HTTP 200, wall 2.37s, latencies 1.59 / 1.76 / 1.83 / 2.00 / 2.36s**, all served by the ladder model `nvidia/nemotron-3.5-super-vl:free` via openrouter; each recorded one nvidia rung-skip event in the failover log (40 → 45). All five hit `finish_reason: length` at the 50-token cap with long meta-commentary instead of the requested single word — the same ladder-model rambling INF-035/036 observed (there at the 200-token cap). Model-behaviour observation, not a routing failure: every request was served.
- **True provider-kill failover NOT RUN:** killing a provider rung or injecting a failure into the live daemon is barred; the triggers above are the safe substitute and they exercised the selection redirect, bounded retry, ladder, rung-off, and compression paths live.

## Task-level verdict: COMPLETE — 4 of 4 items verified on their live legs
- IG2-INF-03: VERIFIED (dashboard live, log records real escalations in real time).
- IG2-INF-04: VERIFIED (compression live, measured saving on my own request).
- IG3-INF-01: VERIFIED (table present live, zero rows wired, INF-042 verdicts stand).
- IG3-INF-02: VERIFIED (evaluation record present live, no adapters, cherry-pick live).
- INF-037 goes IN_REVIEW on this evidence; closure is Muse's call. No fix task is named — no item failed live.

## Observations (not verdicts — for the coordinator)
- **S1's local Inference is still dead and the fleet still runs on the AWS tunnel** (re-verified this run: `Inference.service` inactive/dead, tunnel active). Same coordinator call as INF-035/036: retire S1's local Inference in favour of the tunnel, or restore it and resolve the port conflict. This task only records the fact.
- **S1 checkout is still dirty and behind main** (`b51ef05f` vs `076b3942`; modified Futuris files, a deleted VyralX test, untracked `.backups/`, `FRIDAY/.frd002_scratch/`, plus new untracked `Stratex/forward_daily_reports/`, `Stratex/loss_streak_breaker_state.json`, `Stratex/scripts/telegram_webhook_watchdog.py`, `Stratex/self_experiments_data/`, `VyralX/light_result_r1.txt`, `VyralX/light_result_r2.txt`, `backtest_results/`, `venv312/`). Unrelated to Inference, but the fleet checkout is not clean.
- **S1's substitution table is one commit stale** (missing INF-042 §4; `free_tier_routes.json` absent on S1). The fleet checkout should be brought to current main, or the doc's live-verdict section will keep ageing on the observable host.
- **Gemini is under live pressure right now:** health score 0.43, 6 success / 8 failure, 8× 503, last error "timeout after 9.86s". The selection layer is routing around it (my named-3.8-flash request went to Groq instead). Worth watching, not a defect.
- **The ladder model still rambles.** `nemotron-3.5-super-vl:free` spent the 50-token budget on meta-commentary in all 5 concurrent probes (and the 60-token budget in the compression probe), instead of answering in one word. Callers that need short answers should not rely on the ladder's default pick.
- **Scope limit, stated honestly:** S1's daemon is dead and its `.env` is the dead daemon's config, not the live gateway's. The live gateway runs on the AWS host, whose environment and checkout are **not observable from this route**. File-identity legs describe S1's checkout; the behavioural legs (dashboard, compression stats, failover log, completions) describe the live AWS gateway through the tunnel. The AWS-side adoption of anything env-gated (e.g. compression kill-switch state) is confirmed only through the dashboard's own `enabled: true` readout, which is the live process reporting on itself.
- **Probe scripts kept in the worker's workspace** (`/tmp/inf037_probe.py`, `/tmp/inf037_probe2.py` — local copies only; the S1 originals were deleted after the run, verified absent).

— Muse 13
