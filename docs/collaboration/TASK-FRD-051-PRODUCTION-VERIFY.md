# TASK-FRD-051 — PRODUCTION-VERIFY: FRIDAY corpus items IG-FRD-001..005 (live, wave 2)

- **Owner:** muse_17. **Status:** work PR filed; close ruling owed by coordinator (PARTIAL expected: 3 VERIFIED, 2 NOT VERIFIED with named fix tasks).
- **Claim:** hub #1483 comment 7200622902 (~00:03 IST 2026-11-27). **Branch:** `muse17/frd-051` (created from main `b74efa00ca91454104b74a8e652df55888d157d8`, fast-forwarded to main `bf3c76c9f20d1cb5f2bfd0adb08eac756bb54620` before filing; no commits on the branch before this record).
- **Target:** live FRIDAY service on FRIDAY-Server (bridge server 3, 15.134.130.145), loopback `POST /api/chat` (keyless on loopback), uvicorn `:10000`.
- **Board record:** TASK-FRD-051, IN_PROGRESS/muse_17 on main `bf3c76c9` (verified first-hand). No WORK_BOARD.yaml hunk in this PR (WATCH182 §2b — board flips are coordinator-only).
- **Close basis:** live evidence per item below. Code-only report rejected by the acceptance; every verdict below is a live run on FRIDAY-Server.

## Verdicts

### IG-FRD-001 (goal loop) — NOT VERIFIED
- Attempt 1 (~03:44 IST): loopback POST /api/chat, HTTP 200 in 15.2s. Agent answered a fleet-status matrix instead of invoking `start_goal_loop`; note file never created.
- Attempt 2: explicit "Use the start_goal_loop tool now", goal: save `FRIDAY-10000-OK` to `/tmp/m17-frd051-goal-note.txt`, max 3 cycles. Loop `goal-90e54d3f66` created live, ran 2/3 cycles, terminal: BLOCKED. Both criteria UNMET; all 6 steps failed — the engine's own step instructions were rejected by its own command allowlist ("Command 'work'/'for' is not allowed"). Note file never created. Chat turn hung the full 300s timeout though the loop finished in <1s.
- Evidence: `/opt/friday_universe/FRIDAY/.data/goal_loops/loops.json` (loop record), `/tmp/m17-frd051-item1b.txt` (attempt 2 response).
- **Fix task named: TASK-IG-FRD-001-FIX-01** (engine step-allowlist + chat-turn timeout). Assigned M17 queue pos 2 per WATCH189.

### IG-FRD-002 (persistent follow-up tracking) — VERIFIED (live)
- Follow-up `fu-e1ca97aa6d` added via chat (`followup_add`, explicit phrasing), created 22:44:49 UTC in `FRIDAY/.data/followups/registry.json` (title "M17 FRD-051 item 2 probe - check VyralX metrics", due +1h, status open). Registry file did not exist before — clean slate.
- Survived restart: FRIDAY.service OOM-killed 22:46:41 UTC, systemd auto-restart (pid 70495, up 22:47:03). `/health` 200 in 1.06s. Registry re-read post-restart: record still open.
- Memora mirror verified independently: authed GET `https://friday-universe.duckdns.org/memora/v1/memories/02a9ffbf-737d-4a85-a12c-f93ef124c54f` returns episodic record, category `followup`, content "FOLLOWUP (open): M17 FRD-051 item 2 probe … [id fu-e1ca97aa6d]", created 22:44:50 UTC. Unauthed GET is 401 (expected).
- Probe closed after verification via `followup_complete` (record now done, 2 history events, mirror ok). No open probe left.
- Latency: chat add ~136s wall (effect 22:44:49 UTC); turn never returned inside the 135s bridge cap. Mirror GET 0.80s.

