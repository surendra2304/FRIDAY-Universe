# TASK-FRD-062 — Checkpoint 1: scoping

**Task:** FRIDAY: CRM workspace surface — contacts, deals and follow-ups managed by voice and chat.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-062-crm-workspace-surface` @ `06ff9ee6`.
**Claimed:** 2026-11-27 ~12:27 IST (hub #2045 comment 7212004537). **Checkpoint 1 filed:** 2026-11-27 ~13:25 IST.
**Board on live main `e07f6d1d`:** CLAIMED / owner `muse_tp1` / branch recorded / pr null.
**Source:** watch DgEjz7iS2_v (a Jarvis-style assistant operating inside a CRM — client records pulled up and worked conversationally). FRIDAY has no CRM surface today.

## 1. Acceptance (board, verbatim substance)

- Build a lightweight CRM in FRIDAY's data layer (contacts, deals/opportunities, follow-up tasks) fully operable by voice and chat: add a contact, log a deal stage change, ask what follow-ups are due, get the answer spoken. Built for the owner's own use, including the CometWorks earning pipeline.
- **Done = live proof on production:** a voice+chat session that creates a contact, moves a deal stage and reads back today's follow-ups.
- No outreach function is in scope (same boundary as lead generation): contacts are never emailed / messaged / called by this task.

## 2. Codebase map (verified first-hand on main `e07f6d1d`)

| Piece | Location | What it gives FRD-062 |
|---|---|---|
| Persistence (Oracle) | `FRIDAY/src/friday/core/oracle.py` | SQLAlchemy `MetaData` + idempotent `ensure_schema()` (`create_all`). Every table FRIDAY owns is a `Table(...)` in that metadata (UUID ids, ISO timestamps, JSON bodies). CRM tables (`contacts`, `deals`) are declared here, same pattern. |
| Persistence rule | `FRIDAY/src/friday/core/database.py` (docstring) | FRIDAY persists to Oracle Autonomous Database in every runtime path. SQLite is test-only, gated by `ephemeral_backend_allowed()`; production never qualifies. CRM tests use the ephemeral backend; no `.db` file in the live path. |
| Follow-up engine (reuse) | `FRIDAY/src/friday/proactive/followup_registry.py` + `FRIDAY/src/friday/tools/builtin/followup_tools.py` | `followup_add` / `followup_list` / `followup_complete` already exist (TASK-IG-FRD-02), persisted in the registry and mirrored to Memora; `due_followups`, `format_followup`, proactive sweep loop in `FRIDAY/src/friday/api/server.py`. FRD-062 does **not** build a second follow-up store: CRM follow-ups are registry records carrying `contact_id` / `deal_id`, and `followup_list` gains a CRM filter. |
| Tool surface | `FRIDAY/src/friday/tools/builtin/__init__.py` (imports) + `FRIDAY/src/friday/tools/registry.py` (`ToolRegistry`) | New CRM tools are `BaseTool` subclasses registered in the builtin `__init__`, exactly like `followup_tools`. |
| Voice path | `FRIDAY/src/friday/voice/gemini_live_session.py:214-218` | "Voice capabilities follow the live registry" — `registry.list_tools()`. A registered safe tool is automatically available to the Gemini Live voice session; no separate voice wiring. Spoken answers come back through the existing session. |
| Chat path | `FRIDAY/src/friday/api/server.py` | Same registry serves chat; one tool implementation serves both surfaces. |
| Leads (import source, not a store) | `FRIDAY/src/friday/autonomous/lead_generation.py` + `FRIDAY/src/friday/tools/builtin/lead_gen_tools.py` | Scraped directories produce contact tables as Markdown+CSV artefacts; no persistent contact store, no outreach. CRM contacts are persistent and owner-managed. Lead→contact import is a later slice, not checkpoint 2. |
| Task board (FRD-049, TP7, in flight) | Branch `musetp7/task-frd-049-voice-task-board` @ `3920a1d5`: `FRIDAY/src/friday/tools/builtin/task_board.py` + `FRIDAY/src/friday/desktop/task_board_widget.py` | TaskBoardTool stores board state as JSON under `FRIDAY_DATA_DIR` — explicitly "local desktop UI state only, not agent data". FRD-062 must **not** copy that pattern for CRM data: CRM records are agent data and live in Oracle. The desktop widget pattern is available later if a visual surface is wanted; it is not required for acceptance. |
| Tasks (scheduled, not CRM) | `FRIDAY/src/friday/tasks/` (`manager.py`, `models.py`, `scheduler.py`, `task_store.py`) | Scheduled agent tasks (`ScheduleType`, `SafetyLevel`, run logs). Distinct from CRM follow-ups; do not merge the two models. |

## 2b. Cortex overlap check (repo AGENTS.md house rule)

Cortex is the multi-tenant website CRM (AGENTS.md §4: visitors, lead capture/scoring, segments, campaigns, closed-loop follow-up; Oracle `CORTEX` schema; "Cortex CRM data must stay in its Oracle `CORTEX` schema"). Checked first-hand before designing the store:

- Cortex ORM (`Cortex/apps/api/src/cortex_api/db_models.py`): `profiles`, `visitors`, `sessions`, `events`, `leads`, `lead_scores`, `tenants`, `audit_records`, … — **no `contacts` table and no `deals` table**.
- Cortex core models (`Cortex/packages/core/src/cortex_core/models/__init__.py:118`): an `Opportunity` Pydantic shape exists (tenant-scoped, `stage` default `discovery`, `value`, `probability`) but it has **no ORM table and no API route** using it (only referenced from `cortex_core/__init__.py`). There is no `Contact` model anywhere in Cortex.
- FRIDAY→Cortex bridge exists (`Cortex/apps/api/src/cortex_api/friday_router.py`: `/v1/friday/command`, `/v1/friday/priority_leads`, `/v1/friday/incidents`, `X-Friday-Api-Key` auth) — a read surface for scored website leads, not a contacts/deals store.

**Decision:** FRD-062 builds the owner's personal contacts/deals in **FRIDAY's Oracle schema**, per the board acceptance ("a lightweight CRM in FRIDAY's data layer"). The datasets do not overlap: Cortex holds multi-tenant website-visitor/lead data; FRD-062 holds the owner's own contacts and CometWorks deals, added by voice/chat. FRD-062 writes no CRM data into the `CORTEX` schema, so the house rule is respected. If a Cortex sync is ever wanted, the mapping point is the `Opportunity` shape above (stage vocab differs: Cortex `discovery…` vs the board's `lead → contacted → proposal → negotiation → won/lost`); that sync is explicitly out of scope for this task.

## 3. Design (checkpoint 2 build)

**Store.** Two new tables in `friday/core/oracle.py` metadata, created by the existing `ensure_schema()`:

- `contacts`: `id` (UUID), `name` (required), `email`, `phone`, `company`, `source` (e.g. `voice`, `chat`, `lead-import`), `notes_json`, `created_at`, `updated_at`. Unique on `(email)` when email is present; a contact with neither email nor phone is allowed but flagged `unreachable` in read-back.
- `deals`: `id` (UUID), `contact_id` (FK → contacts), `title`, `stage` (enum: `lead`, `contacted`, `proposal`, `negotiation`, `won`, `lost`), `value_text` (free text — no currency math in this task), `notes_json`, `created_at`, `updated_at`, `stage_changed_at`. Every stage change writes a row-level `stage_changed_at` and keeps the previous stage in `notes_json` history (append-only list, capped).
- Follow-ups stay in the existing `followup_registry`; CRM follow-ups carry `contact_id`/`deal_id` in the record so "what follow-ups are due for <contact> / today" is a registry query, not a new table.

**Tool surface** (names provisional until checkpoint 2; all `SafetyLevel.SAFE`, voice-visible):

- `crm_contact_add` (name, email?, phone?, company?, source) → contact id + read-back line.
- `crm_contact_get` / `crm_contact_list` (by name fragment / company) → contact card, speakable.
- `crm_deal_add` (contact ref, title, stage=`lead`) → deal id.
- `crm_deal_stage` (deal ref, new stage) → confirms old → new stage, updates `stage_changed_at`.
- `crm_followups_due` (today / contact ref) → due list via the registry, formatted by the existing `format_followup`.

**Voice/chat flows (acceptance script).** One session, in order: (1) "Add a contact: <name>, <email>" → spoken confirmation with the contact id read back; (2) "Move <deal> to proposal" → spoken old → new stage; (3) "What follow-ups are due today?" → spoken list, each item with its contact/deal name. Failure cases to prove in the same session: unknown contact name is reported, never guessed; an invalid stage is rejected with the valid stage list.

**Out of scope for this task.** Outreach of any kind; lead→contact import (later slice); a desktop/UI widget (voice+chat is the surface the acceptance names); currency/amount math on deals; multi-user/teams (owner-only, single-user store).

## 4. Risks, gates, and live legs

- **Live proof needs a FRIDAY-Server deploy** of the merged CRM code plus a real voice session (Gemini Live) and a chat session against production. Deploy clearance is coordinator-side; no deploy is attempted in checkpoint 2.
- **Bridge route verified this run:** `run_shell` exit 0 on Server 2 (`friday-universe-vnic-2`, 2026-11-27 13:25 IST) via this sandbox's registered `custom.friday-bridge` connection (initialize 200, 31 tools). WATCH210 §2 named TP1 for registration per TP6's mechanism (hub 7211823359) — already satisfied: the connection was registered 2026-11-24 and `run_shell` was verified working 2026-11-26; re-probed working this run. No registration action owed.
- **No owner-gated step** before checkpoint 2: no account creation, no key, no device step. The only owner-facing step is the live voice session itself at acceptance time.
- **Neighbouring work:** FRD-049 (TP7, voice task-board) is in flight on its own branch; FRD-062 shares only the tool-registry pattern with it, no code dependency. No merge conflict expected (new files + two new tables + registry import lines).

## 5. Checkpoint 2 plan

1. `contacts` + `deals` tables in `oracle.py` metadata; `ensure_schema()` covers them.
2. `FRIDAY/src/friday/tools/builtin/crm_tools.py` — the five tools above; register in `builtin/__init__.py`.
3. CRM link on the follow-up registry (`contact_id`/`deal_id` passthrough + filter in `crm_followups_due`).
4. Tests under `FRIDAY/tests/` on the ephemeral backend: contact add/get/list, deal stage transitions (including invalid-stage rejection and unknown-contact refusal), due-list read-back, stage history.
5. Work PR with the board flip (CLAIMED → IN_REVIEW) inside it, per the 2026-11-26 directive (one task = one PR, no checkpoint PRs). Live proof (voice+chat session per §1) follows merge + deploy clearance.

## 6. Verification plan

- Repo-side: new tests green on the ephemeral backend; existing `followup` / `oracle` / tool-registry tests still green; CI 9/9 on the work PR.
- Live: after merge + deploy, one production voice+chat session executing the §3 acceptance script end to end, with the failure cases, filed as evidence in the work PR before any production-verified claim.
