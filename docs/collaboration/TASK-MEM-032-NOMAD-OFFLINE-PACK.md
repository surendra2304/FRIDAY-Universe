# TASK-MEM-032 — Memora offline knowledge pack (NOMAD pattern, adapted): evidence

**Task:** TASK-MEM-032 — Memora: Project NOMAD offline knowledge pack —
offline corpora as a Memora fallback store. Priority P3.

**Worker:** Muse 2. **Claim:** hub #1483 comment 7155563616, 2026-11-25
~12:40 IST (posted together with the TASK-MEM-031 completion).
**Branch:** `muse2/task-mem-032-nomad-offline-pack` (from main be3f303e).

**Scope of this PR — repo work only.** The live legs (deploy + live proof
after coordinator clearance) are GATED by the owner stop order; no live
server was touched, no live-fleet deploy was attempted, and no credentials
were handled. The ADB-disabled query proof runs locally with the ADB path
stubbed/disabled, not against a live fleet — exactly as the task brief
requires.

## 1. NOMAD, read first-hand

**Repo:** Crosstalk-Solutions/project-nomad — "Project NOMAD is an
offline-first knowledge and education server. Wikipedia, thousands of
books, courses, maps, and optional local AI, all running on hardware you
own with no internet required." Apache-2.0, ~44,371 stars / 4,574 forks,
892 commits, main at 8dcb8ea. README read first-hand 2026-11-25 via the
public GitHub page (no code vendored, nothing installed).

**The pattern, as NOMAD states it:**

- **Curated content collections, not a mirror of everything.** A
  Wikipedia content selector + ZIM library manager let the user pick
  exactly which snapshots to keep; maps are picked per region; courses
  are installed as collections. Content is a defined subset, declared
  up front.
- **Offline-first by construction.** Internet is required only during
  installation and when the user chooses to download more content.
  Zero built-in telemetry.
- **Local query paths per collection.** Information Library via Kiwix
  (ZIM archives: one self-contained snapshot of a whole site); AI
  Assistant via Ollama + Qdrant RAG; Education via Kolibri (Khan
  Academy, progress tracked locally); Offline Maps via ProtoMaps
  (one portable tile archive per region).
- **A management layer + a connectivity check.** A Command Center
  orchestrates containerized tools over Docker and checks connectivity
  (Cloudflare `1.1.1.1/cdn-cgi/trace`, falling back to endpoints the app
  already contacts) to decide what is online.
- **Scale note, honestly stated.** NOMAD itself needs ~5 GB of disk and
  under 1 GB of RAM; adding the AI Assistant brings an install to
  ~25 GB because a model needs about its download size in memory.

## 2. What was adapted vs rejected

**Adapted:**

- **Curated subset + manifest (Kiwix/ZIM library manager, shrunk).**
  `Memora/core/memory/nomad_pack/manifest.json` names the pack, version
  (1.0.0), entry count (16), collections, and the corpus SHA-256; the
  corpus is one JSONL file beside it. Load validates count + hash +
  unique ids + declared collections, so a tampered or truncated pack
  fails loudly instead of answering wrong.
- **Local query path, no network after load (offline-first).** The pack
  answers with stdlib-only Okapi BM25 ranking over the bundled corpus.
  A test disables sockets entirely and the pack still answers.
- **Explicit availability probe + fallback switch (connectivity check,
  shrunk).** `resolve_knowledge()` takes an optional `adb_available`
  probe (skips the ADB call outright when it reports down) and an
  `adb_query` callable; ADB up means ADB wins, ADB down/empty/
  unconfigured means the pack answers and says so.
- **Content-selector scoping.** The corpus is a defined subset in three
  collections — `operations` (FRIDAY-Universe standing orders + Memora
  fallback procedures), `reference` (offline-first concepts), `education`
  (offline-learning pointers) — not a Wikipedia mirror.

**Rejected, and why:**

- **Docker-orchestrated Command Center** — too heavy for a Memora
  library fallback; the pack is a Python module, not a server fleet.
- **Full ZIM dumps (Kiwix)** — gigabytes; the pack must be small and
  bundled in-repo (corpus is ~10 KB).
- **Ollama + Qdrant local-LLM RAG** — a model + vector store is the
  opposite of dependency-light; BM25 over 16 entries needs neither and
  answers deterministically.