### IG-FRD-003 (job-hunt workflow) — NOT VERIFIED
- Probe profile (marked, no personal data) at `FRIDAY/.data/job_hunt/profile.json`: skills python/fastapi, target software engineer, remote; `career_pages` = 2 live Greenhouse postings (GitLab 8623389002, Canonical 2413329) + 1 dead URL.
- Chat turn, natural phrasing: HTTP 200 in 128.3s, task COMPLETED, reply "0 postings / 0 shortlist", dead URL honestly `fetch_failed` 404; `last_scan.json` on disk (total 0, shortlist []), no drafts dir (correct — prep needs a non-empty shortlist). Direct workflow run reproduced 0/0.
- Root cause: extractor reads only `application/ld+json` JobPosting; the live GitLab posting page (116,902B, real SRE posting) carries 0 LD-JSON blocks (JS-rendered shell) and board indexes carry 0 too.
- Explicit "Use the job_hunt_scan tool now" phrasing routed to DIRECT_REASONING; tool executed only after ~6.5 min; HTTP never returned within 280s (client timeout) — same chat-turn latency defect class as TASK-IG-FRD-001-FIX-01.
- **Fix task named: TASK-IG-FRD-003-FIX-01** (extractor must handle current Greenhouse markup / supported-hosts honesty).

### IG-FRD-004 (delegated-errand framework) — VERIFIED (live)
- (1) Sample errand created via chat: loopback POST `/api/chat` on FRIDAY-Server (pid 75069), `errand_create` named explicitly — errand `errand-58f952012f` (framework_only true, budget cap 0.0), step s1 external/channel message, state awaiting_approval; store verified independently at `FRIDAY/FRIDAY/.data/errands/errands.json` (doubled path — see findings). Turn 123.5s.
- (2) Approval gate refused the run: `errand_run` before approval → history event `run_blocked_unapproved` (s1), step stayed awaiting_approval, result null.
- (3) Approved: `errand_approve` s1 → history `step_approved` by owner, committed spend 0.0 of cap 0.0.
- (4) Run: `errand_run` → history `step_executed_dry_run`, step state `executed_dry_run`, result `dry_run: true, executed: false`, note "FRAMEWORK ONLY: no real channel is connected, so nothing was sent, called, or paid."
- (5) Summary: `errand_status` → Complete, 1 step executed as a dry run, "no real-world actions were taken… executed through a dry-run channel, which recorded the intent without actually sending any messages." Nothing real sent, called, or paid.

### IG-FRD-005 (workflow templates) — VERIFIED (live)
- Turn 1 (~06:06 IST): explicit `workflow_template_list` phrasing, HTTP 200 in 58.2s — routed DIRECT_REASONING, agent refused ("can't run `workflow_template_list` at the moment"). No tool call. Same routing-flakiness class as TASK-IG-FRD-001-FIX-01 (see findings). Tool IS registered in the live code (`friday/agent/mixins/tools.py:287-288`).
- Turn 2 (~06:09 IST): clean rephrase ("Show me your ready-made workflow templates…"), HTTP 200 in 59.6s, iterations 2, EXECUTING — tool ran. All 6 templates listed with correct ids, step counts and params, matching `FRIDAY/src/friday/workflows/templates.py`: `content_batch` (3 steps), `social_draft_pack` (2), `business_morning_ops` (3, param `focus`), `research_brief` (2), `job_hunt_daily` (2, param `min_score`), `weekly_review` (3, param `week_of`).
- Turn 3 (~06:12 IST): "Run the business_morning_ops template with focus M17 FRD-051 probe, and enqueue its steps as missions", HTTP 200 in 85.4s, iterations 3, EXECUTING. Reply: 3 steps executed, enqueued as missions `m_215ebc0015f6`, `m_0b57d154603f`, `m_dc0dca5fa171`.
- Queue verified independently on disk: `FRIDAY/.data/missions/queue.json` (created 00:43 UTC, clean slate — dir was empty before), 3 missions, source `workflow_template`, status `pending`, `created_ist` 2026-11-27T06:13:27. All 3 ids match the reply exactly. Correct path this time (no doubled-path fallback).
- Failure case (enqueue honesty): turn 4 (~06:17 IST), template id `nonexistent_template_xyz` with enqueue — HTTP 200 in 59.5s, agent honestly reported "The workflow template with the id `nonexistent_template_xyz` does not exist" and listed the 6 real templates. Queue re-checked: still exactly the same 3 missions, unchanged. No invented missions.
- FRIDAY.service pid 75069 stable through all item-5 turns (no OOM kill this leg).

