# TASK-FRD-062 — Checkpoint 2: CRM build (implemented + tested)

**Task:** FRIDAY: CRM workspace surface — contacts, deals and follow-ups managed by voice and chat.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-062-crm-workspace-surface`.
**Claimed:** 2026-11-27 ~12:27 IST (hub #2045 comment 7212004537).
**Checkpoint 1 (scoping):** filed 2026-11-27 ~13:25 IST (commit `54b241c6`).
**Checkpoint 2 filed:** 2026-11-27 ~15:00 IST.
**Board on live main `25612602`:** CLAIMED / owner `muse_tp1` / branch recorded / pr null (flip to IN_REVIEW rides in the work PR).

## 1. What checkpoint 2 built

Per the checkpoint-1 design (§3), no scope change:

- **`FRIDAY/src/friday/core/oracle.py`** — two new tables in the shared
  metadata, created idempotently by the existing `ensure_schema()`:
  `contacts` (id, name, email UNIQUE, phone, company, source, notes_json,
  created_at, updated_at) and `deals` (id, contact_id, title, stage,
  value_text, notes_json, created_at, updated_at, stage_changed_at).
  No FK constraint, following the codebase convention (e.g.
  `messages.conversation_id`); the store enforces contact existence.
- **`FRIDAY/src/friday/crm/store.py`** (new) + `friday/crm/__init__.py` —
  `CrmStore`: SQLAlchemy Core constructs only (`select`/`insert`/`update`,
  no raw SQL, no dialect syntax) so the same code runs on Oracle and on
  the test SQLite engine. Production: lazy `oracle.get_engine()`. Tests:
  caller-supplied engine, gated by `ephemeral_backend_allowed()` exactly
  like the other test-only backends. Fail-closed: unknown contact/deal
  reference raises (never guessed), ambiguous name fragment raises
  listing the matches, invalid stage raises with the valid list,
  duplicate email raises. Stage moves append to an append-only history
  in `notes_json` (capped at 20) and update `stage_changed_at`; moving to
  the current stage is a no-op that reports it.
- **`FRIDAY/src/friday/proactive/followup_registry.py`** — CRM link only:
  `add(..., contact_id, deal_id)` passthrough, `list()` and
  `due_followups()` filters. No second follow-up store; all existing
  callers use keyword args and are unaffected.
- **`FRIDAY/src/friday/tools/builtin/crm_tools.py`** (new) — six tools,
  all `SafetyLevel.SAFE` (the Gemini Live session only offers SAFE tools,
  so the whole surface is voice-visible per the acceptance):
  `crm_contact_add`, `crm_contact_get`, `crm_contact_list`,
  `crm_deal_add`, `crm_deal_stage`, `crm_followups_due`. Name/title
  fragments resolve through the store's fail-closed resolver; due
  follow-ups are formatted by the existing `format_followup` with the
  linked contact/deal name appended.
- **Wiring** — exported from `friday.tools.builtin`, registered in the
  live agent registry (`agent/mixins/tools.py`, after the follow-up
  tools), and added to the AUDIT-2 wiring regression
  (`test_ig_tool_registry_wiring.py` EXPECTED) so a missing
  `registry.register(...)` line fails the suite.
- **CI collection** — `tests/test_frd062_crm.py` added to the FRIDAY
  tier-1 invocation in `.github/workflows/friday-universe-ci.yml` (REL-068
  guard: a PR test must be collected by a PR-triggered workflow). The
  same PR touches `tests/test_ig_tool_registry_wiring.py` (CRM tools
  added to EXPECTED), so that file rides the same invocation too — it
  was uncollected pre-existing debt, surfaced by this PR's change.

Out of scope, as designed: no outreach of any kind; no lead→contact
import; no desktop/UI widget; no currency math; owner-only, single-user.

## 2. Verification (repo-side, first-hand this run)

Local venv (`/home/hatch/.venvs/friday-frd062`, FRIDAY `requirements.txt`
+ pytest + pytest-asyncio, `PYTHONPATH=src`), branch head:

- **New suite `tests/test_frd062_crm.py`: 19 passed in 0.74s.**
  Store round-trips (add/get, unreachable flag, duplicate-email
  rejection, fragment/company search, resolve ambiguity), deal pipeline
  (default `lead`, invalid-stage rejection, stage history + timestamps,
  same-stage no-op), registry CRM link (passthrough + filters), tool
  round-trip through the acceptance script (add contact → open deal →
  move to proposal → due follow-up reads back with the contact name),
  fail-closed tool errors (unknown/ambiguous contact, invalid stage,
  unknown deal), and the all-SAFE assertion.
- **Neighbouring suites: 199 passed** — `test_ig_frd_002_followup_registry`,
  `test_ig_tool_registry_wiring`, `test_gemini_tool_schema_validity`
  (all builtin schemas incl. the six new ones), `test_voice_tool_security`,
  `test_frd002_tool_gates`.
- **One pre-existing failure, NOT caused by this PR:**
  `test_frd002_tool_gates::test_default_registry_tool_names_are_unique`
  asserts `len(names) == 97`. Proven on pristine main `25612602` in a
  scratch worktree: it fails there too, with **155** tools (the hardcoded
  97 is stale — the registry has grown since TASK-FRD-002). This PR makes
  it 161 (155 + 6 CRM tools). The test's real assertion — no duplicate
  tool names — still passes. The file is not named in any PR-triggered
  workflow, so it does not block this PR. The stale count is left
  untouched here (out of scope; coordinator re-slot) and recorded here
  so no one mistakes it for a regression.
- **`ruff check src/friday`: all checks passed** (whole tree, CI lint
  command). `ruff format` is not enforced in CI; formatting left as-is.
- **REL-068 collection guard** (`scripts/ci_test_collection_audit.py
  --base origin/main`): first run (pre-commit) flagged the workflow
  reference as stale only because the test file was still untracked;
  second run (post-commit) flagged `test_ig_tool_registry_wiring.py`
  as uncollected because this PR modifies it — fixed by adding it to
  the same tier-1 invocation; re-run after the fixup commit, guard
  green (see work PR checks).

## 3. States

- Implemented: YES (this checkpoint).
- Tested: YES (19 new + 199 neighbouring, local evidence above).
- Merged: NO — work PR next; never merge my own PR (paired verifier + coordinator merge).
- Deployed: NO — deploy clearance is coordinator-side; no deploy attempted.
- Production-verified: NO — live proof needs a merged + deployed build
  and a real voice+chat session executing the checkpoint-1 §3 acceptance
  script (create contact, move deal stage, read back today's follow-ups,
  plus the unknown-contact / invalid-stage failure cases).

## 4. Next

1. Open the work PR (one task = one PR; board flip CLAIMED → IN_REVIEW inside it).
2. Paired verifier verdict, then coordinator merge.
3. Deploy clearance → live voice+chat acceptance session on production, filed as evidence before any production-verified claim.
