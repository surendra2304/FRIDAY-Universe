# TASK-INT-042 — IntelX running-home consolidation: checkpoint 1

- Task: TASK-INT-042 — IntelX: running-home consolidation — answer where IntelX runs after the S1/S2 consolidation, with gates (P1).
- Claim: hub #1483 comment 7184018145 (2026-11-26 ~11:31 IST), on coordinator assignment in WATCH142 (hub 7183853818), answering work request 7183756841.
- Branch: `muse10/task-int-042-running-home`, from main `4c56e44d`.
- Board: record verified AVAILABLE, owner null, no prior claim, branch or PR, on main `4c56e44d` (board blob `f2a175fd`, verified against the true main blob before claiming). The board flip (AVAILABLE → CLAIMED, owner muse_10) rides in the coordinator's next board PR per WATCH142 — NOT in this work PR, to avoid a double-flip conflict (same pattern as DB-010, WATCH142).
- Queue: position after TASK-CTX-009; under the blocked-head rule this repo leg is worked meanwhile while CTX-009 stays gated on VOICE-E2E-003 (do-not-execute).
- Usage at checkpoint: ~55% of free weekly limit (reset Nov 28 02:03 IST).

## Verdict

**IntelX runs on IntelX-Server (server 6, AWS Sydney, 32.236.185.237) — the ONLY running copy.** Verified first-hand this run (2026-11-26 ~11:30–11:45 IST) on all three hosts. Oracle Server 1 holds a sleeping copy (unit masked + failed since Nov 20; checkout stale at `b51ef05f`, 24 behind main). Oracle Server 2 holds no running copy (unit inactive/dead; no outbox file). Gate 3 is answered with fresh evidence below; gate 1 (owner stop order) still closed; gate 2 (shipper) cleared but re-scope still owed. No service was moved, restarted, or reconfigured — all probes read-only.

## 1. IntelX-Server (server 6) — the running home

All reads via the bridge, first-hand, 2026-11-26 ~11:30–11:45 IST (06:00–06:15 UTC):

- **Unit:** `IntelX.service` LoadState=loaded, ActiveState=active, SubState=running, MainPID=4973, Result=success. ActiveEnterTimestamp Tue 2026-11-24 13:29:50 UTC — same PID 4973 as the INT-049 live leg (WATCH140 follow-up); the service has not restarted since Nov 24.
- **ExecStart:** `/opt/friday_universe/venv/bin/python -m uvicorn intelx.app.main:app --host 0.0.0.0 --port 8005 --workers 1`. FragmentPath `/etc/systemd/system/IntelX.service`.
- **/health:** `curl http://127.0.0.1:8005/health` answers **HTTP 503**, body `status: "degraded"`, service `intelx`, version `2.0.0`, `mock_mode: false`, `database: "connected"`, observed_at `2026-11-26T06:08:46Z`. Capabilities `research` = unknown (`NO_LIVE_PROBE` — "no live research probe exists") and `model_provider` = unknown (`CONFIG_ONLY`); dependencies `database` ok (live `SELECT 1` round-trip) and `storage` ok (writable data-dir probe). The service runs but reports degraded by its own report — same shape as the Nov 23 observation in INT-023. `production-verified` for the health leg stays NO.
- **Outbox:** `/opt/friday_universe/IntelX/data/watches/outbox.jsonl` — exactly **4 envelopes**, 3782 bytes, mtime Nov 24 21:30 UTC (03:00 IST Nov 25). Same four envelope_ids as M12's checkpoint 3; latest is the GPT-6 protein-design digest, `fired_at` 2026-11-24T21:30:32Z. **No new digest in ~33h.**
- **Watch loop alive:** `state.json` 1,412,428 bytes, mtime Nov 26 06:02 UTC (minutes before this probe). Journal (`IntelX.service`, today): polls every ~30 min (04:02, 04:32, 05:02, 05:32, 06:02 UTC), both watches cycling (`ai_model_releases` fetched=2367, `india_tech_regulatory` fetched=64), `alerted=0`, nearly all duplicates — the producer loop is alive and polling; nothing new fires because everything fetched is a duplicate or below threshold. One live-research run persisted 04:00:35 UTC (`run_id=lr_f45f44a57c7a42e6b0aa0819`, status DEGRADED).
- **Soak timer:** `intelx-soak-runner.timer` loaded, active, UnitFileState=enabled. `intelx-soak-runner.service` loaded, inactive, dead (expected — timer-triggered).
- **Checkout state: NONE — `/opt/friday_universe` on S6 is NOT a git repository** (`fatal: not a git repository`, no `.git`). The deployed tree is a subset only: `Futuris`, `IntelX`, `mesh`, `venv`, `venv312`. The running code's version therefore cannot be stated as a commit. Provenance is per-file: INT-049 already found one drifted file (`browser_sidecar.py` live hash ≠ main; re-sync route owed from M6). INT-053 verified `grounded_live_research.py` on S6 carries the INF-028-verified hash. A full deployed-tree hash audit against main is owed before any "deployed" claim for the S6 copy.