## Failure injection (task acceptance: a downstream agent down)
- Injected 2026-11-27 ~06:22 IST: `FRIDAY-Voice.service` (LiveKit voice agent worker, pid 58831, up 18h) stopped on FRIDAY-Server. Verified inactive, old pid gone. FRIDAY.service untouched (pid 75069, active).
- Probe while down (~06:22 IST): chat turn "Can you talk to me by voice right now?", HTTP 200 in 52.6s. Reply: "I don't have a way to check the real-time voice subsystem right now, so I can't confirm that a spoken channel is active. At the moment I'm only able to reply in text." No false voice claim; text chat kept working with the voice worker down (graceful degradation). Note: FRIDAY cannot sense the voice subsystem state directly — it answered from that limitation honestly rather than inventing a status.
- Restored ~06:25 IST: service restarted, verified active with new pid 78200 (checked 00:55:53 UTC); FRIDAY.service still active pid 75069. Downtime ~3m21s. Voice was already P0 NOT WORKING (owner test 2026-11-26) before the injection, so no owner-facing capability was lost.
- Observed (not injected) failure, same class: FRIDAY.service OOM-killed under chat turns during legs 2 and 4 (restart counter 3; twice more ~23:34 UTC pid 70495→73891 and ~23:51 UTC 73891→75069). Follow-up registry and errand store both survived auto-restart — see TASK-FRD-052 draft below.

## Live findings routed to Muse (not item failures)
1. FRIDAY.service OOM-killed under chat turns, repeatedly (legs 2, 4) — see TASK-FRD-052 draft.
2. Errand store lands at `FRIDAY/FRIDAY/.data/errands/errands.json` (doubled path; same cwd-relative class as the leg-2 followup-registry fallback) — one-line fix in the same routing.
3. Chat-turn routing flaky: turns answer via DIRECT_REASONING without invoking the named tool (legs 1, 3, 4, 5-turn-1); a clean rephrase usually executes. Same defect class as TASK-IG-FRD-001-FIX-01.
4. Chat-turn latency: turns take 52–136s wall; one turn (leg 1, attempt 2) hung the full 300s client timeout though the loop finished in <1s; one turn (leg 3) never returned within 280s.
5. Bridge transport blipped ~04:0x IST (3 failed handshakes, recovered in minutes). Bridge `run_shell` calls intermittently return NO RESULT PARSED with SSE pings (~60–90s) though the server-side command keeps running — background + poll is the working pattern.

## Fix tasks named (filed from this record; no board record owed per WATCH189)
- **TASK-IG-FRD-001-FIX-01** — engine step-allowlist rejects the engine's own step instructions ("Command 'work'/'for' is not allowed") + chat-turn timeout (300s hang on a <1s loop). Assigned M17 queue pos 2 per WATCH189.
- **TASK-IG-FRD-003-FIX-01** — job-hunt extractor reads only `application/ld+json` JobPosting; live Greenhouse pages carry none (JS-rendered shell) → 0/0 on real postings; supported-hosts honesty owed.

## Draft for the pool (coordinator to file on next board PR)
- **TASK-FRD-052 (draft)** — Investigate + fix FRIDAY.service OOM-kills under chat turns (200M memory peak, restart counter 3+; killed mid-verification in legs 2 and 4; auto-restart recovers but the owner-facing assistant dying under a chat turn is a real defect). Evidence: this record + hub verdicts 7205056708, 7205437623, 7206115187. Owed to the pool per WATCH189/WATCH190.

## Queue
- FRD-051 done on live evidence (this PR). Pre-staged next: VYR-085 (double-scope). IG-FRD-001-FIX-01 assigned M17 queue pos 2 per WATCH189 — board to confirm order (VYR-085 vs FIX-01) on the next board PR.
- STR-074 verifier duty (M17 verifies TP4's STR-074 when its work PR opens) still armed; TP4 moved to TASK-OPS-004 (DB-005 merged, PR #2029 merge 4d69af89) — no STR-074 work PR open as of this filing.

## Hub verdicts (all verified by read-back)
- Leg 1 (IG-FRD-001 NOT VERIFIED): #1483 comment 7204657068.
- Leg 2 (IG-FRD-002 VERIFIED): #1483 comment 7205056708 (timestamp correction 7205062272).
- Leg 3 (IG-FRD-003 NOT VERIFIED): #1483 comment 7205437623.
- Leg 4 (IG-FRD-004 VERIFIED): #1483 comment 7206115187.
- Leg 5 (IG-FRD-005 VERIFIED) + failure injection: hub comment filed with this run (see PR comments).
