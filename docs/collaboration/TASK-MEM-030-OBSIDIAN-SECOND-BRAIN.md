# TASK-MEM-030 — Memora: Obsidian-vault second-brain presentation plus nightly per-agent work summaries

- **Work PR:** #1772 (head `427ec8237f`, branch `muse2/task-mem-030-obsidian-second-brain`; evidence-doc + board-flip commit follows on the same branch)
- **Claim:** hub #1483 comment 7152738824 by Muse 2, 2026-11-25 ~09:50 IST
- **Board:** MEM-030 verified AVAILABLE / owner null on main `c52daf14` (board blob
  `e997ed62`, 22,565 lines, verified against the true main blob before editing).
- **Status:** implemented YES / tested YES / merged NO / deployed NO /
  production-verified NO (see §5).

## 1. Scope (what the acceptance lines mean, grounded in the store)

The board record's two acceptance lines, read against the live store:

- *"The vault view exists over Memora's store (Inbox, Daily Logs, Projects, Areas, Resources, Memories, Archive)."* Memora's store is the relational `MemoryRecord` table (`Memora/storage/relational/models.py`): `content_text`, `memory_type` (episodic/semantic/procedural/preference/working/decision/relationship/experience/project/tool/system), `lifecycle_state` (candidate/active/verified/superseded/archived/deleted), `namespace_path` (`memora://<agent>/...`), `agent_id`/`owner_agent`, `provenance`, `confidence`, `importance`, `scope` (PRIVATE/SHARED/UNIVERSAL). The vault view is a Markdown rendering of those records: one note per memory, filed into the seven named folders, plus one hub note per agent and a root index note — readable in Obsidian with no service running.
- *"One nightly summary cycle from every agent is evidenced in the vault."* The feed is the capture-event stream MEM-029 wired as production callers (every turn captured as a `POST /v1/capture/events` observation with `provenance.session_id` + `event_kind`; sessions compressed at session end). One nightly run writes one summary note per agent per night into Daily Logs, grouped by session and kind. "Every agent" is the ten canonical handles (friday, memora, cortex, forge, futuris, inference, intelx, sentinel, stratex, vyralx — the ten top-level agent directories, lower-cased to the `AgentCreate.name` handle form).

Note: GAP-LIST.md itself is not in the repo tree (no such path on main); the task's source line is the board record's citation, and the scope above was grounded by reading the store schema, the capture service, and the MEM-029 evidence doc rather than by reading the list — the same position MEM-029 recorded.

What MEM-029 enables here: without its production callers there would be no per-agent event stream to summarise — the vault would render memories but the nightly cycle would have nothing to count. The vault reads the same records MEM-029's callers write (skill outcomes → drafts, owner corrections → standing rules, turns → capture events).

## 2. What changed

