# TASK-INT-021 — Deploy evidence (live, Server 2)

- **Task:** Fix the S2 stale localhost env so IntelX synthesis reaches Inference, restart, re-run the WF-001 IntelX leg.
- **Worker:** Muse 9. **Clearance:** coordinator comment 7083712388 (2026-11-23 ~00:05 IST, re-delivered after the 23:51 IST watch post failed to land) — GRANTED, exactly the 3 values below.
- **Work PR:** #1402 (branch `muse9/task-int-021`) — merged, merge `2dcd366`. This evidence doc rides in follow-up PR (branch `muse9/task-int-021-evidence`); board flip to MERGED rides in the coordinator's consolidated board PR.
- **Deploy window:** 2026-11-23 ~00:42–00:50 IST.

## 1. Pre-deploy state verified live (Server 2, ~00:42 IST)

- `IntelX.service` active, running, MainPID 563553, NRestarts 0. S2 checkout HEAD `db933cfc` (plan said `09a05ea3` at 23:40 IST — checkout moved by routine fleet CD since; no pull done by me).
- Env URL keys, each exactly once: `INFERENCE_URL=http://127.0.0.1:8001`, `MEMORA_URL=http://127.0.0.1:8002`, `STRATEX_URL=http://127.0.0.1:8003`, `INTELX_URL=http://127.0.0.1:8005`, `FUTURIS_URL=http://127.0.0.1:8004`, `FORGE_URL=http://127.0.0.1:8006`, `FRIDAY_URL=http://127.0.0.1:10000`.
- Probes from S2: `127.0.0.1:8001/health` = 000, `10.0.0.121:8001/health` = 200, IntelX self `127.0.0.1:8005/health` = 200. Matches the plan exactly.

## 2. Backup + exactly 3 values corrected

- Backed up `/opt/friday_universe/IntelX/.env` to `/opt/friday_universe/IntelX/.env.pre-int021-20261122` (`cp -p`, `cmp` identical) before any edit.
- `diff` backup-vs-edited shows exactly 3 lines:

| Key | Before (stale) | After (corrected) |
|---|---|---|
| `INFERENCE_URL` | `http://127.0.0.1:8001` | `http://10.0.0.121:8001` |
| `FRIDAY_URL` | `http://127.0.0.1:10000` | `http://10.0.0.121:10000` |
| `MEMORA_URL` | `http://127.0.0.1:8002` | `http://10.0.0.121:8002` |

- Each corrected key occurs exactly once in the file. Untouched per clearance: `FORGE_URL` (target unverified, 000 at both ends — not guessed), `STRATEX_URL` (live Stratex is AWS via tunnel; VAL-006 territory), `INTELX_URL` (self, 200 on localhost), `FUTURIS_URL` (co-hosted on S2, 200 on localhost). No secret value was read, printed, or stored; only URL keys were grepped.

## 3. Restart verified

- `sudo -n systemctl restart IntelX.service` 00:43:18 IST, exit 0. MainPID `563553` → `596940`, `ActiveState=active`, `SubState=running`, `NRestarts=0`.
- `GET http://127.0.0.1:8005/health` → 000, 000, then **200** from the third probe (~10 s startup), stable 200. Body: `status: ok`, `service: intelx`, `version: 2.0.0`, `mock_mode: false`.
- Journal: clean startup, production mode, DB initialised, standing watches started (`ai_model_releases`, `india_tech_regulatory`).

## 4. WF-001 IntelX leg re-run (exactly as FRD-036)

Run 1, ~00:45–00:47 IST (from Server 1, loopback to FRIDAY `:10000`):

- **Bus path:** `POST /api/v1/dispatch/send?agent=IntelX&action=research_live` (`{"topic": "latest AI model releases"}`) → HTTP 200, `task_id: disp_b019c42259b2`, `status: completed`, latency 79.6 s. Result `DEGRADED`: 15 real findings fetched (source excerpts with citations, e.g. blog.mean.ceo April 2026 AI-model-releases article), `answer_kind: unsynthesised_raw_findings`, `synthesis_status: failed`, `synthesis_error: {reason: synthesis_HTTPStatusError}`.
- **Chat path:** `POST /api/chat` ("Research the latest AI model releases and give me the highlights") → HTTP 200, 55.5 s, `task_state: FAILED`, `probe_success: false`. Reply, honestly: "IntelX could not complete that research: sourced_findings_unverified. That is the real outcome — no highlights were fabricated."
- Dispatch report after: 1 total, 1 completed, 0 failed, 0 circuits open.

Note on the run: the bridge `run_shell` client timed out reading the combined bus+chat response (~120 s client timeout), but the S1 command completed and both responses were on disk (`/tmp/int021_bus.json`, `/tmp/int021_chat.json` on S1); all figures above were read from those files, not assumed.

## 5. Diagnosis — the failure moved downstream, off INT-021

- **The ConnectError is gone.** IntelX journal shows synthesis POSTs now reaching Inference at the corrected URL: `POST http://10.0.0.121:8001/v1/chat/completions` → `200 OK` at 00:45:35 and 00:45:36, then `503 Service Unavailable` at 00:46:03, 00:46:04, 00:46:57.
- **The 503 comes from upstream Gemini, via Inference.** Inference (S1) is healthy as a process (active, MainPID 2365064, NRestarts 0, `/health` 200, providers groq/cerebras/openrouter/gemini/nvidia). Its journal at the same minutes: `Gemini model gemini-3.8-flash experienced 503 high demand; failing over to gemini-3.6-flash` (00:45:31, 00:45:34), `Provider 'gemini' timed out after 15.0s ... Initiating capability fallback` (00:45:47), then `POST /v1/chat/completions` → `503` to IntelX (00:46:03, 00:46:04, 00:46:57).
- **Retry (bus only, 00:49 IST):** `task_id: disp_b76eff38c0a3`, completed, 22.8 s, still `DEGRADED` + `synthesis_HTTPStatusError`, 15 findings, no synthesised brief. IntelX journal 00:49:36: same POST → `503`. The Gemini 503 persisted across both probes in this window — not a one-off transient. No further retry: the cause is identified and outside this task's scope.

## Verdict

- **INT-021 env fix: VERIFIED.** Synthesis now reaches Inference through the corrected `INFERENCE_URL` (200s observed; the error is now an HTTP status from Inference, not a connection failure). Restart verified, exactly 3 values changed, backup retained.
- **WF-001 IntelX leg acceptance (real highlights returned): NOT MET — blocked downstream, not by INT-021.** The remaining failure is Gemini 503 high-demand/timeout inside Inference's synthesis path. No rollback: the re-probe did not regress (bus `completed` both times, same DEGRADED shape; chat FAILED the same honest way, nothing fabricated). Rollback target, if ever needed: env backup `.env.pre-int021-20261122` + restart.
- **Follow-up for Muse's pool (new, not INT-021's):** Gemini capacity on the synthesis path — `gemini-3.8-flash` 503 high demand with failover to `gemini-3.6-flash` also timing out; Inference returns 503 to IntelX synthesis. Needs an Inference-side look (provider ladder / timeout / model pin), not another IntelX env change. Muse 7: INT-020 run 3 still waits on a green synthesis.

— Muse 9, 2026-11-23 ~00:51 IST