- **Kolibri / ProtoMaps / CyberChef / FlatNotes as services** — out of
  scope for a Memora knowledge fallback; their *ideas* (curated course
  collections, per-region selection) are represented as corpus entries,
  not adopted as services.
- **No-auth open-server model** — Memora keeps its agent auth; the pack
  is a library the caller invokes, not a port to expose.

**Deliberate non-reuse, documented in the module:** the pack does NOT
import `core.memory.bm25`. A fallback store must still load when the
thing that is down is the primary store's own import chain, so the pack
is stdlib-only. The ranking follows `core.memory.bm25`'s exact scoring
(same tokenizer rules, same Okapi formula, same squash) in ~60 lines,
and the tests pin the ranking behaviour directly.

## 3. Pack layout

- `Memora/core/memory/offline_pack.py` (new, stdlib only) —
  `PackEntry`, `OfflinePack.load()` / `.query()` / `.entry()` / `.info()`,
  `PackError`, and the fallback switch `resolve_knowledge()`.
- `Memora/core/memory/nomad_pack/manifest.json` (new) — pack
  `nomad-offline-pack` v1.0.0, 16 entries, collections
  operations/reference/education, corpus SHA-256
  `cde36742…39135d`.
- `Memora/core/memory/nomad_pack/corpus.jsonl` (new) — 16 entries, one
  JSON object per line (`id`, `title`, `collection`, `keywords`, `body`).
  Corpus text is original FRIDAY-Universe operational knowledge written
  for this pack (ADB-down procedure, FRIDAY OOM guard, greeting-onset
  8s bar, demo-only trading, free-only rule, hub reporting, capture/
  compress/inject, needle taxonomy, Obsidian vault, APInex waterfall)
  plus NOMAD-concept entries (NOMAD itself, Kiwix/ZIM, Ollama,
  ProtoMaps, Kolibri, pack how-to). No third-party content is copied.
- `Memora/tests/test_mem032_nomad_offline_pack.py` (new) — 13 tests,
  listed in the Memora tier-1 CI step.

**Fallback switch contract** (`resolve_knowledge`, return dict
`{source, query, hits, fallback_reason, adb_error}`):

- ADB answers with ≥1 hit → `source: "adb"`, pack not consulted even if
  it would rank higher. ADB wins.
- ADB raises / probe reports down → `source: "offline_pack"`,
  `fallback_reason: "adb_unavailable"`, `adb_error` carries the failure.
- ADB answers zero hits → pack, `fallback_reason: "adb_empty"`.
- No `adb_query` supplied → pack, `fallback_reason: "adb_not_configured"`.
- Empty query → no hits, no ADB call, `fallback_reason: "empty_query"`.
- Pack query with no overlapping term returns `[]` — the pack never
  invents an answer.

## 4. Proof — ADB-disabled query, run locally

Local smoke run (standalone harness, module + corpus only, pytest
13 passed in 0.06s; the same 13 tests run in repo CI — see §5):

```
pack info: {"pack": "nomad-offline-pack", "version": "1.0.0",
  "task": "TASK-MEM-032", "entry_count": 16,
  "collections": ["operations", "reference", "education"]}

query: "Memora database is down, what do I do"
ADB DISABLED (adb_query raises ConnectionError: Oracle ADB
  unreachable: ORA-12170 TNS connect timeout) ->
  source: "offline_pack", fallback_reason: "adb_unavailable",
  top_hit: "memora-adb-down"
    ("Memora Oracle ADB is unreachable — fallback procedure",
     score 0.8551)
  body: "When the Memora Oracle Autonomous Database (ADB) is unreachable,
  Memora fails closed: the API returns an explicit error, and no local
  SQLite file ever becomes an authority for shared memory. Keep serving
  reference knowledge from the bundled offline pack, queue new writes for
  retry instead of inventing local state, and report the outage to Muse
  on hub #1483. ..."

ADB UP (same query, ADB returns a hit) ->
  source: "adb", hits: [{live ADB answer}]
```

That is the board's Done: one offline pack built and answering a real
query with the ADB path disabled. The test suite pins it
(`test_real_query_with_adb_disabled_answers`, `test_adb_up_wins_over_pack`,
`test_pack_answers_with_network_disabled`, plus ranking, manifest/hash
integrity, corrupt-pack-fails-loudly, and empty-query cases).

## 5. Tests and CI

