# TASK-MEM-004 — Memora dedup + contradiction hygiene: DRY-RUN REPORT

**Status: dry-run only. Nothing was written to production.** The scan ran
read-only (SELECT-only, via Memora's own ORM/session on Server 1) on
2026-11-15 ~13:5x IST. The store is live and being written during the scan
window (a second scan ~30 min later counted 419 live records vs 413), so all
counts are a snapshot, not a fixed constant.

## Method (the repo's own semantics, no new definitions invented)

- **Live** = lifecycle_state in {candidate, active, verified}, grouped strictly
  within (tenant_id, namespace_id) — identical text in different namespaces is
  never a duplicate.
- **Exact duplicate** = normalized content identical (whitespace collapsed,
  casefolded) — the write pipeline's own duplicate definition.
- **Near duplicate** = token Jaccard ≥ 0.85 — the write pipeline's own
  threshold (`DeduplicationEngine`).
- **Direct contradiction** = the repo's conservative `ContradictionDetector`
  (opposite explicit polarity over the same statement skeleton, or a different
  single scalar value for the same property). Precision-first by design.

## Snapshot counts (production `memory_records`, scan 1)

| Measure | Count |
|---|---|
| Total records | 441 |
| By state | active 413, deleted 28 — **no candidate / verified / superseded / archived records exist** |
| Live records | **413** (episodic 410, experience 3) across 5 of 9 namespaces |
| Live by source | agent:friday 223, agent:stratex 147, agent:forge 43, api 5, event-inbox 1 |
| **Exact-duplicate groups** | **13** (44 records involved) |
| **Exact-duplicate excess records** | **31** — 7.5% of the live store |
| **Near-duplicate pairs (≥0.85)** | **32** (31 records involved) |
| **Direct-contradiction pairs** | **0** |
| `contradicts` / `supersedes` relationship rows | 0 / 0 |
| Records carrying a write-time `contradiction_candidate` provenance flag | 0 |
| Live records missing `content_hash` | 0 (hash-collision groups: 0) |
| Records with `superseded_by_id` set but not in superseded state | 2 — both are **deleted** 2026-11-13 test-probe leftovers (`wf015…` in friday/private) whose targets are also deleted; cosmetic, on dead rows only |

Duplicates by namespace: `memora://friday/general` — 11 groups / 29 excess;
`memora://forge/private` — 2 groups / 2 excess.

## Evidence (samples; full scan JSON retained by the crew)

- Largest group: **10 copies** of “Store the research findings and analysis in
  persistent memory: Research current crypto market trends and store …” in
  friday/general, created 2026-11-03 07:57–14:50 (ids dc2b385c…, 6b3ed9ee…,
  b2c261d8…, 494cf674…, b8b63632…, de719d77…, +4).
- “report status” ×6 in friday/general (2026-11-02, ids 722cbaa6…, fc2810c4…,
  62c5052e…, cfd5e8ba…, 7520969c…, b5a133ac…).
- Two more “Store the research findings…” variants ×5 and ×4 (2026-11-04);
  “store that autonomous orchestration is working” ×3 (2026-11-03).
- Near-duplicate texture: the same task-instruction records re-stored with
  small wording drift (Jaccard 0.875–0.979, e.g. 8723f4f8… vs 45b50b19… at
  0.979), plus a Forge incident record pair at 0.952 (30a3c6ad…/ea663839…).

## Interpretation (stated plainly)

1. **The duplication is real but narrow**: repeated *episodic task-instruction
   records* written by FRIDAY/Forge orchestration on Nov 2–4, bypassing or
   predating the write pipeline's dedup guard. It is not a store full of
   conflicting facts.
2. **Zero contradictions is a measured result, not a missing check**: the
   conservative detector found no same-subject conflicting values, and the
   write pipeline's own contradiction flags agree (0 stored). The honest
   caveat: the store holds almost no short factual assertions (410/413
   episodic), and the detector is precision-first — broader semantic conflicts
   (e.g. two long research summaries disagreeing) are outside its rules by
   design and are **not** claimed absent.
3. **The lifecycle machinery is unused in production**: no record has ever
   been verified or superseded. The cleanup therefore cannot lean on
   “verified” status today — winner selection resolves via evidence score
   then recency (see the module docstring for the full rule order).

## What the shipped pass would do on this snapshot (on coordinator go-ahead)

- **31 supersessions** (exact duplicates): per group, keep the winner
  (verified → evidence → last-verified → newest), supersede the other 31 with
  `superseded_by_id` set, provenance preserved + annotated, one AuditLog row
  each. Nothing deleted; fully reversible by state transition.
- **0 contradiction actions.**
- **32 near-duplicate pairs: review class only** — planned and reported,
  never auto-applied unless a human opts in per run (`--include-near`).

## Deliverables in the PR

- `Memora/core/memory/hygiene.py` — analyzer + guarded apply (reuses
  `ContradictionDetector`, `SupersessionEngine`, `MemoryLifecycleEngine`).
- `Memora/scripts/memory_hygiene.py` — operator CLI; dry-run by default;
  `--apply` additionally requires `MEMORA_HYGIENE_APPLY=1`.
- `Memora/tests/test_memory_hygiene.py` — 10 tests (winner rules, evidence
  before recency, provenance preservation, audit rows, idempotency, scope
  isolation, near-dup opt-in gate).

**Production apply is NOT part of this task's execution — it waits for the
coordinator's confirmation, per the tasking.**
