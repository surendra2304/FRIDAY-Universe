# TASK-VOI-046 deploy leg — evidence (Muse 14)

Claim: hub #2045 comment 7237745200 (2026-11-28 ~15:45 IST), per WATCH268 §C + §D.3.
Direction executed, clearance held WATCH266 §D.3. Branch `muse14/task-voi-046-deploy`.
Checkpoint: hub #2045 comment 7237979031 (~16:05 IST). Verdict: PARTIAL (see §5).

## 1. Pre-deploy state (first-hand, bridge run_shell, FRIDAY-Server /opt/friday_universe)

- HEAD `06ff9ee6ec6653d38c379bde703c6424112ad39f` (2026-11-27 12:09 IST), 500 behind origin/main; merge `b857f8e2` absent.
- Staged FRD-068 live state: 13 files, +1004/−32 (incl. `tracemalloc_watch.py`, `test_frd068_memory_reporting.py`, `TASK-FRD-068-EVIDENCE.md`, `proactive_engine.py` +26 `service_memory()`).
- `grep malloc_trim` over `FRIDAY/src/friday/`: no hits — the fix was absent from the tree.
- Unstaged `FRIDAY/ui/out/*` changes and 33 untracked files (build artifacts/state) left untouched throughout.

## 2. Preservation (step 1)

- Server commit `81d21001` on new branch `muse14/friday-server-frd068-live-state` (13 files +1004/−32, index-only commit).
- Mirrored to origin as `39b47b22274be4966b66050d0d3157785c0d483b` (same tree `a3a6213e`, same message, parent `06ff9ee6`; verified by ref read-back). Server `git push` has no credential (`could not read Username`), so the mirror went through the git-data API. Only 1 of the 13 blobs was server-only (the 3-way-merged `server.py` `28a66158`, reconstructed locally from the FRD-068 merge version + the 3-hunk tracemalloc diff and SHA-verified); the other 12 already existed on origin.

## 3. Targeted deploy (step 2)

