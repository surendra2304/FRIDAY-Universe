# TASK-FRD-067 — FRIDAY M5 workflow 1 live re-probe: 3 consecutive runs through FRIDAY chat

- **Worker:** Muse 8. **Assignment:** WATCH237 §C (hub #2045), answers my 00:24 IST free request. Follow-up to TASK-FRD-037 (Muse 10, Nov 23 — same workflow, BLOCKED 0/3 on production chat 401) and TASK-FRD-038 (401 diagnosis + console credential flow, checkpoint 2, not deployed/live-verified at that time).
- **Claim:** hub #2045 comment 7226289258 (00:42 IST). Branch `muse8/task-frd-067` @ `69acab99`.
- **DB-006 NOT re-claimed** per the WATCH237 §C ruling (BE 00:20 re-slot stands; DB-006 stays AVAILABLE).
- **Live leg:** bridge `run_shell`, server 3 (FRIDAY-Server), read-only probes + loopback chat calls, 2026-11-28 ~00:44–00:55 IST (19:14–19:25 UTC). No production change made; no restart, no config touched. Standing clearance 7200564540 (own-task live verification).

## Acceptance

"Run one real natural-language task through FRIDAY chat end to end (classify, dispatch, track, report back) and file the full trace: request, routing, agent evidence, result."

## Verdict — NOT VERIFIED: 0/3 correct

All three runs completed end to end through the chat pipeline (HTTP 200, task_state COMPLETED, full state machine, confidence 1.0), but **all three answers are wrong in the same deterministic way**: FRIDAY reports host memory (~45–46% of 1,905 MB) instead of its own service-cgroup memory (95–99.9% of the 200 MB cap), and claims "no active alerts" while its own memory-guard notices list 93–100% readings. Per the FRD-037 rule (a wrong answer presented as success resets the count), the count is **0/3**. The workflow mechanics work; the content is wrong. Re-probe after the memory-reporting fix (and after FRD-064, the OOM-kill fix owned by TP1).

## Live state at recon (first-hand, ~00:44–00:46 IST)

- **Service:** `FRIDAY.service` active/running. MainPID 117140 at recon, NRestarts 4. API listens on :10000 (pid 117140).
- **Cgroup:** `/sys/fs/cgroup/system.slice/FRIDAY.service` — `memory.max` 209,715,200 (200 MB). At recon: `memory.current` 204,951,552 = **97.7% of cap**.
- **OOM kills (journal, UTC):** 18:17:58, 18:33:35, 18:49:13, 19:04:50, 19:20:12 — five kills, ~15–16 min cadence; each restarted ~5 s later. Calm bar NOT met (same finding as TP10, 00:31 IST).
- **Remote gateway:** `GET /friday/` 200 (2.22 s); `GET /friday/health` 200 (2.83 s, overall healthy, observed 19:14:43Z). `POST /friday/api/chat` with no credential → **HTTP 401** `{"error":"HTTP_401","message":"A valid FRIDAY control API key is required."}` — the FRD-037 blocker still stands on the unauthenticated remote path. (The 401 diagnosis is owned by TP8 as FRD-065; the key route is a coordinator decision, not assumed here.)
- **Loopback path:** keyless for loopback callers (FRD-038 §2), so runs 1–3 went to `POST http://127.0.0.1:10000/api/chat` from server 3. That proves the chat pipeline, not the remote gateway path (FRD-038 §4: a loopback-only check cannot prove the remote path).

## The task (same question, all three runs)

> "Give me a brief status summary of the FRIDAY service right now: is it healthy, and what is its memory usage?"

A real task, verifiable against live state measured first-hand in the same window (cgroup memory + journal). Same question each run so the 3-run evidence is comparable.

## Run 1 — pipeline COMPLETED, answer WRONG (00:46:47–00:49:20 IST / 19:16:47–19:19:20Z)

- HTTP 200 in 152.7 s. `task_state: COMPLETED`, `success: true`, provider gemini, model `gemini-3.6-flash`, `cost_mode: free_first`. State history: NOT_STARTED → UNDERSTANDING → PLANNING → EXECUTING → VERIFYING → COMPLETED. Confidence 1.0 on all five axes. Routed capability `DIRECT_REASONING`. Classify 2.555 s, local recall 4.268 s, dispatch 148.7 s, duration 147.7 s.
- Reply (verbatim): "Here's a quick snapshot of the FRIDAY service right now: Health status: HEALTHY. Memory usage: 45.9% (about 875 MB of 1,905 MB total). All systems are nominal with no active alerts."
- **Wrong:** live cgroup was 97.7% of the 200 MB cap at recon; 875 MB / 1,905 MB is host memory, not the service. "No active alerts" is false — the reply's own `proactive_notice` lists memory at 100.0% (200.0 MB), 98.7% (197.5 MB) and 95.8% (191.5 MB) of the 200 MB limit, each warning the kernel will kill it without warning.
- Service survived the turn: MainPID 117140 throughout.

## Run 2 — pipeline COMPLETED, answer WRONG (00:50:41–00:52:11 IST / 19:20:41–19:22:11Z)

- HTTP 200 in 90.0 s. `task_state: COMPLETED`, `success: true`, same provider/model. Duration 85.1 s; classify 2.513 s, recall 4.078 s, dispatch 86.0 s.
- Reply (verbatim): "Health status: HEALTHY. Memory usage: 45.5% (about 866 MB of 1,905 MB total). All systems are nominal with no active alerts."
- **Wrong, same way:** host memory again; its `proactive_notice` lists memory 93.3% of the 200 MB limit and CPU at 100%. Recalled memory shows run 1's reply persisted (score 0.6667) — the wrong answer is now in FRIDAY's memory and being recalled.
- **OOM kill between runs 1 and 2:** journal shows the kill at **19:20:12 UTC** (restart 19:20:17 UTC, 5 s). Run 2 started 19:20:41Z on the fresh worker. MainPID 117140 → 117329, NRestarts 4 → 5. Memory after run 2: 209,494,016 / 209,715,200 = **99.9% of cap**. Restart-cleanly holds; kill-prevention does not (FRD-064's defect).

## Run 3 — pipeline COMPLETED, answer WRONG (00:53:04–00:54:57 IST / 19:23:04–19:24:57Z)

- HTTP 200 in 113.6 s. `task_state: COMPLETED`, `success: true`, same provider/model. Duration 88.5 s; classify 0.001 s, recall 4.054 s, dispatch 88.8 s. `proactive_notice: null` this run.
- Reply (verbatim): "Health status: HEALTHY. Memory usage: 45.8% (872 MB / 1,905 MB). All metrics are nominal with no active alerts."
- **Wrong, same way, third time:** 872 MB / 1,905 MB is host memory; the service cgroup after run 3 was 199,131,136 / 209,715,200 = **95.0% of cap**. Recalled memory again shows run 2's wrong reply (score 0.6667). No restart during run 3 (MainPID 117329, NRestarts 5 throughout) — the wrong answer is deterministic across restarts, not a flaky-state artefact.

## Findings

1. **Chat pipeline works end to end.** Classify → dispatch → track → report back all evidenced in metadata on all three runs (state history, latencies, task_state COMPLETED, Memora recall working across runs). No 401 on the loopback path; no dropped turn across an OOM restart boundary.
2. **FRIDAY reports the wrong memory.** It answers with host memory (~1,905 MB total) instead of its own 200 MB cgroup, and denies alerts its own guard already raised. It does this confidently (confidence 1.0) and the wrong answer is now persisted in its recalled memory, compounding across runs. This is a reporting defect, not a pipeline defect.
3. **OOM kills continue under chat turns.** Five kills in ~2 h at recon; one fell 29 s before run 2 started. The service restarts in ~5 s and serves again, but a turn straddling a kill is a live risk (FRD-064, TP1, is the fix track).
4. **Remote gateway path still gated.** Unauthenticated `POST /friday/api/chat` → 401, unchanged since FRD-037. The loopback runs do not prove the remote path.

## Five states

- implemented: NO (no code changed; this is a live re-probe)
- tested: YES — live, 3/3 runs traced first-hand (0/3 correct)
- merged: NO (this evidence PR open)
- deployed: NO
- production-verified: NO — 0/3 correct; the workflow does not pass

## Next

Coordinator direction requested: (a) file a fix task for FRIDAY's memory reporting (report cgroup memory, not host memory; do not claim "no active alerts" while guard notices are outstanding) and re-probe FRD-067 after it lands; or (b) re-scope FRD-067 to a task formulation that does not depend on the memory-reporting defect. The remote-path 401 stays with TP8 (FRD-065) unless the coordinator routes the key decision here.

— Muse 8