## 2. Oracle Server 1 — sleeping copy

- **Unit:** `IntelX.service` LoadState=masked, ActiveState=failed, SubState=failed, MainPID=0, Result=timeout. `oracle_check_service` agrees: masked, failed since Fri 2026-11-20 23:56:31 IST, Main PID 1066051 (code=killed, signal=KILL). Not the home; unchanged since Nov 24.
- **/health:** `curl http://127.0.0.1:8005/health` → exit 7 (connection refused). Nothing listening. /health empty, confirmed first-hand.
- **Checkout:** `/opt/friday_universe` on main, HEAD `b51ef05f` (merge PR #1669), **behind origin/main by 24**. Uncommitted modifications present (not mine — observed only): `M Futuris/futuris/integrations/memora_cloud_fallback.py`, `M Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py` (the FUT-022 fix files).
- **Outbox (sleeping copy):** `/opt/friday_universe/IntelX/data/watches/outbox.jsonl` exists, 1823 bytes, mtime Nov 23 22:03 — the pre-consolidation S1 copy (matches the "offset 3644 > outbox 1823 B" drainer defect carried from M12's checkpoint 3).
- **Soak timer:** `intelx-soak-runner.timer` LoadState=not-found — not installed on S1.

## 3. Oracle Server 2 — no running copy

- **Unit:** `IntelX.service` LoadState=loaded, ActiveState=inactive, SubState=dead, MainPID=0, Result=success. Not running.
- **/health:** `curl http://127.0.0.1:8005/health` → exit 7 (connection refused). Nothing listening. /health empty, confirmed first-hand.
- **Directory:** `/opt/friday_universe/IntelX` exists as part of the repo checkout, but `IntelX/data/watches/outbox.jsonl` does NOT exist — no producer state on S2. (INT-023 §8 recorded the directory as gone on Nov 24; the directory is present now because the checkout holds the repo tree. The service state and the missing outbox are what matter: nothing runs here.)
- **Checkout:** branch `muse10/task-voi-044-acceptance-run-27` @ `b85faddc`, ahead 21 of origin — the bridge workspace is parked on my merged VOI-044 branch. Shared state; not switched by this task. Untracked CI venvs present (`Cortex/.venv-cortex-ci/`, `FRIDAY/.venv-friday-ci/`).
- **Soak timer:** `intelx-soak-runner.timer` and `.service` both LoadState=not-found — never installed on S2.

## 4. Repo-side corroboration (current main `4c56e44d`)

- `docs/collaboration/WORKER_PROMPT.md` fleet map: "**IntelX-Server** (AWS Sydney, 32.236.185.237) — IntelX + Futuris, live"; "Oracle Server 1 — Memora, Forge, Sentinel and Cortex, live; also the Caddy gateway and the sleeping copies of the moved agents' trees"; "Oracle Server 2 — NO deployed agents. The bridge, the fleet repo checkout, and CREDENTIALS.md live here." "Exactly ONE copy of an agent runs at a time; the other copies are sleeping files only."
- `AGENTS.yaml`: IntelX port 8005, status production.
- `IntelX/intelx/api/v1/health.py`: `/health` and `/readyz` share the same storage-state report.
- Prior live legs agree: INT-036 (re-scoped to the IntelX-Server home), INT-049 (S6 service active since Nov 24 13:29 UTC, PID 4973), INT-053 (IntelX on IntelX-Server active, MainPID 4973, /health 200 — see note below).

## 5. Gates

- **Gate 1 — owner stop order: STILL CLOSED.** No lift in WATCH142 (hub 7183853818, read in full this run). No live dispatch, no flag enablement, no service move attempted. All probes in this checkpoint were read-only (`systemctl show`, `ls`, `git rev-parse`, `curl` localhost health, `journalctl` tail, `cat` outbox).
- **Gate 2 — shipper: CLEARED, re-scope still owed.** PR #1676 MERGED (merge `4bc4159c`, Nov 24) — the S2 → S1 transfer mechanism exists on main. But its source (the S2 outbox) no longer exists: S2 has no outbox file (this run). The transfer leg must be re-pointed at the IntelX-Server outbox (or the drainer reads it where it now lives) before any live leg is scoped. The drainer offset defect (offset 3644 > S1 outbox 1823 B) is still unverified. Both are coordinator decisions, not worker work.
- **Gate 3 — where IntelX runs after the consolidation: ANSWERED.** IntelX runs on IntelX-Server (server 6, 32.236.185.237) and nowhere else. This confirms and refreshes the 20:57 Nov 24 coordinator ruling (M12 checkpoint 3) with first-hand evidence as of Nov 26 11:30–11:45 IST: S6 service active (PID 4973, since Nov 24 13:29:50 UTC), watch loop cycling today, outbox 4 envelopes; S1 masked/failed; S2 inactive/dead.

## 6. Notes and discrepancies (recorded, not resolved here)

- **INT-053's "/health 200" vs this run's 503:** TASK-INT-053.md states "IntelX on IntelX-Server active (MainPID 4973, /health 200, mock_mode false)". This run measured HTTP 503 with body `status: "degraded"` at 06:08:46 UTC. Either the health state changed between the two probes, or INT-053 read the service as up (200 on a different path, e.g. `/readyz`) while `/health` reports degraded. Not chased further here — the endpoint and its degraded payload are recorded verbatim above; a re-probe can settle it.
- **S6 has no git checkout:** deployment provenance for the running copy is per-file hashes only. INT-049's `browser_sidecar.py` drift (live hash = pre-INT-051 blob) stands unrepaired; M6's re-sync route is the carried item.
- **S1 checkout stale + dirty:** main @ `b51ef05f`, 24 behind, with the two FUT-022 files modified in the working tree. Sleeping copy only — no action taken.
- **S2 checkout parked on my merged VOI-044 branch:** bridge workspace state; left untouched.
- **No new digest in ~33h:** the outbox still holds exactly the same 4 envelopes as Nov 24 21:30 UTC. The watch loop polls and finds only duplicates — expected behaviour while no qualifying item fires, not a stall by itself. The digest end-to-end leg (M12's original INT-042 reading) still waits on gate 1.

## 7. States

- Implemented: NO (evidence only — checkpoint record, no code or service change).
- Tested: NO (read-only probes, no test run; the doc itself is the evidence).
- Merged: NO (work PR open, awaiting coordinator review).
- Deployed: NO (no deploy; S6 copy already running, provenance per-file only).
- Production-verified: NO — the home is established, but /health reports degraded (503) and the S6 code has no checkout to verify against.

## Next

- Coordinator: flip INT-042 AVAILABLE → CLAIMED (owner muse_10, pr TBD) in the next board PR per WATCH142.
- Checkpoint 2 (when gate 1 lifts or Muse directs): re-probe /health + outbox for a new digest; the drainer/flag side of the digest leg on the new home; the shipper re-point decision.
- Carried, not mine: INT-049 `browser_sidecar.py` re-sync route (M6); S6 deployed-tree hash audit; the /health 200-vs-503 note above.

— Muse 10, 2026-11-26 ~11:45 IST
