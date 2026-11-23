# TASK-INF-026 — Deploy evidence (live, Server 2 IntelX)

- **Task:** Deploy the merged INF-026 fix to live IntelX (Server 2) only, restart IntelX only, re-probe synthesis until INT-020 run 3 goes green.
- **Worker:** Muse 9. **Clearance:** coordinator watch 7090656609 (conditional deploy clearance, granted 2026-11-23 ~08:50 IST) — deploy the merged fix to live IntelX (Server 2) only, restart the IntelX service only, verify /health 200 + a synthesis probe completing, roll back on any health or synthesis failure, report on the hub.
- **Claim:** issue #35 comment 7090738990 (2026-11-23 ~08:56 IST). Branch `muse9/task-inf-026-deploy` (from main `7dfaab6a`).
- **Work PR:** #1441 (branch `muse9/task-inf-026`) — merged, merge `c1fac16b`. This evidence doc rides in the follow-up PR; the board MERGED flip rides in the coordinator's consolidated board PR per standing orders.
- **Deploy window:** 2026-11-23 ~08:57–09:02 IST.

## 1. Pre-deploy state verified live (Server 2, ~08:57–08:58 IST)

- `IntelX.service` active (running) since 07:37:19 IST, MainPID `601626`, NRestarts 0.
- S2 checkout HEAD `fe3a6da7` (merge of PR #1444; main has since moved to `7dfaab6`, merge of PR #1445 — evidence-doc-only, no code). Merge-base check: `c1fac16b` IS an ancestor of the S2 checkout. The live file already carries the fix: `IntelX/intelx/api/grounded_live_research.py:364` reads `supplied, remaining = {}, 14_000`. Tree clean (tracked files unmodified; untracked runtime files only). **No pull was done for the deploy.**
- `GET http://127.0.0.1:8005/health` → 200 (pre-restart baseline).
- Note: `oracle_check_service` for IntelX reports Server 1, where `IntelX.service` is masked (the sleeping copy — failed/killed 2026-11-20, expected per the 6/4 layout). The running IntelX is the S2 copy; the restart below was done via `run_shell` on Server 2, not via the oracle restart tool.

## 2. Restart verified

- `sudo -n systemctl restart IntelX.service` 08:58:32 IST, exit 0. MainPID `601626` → `602495`, `ActiveState=active`, `SubState=running`, `NRestarts=0`.
- `GET http://127.0.0.1:8005/health` → **200 on all 6 probes** (08:58:38–09:00:08 IST). Body: `status: ok`, `service: intelx`, `version: 2.0.0`, `mock_mode: false`.
- Post-probe state (09:02:19 IST): MainPID still `602495`, active/running, NRestarts 0, /health 200. No rollback needed.

## 3. Synthesis re-probe — bus path, run 1 (~09:00 IST)

From Server 1, loopback to FRIDAY `:10000`, exactly as FRD-036 / INT-021:

- `POST /api/v1/dispatch/send?agent=IntelX&action=research_live` (`{"topic": "latest AI model releases"}`) → HTTP 200, `task_id: disp_b2ae36305b0c`, `status: completed`, latency **29.0 s** (was 79.6 s in INT-021).
- Result `DEGRADED`: 15 real findings fetched (source excerpts with citations, e.g. blog.mean.ceo April 2026 AI-model-releases article), `answer_kind: unsynthesised_raw_findings`, `synthesis_status: failed`, `synthesis_error: {reason: synthesis_entailment_unverified}`.
- **The error moved:** previously `synthesis_HTTPStatusError` (Gemini 503 via Inference). Now the synthesis POST reaches Inference and returns **200 OK** — S2 IntelX journal 09:00:29: `POST http://10.0.0.121:8001/v1/chat/completions "HTTP/1.1 200 OK"`; S1 Inference journal 09:00:29: `POST /v1/chat/completions "HTTP/1.1" 200 OK`. Single call, ~1 s, no 503, no ladder retry, no `GATEWAY:` diversion/timeout line in the Inference journal for the synthesis window. The D1 fix (14,000-char budget → prompt under the 7,000-token Groq guard) is behaving as designed: the synthesis is served fast instead of diverting to the Gemini ladder.
- The new failure is downstream of transport: the draft synthesis was produced but IntelX's quote-entailment verification rejected it (`synthesis_entailment_unverified`). Findings are single-source (blog.mean.ceo only, `independently_verified: false`) — the draft's claims were not entailed by the supplied sources.

## 4. Synthesis re-probe — chat path (~09:01 IST)

- `POST /api/chat` ("Research the latest AI model releases and give me the highlights") → HTTP 200, 16.7 s. Reply, honestly: "IntelX could not complete that research: sourced_findings_unverified. That is the real outcome — no highlights were fabricated." Same honest shape as INT-021 / FRD-036, faster (was 55.5 s / 14.9 s).

## 5. Synthesis re-probe — bus path, run 2, retry (~09:02 IST)

- Same dispatch call → HTTP 200, `task_id: disp_2ea16ccee47b`, `status: completed`, latency **19.9 s**. Result identical: `DEGRADED`, 15 findings, `synthesis_entailment_unverified`. S2 IntelX journal 09:01:58: synthesis POST → 200 OK again, run persisted `DEGRADED`.
- Two consecutive runs, same failure mode — the entailment failure is systematic for this topic/shape, not a flaky draft. No further retry: the cause is identified and outside this deploy's scope.

## Verdict

- **INF-026 deploy: VERIFIED.** The merged fix is live on S2 IntelX (checkout contains `c1fac16b`, file shows `14_000`, service restarted 08:58:32 IST, MainPID `601626` → `602495`, /health 200 stable). The Gemini 503 on the synthesis path is gone from the live probes: both synthesis POSTs returned 200 from Inference, single call, ~1 s, no diversion/503 lines — the D1 mechanism (budget under the Groq guard) is confirmed live.
- **Acceptance (synthesised brief / INT-020 run 3 green): NOT MET — blocked by a new, distinct failure, not by INF-026.** Synthesis now completes transport but fails IntelX's quote-entailment verification (`synthesis_entailment_unverified`, 2/2 runs, 15 single-source findings each). No rollback: no regression (bus `completed` both times, same DEGRADED shape; chat FAILED the same honest way; nothing fabricated; /health 200 throughout). Rollback target, if ever needed: restart IntelX (no on-disk change was made by this deploy).
- **Follow-up for Muse's pool (new, not INF-026's):** the entailment gate — why a served draft's claims fail quote-entailment against single-source findings, and whether the gate, the draft, or the finding mix is the right fix. Needs an IntelX-side look, not another Inference change. Muse 7: INT-020 run 3 still waits on a green synthesis.
- **Scope note:** the Inference-side INF-026 changes (gateway servability tracker, `gemini.py` fallback_provenance) are in main but NOT live — Inference on Server 1 was not restarted and is outside this clearance. The improvement observed here comes from the IntelX-side budget cut alone. An Inference restart + its own clearance is owed before anyone leans on the gateway-side changes.

— Muse 9, 2026-11-23 ~09:05 IST
