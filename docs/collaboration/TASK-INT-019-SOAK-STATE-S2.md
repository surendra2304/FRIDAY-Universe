# TASK-INT-019 — INT-876 soak state onto S2 + one traced IntelX → Memora universal → FRIDAY consumption (PARTIAL — repo-side legs done, S2 live legs blocked)

**Worker:** Muse 16. **Claim:** issue #1483 comment 7119132656, 2026-11-24 ~06:58 IST, head of queue after TASK-VYR-048 merged (work PR #1582, merge 08453024). **Branch:** `muse16/task-int-019-soak-state-s2`. **Base:** main 1c754828. **Work PR:** #1606 (claim PR converted; this doc + board flip CLAIMED → IN_REVIEW ride in it).

**Status of this document:** PARTIAL FILING. The repo-side legs are verified first-hand and filed here. The S2 live legs — timer install, day-4 09:30 run observation, traced live consumption — are BLOCKED on bridge access (approval request to Muse, hub comment 7113152293, still open, no reply) and on Muse's hub clearance for the timer install (a fleet mutation). Nothing live on S2 is claimed verified in this document. The live procedure for those legs is written out in §5 so the next run with an approved connection can execute it without re-deriving it.

Five states: implemented PARTIAL (repo-side verification + live procedure done; S2 install + live trace not done) / tested PARTIAL (runner failure modes tested locally, §3; no live run tested) / merged NO (PR #1606 open) / deployed NO (timer not installed on S2) / production-verified NO.

## 1. Soak state location — verified in the repo

The soak runner was defined by TASK-INT-032 (Muse 7, work PR #1553, merge b63d0f30) and is on main 1c754828:

| Piece | File on main | What it is |
|---|---|---|
| Runner script | `IntelX/scripts/run_int876_soak.py` (216 lines) | Stdlib-only. POSTs `research_live` to local IntelX (`POST /v1/task/execute`, `task_id` `soak-876-YYYY-MM-DD`), writes the day record. Exit 0 = run observed and recorded (even DEGRADED); 2 = no run could be triggered; 3 = day record unwritable. Refuses a second run for the same date unless `--force`. |
| Unit | `deploy/intelx-soak-runner.service` (28 lines) | `Type=oneshot`, `WorkingDirectory=/opt/friday_universe`, `EnvironmentFile=/opt/friday_universe/IntelX/.env` (fleet key `FRIDAY_API_KEY`; never printed/logged), `ExecStart` = fleet venv python + the script, `User=ubuntu`, `StateDirectory=friday-universe`. |
| Timer | `deploy/intelx-soak-runner.timer` (18 lines) | `OnCalendar=*-*-* 09:30:00`, `Persistent=true`, `AccuracySec=30s`. S2 local time is IST, so this is the 09:30 IST slot. |
| Day record | `/var/lib/friday-universe/intelx-soak/YYYY-MM-DD.json` on S2 | Run time (IST+UTC), `task_id`, `run_id`, envelope status, synthesis status/reason, source/finding counts, summary, delivery path (archive recall URL + record path), `pass` boolean. A day passes iff the envelope status is `SUCCESS`. |
| Durable run record | IntelX live research archive (Oracle-backed) | The run itself, recallable at `GET /v1/research/live/{run_id}`. |

**S2 install state (from INT-032, verified first-hand on S2 via the bridge 2026-11-24 ~00:26–00:51 IST):** NO soak timer/cron/unit/file exists on S2 — the timer is defined in the repo but not installed or enabled. Install facts verified then: `IntelX.service` reads `EnvironmentFile=/opt/friday_universe/IntelX/.env` (exists, 0600, carries the `FRIDAY_API_KEY` name — name only, value never read), fleet venv python exists at `/opt/friday_universe/venv/bin/python`, `/var/lib/friday-universe` exists, IntelX `/healthz` 200. Only the install/enable step itself remains. **That install is a fleet mutation and is NOT done in this run: it needs Muse's hub clearance, and this worker has no approved bridge connection to perform it with.**

The first soak chain (4 days) was lost in the 2026-11-20 sandbox workspace cleanup; the chain restarted 2026-11-21. Until the timer is installed on S2, the chain still lives only in coordinator status lines + the live archive — a sandbox cleanup can still burn the day records. That is the gap this task exists to close, and it is not closed yet.

## 2. The 2026-11-27 D4 chain — verified from the filed evidence (INT-023 + INT-035)

Chain days, from the merged evidence (INT-023 interim, PR #1460; INT-035 initial pack, PR #1572, merge e261ca17):

| Day | Date | 09:30 run observed? | Verdict |
|-----|------|---------------------|---------|
| 1 | 2026-11-21 | Not verifiable | Coordinator-asserted only (hub 7058036493, 7060081284). Zero runs in the live archive on 2026-11-21; journal gone. |
| 2 | 2026-11-22 | No | No 09:30 run in archive or journal. Only off-schedule DEGRADED runs (22:53–23:28 IST), synthesis failed. The INT-019 board evidence's "day 2 recorded" assertion has no discoverable source. |
| 3 | 2026-11-23 | No | No 09:30 run. Three 09:00 FRIDAY-chat runs, all DEGRADED (`synthesis_entailment_unverified`, 15/15 single-source findings). IntelX /health 503 degraded. |
| 4 | 2026-11-24 | Not yet run at filing | 09:30 slot ~2h after this filing (~07:14 IST). **No automatic run will fire: the timer is not installed on S2.** |
| 5–7 | 2026-11-25 → 2026-11-27 | Not yet due | Day 7 = judgement day (2026-11-27). |

**What changed for the better:** the systematic synthesis failure is gone from the live path. INF-028 deployed live 2026-11-24 01:05:58 IST (IntelX.service restart, MainPID 605920 → 622490); five live runs 01:18–01:43 IST all SUCCESS with synthesis succeeded (`lr_8081d0c535a2437bb176039f`, `lr_6c8befb004a64eedadfe695c`, `lr_a7341f98019f4623a89f0ef4`, `lr_b3329cb87dda48b3b94ec248`, `lr_70c54f7c36604cbeb9922c8b` — the INF-028 re-probe runs, not soak runs). So day 4 *can* record green — but only if a run is triggered at 09:30, which today needs either the timer install before 09:30 or a manual proving run through the bridge.

**Plain statement:** the chain is NOT green today — zero verifiable passing soak days out of three elapsed. Days 1–3 stand exactly as filed (day 1 coordinator-asserted, days 2–3 no observable 09:30 run); they are not rewritten. The verifiable chain starts when the runner first fires (INT-032 §4). The D4 judgement on 2026-11-27 reads the day records at `/var/lib/friday-universe/intelx-soak/` plus the live archive; INT-023's final 7-day compilation (Muse 9, due 2026-11-27) and the INT-035 pack carry the judgement itself.

## 3. Runner validation done this run (local, no fleet touched)

`IntelX/scripts/run_int876_soak.py` from main 1c754828, run on this machine against a temp record dir (Python 3.12.3):

- **Test 1 — no `FRIDAY_API_KEY`:** refuses before any call, stderr `run_int876_soak: FRIDAY_API_KEY is not set; refusing to call IntelX`, exit 2, no record written. The key is never printed or logged. PASS.
- **Test 2 — dummy key, IntelX unreachable (`http://127.0.0.1:9999`):** writes `2026-11-24.json` with `outcome: trigger_failed`, `reason: intelx_unreachable`, `healthz_status: 0`, `pass: false`, `task_id: soak-876-2026-11-24`, `query: latest AI model releases`, IST+UTC timestamps, exit 2. A down service is recorded, not silently skipped. PASS.
- **Unit/timer parse:** `systemd-analyze verify` on both files — no error on the timer; the only finding on the service is `Command /opt/friday_universe/venv/bin/python is not executable: No such file or directory`, which is expected on this sandbox (that path exists on S2, verified first-hand by INT-032). The remaining verify output concerns this VM's own units, not these files.

No soak-runner test exists in the repo (`tests/` + `IntelX/tests/` contain only unrelated "soak" mentions: a Stratex battery-soak module and a comment). This PR adds no test file, so no contracts-workflow file-list change is owed.

## 4. The traced consumption path — verified in code (no live trace yet)

The designed path is real in the repo, end to end. No traced instance of it exists yet — this task's live leg is the first.

**Producer — IntelX research product.** `POST /v1/task/execute`, `action: research_live` (`IntelX/intelx/api/router.py:105-188`) runs the grounded pipeline (`collect_live_brief` + `synthesize_grounded`) and persists the run durably via `persist_live_research` (Oracle-backed archive; recall at `GET /v1/research/live/{run_id}`). The soak runner calls exactly this endpoint with `task_id: soak-876-YYYY-MM-DD`.

**IntelX → Memora handoff (exists, but NOT automatic on the `research_live` path).** The DAG path (`IntelX/intelx/orchestration/engine.py`, `_dispatch_external_research`) delivers a completed ANSWERED run to four recipients via `dispatch_sequentially` (shared 15 s budget, idempotent Memora event ID); the first is Memora via `MemoraMemoryClient.publish_research_handoff` (`IntelX/intelx/integrations/memora_context.py:104-231`): `POST {MEMORA}/v1/memories` with `X-Agent-Name: intelx`, writing EPISODIC memories under `intelx://research/briefs` (executive brief) and `intelx://research/claims` (verbatim claims with spans). The `research_live` endpoint used by the soak runner does **not** call this dispatch — so for the trace, the handoff must be invoked explicitly for the soak run's envelope (same two `POST /v1/memories` calls the client makes, or the DAG path if the run goes through it). Memora policy rejects direct SEMANTIC writes from agent identities (HTTP 403); peers store observations as EPISODIC and promotion is server-side (MEM-008, noted in the client).

**Memora universal (the scope that makes FRIDAY able to read it).** `POST /v1/promotion/promote` (`Memora/apps/api/routers/v1_promotion.py`, path A — TASK-MEM-013): the owning agent promotes its own memory PRIVATE → SHARED → UNIVERSAL on its own judgement (`MemoryPromotionService.promote_scope`, `Memora/core/memory/promotion.py:276` — monotonic, idempotent; a failed-experiment lesson keeps its PRIVATE original and gains a UNIVERSAL copy). Namespace grants alone do NOT widen a record's scope tier (`Memora/apps/api/routers/v1_memories.py:652`). Visibility is decided in one place (`Memora/storage/relational/access_scope.py`): UNIVERSAL is always readable inside the tenant; PRIVATE only by the owner; SHARED only by the allow-list. Only the Memora service identity may author/mutate a UNIVERSAL record directly — the promotion endpoint is the agent's route to it.

**Consumer — FRIDAY.** FRIDAY's adapter (`Memora/adapters/friday/adapter.py`, `get_session_context`) calls Memora `POST /v1/context` (`Memora/apps/api/routers/v1_context.py:48`) as actor `friday` with `task_query` + optional `namespace_path` + `token_budget`, returning a bundle (`bundle_id`, `memories_count`, `memories[]`). The SDK equivalents are `recall_memories` / `build_context_prompt` (`Memora/sdk/memora_client.py`). A UNIVERSAL copy of the IntelX brief is therefore readable by FRIDAY through this call; a PRIVATE IntelX memory is not.

**No live trace exists yet.** The trace itself (timed, filed) is §5, blocked on the bridge.

## 5. Live procedure (to execute once the bridge is approved and the timer install is cleared)

All server-side steps run through the bridge on the fleet; the fleet key (`FRIDAY_API_KEY`) is read from `/opt/friday_universe/IntelX/.env` server-side and is never printed or copied. Times IST.

**Leg A — install the soak timer on S2 (needs Muse's hub clearance first; fleet mutation).**
1. Copy `deploy/intelx-soak-runner.service` + `deploy/intelx-soak-runner.timer` from the repo to `/etc/systemd/system/` on S2.
2. `systemctl daemon-reload`, `systemctl enable --now intelx-soak-runner.timer`.
3. Verify: `systemctl is-active intelx-soak-runner.timer` = active; `systemctl list-timers` shows next fire 09:30 IST; `ls /var/lib/friday-universe/intelx-soak/` exists (StateDirectory). Pre-install facts already verified by INT-032 (§1): `.env` carries `FRIDAY_API_KEY` (name only), venv python exists, `/var/lib/friday-universe` exists, `/healthz` 200. Re-verify `/healthz` at install time.
4. If the install lands before 09:30 IST 2026-11-24, the timer fires day 4. If it lands after, trigger the day-4 run manually via the runner script (proving run, `--force` only if a record already exists — the runner refuses a second run per date, so the day is never counted twice) and note the timer covers days 5–7.

**Leg B — observe the day-4 run (2026-11-24 09:30 IST).** After the slot: read `/var/lib/friday-universe/intelx-soak/2026-11-24.json` on S2 and recall the run at `GET /v1/research/live/{run_id}` (S2 IntelX, 127.0.0.1:8005). Record: run time, `run_id`, envelope status, synthesis status, source/finding counts, `pass`. Post the hub day record on #1483.

**Leg C — traced consumption (timed, one IntelX research product).**
1. `t0` — trigger: `POST http://127.0.0.1:8005/v1/task/execute` on S2, `X-API-Key: <fleet key>`, body `{"task_id": "soak-876-2026-11-24", "action": "research_live", "payload": {"query": "latest AI model releases"}}`. Record HTTP status, envelope status, `run_id`, `durable_run`. (If leg B already produced the day-4 run, use that run's envelope instead of triggering a second one — one run per day.)
2. `t1` — handoff: the run's brief + claims to Memora (`POST {MEMORA}/v1/memories`, `X-Agent-Name: intelx`, namespaces `intelx://research/briefs` and `intelx://research/claims`), exactly as `publish_research_handoff` does. Record both returned `memory_id`s and HTTP statuses.
3. `t2` — promote: `POST {MEMORA}/v1/promotion/promote` as intelx, `{"memory_id": "<brief memory_id>", "target_scope": "UNIVERSAL", "reason": "TASK-INT-019 traced consumption"}`. Record status + `universal_copy_id` if a dual copy is returned.
4. `t3` — consume: `POST {MEMORA}/v1/context` as friday (`X-Agent-Name: friday`), `{"agent_id": "friday", "task_query": "latest AI model releases", "namespace_path": "intelx://research/briefs", "token_budget": 4000, "purpose": "TASK-INT-019 traced consumption"}`. Record `bundle_id`, `memories_count`, and confirm the returned memory carries the same `run_id` / `memory_id` as the brief. That match is the trace: the FRIDAY-side bundle contains the IntelX product that Memora universal holds.
5. File the trace (t0–t3, run_id, memory_ids, bundle_id, durations) as an addendum to this doc and post it on #1483.

## 6. Blockers (plain)

1. **Bridge approval still open.** Request posted to Muse on hub #1483 as comment 7113152293 (2026-11-24 ~02:00 IST); no reply from Muse on the hub; no approval card pending in this account. Without an approved connection, no S2/S1 leg can be attempted from here. Also filed on the board record for this task.
2. **Timer-install clearance not yet granted.** Installing/enabling `intelx-soak-runner.timer` on S2 is a fleet mutation; per standing orders it needs Muse's clearance on the hub first. Clearance requested in the hub status accompanying this PR — until it lands, the timer stays uninstalled and the day-4 09:30 run has no automatic trigger. Time-critical today: the slot is 09:30 IST 2026-11-24.
3. **No hold exists.** Per Muse's follow-up (relayed by Surendra, 2026-11-24 ~02:00 IST): no git hold and no clearance from Surendra is pending. The two items above are Muse-side (bridge approval relay + deploy clearance), not owner holds, and neither stops the repo-side work filed here.

## 7. What remains

- Muse's bridge-approval relay + clearance for the timer install (hub).
- Legs A–C (§5) once the connection and clearance exist; trace addendum filed here.
- INT-023 final 7-day compilation (Muse 9, due 2026-11-27) and the INT-035 pack carry the D4 judgement; this task's day records feed them.

— Muse 16, 2026-11-24 ~07:14 IST
