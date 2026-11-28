# TASK-VOI-029 — Checkpoint 1: scoping (M5 workflow 5, session mechanism + evidence shape)

- Task: TASK-VOI-029 — Voice: prove M5 workflow 5, 3 consecutive live voice sessions (consumes the VOI-027 verdict)
- Owner: muse_6. Branch: `muse6/task-voi-029-m5-three-live-sessions`. Base: main `dfa2e8a9` (2026-11-27).
- Claimed: 2026-11-27 ~22:08 IST, per coordinator ruling WATCH230 §C.5 (hub #2045 comment 7223417776): "M6 — stays on VOI-027 head through next run's calm-window check; if still waiting then, M6 starts VOI-029 and VOI-027 drops to queue position 2." Calm-window check this run: still waiting (see §2). Claim posted hub #2045 (this run).
- Five states: implemented NO / tested NO / merged NO / deployed NO / production-verified NO (claim + scoping only).

## 1. Acceptance (board, live main `dfa2e8a9`, read first-hand)

- "Three consecutive live voice sessions with FRIDAY (speak, be understood, get spoken answers), each recorded with its trace and per-probe latency; a session that fails to converse resets the count. If the VOI-027 calm-window verdict is negative, fix the cause first and re-prove."
- Board record: status AVAILABLE, owner muse_6, branch null, pr null, priority P1, `next_action: 'Queued pos 3 for muse_6 (behind REL-104, VOI-027).'` (flip to CLAIMED rides the next board PR; board PR #2151 shipped this run per WATCH230 §B, merge owed next run).
- M5 definition (`docs/MASTER_PLAN.md` §M5, read first-hand): the five core workflows are (1) chat conversation with FRIDAY, (2) research with sources via IntelX, (3) memory recall across sessions via Memora, (4) a Forge code build from a FRIDAY request, (5) a voice session. "A workflow counts as proven only after **3 consecutive successful live runs on production, each recorded with its trace** (request, routing, agent evidence, result) in ACTIVITY_LOG/handoff records. A silent failure — a wrong answer presented as success, a dropped result, a fabricated status — resets that workflow's count."

## 2. VOI-027 verdict dependency — how the start is ruled

- VOI-027 calm-window verdict filed 2026-11-27 08:08 IST on hub #2045 comment 7208389980 (verified by read-back): **NOT RUN — unproven.** No decomposition filed, no verdict on the board, no VOI-027 commit on branch @ `44cb0cef`, no main commit since 2026-11-26 records a calm-window run or verdict. VOI-026 MERGED (PR #1208), live; 8 s bar unproven on a calm run.
- Calm-window check this run (22:08 IST): still waiting. Hub #2045 read through comment 7223532220 (592 comments): no Surendra voice call reported anywhere; no VOI-027 evidence; WATCH228 (7222477145), WATCH229 (7223011500), WATCH230 (7223417776) and Burn Enforcer 21:28 (7222716768) / 21:58 (7223408571) read in full — no calm-window call, no new VOI-027 direction. VOI-027 branch @ `44cb0cef` unchanged (ls-remote). No main commit since `06b32a81` touches VOI-027 (merges #2165/#2164/#2163/#2157/#2152/#2148/#2154). The call itself is owed by Surendra only; P0 voice-note ruling (WATCH094) still owed.
- The acceptance's "if negative, fix first" clause does NOT trigger: the verdict is unproven, not negative. WATCH230 §C.5 rules the start anyway — VOI-029 begins now, VOI-027 drops to queue position 2 and its calm-window verdict remains owed. When that verdict lands, its outcome feeds the sessions: a negative verdict means fix-first per the acceptance before the count can stand.
- Prior holder: Muse 1 claimed VOI-029 2026-11-27 07:35 IST (hub 7207821435), branch `muse1/task-voi-029-m5-three-live-sessions` @ `ed178145` (ls-remote; head commit message "VOI-029: evidence doc — claim + VOI-027 verdict check (run-27 PASS operative), 0/3 sessions"). That branch's contents were NOT read, checked out, or adopted this run (fetch tripped an execution-risk flag; no checkout, no copy). M1's "run-27 PASS" reading in that commit message is NOT the VOI-027 verdict — the filed verdict (NOT RUN, hub 7208389980) stands, confirmed by WATCH198 §4, WATCH227 §C, and WATCH230 §C.5. Board note: "Fresh branch + new work PR when claimed" (watch130 re-slot) — this claim uses a fresh `muse6/` branch, as ruled.

## 3. Session mechanism — what is known first-hand, what is open

Known (verified first-hand on live main `dfa2e8a9` / repo records):

- Voice stack (standing): FRIDAY voice runs on LiveKit Cloud; Gemini Live is the only voice AI. Voice is judged on SPEED first.
- Owner route (MASTER_PLAN §M5 context, line 43): the owner can open `https://friday-universe.duckdns.org/friday/` in a browser and talk to FRIDAY.
- Live wiring (repo `AGENTS.md`, read this run): production is systemd + Caddy on two Oracle VMs; FRIDAY on Server 1 :10000; public ingress `https://friday-universe.duckdns.org`, Caddy path-routes `/friday` to the local port. "Verify a route in OpenAPI before relying on it."
- Precedent — M1 VOI-030 acceptance run 17 (PR #2100, paired verdict VERIFIED filed by Muse 6 as review 6085510230, ~14:11 IST): 1 commit `f377d083`, 1 file +198/-0 evidence-only; CI 9/9; all 7 `FRIDAY/voice_acceptance/` preflight md5s re-derived exact vs main `25ce04a3`; greeting 0.58 s < 8 s bar, all 7 latencies inside limits. Limit carried: the live journal on FRIDAY-Server cannot be re-derived from this VM (no bridge route) — taken as filed by M1.
- Precedent — M1 VOI-030 run-20 / M17 FRD-051 leg-5: live voice sessions were executed and recorded with traces and latencies; the session-evidence shape (trace + per-probe latency, live journal) is the pattern VOI-029 follows. The exact probe commands used for those runs are the open item below.

Open (not yet verified — no live move made from this VM):

- §3.1 Who speaks in each session: an owner voice call, or a worker-run probe client against the LiveKit/Gemini Live path? The VOI-027 acceptance needs Surendra's call; whether VOI-029 sessions can run without one is UNVERIFIED.
- §3.2 The exact session probe commands and the trace/latency capture route (live journal on FRIDAY-Server vs a probe-side record). No bridge client copy and no bridge key on this VM — live legs stay coordinator-side via bridge run_shell under standing clearance 7200564540 (grant settled per WATCH224 §C / WATCH230 §C.5 context), or per-sandbox registration (TP6 7211823359; M16 failed 403). Same position as REL-104 checkpoint 1.
- §3.3 Whether the three sessions must run on consecutive days or back-to-back in one window: the acceptance says "3 consecutive live voice sessions" and M5 says "3 consecutive successful live runs" — consecutive in count (a failed session resets the count), not necessarily in wall-clock time. Stated as read; a coordinator ruling is owed only if the sequencing is disputed.

## 4. Evidence shape per session (what counts)

Per session, filed in the checkpoint-2 evidence doc + ACTIVITY_LOG/handoff records per M5:

- Session identity (date/time, run number 1–3, count state before/after), the spoken request, FRIDAY's spoken answer, and whether the session conversed end-to-end (speak → be understood → get a spoken answer).
- Trace: request, routing, agent evidence, result (M5 §3 form).
- Per-probe latency: greeting-onset latency against the 8 s bar (VOI-026/VOI-027 precedent), plus the per-probe latencies the VOI-030 evidence carries.
- A session that fails to converse resets the count to 0 — the reset is recorded, not hidden.

## 5. Blockers and risks (stated, not solved here)

- FRIDAY stability: TP1 FRD-064 checkpoint 6 (hub 7222945101, ~21:40 IST) — no seventh OOM kill, FRIDAY stable 1h24m since 14:42 UTC; swap still watched. The FRD-064 fix PR is still owed (WATCH229 §F / WATCH230 §F.6); VOI-045 firing stays HELD until it lands. The same OOM fragility applies to live voice sessions — a mid-session kill fails that session and resets the count.
- Server-move freeze: WATCH174 (a) still stands — re-sync + service restarts DENIED while the freeze stands. Any session that needs a restart or re-sync needs separate clearance.
- No live move from this VM: no bridge route (see §3.2). Checkpoint 2 carries the session plan; live sessions are owed coordinator-side or once a route is settled.
- VOI-027 calm-window verdict still owed (call by Surendra only).

## 6. Next

- Checkpoint 2: session plan — the §3.1/§3.2 answers (who speaks, exact probe commands, trace capture route), then session 1 attempt once the mechanism and route are settled. Work PR follows checkpoint 2 (rule 1: checkpoint first, PR follows implementation).
- Hourly self-check 23:08 IST; VOI-027 calm-window watch continues (next check 23:08 IST, queue position 2).
