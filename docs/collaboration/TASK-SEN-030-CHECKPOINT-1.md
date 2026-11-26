# TASK-SEN-030 — Checkpoint 1: scoping (2026-11-25 ~16:00 IST)

- **Task:** Sentinel: DNS-hygiene and Android Private DNS checks in the owner-device posture evaluator.
- **Claim:** hub #1483 comment (this run), on coordinator assignment WATCH093 (7159599715): head of queue SEN-030 -> SEN-031.
- **Board verified first-hand before claiming:** TASK-SEN-030 AVAILABLE / owner null / branch null / pr null, P2, on main `1371db89` (board blob `1ee826e7`, 22,779 lines, via git blobs API). No prior claim, branch or PR. Branch `muse12/task-sen-030-dns-hygiene-posture` @ `1371db89` created and verified.
- **Acceptance (board):** the posture report (TASK-IG-SEN-02 evaluator) states the device's Private DNS setting and resolver hygiene; both checks are included in the output.

## Gap verified first-hand (main 1371db89, depth-1 clone)

- Target: `Sentinel/sentinel/modules/endpoint/device_posture.py` (350 lines) — `DevicePostureReport` + `DevicePostureEvaluator` (TASK-IG-SEN-02); tests `Sentinel/tests/unit/test_ig_sen_device_posture.py` (164 lines).
- `grep -i "dns|private.dns|resolver"` over both files: **zero hits**. The report carries no DNS fields at all; the evaluator's rules run DP-001..DP-011 (unknown sources, ADB, screen lock, encryption, permission grants, Play Protect, patch age, Bluetooth, developer options) — none DNS.
- No in-repo producer constructs `DevicePostureReport` (only the class definition and its tests reference it). The report shape is produced by the FRIDAY phone bridge / companion outside this repo, so this task's change is model + evaluator + tests; companion-side field production is a follow-up, not this repo.

## Plan (checkpoint 2)

1. Add `private_dns_mode` (off / opportunistic / strict, plus hostname when strict) and resolver fields (`dns_servers` / resolver list) to `DevicePostureReport`, with the evaluator judging claims only (it stays pure — it never touches a device).
2. New rules: DP-012 Private DNS off (finding; Private DNS off leaves DNS in cleartext on untrusted networks — the Phantom Droid untrusted-connection pattern); DP-013 resolver hygiene (resolver not in the owner-trusted set, or unknown resolver, is a finding).
3. Extend `test_ig_sen_device_posture.py`: off/opportunistic/strict modes, trusted vs untrusted resolver, missing-field behaviour. Keep the shared AlertEngine (`emit_posture_alerts`) path unchanged.
4. Verify: run the Sentinel device-posture test file plus the endpoint module suite; register any new test file in the CI list if the contracts step enumerates it.

## Notes

- Repo-side evaluator work only — no live or fleet step, so the owner stop order does not block this task.
- Board flip (AVAILABLE -> CLAIMED, owner muse_12, branch, pr) rides in the work PR. Coordinator board PR #1820 (open) also flips SEN-030 owner null -> muse_12; same owner value, so no conflict on that line — only the evidence-list additions may need a rebase once #1820 lands.
- Queue: SEN-030 (this task) -> SEN-031 (PRODUCTION-VERIFY Sentinel corpus wave 3; live leg, owner stop order in force).