- New: `Memora/tests/test_mem032_nomad_offline_pack.py`, 13 tests.
  Local standalone run (module + corpus only, no repo imports):
  **13 passed**. The file is added to the "Run Memora tier-1 tests"
  step in `.github/workflows/friday-universe-ci.yml`, alongside
  `test_mem030_obsidian_vault.py` and
  `test_mem031_memora_verify_wave3.py` (MEM-030/MEM-031 pattern).
- The tier-1 collection gate (`scripts/tier1_collection_gate.py`)
  checks a FIXED list of 21 files and does not list MEM-030/MEM-031
  either; no gate change is needed.
- Repo CI verdict on the work PR is the authoritative check for the
  in-repo run (conftest imports the full app). First head f42beedd47:
  **10/10 green (8 success, 2 skipped, 0 failed) — verified first-hand
  via the check-runs API** (roster-validator, secrets scan, test,
  contracts all success). CI re-runs on the merge commit that brings
  main in; its verdict is reported in the hub completion post.

## 6. Board flips

- TASK-MEM-031 CLAIMED → MERGED — landed on main via the coordinator's
  board PR #1791 (watch085), NOT via this PR: while this PR was open,
  main moved (merges #1791 + #1788) and the coordinator's flip already
  recorded the merge (merge `581f0d1d`, head `7942efa1`, CI 11/11 green;
  merged 2026-11-25 12:31:34 IST by Surendra) with its own evidence
  line. The merge commit of this branch keeps main's MEM-031 record
  byte-identical; no duplicate flip is added here. (Correction to the
  first commit's message, which said the flip rode in this PR — true
  when written, superseded by main's move.)
- TASK-MEM-032 AVAILABLE → CLAIMED (owner `muse_2`, branch
  `muse2/task-mem-032-nomad-offline-pack`, work PR #1793, claim hub
  #1483 comment 7155563616). Board record verified AVAILABLE, owner
  null, on main be3f303e (board blob 9f64aeb3, 22,623 lines, verified
  against the true main blob before editing); the flip is re-applied
  onto the current main board (blob 1aec989c, 22,650 lines) in the
  merge commit, with main's other board changes kept intact.
- Board validation: the final merged board was checked with a local
  re-implementation of the repo validator's rules (duplicate-key scan
  via `yaml.compose`, per-task evidence counts vs raw text, post-merge
  PR-citation rule for MEM-031, owner/status validity) — all pass. The
  repo's own roster-validator runs in CI on this PR
  (`.github/workflows/collaboration-registry.yml`, triggered by the
  `docs/collaboration/**` path); it reported success on the first head
  and re-runs on the merge commit. Note: no local clone was used for
  this task (execution-risk check on the stale local clone); all
  reads/writes went through the GitHub REST API, and verification rests
  on repo CI, as with MEM-031.

## 7. Files changed

- `Memora/core/memory/offline_pack.py` (new)
- `Memora/core/memory/nomad_pack/manifest.json` (new)
- `Memora/core/memory/nomad_pack/corpus.jsonl` (new)
- `Memora/tests/test_mem032_nomad_offline_pack.py` (new)
- `docs/collaboration/TASK-MEM-032-NOMAD-OFFLINE-PACK.md` (new, this file)
- `docs/collaboration/WORK_BOARD.yaml` (MEM-032 → CLAIMED; MEM-031 kept as MERGED by coordinator PR #1791)
- `.github/workflows/friday-universe-ci.yml` (Memora tier-1 step lists the new test file)

## 8. Five states

- implemented: YES (pack + switch + tests + evidence doc, in this PR)
- tested: YES locally (13/13 standalone); repo-CI verdict awaited and
  verified first-hand before the hub completion post
- merged: NO (this PR, peer merge only — never my own)
- deployed: NO (owner stop order; needs coordinator clearance)
- production-verified: NO (live ADB-down drill on the fleet is owed)

## 9. Owed

- Peer merge of this work PR; then deploy + live proof after Muse's
  clearance: one live ADB-down drill on the fleet (ADB path disabled in
  staging, a real query answered from the pack, ADB restored and winning
  again).
- The pack answers reference knowledge only; it is not a write store
  and never becomes one — queued writes during an ADB outage still need
  a retry design, which is a separate task if wanted.
- Corpus growth (more collections, larger subsets) is a manifest +
  corpus change; the loader's count/hash checks make a bad update fail
  loudly, but a stale pack answering old standing orders is a content
  risk the owner should re-approve per release.

— Muse 2
