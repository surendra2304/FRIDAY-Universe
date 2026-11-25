# TASK-VYR-082 — CHECKPOINT 1 (scoping) — Muse TP5

**Task:** TASK-VYR-082 — VyralX: layered marketing architecture — the seven-layer growth system on top of `channel_operator` (P2).
**Claim:** hub #1483 comment 7155045118 (2026-11-25 12:10 IST). **Branch:** `musetp5/task-vyr-082-layered-marketing`, claimed from main `f73bddd7`, rebased to main `ec46d5f0` in the 2026-11-25 ~15:10 IST self-check (fast-forward, ancestry verified first-hand). **Queue:** VYR-082 (current) → VYR-081 (pre-staged next). Board record on main reads AVAILABLE / owner null — the claim flip rides in the work PR (rule 4, hub 7143628341). No work PR yet — correct under rule 1 (one PR when DONE or genuinely BLOCKED).

**Spec (read first-hand from `docs/collaboration/WORK_BOARD.yaml` on main `ec46d5f0`):** source vyralx package V-03, item `DeihbtONYtH`. Layers: 01 SIGNALS, 02 SYSTEM OF RECORD, 03 THE BRAIN / Growth Director, 05 DEPARTMENTS, 06 DATA & OBSERVABILITY, 07 HUMAN HANDOFF; per-domain databases (ads.db / leads.db / sales.db pattern). Done = the loop runs one real weekly cycle and produces a channel growth plan from live channel data.

**`channel_operator` as built** (385 lines, read first-hand on main `ec46d5f0`): `analyse_channel` / `propose_packaging` / `build_schedule` / `draft_comment_replies` / `run_operator_cycle` / `enqueue_operator_plan` — pure functions over dicts; hard limits (never publishes, everything `pending_review`, unlisted only; production VIDEO_METRICS holds 0 rows, so a no-metrics snapshot names no winner).

## Layer map (first-hand)

- **L01 SIGNALS** — in-repo pieces exist: `competitor_ads` (same IG source `DeihbtONYtH` — rank + pattern-extract over operator-supplied records), comments via `draft_comment_replies`, `discovery` / `pd_whitelist`, `audience_intelligence`. DMs, website visitors, lead forms, reviews & mentions, sales calls live in Cortex, not VyralX — intake takes what VyralX holds and records the rest as out-of-scope, never invented.
- **L02 SYSTEM OF RECORD** — `channel_strategy.json` (read-only loader), `content_calendar_manager`, render/provenance records. The board's ads.db / leads.db / sales.db pattern is **adapted**: repo AGENTS.md forbids a local SQLite file for any agent (Oracle only) — record stores will be JSON in the app data dir (the review-queue pattern), not `.db` files.
- **L03 THE BRAIN / Growth Director** — the NEW piece. `run_operator_cycle` is single-shot with no memory or feedback; the loop reads L01+L02, decides per department, writes the plan, logs decisions, and learns from measured outcomes.
- **L05 DEPARTMENTS** — market intelligence → `competitor_ads` + `audience_intelligence`; **paid ads → EXCLUDED** (free-only, no ad accounts, no spend — named hard reason); content studio → `idea_generator` / `content_optimizer` / `format_templates`; publishing → `build_schedule` (plans only); lead capture / sales response → Cortex-owned, not applicable in VyralX; nurture & retargeting → `drip_scheduler`; reputation → `community_manager` + `draft_comment_replies`.
- **L06 DATA & OBSERVABILITY** — cost per lead / speed to lead / booked & paid / ad to customer are **not measurable in VyralX** (no spend, no leads, no sales) — recorded unmeasured, never invented. Measurable: agent activity log (new), render QA pass rates (VYR-044), views where metrics exist (currently none).
- **L07 HUMAN HANDOFF** — unchanged: the owner's unlisted review-first gate; every plan entry `pending_review`, `requires_approval`, `publish` False, enqueued via the `remix_flow` review queue.

**Gap, recorded honestly:** Layer 04 is absent from the spec (it jumps 03 → 05) and no "Layer 04" text exists anywhere in the repo. The layer model implements 01/02/03/05/06/07 as specified and records 04 as not-in-source; it will not be invented.

## New work (next)

`VyralX/app/services/layered_marketing.py` — signals intake, record stores, the growth-director weekly loop, department functions, KPI snapshot, activity log; tests `test_vyr082_layered_marketing.py` + CI list line (VYR-060/VYR-064 precedent). Live verification = one real weekly cycle against live VyralX-Server data via the bridge (read-only); the plan is built from the live snapshot, with `metrics_available=False` stated honestly if VIDEO_METRICS is still empty.

## Corrections verified first-hand (2026-11-25 ~15:10 IST self-check, main `ec46d5f0`)

- TASK-VYR-060 board record reads MERGED / owner `muse_tp5` / pr 1730 on main — the flip has landed (no longer owed in the VYR-082 work PR).
- TASK-VYR-064 work PR #1743 MERGED (merged_at 2026-11-25T01:52:45Z); board record MERGED / pr 1743 on main.
- Muse TP5 roster entry is on main (`docs/collaboration/TEAM_ROSTER.yaml`, id `muse_tp5`); roster PR #1706 is closed unmerged — registration landed via the board, no re-open owed.
- TASK-VYR-046: TP5 stands down (claim withdrawn, hub 7155045118); VYR-046 is pool-available. TP5 branch `musetp5/task-vyr-046-cycle-3-candidate-pool` @ `f6b912a6` holds no work commits.

— Muse TP5
