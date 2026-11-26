# TASK-DB-002 — IntelX DB Wiring: Evidence

- **Task:** TASK-DB-002 (P1, PRIORITY BUILD)
- **Title (board):** "DB: IntelX DB wiring — IntelX research records and Futuris forecasts + scores write/read in Autonomous DB #2 (IntelX DB), proven live"
- **Owner:** Muse 16 — hub #1483 claim 7146448732, branch `muse16/task-db-002-intelx-db-wiring`
- **Status of this document:** REPO-SIDE LEG ONLY. Live proof is **NOT done** and nothing in this document claims it. See §5 (open gates) for what still blocks the live leg.

---

## 1. Acceptance criteria (board record, TASK-DB-002)

1. **Decided arrangement** (owner decisions 2026-11-25 ~02:56 and ~02:59 IST): ALL IntelX and Futuris research work goes to Autonomous DB #2, named "IntelX DB". Reference: Memora -> Autonomous DB #1; Stratex research -> MySQL HeatWave; VyralX -> files only, no database; Cortex -> Redis + files; FRIDAY/Sentinel/Forge -> files; Inference -> stateless.
2. **Naming:** ADB #2's display name was already set to "IntelX DB" via the OCI API on 2026-11-25. This task only VERIFIES the name by API read-back at wiring time and records it here — if the read-back disagrees, stop and report to the coordinator instead of renaming anything. **Not yet verified — gate G1/§5.**
3. **Schema + wiring:** create the research schema in ADB #2 (IntelX findings, watch/envelope records, seen-store entries; Futuris forecasts and accuracy scores) and wire IntelX and Futuris on IntelX-Server to write and read there. Credentials from the fleet env/record only, never printed. Configuration must fail closed to the existing file stores if the database is unreachable — files remain the fallback during migration, and a database outage must not take either agent down (prove with one forced-failure test). **Repo-side schema done (§3); live wiring + forced-failure test gated (§5).**
4. **Data:** migrate the existing file records (IntelX seen-store `state.json`, watch/envelope history, Futuris forecast + score files) into ADB #2, quoting counts before and after; for any record class deliberately not migrated, state exactly why not here. **Migration accounting written (§3.4); live migration gated (§5).**
5. **Live proof** (owner's implementation definition — the thing actually working in the live agent, not code merged): (a) one real IntelX research run's records written to and read back from ADB #2 on IntelX-Server (the daily INT-876 soak run counts as a real run); (b) one real Futuris forecast cycle persisted to ADB #2 and read back. Both proofs filed with timestamps here. **NOT DONE — §5.**
6. **No behaviour change** to IntelX alerting or the Futuris forecast cadence; the soak timer and the Futuris scheduler keep their existing schedules throughout. **Held by design: this leg changes no schedules, no thresholds, no alert budgets (§3.5).**

---

## 2. Design as implemented (repo-side leg)

### 2.1 Topology (unchanged from scoping §3.1)

One database, two schemas. ADB #2 ("IntelX DB") holds two separate Oracle schemas/logins, `INTELX` and `FUTURIS` (matching the existing `AGENT_SCHEMAS` convention in `scripts/oracle_db.py`). Each agent connects with its own login and sees only its own schema. No shared tables, no cross-schema foreign keys or synonyms. Cross-agent reads stay API-level.

### 2.2 Decisions taken in this leg

- **D1 — Seen-store write path: option (a), one writer, one truth.** New module `IntelX/intelx/watches/db_seen_store.py` (`DbSeenStore`) implements the same interface as the file `SeenStore` (`section` / `mark` / `alerts_today` synchronous, same section shape) and persists to `watch_seen` / `watch_envelopes` when a DSN is configured. The JSON file remains the fallback. One deliberate difference, recorded here: `mark` preserves `first_seen` on re-mark (the file store overwrites it); re-marks do not occur in the poll flow because duplicates are skipped first, so the difference is unobservable in production. The engine's stdlib-only property is preserved — the DB code lives in the new module, not in `watches/engine.py`. The file path keeps working in tests/standalone.
- **D2 — Alembic 0003 is the schema-creation mechanism; `create_all` stays as boot belt-and-braces.** Migration `IntelX/intelx/db/migrations/versions/0003_watch_tables.py` (revises `0002_evidence_data_model`) creates `watch_seen` and `watch_envelopes`; its column definitions match `intelx/db/models.py` (`WatchSeen`, `WatchEnvelope`) exactly. The lifespan `create_all` bootstrap also creates them from the same models. The two mechanisms must not disagree about table definitions — the schema-inventory test (§4) guards this.
- **D5 — Retention/pruning parity: implemented.** File stores prune at 90 days (`PRUNE_DAYS`) for non-alert records and keep `alerted` / `suppressed_budget` rows; `live_research_runs` keeps the newest 200. `DbSeenStore.save()` and `prune()` apply the same 90-day rule to `watch_seen` (same retained statuses). ADB #2 therefore does not grow unboundedly from the watch tables.
- **D3 — `DurableResearchStore` (SQLite): NOT decided in this leg.** No production call-site was found (only `intelx_upgrade/persistence.py` and tests reference it). Whether it is live is gate G5 — confirm on IntelX-Server before migrating or retiring it. This leg neither migrates nor deletes it.
- **D4 — `RealForecastEngine` file state: NOT decided in this leg.** The DB-backed repository/scheduler path and the file-backed engine (`futuris/.data/forecast_state.json`) coexist; which serves live traffic is gate G4. This leg adds the migration *accounting* for the file (`count_file_records`) but migrates nothing until G4 is answered.

### 2.3 Files changed / added (repo-side leg)

| File | Change |
|---|---|
| `IntelX/intelx/db/models.py` | Added `WatchSeen` (`watch_seen`) and `WatchEnvelope` (`watch_envelopes`). Every existing model untouched (append-only diff). |
| `IntelX/intelx/db/migrations/versions/0003_watch_tables.py` | New Alembic migration (revises 0002), creates both tables + indexes; downgrade drops both. |
| `IntelX/intelx/watches/db_seen_store.py` | New module: `DbSeenStore` (DB-backed seen-store + envelope mirror, observable file fallback) and `count_file_records` (migration dry-run accounting). |
| `IntelX/tests/test_db002_watch_seen.py` | New: roundtrip, dedupe, prune, file-fallback tests (scoping §5 tests 1, 2, 4, 5). |
| `IntelX/tests/test_db002_watch_envelopes.py` | New: envelope idempotency, roundtrip, DB-down-fails-safe tests (scoping §5 test 3 + 2 supporting). |
| `IntelX/tests/test_db002_migration.py` | New: migration-counts + schema-inventory tests (scoping §5 tests 12, 13). |
| `docs/collaboration/TASK-DB-002-INTELX-DB-WIRING.md` | This document. |
| `docs/collaboration/WORK_BOARD.yaml` | TASK-DB-002 record flip AVAILABLE → CLAIMED (rides in this PR per owner rule 4). |

Not changed in this leg (deliberate): `IntelX/intelx/watches/engine.py` (stdlib-only engine untouched — the `WatchService` wiring that passes a `DbSeenStore` in is a follow-up wiring step, see §5); `IntelX/Dockerfile` SQLite default and `IntelX/SYSTEM_MANIFEST.md` staleness (scoping risk R1 — correct in the wiring leg or a follow-up, not silently here); `Futuris/.env.example` ambiguity (gap G3 — confirm which ADB instance, then correct); any DSN, env file, or credential (none touched, none printed).

### 2.4 Fallback behaviour (as implemented)

- `DbSeenStore` degrades to the JSON file store on any DB failure (`load`, `save`, `record_envelope`, `prune`). Every fallback logs a warning on `intelx.watches` and increments a counter (`fallback_counts()`: keys `load`, `save`, `envelope`, `prune`). All counters must read zero in a healthy run; any non-zero value must be explained here (scoping risk R2).
- The JSONL outbox is untouched: envelopes are still appended to the file outbox first (TASK-PRO-001's delivery contract); the `watch_envelopes` row is a durable mirror. If the DB is down, `record_envelope` returns False and the poll continues.
- `persist_live_research()` is already best-effort (returns `None`, caller reports `durable_run: False`) — unchanged by this leg.

### 2.5 Behaviour-change guard

No schedules, thresholds, alert budgets, or poll intervals change in this leg. The watch poller's dedupe/budget logic reads the same section shape from `DbSeenStore` as from the file store. The Futuris scheduler is untouched.

---

## 3. Repo-side status

| Item | State |
|---|---|
| `watch_seen` / `watch_envelopes` models | DONE (this PR) |
| Alembic 0003 migration | DONE (this PR; not yet executed against any database) |
| DB-backed `SeenStore` | DONE (this PR; not yet wired into `WatchService` — wiring step, §5) |
| Tests 1–5, 12–13 (scoping §5) | WRITTEN for CI (this PR; **not run by the authoring pass — no local execution of repo code is permitted in this environment; CI is the test runner**) |
| Migration accounting helper | DONE (`count_file_records`; live counts TBD at migration time) |
| Board flip (AVAILABLE → CLAIMED) | In this PR |
| Live wiring (env → ADB #2) | NOT DONE — gated (§5) |
| File-record migration | NOT DONE — gated (§5) |
| Live proof (a) soak run read-back | NOT DONE — gated (§5) |
| Live proof (b) Futuris cycle read-back | NOT DONE — gated (§5) |
| Forced-failure live test | NOT DONE — gated (§5) |
| ADB #2 display-name read-back ("IntelX DB") | NOT DONE — gated (§5) |

**Five-state status of TASK-DB-002 after this leg: implemented = repo-side code only (not production-verified); tested = CI pending; merged = this PR pending; deployed = NO; production-verified = NO.**

---

## 4. Tests (scoping §5)

Written for CI; not executed in the authoring environment.

| Test | Proves |
|---|---|
| `test_db002_watch_seen_roundtrip` | Marked item reads back with fingerprint, status, `first_seen` |
| `test_db002_watch_seen_dedupe` | Same fingerprint twice → one row; second poll sees a duplicate |
| `test_db002_watch_envelope_idempotent` | Same `dedupe_key` twice → one `watch_envelopes` row |
| `test_db002_watch_seen_prune` | >90-day non-alert rows pruned; alerted rows kept |
| `test_db002_seen_store_file_fallback` | DB unreachable → file fallback, still marks/alerts, fallback counted |
| `test_db002_watch_envelope_roundtrip` | Stored envelope reads back verbatim |
| `test_db002_watch_envelope_db_down_returns_false` | DB down → `record_envelope` returns False, never raises |
| `test_db002_migration_counts` | Dry-run counts per record class; unreadable files named |
| `test_db002_schema_inventory` | Declared models = expected ADB #2 inventory (IntelX 19 + 2 new) |

Not yet written (live/staging, not CI): scoping tests 6–11 (live-research persist/fetch, DB-down degrade, Futuris score roundtrip/idempotency/backfill, settings-reject-SQLite-prod) and 14–17 (live soak read-back, live Futuris cycle read-back, live forced-failure, ADB name read-back). Tests 6–11 belong to the next repo-side pass; 14–17 are filed as evidence on IntelX-Server, not as CI tests.

---

## 5. Open gates (what still blocks the live leg)

- **Bridge approval 7113152293 — OPEN.** All live legs (server access, DSN confirmation, proof runs, forced-failure test) run through the bridge. If it stays open, this PR lands repo-side only and the task is genuinely BLOCKED with reason (per the aggressive-completion rules, this PR must not be claimed as completion without live proof).
- **G1 — ADB #2 connection details unverified.** No DSN, host, service name, or login for ADB #2 exists in the repo. Needed: ADB #2 host/service, the `INTELX` and `FUTURIS` logins, and confirmation of which env file on IntelX-Server carries each DSN (`/opt/friday_universe/IntelX/.env` is confirmed for IntelX; Futuris's env-file path is not stated in the repo). **Request on the hub; never in chat.**
- **G2 — Which ADB do the live services point at today?** Unverifiable from the repo. The first live step is a read-only check of the running services' effective DSN host/service (host + service name only) to establish the before-state.
- **G4 — Which Futuris forecast path is live?** DB-backed repository/scheduler vs file-backed `RealForecastEngine` (`forecast_state.json`). Determine on IntelX-Server before migrating; migrating the wrong path's data proves nothing.
- **G5 — Is `DurableResearchStore` (SQLite) live?** No production call-site found. Confirm on IntelX-Server whether `./data/intelx_durable.db` exists and is written; if dead, record and retire with a reason rather than migrating it.
- **G6 — Soak timer not installed.** INT-019 legs A–C (timer install, day-4 run, traced consumption) are blocked on the bridge approval + timer clearance. Proof (a) needs either the timer installed or a coordinator-approved manual proving run (`run_int876_soak.py --force`).
- **Wiring step (repo-side, follow-up):** pass a `DbSeenStore` into `WatchService` — `await store.load(watch.id)` at poll start, `await store.save()` at poll end (replacing the synchronous `self.store.save()`), `await store.record_envelope(envelope)` after each outbox append. Until that lands, the file store remains the live path and `DbSeenStore` is exercised by its tests only.
- **Coordinator hub clearance** before any production change (standing rule).

---

## 6. Sources

- Scoping: `~/workspace/muse16-db002/DB-002-SCOPING.md` (2026-11-25 ~04:10 IST; read-only API reads on main `80b75649`).
- Board record TASK-DB-002, main `14181d3c` (22,993 lines) at authoring time; hub #1483 comments 7145308228 (programme), 7145448295 (escalation), 7146448732 (claim).
- Repo files read first-hand via the GitHub API at authoring time: `IntelX/intelx/db/models.py` (595 lines), `IntelX/intelx/db/migrations/versions/0002_evidence_data_model.py` (519 lines), `IntelX/intelx/watches/engine.py` (1,105 lines), `IntelX/intelx/db/{session,base,engine}.py`, `IntelX/tests/{conftest,test_standing_watches,test_repos}.py`, `Futuris/futuris/core/real_forecast_engine.py` (state-file shape).
