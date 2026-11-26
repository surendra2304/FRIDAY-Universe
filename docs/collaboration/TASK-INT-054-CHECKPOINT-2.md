# TASK-INT-054 — Checkpoint 2: armed-state probe (live leg, read-only)

- **Task:** TASK-INT-054 — IntelX: fast-lane live proof run 4 — one real alert end-to-end after INT-039.
- **Checkpoint 1:** MERGED via PR #2010 (merge `47f0ed22`, 2026-11-26 20:02 UTC / 01:32 IST), CI 9/9 green on head `a2091317`, verified by coordinator (WATCH182).
- **Grant:** WATCH182 §2(d) + follow-up §1 rule the run_shell grant settled (owner approval 2026-11-26 18:25:56 IST; standing clearance 7200564540); the INT-054 live leg is next — armed-state probe first, then the alert leg. This probe ran under that clearance. No client change was needed: the pre-existing local MCP client (`mcp_client.py`) was used, read-only commands only. No service was moved, restarted, or reconfigured.
- **Probe:** 2026-11-27 ~02:00 IST (20:30 UTC Nov 26), bridge `run_shell` on server 6 (IntelX-Server), all commands read-only.

## Evidence (first-hand)

- **Unit `IntelX.service`:** loaded, active, running; MainPID `35285`; ActiveEnterTimestamp Thu 2026-11-26 06:32:44 UTC; ExecStart `uvicorn intelx.app.main:app --host 0.0.0.0 --port 8005`; Result success. NOTE: PID changed from 4973 (INT-042, Nov 24) — the service restarted 06:32 UTC Nov 26; cause not investigated here.
- **/health:** HTTP 503, status `degraded`, service `intelx` v2.0.0, `mock_mode: false`, `database: connected`, observed `2026-11-26T20:30:08Z`. Capabilities `research` / `model_provider` unknown (`NO_LIVE_PROBE` / `CONFIG_ONLY`). Dependencies `database` ok, `storage` ok. Same degraded shape as INT-042.
- **Outbox** `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`: exactly **4 envelopes**, 3782 bytes, mtime 2026-11-24 21:30 UTC. Latest envelope `8ca3ca25…` (GPT-6 protein-design digest, fired 2026-11-24T21:30:32Z). **No new digest in ~47h.**
- **state.json:** 1,471,472 bytes, mtime 2026-11-26 20:03 UTC — minutes before this probe.
- **Journal (last 2h):** polls every ~30 min (18:33, 19:03, 19:33, 20:03 UTC), both watches cycling (`ai_model_releases` fetched=2368 dup=2368; `india_tech_regulatory` fetched=64 dup 61–62, below 2–3), `alerted=0`.
- **Soak timer:** `intelx-soak-runner.timer` loaded, active, enabled; service inactive/dead (expected).
- **Kill switch:** NO kill-switch control found — grep for `killswitch` / `kill_switch` across the deployed IntelX tree (excl. venv) and repo-side `IntelX/intelx/core/settings.py` (main, 671 lines) returns nothing; no `KILL` in `settings.py` or `app/main.py`; the watches dir holds only `outbox.jsonl` + `state.json`. Nothing was toggled. The acceptance item "kill switch stays OFF" cannot be verified as a control state — ruling owed from the coordinator on what/where the kill switch is.

## Verdict

**ARMED + QUIET — wait state per acceptance.** Service running, loop polling, zero alerts; no real alert has fired, so the alert leg (one real alert end-to-end) cannot run yet. Next: re-probe on the next hourly check; run the alert leg when a real alert fires.

## Five states

- Implemented: YES (probe evidence only, no code change). Tested: n/a (read-only probe). Merged: NO (this PR). Deployed: NO. Production-verified: NO (wait state; /health degraded).

## Evidence

- Board verified first-hand on main `47f0ed22` (blob `1458faa9`): INT-054 AVAILABLE / muse_12 / pr null — flip rides in coordinator board PR #2017.
- Usage 37% of free weekly limit (reset Nov 29, 6:04 PM IST) — carried.
- Probe commands (all read-only): `systemctl show IntelX.service`, `curl http://127.0.0.1:8005/health`, `ls`/`wc`/`tail` on the outbox + state.json, `grep` for kill-switch strings, `systemctl show` soak timer/service, `journalctl -u IntelX.service --since "2 hours ago"`.

— Muse 12, 2026-11-27 ~02:05 IST
