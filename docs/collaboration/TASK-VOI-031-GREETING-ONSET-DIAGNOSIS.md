# TASK-VOI-031 — FRIDAY voice: greeting-onset diagnosis (acceptance run 16, both arms)

**Worker:** Muse 15. **Claim:** hub #1483 comment 7167342824 (TASK-VOI-039
completion post), 2026-11-25 ~21:19 IST, per coordinator WATCH104 (hub
#1483 comment 7166508436, queue VOI-039 → VOI-031 → FRD-043 (HELD)).
**Branch:** `muse15/task-voi-031-greeting-onset-diagnosis` from main
`0eeaa43a`, rebased onto current main `bdb6a0fa` at filing.
**Board:** main `bdb6a0fa`; VOI-031 verified AVAILABLE, owner muse_15,
branch null, pr null, before the flip in this PR (assignment to muse_15
rode in coordinator board PR #1866, WATCH107).

## 1. The task

Title: *"Voice: diagnose greeting onset missing the 8s bar on a calm box
(acceptance run 16, both arms) — first-audio latency root cause plus fix."*
Acceptance: *"Onset path timed per stage on a calm box; root cause filed;
fix or mitigation landed with per-probe greeting-onset numbers under the
8s bar."*

This is a diagnosis-and-proof task, not a code task. The fix it asks
about already exists (VOI-028, §3) — what was still owed was the
calm-box per-stage proof that the fix works, which this doc files.

## 2. The defect — run 16 (2026-11-19), VOI-024 A/B arms

Greeting onset missed the 8s bar on a calm box in **both arms**:
**11.3 s / 17.0 s**. A load-independent defect, separate from the
send-cadence collapse that run 16 also convicted (board records for
TASK-VOI-026 and TASK-VOI-028; no run-16 evidence doc exists in the repo
and run-16 per-stage numbers were never filed — see §7).

## 3. Root cause — filed by TASK-VOI-026 (Muse 6, PR #1208, merged `b4837aac`)

Diagnosis (code + library source, local measurements 2026-11-21 ~19:00
IST, production pins livekit-agents 1.8.11 / livekit-plugins-google 1.8.10
/ google-genai 2.33.0), quoted from the VOI-026 board record:

1. Local construction is ~0.01 s (RealtimeModel + Agent + AgentSession)
   — the VOI-011 1.1–5.1 s was host-condition cost, not intrinsic;
   construction exonerated as a code cost.
2. `pre_connect_audio_timeout=3.0` does NOT add 3 s in the normal path
   — livekit-agents 1.8.11 only waits for the pre-connect buffer when
   the client sends a byte stream with the TF_PRECONNECT_BUFFER feature;
   exonerated by library source.
3. The Gemini Live websocket connect runs in the plugin's background
   `_main_task` and is NOT awaited by `sess.start()` — the Live
   handshake is not on the greeting path.
4. **PRIME SUSPECT (confirmed by local demonstration): the greeting is
   gated on session-listening with a 5 s cap, but the cap is an
   `asyncio.wait_for` timeout — it fires only when the job loop
   iterates.** A 0.5 s cap under a 2.0 s loop block resolves at ~2.05 s,
   not 0.5 s. On the ~87%-swapped voice host the same stall stretches
   the cap with `sess.start()`, so the line fires when the session
   starts (~11–17 s), not at the cap — which reconciles the 5 s cap
   with the 11.3 s / 17.0 s onsets in BOTH A/B arms (both arms share
   the start path).
5. The model is built twice per job (`_try_gemini_realtime` proof +
   `_make_session`) — negligible healthy (~0.01 s each), noted only.

## 4. The fix — TASK-VOI-028 (Muse 2, PR #1397, merged `60e09844`)

Fix in `FRIDAY/src/friday/voice/livekit_worker.py`:

1. The first `_make_session` call reuses the proof model via
   `artifacts={"model": _proof_model}`, eliminating the duplicate
   RealtimeModel construction.
2. `_make_session` yields the loop (`await asyncio.sleep(0)`) after the
   `Agent()` construction and after the model build, before the
   `AgentSession` construction, so the greeting task's gate timer fires
   on wall-clock time during the synchronous build.

Regression coverage: `FRIDAY/tests/test_voice_greeting_onset_voi028.py`
4/4 pass; VOI-026 suite still 10/10 on the edited worker; both suites
added to the CI voice-regressions list. Deployed via fleet CD at
`e4c78c04` (FRIDAY-Voice restarted 00:13:46 IST, Nov 23; fix markers in
the running worker, Muse 2 probe hub 7083938049).

## 5. Fix verified live on FRIDAY-Server — 2026-11-25 ~22:05 IST (read-only, first-hand)

Bridge `run_shell` on Oracle Server 2 → `ssh` to FRIDAY-Server
(15.134.130.145). Host calm at probe time: load **0.10 / 0.14 / 0.16**,
1004 MB available. No participant process running (worker idle).

- **Fix markers present in the deployed worker code**
  (`/opt/friday_universe/FRIDAY/src/friday/voice/livekit_worker.py`):
  `_proof_model` reuse at lines 3793/3799/3809
  (`artifacts={"model": _proof_model}`); `await asyncio.sleep(0)` yields
  at lines 3588/3594 with `TASK-VOI-028` comments.
- **Deployed checkout history contains the fix:** `git log` on
  `/opt/friday_universe` shows merge `60e09844` (PR #1397) as an
  ancestor of the deployed checkout head `5b245ffd` (merge #1632).
- **Running worker postdates the fix deploy:** FRIDAY-Voice.service
  active, NRestarts 0, MemoryCurrent 266,477,568,
  ActiveEnterTimestamp Tue 2026-11-24 07:21:18 UTC (12:51 IST Nov 24)
  — after the Nov 23 VOI-028 deploy. The running worker includes the
  fix. (VOI-043, merged Nov 25 20:39 IST, is NOT in this worker — the
  worker predates it; that is expected and out of scope here.)

## 6. Onset path timed per stage on a calm box — two runs tonight

No new probe was launched for this task: two independent calm-box runs
already ran tonight on the same live build, and the single
FRIDAY-Voice worker is next needed by Muse 1's VOI-040 (run 25). Both
timelines were read first-hand from FRIDAY-Server
(`/tmp/frd005/runs/<dir>/<room>_timeline.json`) and both jobs'
server-side decomposition lines from the FRIDAY-Voice journal.

### 6a. Participant-side stages (LiveKit connect → first audio frame)

| Stage | Run 24 (VOI-039) | Run 18 (VOI-033, Muse 1) |
|-------|------------------|---------------------------|
| Room / job | `friday-frd005-20261125-152842` / `AJ_6j9wd8BQ7vmY` | `friday-frd005-20261125-154327` / `AJ_BCUYjraAnTNJ` |
| Launched (IST) | 20:58:42, host load 0.14 | 21:13, calm re-confirmed (Muse 1, hub 7167826439) |
| connect → mic published | 0.044 s | 0.042 s |
| connect → agent joined | 0.378 s | 0.548 s |
| agent joined → first audio track | 0.140 s | 0.147 s |
| first audio track → first audio frame | 0.006 s | 0.005 s |
| **connect → first audio (greeting onset)** | **0.524 s** | **0.700 s** |
| Bar / verdict | 8.0 s / **PASS** | 8.0 s / **PASS** |

The previously suspect zone — agent-joined → first audio, i.e. the
session build plus the listening gate — is **0.14–0.15 s** in both
runs, against the 11.3 s / 17.0 s run-16 onsets. Total onset is 6.5–
8.7% of the 8 s bar.

### 6b. Server-side VOI-026 decomposition lines (FRIDAY-Voice journal)

Both jobs, identical (from `_play_early_greeting_line`,
`livekit_worker.py:3735`):

> `VOICE greeting onset decomposition (TASK-VOI-026): job-to-connect
> 0.11s, connect-to-key 0.00s, key-to-participant 0.00s,
> participant-to-gate 0.30s, gate LISTENING after 0.00s,
> connect-to-first-audio 0.30s`

Run 24 job `AJ_6j9wd8BQ7vmY` at 15:28:46 UTC (20:58:46 IST); run 18
job `AJ_BCUYjraAnTNJ` at 15:43:30 UTC (21:13:30 IST). **The listening
gate resolved LISTENING after 0.00 s in both jobs** — the VOI-026
failure mode (gate cap stretching with the session build) is gone on
the live build. The 0.30 s server-side connect-to-first-audio vs the
0.52 s / 0.70 s participant-side onset is the participant's LiveKit
connect + agent-join leg (§6a, first two rows).

### 6c. Third data point — run 23 (VOI-038, 2026-11-24)

Greeting onset **0.67 s** vs the 8 s bar, PASS (holding line
"Still waiting on those Stratex details…" — the gap measures onset,
not content). Three calm-box runs on the post-VOI-028 build:
0.67 s / 0.52 s / 0.70 s — all under the bar with ~10× margin.

## 7. Caveats — read before citing the verdict

- **Run-16 per-stage numbers were never recovered.** No run-16
  evidence doc exists in the repo and the board record already notes
  run-16 per-stage numbers are not in the repo. The root-cause chain
  therefore rests on VOI-026's local demonstration (a 0.5 s cap under
  a 2.0 s loop block resolving at ~2.05 s) plus the fixed behaviour
  measured live (§6) — not on recovered run-16 stage data. The
  11.3 s / 17.0 s run-16 totals are cited from the VOI-026 / VOI-028
  board records.
- **No new probe run was launched for VOI-031** (§6 intro). The
  per-stage proof comes from runs 24 and 18, both tonight, both
  calm-box, both read first-hand from the live timelines and journal.
- **The fix is VOI-028's, not this task's.** This PR lands the
  diagnosis + the calm-box proof. No code in this PR changes the voice
  path; no live restart, deploy, or fleet write happened in this run
  (read-only bridge probes only; one bridge transport drop on the
  journal read, retried once as a read — nothing was claimed from the
  failed attempt).
- **Scope is onset only.** Content correctness of the greeting and
  later turns is NOT verified here — runs 24 and 18 both scored
  content FAIL on the scorer's order-based attribution (see the
  run-24 / run-18 evidence docs). The 8 s bar measures first audio,
  and first audio is what VOI-031 asks for.

## 8. Verdict

**TASK-VOI-031 COMPLETE — run-16 greeting-onset defect CLOSED.**
Root cause filed (VOI-026, §3); fix landed and live (VOI-028, §4–5);
onset path timed per stage on a calm box with per-probe numbers under
the 8 s bar (0.52 s run 24, 0.70 s run 18, 0.67 s run 23; gate
LISTENING after 0.00 s both jobs). The sibling proof tasks VOI-027
(Muse 6) and VOI-030 (Muse 13) remain CLAIMED with no PR — their
acceptance is now satisfied by the numbers in §6, and the coordinator
may close them on this evidence.

## 9. States

- implemented YES (diagnosis + calm-box proof filed; fix VOI-028
  already merged and deployed) / tested YES (two live calm-box runs
  read first-hand tonight + run 23 on record) / merged NO (work PR
  open, merge is Muse's — workers never merge own PRs) / deployed YES
  (VOI-028 fix verified live in the running worker, §5) /
  production-verified YES (onset 0.52–0.70 s vs the 8 s bar on the
  live build; scope is onset only, §7).
- Usage: 30% of free weekly limit (checked live this run via
  subscription-status; reset Nov 30, 7:04 PM IST). Additional tokens
  0% used.
- Queue: VOI-031 done; FRD-043 stays HELD (no deploy clearance; fleet
  CD broken, owner stop order). No next task of mine is available —
  free, requesting work; work-request cron re-armed on completion.
