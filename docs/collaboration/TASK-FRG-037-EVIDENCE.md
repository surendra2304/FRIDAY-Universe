# TASK-FRG-037 — Evidence: Forge→Memora 401s fixed (per-agent key shadowing)

- Task: TASK-FRG-037 — Forge: ship the tool the highest-priority stuck task is blocked on, or the next self-upgrade slice with live proof (follow-up FRG-036).
- Worker: Muse TP14. Branch: `musetp14/task-frg-037-ship-blocked-tool-self-upgrade`.
- Claim: hub #2045 comment 7235963415 (2026-11-28 ~12:58 IST), per BE 12:57 §B. Board verified first-hand on live main `d72d7966` (blob `c3edf42a`): AVAILABLE / owner null / P1.
- Filed: 2026-11-28 ~13:45 IST. Base for this commit: live main `527b073d`.

## §1 — Blocker sweep (board + hub, first-hand)

Board on live main `527b073d` (fresh raw fetch, 1,621,085 bytes, 541 records): BLOCKED tasks are WF-007/008/009, MEM-017, INT-023, EARN-005, VYR-052, FRD-048, VYR-081, DB-001, WEB-009 — the same set FRG-035 (Muse 18) swept at ~07:15 IST, plus WEB-009 (BLOCKED on deploy: live chunks lack FIX-01/FIX-02, owner Muse 4). None is blocked on an unowned Forge tool: owner gates (FRD-048, MEM-017, EARN-005), footage/brief (VYR-081), unachievable QA gate (VYR-052), deploy staleness (WEB-009), owned lanes (DB-001/M6, INT-023/M9).

The FRG-036 §9.2 service-side defect list is where the Forge tool work lives. Its three items:

| Defect (FRG-036 §9.2) | Owner | State |
|---|---|---|
| Forge sandbox deps (`aiosqlite` missing) | FRG-035, Muse 18 | Checkpoint 1 merged (PR #2244); checkpoint 2 not started (~4h, M18's 13:43 post) |
| Forge HTTP wedging (`execute_now` sync block) | FRG-038, Muse 19 | PR #2295 open; contracts failing on PR-caused test breakage; M19 owns the fix, M14 re-verifies |
| Forge→Memora writebacks 401 | **unowned** | **this task's slice** |

**Sweep verdict: no agent is blocked on an unowned Forge tool except the FRG-036 Memora-401 defect, which is the next self-upgrade slice. FRG-037 ships it.**

## §2 — Root cause (live, first-hand)

Forge's Memora writebacks 401 on every call. Journal, Forge.service on Oracle Server 1, 2026-11-28 09:06:54 IST (TP4's FRG-036 Leg B re-run, pid 2396455):

- `GET http://127.0.0.1:8002/v1/memories/search?...` → `401 Unauthorized`
- `POST http://127.0.0.1:8002/v1/memories/record-interaction` → `401 Unauthorized`
- `POST http://127.0.0.1:8002/v1/capture/events` → `401 Unauthorized`

(16 more `401` lines in the 04:00–05:00 IST window, the original Leg B run.)

Two layers were checked; only one is broken:

1. **Headers — correct.** `Forge/app/integrations/memora_client.py::_get_headers` sends `X-Agent-Name: forge` and `Authorization: Bearer <key>`. Memora's `authenticate_agent` (`Memora/apps/api/dependencies.py`) reads identity from `X-Agent-Name` and the credential from `X-API-Key` or Bearer, then verifies against `FORGE_API_KEY` in Memora's env. The one gap: Forge sends the key as `X-Agent-Key`, a header Memora never reads — Bearer covers it, but the contract header was missing.
2. **Key selection — broken.** `Settings.memora_api_key` (`Forge/app/core/config.py`) resolves by `AliasChoices("FORGE_MEMORA_API_KEY", "FORGE_API_KEY", ...)`: the first present alias wins. The live Forge env (pid 2493326) carries BOTH, and `FORGE_MEMORA_API_KEY` holds a stale value Memora does not know. Hash comparison (values never printed or copied): Forge's `FORGE_API_KEY` **matches** Memora's expected `FORGE_API_KEY` exactly; Forge's `FORGE_MEMORA_API_KEY` matches neither Memora's `FORGE_API_KEY` nor `MEMORA_API_KEY`. So Forge authenticates as `forge` with a key Memora rejects.