| File | Change |
|---|---|
| `Memora/core/memory/vault.py` (new, +415) | Stdlib-only vault builder. `build_vault(records, out_dir)` creates the seven folders, one note per memory (YAML frontmatter: id/agent/type/lifecycle/scope/namespace/created/confidence/importance/source/session/event_kind/tags + `[[wikilinks]]`), one hub note per agent in `Areas/Agents/`, root index `00 - Second Brain.md`. Routing, first match wins: archived/superseded/deleted → Archive; candidate → Inbox; project type or `/projects/` namespace → Projects; semantic/procedural/tool/system → Resources; preference/decision/relationship → Areas; episodic/experience/working (and anything else) → Memories. Deterministic + idempotent (same records in, same files out). |
| `Memora/core/memory/nightly_summary.py` (new, +243) | Stdlib-only nightly summariser. `run_nightly(records, date, out_dir)` writes `Daily Logs/YYYY-MM-DD-<agent>.md` per agent: counts by kind, sessions grouped with per-kind first-lines (the capture digest's extractive shape, extended from one session to one agent-day), `[[links]]` to each event's vault note. `run_daily_cycle` ties vault + summaries into one run; `load_records_json` reads a JSON list or JSONL export. |
| `Memora/scripts/nightly_vault.py` (new, +66) | CLI for the nightly job: `--records <export> --date <YYYY-MM-DD> --out <vault> [--include-private]`, prints the run manifest as JSON. Reads `memora_export.py`'s `memory_records.jsonl` (TASK-MEM-007, read-only live-store dump) field for field. No live dependency — no service, no database, no network. |
| `Memora/tests/test_mem030_obsidian_vault.py` (new, +320, 39 cases) | See §3. |
| `.github/workflows/friday-universe-ci.yml` (+1) | New suite collected in the Memora tier-1 step (REL-068 audit requires a PR-touched test file to be collected; the tier-1 collection gate's fixed 21-file list is untouched — this file is not tier-1-named). |
| `docs/collaboration/TASK-MEM-030-OBSIDIAN-SECOND-BRAIN.md` (this file, new) | Evidence doc. |
| `docs/collaboration/WORK_BOARD.yaml` | Flips (§6). |

Two deliberate safety rules, both locked by tests:

- **Scope is fail-closed.** A PRIVATE-scope record — or one whose scope is unknown and cannot be derived from its namespace — is excluded from the vault build AND from nightly summaries unless the caller passes `include_private=True`. A personal vault must never silently publish an agent-private memory, and a summary must never surface an event whose own note the vault withholds.
- **Silent agents are reported, not invented.** An agent with no capture events for the day still gets a note, and the note says "No captured work for \<agent\> on \<date\>" — the note evidences that the cycle RAN for every agent; the count (zero) is the finding.

Deliberately NOT built: no live-server read inside this PR (the nightly job consumes an export file; the live export + first live run are the gated live leg, §5), no second secret-scrubber (scrubbing is the write pipeline's job — `core.memory.capture_service.scrub_secrets` — and the vault renders store content as-is), and no Obsidian plugin or sync daemon (the vault is plain Markdown; sync is the vault host's job).

## 3. Tests (repo-side, CI-run)

New suite `Memora/tests/test_mem030_obsidian_vault.py` (39 cases: 23 test functions, one routing test parametrised over 17 cases), plain record dicts shaped like `MemoryRecordRead`, no live service, no database:

- **Vault:** all seven folders + index exist; the 17-case routing table; PRIVATE excluded by default and counted, included with opt-in; unknown scope without namespace treated as PRIVATE; records without id skipped and counted; frontmatter/body/wikilinks exact; filename sanitisation (`../evil` → `evil.md` inside the vault, nothing escapes); idempotent re-run (byte-identical notes); hub notes for all ten agents even on an empty store; agent derived from the `memora://<agent>/...` namespace; empty store builds an empty vault.
- **Nightly:** one summary per agent with events (counts by kind, session grouping, event-note links); silent agent gets the honest no-work note; other days' events excluded; unknown kinds normalised to `observation` (the capture service's rule); duplicate first-lines collapsed; PRIVATE events excluded from summaries by default; non-capture records not summarised; bad dates rejected; JSON-list and JSONL export loading; the combined daily cycle (vault note + daily note from one run).

The file is added to the Memora tier-1 step in `.github/workflows/friday-universe-ci.yml`, so repo CI executes it. The modules under test are stdlib-only, so they import without the service's SQLAlchemy stack; the Memora tier-1 venv already installs the full requirements, and the directory conftest (whole-app TestClient) loads exactly as it does for the existing Memora suites.

## 4. Files changed (work PR #1772)

- `Memora/core/memory/vault.py` (new)
- `Memora/core/memory/nightly_summary.py` (new)
- `Memora/scripts/nightly_vault.py` (new)
- `Memora/tests/test_mem030_obsidian_vault.py` (new)
- `.github/workflows/friday-universe-ci.yml` (+1)
- `docs/collaboration/TASK-MEM-030-OBSIDIAN-SECOND-BRAIN.md` (this file, new)
- `docs/collaboration/WORK_BOARD.yaml` — flips (§6)

Method note: all work through the GitHub REST API only (API-only per the STR-077 execution-risk precedent). No local clone, no local run/build/test/import of repo code; files were read as text via the API and repo CI is the test runner. Working copies live under `~/workspace/mem030-work/` (persistent — a mid-task `/tmp` wipe destroyed MEM-029's first working copies).

## 5. Five states

- **implemented: YES** — this PR.
- **tested: YES** — 39 new cases, repo CI is the runner; check-runs on the PR head are the verdict (see the PR).
- **merged: NO** — peer merge only; never my own PR.
- **deployed: NO** — deploy needs coordinator clearance; the live leg is GATED by the standing owner stop order (in force since ~2026-11-24 16:42 IST).
- **production-verified: NO** — no live cycle is claimed. Owed after deploy clearance: first live export (`memora_export.py`) → vault build on the vault host with a read-back of all seven folders, first nightly run evidencing one summary note per agent (including honest zero-activity notes for silent agents), and Surendra's Obsidian read-back of the vault.

## 6. Board flips (ride in this PR)

- **MEM-029 IN_REVIEW → MERGED** (work PR #1765, merge `c4267ca1`, 2026-11-25 03:39:41Z, by Surendra).
- **MEM-030 AVAILABLE → CLAIMED** (owner `muse_2`, branch `muse2/task-mem-030-obsidian-second-brain`, pr 1772). Correction (repair pass): the first version of this PR carried the flip as IN_REVIEW; it is corrected here to CLAIMED, the claim state the assignment brief asked for — the task is claimed (hub comment 7152738824) and this work PR carries the claim record.

All old lines were verified against the true main board blob (`e997ed62`, 22,565 lines, main `c52daf14`) before editing — exact-match only. No other record touched.

— Muse 2
