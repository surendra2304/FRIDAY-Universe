# TASK-INF-043 — scoping checkpoint 1 — Muse TP10

Claim: hub #1483 comment 7194179426 (2026-11-26 ~19:31 IST). Branch `musetp10/task-inf-043` from main `28cc4ecb`. Queue: INF-043 (head) -> VOI-045 -> SEN-035. DB-011 closed repo-side (PR #1986 merged `a5b88f4e`); its live Server 1 leg and paired verification remain coordinator-gated and are not part of this task.

## Task (board, main blob `4545b304`)

Inference: routing-deadline live-path re-verification — fresh Gemini 9k-token timing through the live routing path. Acceptance: (1) measure Gemini completion time on ~9k-token prompts through the live routing path; (2) confirm or reset the routing deadline from that evidence; file the numbers.

## Anchors verified first-hand at main `28cc4ecb` (this run)

- `FRIDAY/src/friday/llm/escalation.py` (blob `ec979e19`, 36,917 bytes):
  - Lines 76–77: `FRIDAY_LLM_ESCALATION_TIMEOUT_S` default 70 = 60 s Inference routing deadline + 10 s transport margin.
  - Lines 317–336: `INFERENCE_ROUTING_DEADLINE_S = 60.0`; `INFERENCE_CLIENT_TIMEOUT_MARGIN_S = 10.0`; `_inference_timeout_s()` clamps env override to [10, 600]. Comment (INF-032): mirrors gateway `REQUEST_TIMEOUT` (INF-029 KEEP 60.0 s; INF-031 live-proved 20.12 s wall for a 9k-token prompt); gateway bounds every `/v1/chat/completions` call at 60 s end-to-end; `PRIMARY_ATTEMPT_MAX_SECONDS 15.0`.
  - Line 672: `httpx.Client(timeout=self.timeout)` — FRIDAY-side client bound.
- Board records (WORK_BOARD.yaml blob `4545b304`):
  - TASK-INF-031 MERGED (PR #1567, merge `af90fca8`): deadline set from INF-019 ~9k-token timing evidence.
  - TASK-INF-032 MERGED (PR #1634, merge `c19ab0a8`): deadline wired into live path; client timeout 150 s -> 70 s in `escalation.py`; 5 new tests in `FRIDAY/tests/test_llm_escalation.py`. Board blocker note (historical): fallback-ladder outage for the >7000-token class from ~11:11 IST 2026-11-24.
  - TASK-INF-033 MERGED (PR #1724, merge `1c9efa8d`): live proof 2026-11-25 ~02:05–02:17 IST — 60 s budget bounds every request (worst wall 51.96 s); 15.0 s primary slice fired on the record; >7000-token bypass fires on both paths. Evidence: `docs/collaboration/TASK-INF-033-ROUTING-DEADLINE-LIVE-PROOF.md`.
  - TASK-INF-043 AVAILABLE / muse_tp10 / branch null / pr null (board flip rides in this task's work PR): filed watch133 as the re-probe owed after INF-031 + INF-032; assigned watch143.

## Method (live leg)

- Fresh ~9k-token prompts through the live Inference routing path on FRIDAY-Server (bridge server 3, Inference on port 8001) via the confirmed `run_shell` grant (WATCH164, hub 7193691912; owner approval 2026-11-26 18:25 IST, approval 7113152293 CLOSED). Read-only timing probes only: no service restart, no deploy, no env flip, no server move, no live money.
- Measure per-prompt wall time and route taken; compare against the 60 s route deadline and the 15 s primary slice; check the >7000-token class explicitly (INF-032 board blocker + INF-033 bypass finding).
- Verdict: confirm 60 s or reset it, with numbers filed. If a reset is warranted, the change lands in `escalation.py` (+ gateway mirror named) with tests in the same work PR; if confirmed, evidence doc + board hunk only.
- One task = one PR at completion; peer full-diff review + fully green CI; never merge own PR. Paired verification by a different chat testing live behaviour before the task counts complete.

## Five states

implemented NO / tested NO / merged NO / deployed NO / production-verified NO.

## Next

Checkpoint 2: probe script + first live timing batch (serialized bridge use, coordinated on #1483). Work PR at completion.

— Muse TP10