Reproduced exactly from Server 1 (keys extracted from the live Forge proc env inside the shell, never printed):

- A — Forge's current effective headers (`X-Agent-Name: forge` + Bearer `FORGE_MEMORA_API_KEY`) → **401 `{"detail":"Invalid agent credentials"}`**.
- B — Same headers with Bearer `FORGE_API_KEY` → **200**, real Memora rows (`memora://forge/private`).

## §3 — Fix (this commit)

- `Forge/app/core/config.py` — `memora_api_key` aliases reordered to `("FORGE_API_KEY", "FORGE_MEMORA_API_KEY", "memora_api_key")` with a comment recording why. The per-agent key is the credential Memora verifies; the dedicated alias stays only as a fallback for deploys that set nothing else.
- `Forge/app/integrations/memora_client.py` — `_get_headers` now also sends `X-API-Key` (the header Memora's `get_actor_header` reads). Bearer and `X-Agent-Key` kept for compatibility.
- `Forge/tests/unit/test_memora_integration.py` — two new tests: the per-agent key wins when both are set; headers carry Memora's auth contract (`X-Agent-Name`, `X-API-Key`, Bearer).

No new files; the CI Forge tier-1 list is unchanged (it does not run `test_memora_integration.py`).

## §4 — Tests (run first-hand on Oracle Server 1, scratch tree)

Scratch copy of the live Forge tree (`/tmp/frg037-forge`, workspaces excluded), patched with the identical edits, run under the fleet venv (`venv312`, `PYTHONPATH=/tmp/frg037-forge:/opt/friday_universe` — the repo-root `mesh` import needs it, same as the live service):

- Selected: `test_forge_named_key_is_used_for_memora_identity`, the two new FRG-037 tests, singleton + cloud-mock — **5/5 pass**.
- Full file: the same 3 failures as the unpatched baseline (`test_memora_client_local_fallback`, `test_recall_survives_a_degenerate_query`, `test_recall_still_finds_the_real_memory` — `AttributeError: property 'local_db_path' ... has no setter`; the Oracle-only spool removal left these tests stale). **Pre-existing on main, not introduced by this change** — verified by running the same file from the unpatched live tree: identical 3 failures.

CI repair in-run: `contracts` failed on the first head — the REL-068 collection guard (`scripts/ci_test_collection_audit.py`) rejects a PR that ships a test file no workflow collects, and `test_memora_integration.py` was in no invocation. Fixed in this PR: the file rides the Forge tier-1 invocation in `.github/workflows/friday-universe-ci.yml`, with the 3 pre-existing failures above as `--deselect`s (same pattern as FRG-021/FRG-027). The guard was verified locally against the exact edited workflow (diff-scoped run, exit 0, 1 file checked).

## §5 — Live proof (fixed code against live Memora)

The exact fixed client, run from the scratch tree against live Memora (`127.0.0.1:8002`, pid 2493276) with BOTH live env keys set (so the alias reorder is what selects the right one):

- `a_record_session_event(session_id='frg037-live-proof', kind='observation', content='TASK-FRG-037 live proof FRG037-20261128-1345-proof: ...', task_id='TASK-FRG-037')` → **`{'stored': True, 'id': '55e9468a-dad5-4fa0-b4b1-ad57cf3743cd', 'duplicate': False, ...}`**.
- Read-back: `recall_memories(query='FRG037-20261128-1345-proof')` → **1 hit, same id `55e9468a-dad5-4fa0-b4b1-ad57cf3743cd`**.

Before the fix the same call path 401'd (§2, probes A/B). The fixed code writes and reads back a real Memora record.

**Not yet live on the service:** the running Forge (pid 2493326, started 12:04:51 IST) still carries the old code. Merge + deploy + Forge restart is owed; after it, the post-deploy check is: Forge journal shows no new Memora 401s and the next Leg B re-run (FRG-039 / TP4) gets 2xx writebacks. Restart/deploy clearance is the coordinator's call — no live-fleet deploy was done in this run.

## §6 — Five states (honest, this run)

- Implemented: YES — fix + tests in this PR.
- Tested: YES — 5/5 selected pass on Server 1; 3 pre-existing failures unchanged (see §4).
- Merged: NO — PR #2299 open (see §7).
- Deployed: NO — live Forge still on old code until merge + restart.
- Production-verified: PARTIAL — the fixed code is proven live against Memora (§5); the running service carries it only after deploy.

## §7 — PR + board note

- Work PR: **#2311** (head: commit `b8d28e62` + the CI-repair commit below; base live main `527b073d`). The branch was reset to current main so the PR carries work only — the board flip rides WATCH263's board PR per WATCH262 §D ("FRG-037 → CLAIMED muse_tp14"), so no board hunk is in this PR and no board conflict is created. PR #2299 (board-flip PR) auto-closed unmerged on the branch reset (head==base); #2311 replaces it.
- Paired verification + merge owed (coordinator's call). Usage: 16% of free weekly limit (verified this run; resets Dec 3, 8:51 PM IST).

— Muse TP14

## §8 — Post-deploy 401 check (2026-11-28 ~14:30 IST, first-hand)

WATCH265 §D.7 granted the Forge deploy + restart clearance (one restart covering merged #2295 FRG-038 + #2311 FRG-037); TP14 verifies the 401s are gone from the journal after.

- **Merged:** PR #2311 merged 2026-11-28 14:25:05 IST (merge `1bc92551`, M19 VERIFIED). Board flip FRG-037 → MERGED rides the coordinator board PR (WATCH266 §G.1).
- **Deployed + restarted:** Oracle Server 1 checkout at `1bc92551`. Forge restarted 14:27:37 IST (pid 2569632, cwd `/opt/friday_universe/Forge`, parent pid 1); Memora restarted 14:27:35 IST (pid 2569599, port 8002); Sentinel 14:27:42 IST. No `forge.service` unit exists — services run as direct uvicorn processes.
- **Fix live in the running tree:** `Forge/app/core/config.py:207` — `AliasChoices("FORGE_API_KEY", "FORGE_MEMORA_API_KEY", "memora_api_key")`; `Forge/app/integrations/memora_client.py:134` — `headers["X-API-Key"] = self.api_key`.
- **Keys match (hash comparison, values never printed):** Forge pid 2569632 `FORGE_API_KEY` sha256 `52fbca4598a8d74b` == Memora pid 2569599 `FORGE_API_KEY` sha256 `52fbca4598a8d74b`. Forge's stale `FORGE_MEMORA_API_KEY` (`fcafd28fd776c955`) is no longer selected first.
- **Health:** Forge `:8006` 200, Memora `:8002` 200.
- **Live writeback through the deployed code with the running service's env** (marker `FRG037-20261128-1430-proof`): `a_record_session_event` → `{'stored': True, 'id': '79f5694a-fee9-4632-9bd1-06833d6c67bf', 'duplicate': False}`; read-back `recall_memories` → **1 hit, same id**. (One probe-side bug on the first attempt: `recall_memories` is sync — the `await` TypeError was the probe's, not the service's; re-run sync, 1 hit.)
- **Journal since restart (14:27:00 IST):** zero `401 Unauthorized` / `Invalid agent credentials` lines. The only two `401`-substring matches are the ephemeral ports `44010`/`44018` in Memora `/health` 200 log lines — not HTTP 401s.
- **Verdict: PASS — the Forge→Memora 401s are gone on the deployed service.** Remaining confirmation per §5: the next Leg B re-run (FRG-039, TP12, claimed 14:25 IST) gets 2xx writebacks through the service's own task path.

## §6 (amended) — Five states

- Implemented: YES. Tested: YES. Merged: YES (PR #2311, merge `1bc92551`). Deployed: YES (Forge pid 2569632, Server 1, from `1bc92551`). Production-verified: YES — post-deploy writeback + read-back live (§8); Leg B re-run confirmation rides FRG-039.
