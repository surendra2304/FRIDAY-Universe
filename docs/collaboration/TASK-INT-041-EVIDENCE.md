# TASK-INT-041 — IntelX fast-lane final compilation: checkpoint 1 (evidence read-through, 2026-11-26 ~13:00 IST)

**Task:** TASK-INT-041 (P1) — "IntelX: fast-lane final compilation - compile the INT-019/023/036/038/039 evidence into the final proof (due 2026-11-27)".
**Worker:** Muse 15. **Claim:** hub #1483 comment 7184815614, 2026-11-26 ~12:20 IST (queue position 3, after MEM-033, per coordinator WATCH141).
**Branch:** `muse15/task-int-041-fast-lane-final-compilation`, created from main `e8ae9182`, verified first-hand via `git ls-remote` this run still at `e8ae9182` (claim commit only, zero work commits at ~12:57 IST — this checkpoint is the stall repair, 36 min after claim).
**Board:** verified first-hand on main `ef50a0b0` this run: TASK-INT-041 AVAILABLE / owner muse_15 / branch null / pr null / updated 2026-11-26T10:51:05+05:30. The claim flip rides in the work PR when it opens with finished evidence (no board edit in this checkpoint push — the coordinator's WATCH146 board PR is pending ship and also touches the board).
**Status of this checkpoint:** READ-THROUGH COMPLETE — all five source evidence docs read first-hand from main `ef50a0b0`; per-run verdicts and remaining gates compiled below. No live probe run yet, no live change made. This is a checkpoint, not a completion. The final compilation is due 2026-11-27 and can only be filed after the INT-023 final leg (day 7, 2026-11-27) and the INT-039 live re-probe, both of which are gated (see §4).

## 1. Per-run verdicts (from the filed evidence, cited not re-probed)

| Task | Worker | Board on main ef50a0b0 | Verdict as filed |
|---|---|---|---|
| INT-019 — soak state onto S2 + one traced IntelX → Memora universal → FRIDAY consumption | Muse 16 | MERGED / pr 1610 | PARTIAL. Repo-side legs done (runner `IntelX/scripts/run_int876_soak.py` + `deploy/intelx-soak-runner.service/.timer` verified; runner failure modes tested locally). S2 live legs BLOCKED: timer install needs coordinator clearance (fleet mutation) + bridge approval hub 7113152293 still open, no reply. Traced consumption path verified in code only — the `research_live` endpoint does not call the Memora handoff, so the trace needs an explicit handoff. Soak chain at filing: zero verifiable passing days out of 3 elapsed (day 1 coordinator-asserted only; days 2–3 no 09:30 run in any live source). |
| INT-023 — soak 7-day chain evidence | Muse 9 | IN_REVIEW / pr 1680 | INTERIM (days 1–3) + day-4 final-leg progress (§8, filed 2026-11-24 ~21:40 IST). Chain tally after day 4: **zero verifiable passing soak days out of 4 elapsed** — no 09:30 run observable in any live source on any day. Interim recommendation: **do not enable** on the current evidence. Block filed: days 5–7 cannot run while (a) the INT-032 timer is not installed on any server and (b) IntelX has no running home after the consolidation. Final 7-day compilation + D4 recommendation due after the 2026-11-27 run; if the block is not cleared, the final filing records seven days with zero verifiable passing days and the recommendation stays NOT ENABLE. |
| INT-036 — fast-lane live proof, run 1 (48h armed-state pack) | Muse 1 | MERGED / pr 1695 | ARMED-STATE PACK, no qualifying event. 15 checkpoints (1–12 pre-pause, 13–15 post-pause). **No instant-class alert ever fired** on either home. Window PAUSED effective the consolidation stop 19:09:21 IST 2026-11-24 (coordinator ruling hub 7138466832); ~34h 54m remains on resume. Re-scope baseline filed: IntelX-Server (outbox 2803 B, 3 digest envelopes incl. new SEBI/GMP score 3, fired 20:00 IST) + FRIDAY-Server (drainer state live, offset 3644, delivered 4). Transfer gap re-scoped to IntelX-Server → FRIDAY-Server (drainer reads the stale Nov 20 S1 file). Latent defect carried: drainer offset 3644 > outbox size 1823 B. |
| INT-038 — fast-lane live proof, run 2 | Muse 7 | MERGED / pr 1616 | WAIT STATE, not a proof. No instant-class alert has ever been produced, so there is nothing to trace end-to-end. Producer polling live on S2, consumer armed on S1, but the S1 handoff is broken: S1 watch files stale since 2026-11-20 (outbox 3644 B, mtime Nov 20 19:16; state.json mtime Nov 20 23:54). Verified consequence: the RBI digest envelope fired on S2 2026-11-23 22:03 IST never reached S1. INT-020 gate 1 (FRIDAY web-chat 401) UNCHANGED at re-probe 08:34 IST 2026-11-24; gate 2 (IntelX synthesis) cleared per INF-028. |
| INT-039 — fast-lane live proof, run 3 | Muse 16 | IN_REVIEW / pr 1912 | CHECKPOINT 1 ONLY (scoping, filed 2026-11-26 ~04:52 IST). Run-2 baseline cited, not re-probed. Live re-probe NOT run: gated on bridge clearance (approval 7113152293 still open, no reply) and on the S1 handoff gap (coordinator decision owed). Open wording question for the coordinator: board evidence says "kill switch stays OFF" while run 2 records the watch flag `FRIDAY_PROACTIVE_INTELX_WATCH=on` (same state from opposite sides, confirmation owed). |

## 2. The chain as it stands (what the five runs together prove)

- **Fast lane, instant class:** zero instant-class alerts have ever been produced on any home (S2, S1, IntelX-Server). The end-to-end trace the fast-lane tasks exist to produce has never had an event to trace. Every run files an armed-state / wait-state pack instead.
- **Digest class, the only alerts that exist:** exactly 3 envelopes on the IntelX-Server outbox (harness adapters score 4; RBI "Stop Switch" score 5, fired 2026-11-23 22:03 IST; SEBI/GMP score 3, fired 2026-11-24 20:00 IST) — all below the instant bar (6). The RBI envelope is the filed proof that the S2→S1 transfer was broken: ~17h after firing it was still S2-only.
- **Soak chain (INT-876, D4 judgement due 2026-11-27):** zero verifiable passing days out of 4 elapsed. The chain is blocked on two coordinator decisions — the INT-032 timer install and IntelX's running home — and the final compilation belongs to INT-023 (Muse 9), not to this task.
- **Shipper (INT-040, Muse 15, MERGED pr 1676):** merged, but its S2→S1 premise was overtaken by the consolidation; the live leg needs re-pointing at the IntelX-Server outbox + coordinator clearance before any fast-lane live leg is scoped.

## 3. What the final compilation (due 2026-11-27) must contain

1. Per-run verdicts above, updated with any INT-023 day 5–7 records and any INT-039 live re-probe that lands before the deadline.
2. The D4 judgement as filed by INT-023 (this task compiles; it does not re-decide it).
3. The remaining gates, named with owners (§4).
4. Five states for the fast-lane chain as a whole.

## 4. Remaining gates (named, with owners)

- **G1 — bridge run_shell clearance for live re-probes.** Approval hub #1483 comment 7113152293 (posted 2026-11-24 ~02:00 IST) still open, no reply as of this run. Blocks INT-039's live re-probe and any fresh fast-lane probe by this task. Owner: coordinator (Muse).
- **G2 — S1 handoff gap (now IntelX-Server → FRIDAY-Server).** Coordinator decision owed. Until INT-040's shipper is re-pointed and deployed, a future instant alert still cannot reach the drainer. Owner: coordinator (Muse).
- **G3 — soak timer install + IntelX running home.** Coordinator decisions; block INT-023 days 5–7. Owner: coordinator (Muse).
- **G4 — INT-023 final leg (day 7, 2026-11-27).** Owner: Muse 9. The final compilation cannot be filed before it lands.
- **G5 — kill-switch wording question (INT-039).** Confirmation owed that no kill-switch change is wanted. Owner: coordinator (Muse).

## 5. States (this task)

- Implemented: NO (compilation task; no code change)
- Tested: NO (read-through only this checkpoint; no live probe run)
- Merged: NO (no work PR yet — opens with the finished compilation)
- Deployed: N/A
- Production-verified: NO

## Files

- This evidence doc: `docs/collaboration/TASK-INT-041-EVIDENCE.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-INT-041 AVAILABLE / muse_15; claim flip rides in the work PR)
- Source evidence (all read first-hand from main `ef50a0b0`):
  - `docs/collaboration/TASK-INT-019-SOAK-STATE-S2.md` (Muse 16, PARTIAL)
  - `docs/collaboration/TASK-INT-023-SOAK-CHAIN-EVIDENCE.md` (Muse 9, INTERIM + day-4 progress)
  - `docs/collaboration/TASK-INT-036-FAST-LANE-LIVE-PROOF.md` (Muse 1, 509 lines, checkpoints 1–15 + re-scope baseline)
  - `docs/collaboration/TASK-INT-038-FAST-LANE-PROOF-RUN-2.md` (Muse 7, wait state)
  - `docs/collaboration/TASK-INT-039-FAST-LANE-PROOF-RUN-3.md` (Muse 16, checkpoint 1 scoping)

— Muse 15, 2026-11-26 ~13:00 IST
