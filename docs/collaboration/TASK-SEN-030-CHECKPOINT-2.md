# TASK-SEN-030 — Checkpoint 2: implementation (2026-11-25 ~17:00 IST)

- **Task:** Sentinel: DNS-hygiene and Android Private DNS checks in the owner-device posture evaluator.
- **Branch:** `muse12/task-sen-030-dns-hygiene-posture`, rebased onto main `d15c82c9` (PR #1822 was mergeable False / dirty after board PRs #1820/#1824/#1827 and #1825/#1828/#1829 landed; checkpoint 1 + board flip re-applied on the new base, same content).
- **Change — `Sentinel/sentinel/modules/endpoint/device_posture.py`:**
  - `DevicePostureReport` gains `private_dns_mode` (`off` / `opportunistic` / `strict`; empty = not reported), `private_dns_hostname`, `dns_servers`, `trusted_dns_servers`.
  - DP-012 (HIGH) Private DNS off — DNS leaves the device in cleartext on untrusted networks (Phantom Droid untrusted-connection pattern). INFO variants: setting not reported, mode unrecognised, strict without hostname (mirrors the DP-009 patch discipline).
  - DP-013 (MEDIUM) untrusted DNS resolver in use — each resolver in `dns_servers` outside `trusted_dns_servers` is a finding (mirrors DP-010 untrusted Bluetooth).
  - Evaluator stays pure (judges claims only); shared `emit_posture_alerts` path unchanged.
- **Tests — `Sentinel/tests/unit/test_ig_sen_device_posture.py`:** clean-report base now carries strict Private DNS + trusted resolver; new tests: off → DP-012 HIGH; opportunistic + trusted → clean; untrusted resolver → DP-013 MEDIUM; reporting edges (missing / unrecognised / strict-without-hostname → DP-012 INFO). No new test file, so no CI-list registration needed.
- **Verification:** local test execution was NOT run this run — the repo checkout failed an execution-risk check, so no local pytest; verification rides on PR #1822 CI (`test` check) after push. Both changed files were verified by plain-text diff against main (only the intended hunks differ) and by static parse (no execution).
- **Next:** checkpoint 3 = board MERGED flip + evidence once PR #1822 is green and merged. Companion-side field production (phone bridge) is a follow-up, not this repo.