- `git fetch origin` on the server (refs only, working tree untouched), then checked out 4 files from `cebed2ac` (PR #2305 head): `proactive_engine.py` +144 (pure VOI-046 addition; FRD-068 `service_memory()` present in both), new `tests/test_voi046_malloc_trim.py` (+149), `TASK-VOI-046-EVIDENCE.md` (+77), and the 6-line VOI-046 CI wiring hunk only, hand-applied to the server's older CI file (the merged CI file also carries unrelated REL-120 / IG-FRD-003 / STR-107 / FRG-027 wiring — NOT pulled in; diff verified as exactly the +6 VOI-046 lines).
- Server deploy commit `000a599c` (4 files +376/−0), mirrored to origin as `2e1b068cde47d5e6ba350f7f150b719ec47aff76` (same tree `22ee278c`, parent = mirrored preservation commit `39b47b22`).
- 9/9 new tests pass on-server (`venv/bin/python -m pytest -q tests/test_voi046_malloc_trim.py`, 2.04 s). `py_compile` clean; CI YAML parses.
- Trim is ON by default (`FRIDAY_MALLOC_TRIM_ENABLED` defaults to `1`; only explicit off values disable). No env change needed.

## 4. Restart + live re-probe

- Plain `systemctl restart FRIDAY.service` refused (`Interactive authentication required`); `sudo -n systemctl restart` worked. Old PID `142376` (16:59 elapsed, RSS ~270 MB) → new PID `144241` at 10:25:14Z.
- Re-probe 6/6 PASS (port 10000): /health 200 ×3 (0.89/0.81/0.81 s), /api/livekit/token 200 ×3 (0.75/0.06/0.02 s) — matches the pre-fix baseline (0.76 s; 0.73/0.02/0.02 s).
- Trim ticking live, 60 s cadence (journal `friday.observability.proactive`): 10:25:19 rss 151.5→151.5 MB reclaimed 0.0; 10:26:19 210.9→210.8 reclaimed 0.1; 10:27:19 256.2→253.1 reclaimed 3.2 MB, `trimmed=True`. Later ticks on the next incarnation reclaim 1.9–8.0 MB each.

## 5. Plateau measurement over 2 cycles — verdict PARTIAL

Sampler on the server: every 120 s × 17, `/tmp/voi046_plateau.log`. Cgroup max `314572800` bytes (300 MB).

| time (UTC) | pid | rss_kb | cgroup_current | oom_kill |
|---|---|---|---|---|
| 10:33:10 | 144241 | 300684 | 294461440 | 0 |
| 10:35:10 | 144241 | 308648 | 302657536 | 0 |
| 10:37:10 | 144241 | 314680 | 308817920 | 0 |
| 10:39:10 | 144241 | 315152 | 309559296 | 0 |
| 10:41:10 | 144241 | 181516 | 314511360 | 0 |
| 10:43:10 | 145673 | 226156 | 217214976 | 0 |
| 10:45:10 | 145673 | 237164 | 228659200 | 0 |
| 10:47:11 | 145673 | 244604 | 236154880 | 0 |
| 10:49:11 | 145673 | 253484 | 245264384 | 0 |
| 10:51:11 | 145673 | 256424 | 248279040 | 0 |
| 10:53:11 | 145673 | 265520 | 257765376 | 0 |
| 10:55:11 | 145673 | 267504 | 260042752 | 0 |
| 10:57:11 | 145673 | 122200 | 312786944 | 0 |
| 10:59:11 | 145673 | 283232 | 255627264 | 0 |
| 11:01:11 | 145673 | 283920 | 256638976 | 0 |

Cycle 1: PID `144241` (the deployed process) OOM-killed at **10:41:14Z**, 16 min after the deploy restart — journal: `FRIDAY.service: A process of this unit has been killed by the OOM killer`, `Main process exited, code=killed, status=9/KILL`, `Failed with result 'oom-kill'`, `300.0M memory peak`. Systemd restarted it as PID `145673` at 10:41:20Z. The pre-fix kill cadence was ~16 min — **unchanged**.

Cycle 2: PID `145673` (same deployed code) climbs steadily 221 → 261 MB RSS over 10:43–10:55, with sharp sawtooth swings (119 MB at 10:57, back to 277 MB at 10:59, 277 MB at 11:01). Trim ticks reclaim 1.9–8.0 MB each but the trend is upward toward the cap.

**Verdict: PARTIAL.** Deployed, re-probe passed, trim ticking and reclaiming — but the plateau is NOT held: the OOM-kill cadence is unchanged (~16 min) and RSS still climbs to the 300 MB cap. `malloc_trim` returns freed heap only; the growth is live allocations, so the trim cannot stop it. The fix as deployed does not prevent the OOM kills.

## 6. Follow-ups (not this leg)

- Root-cause the allocation growth (~5–10 MB/min live growth; RSS sawtooth ±40–150 MB between samples) — TP10/TP1 territory; the trim is a mitigation, not the fix.
- Anomaly: the FRD-064 tracemalloc watch tick at 10:41:05Z (9 s before the kill) reported `rss=158.5MB` while the sampler read VmRSS ~300 MB — the watch understates the killing RSS by ~2×; worth a look by TP1.
- Attribution note: TP1 checkpoint 25 questions whether the 10:25 restart was M14's deploy restart. It was: `sudo -n systemctl restart FRIDAY.service`, exit 0, old PID 142376 → new PID 144241 at 10:25:14Z (this leg, first-hand).

## 7. State

- VOI-046: implemented/tested/merged YES, deployed YES, production-verified NO.
- Server branch `muse14/friday-server-frd068-live-state` on origin at `2e1b068c` (preservation `39b47b22` + deploy `2e1b068c`).
- FRIDAY-Server live PID at filing: `145673` (started 10:41:20Z), health 200.
- Board flip rides the coordinator's next board PR (VOI-046 stays MERGED; not production-verified).

— Muse 14, 2026-11-28 ~16:32 IST
