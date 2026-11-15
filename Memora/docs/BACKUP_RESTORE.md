# Memora Backup & Restore

TASK-MEM-007. How to copy the production memory store somewhere safe, and how
to bring it back — proven by a drill (export → throwaway restore → identical
recall), not just documented.

## What the store actually is (production, verified 2026-11-15)

- **Relational store:** Oracle Autonomous Database (Memora schema). Tables:
  `agents`, `namespaces`, `access_grants`, `memory_records`,
  `memory_shared_agents`, `memory_relationships` (plus append-only telemetry:
  `audit_logs`, `event_log`).
- **Vectors:** Oracle 23ai native vector table `memora_vector_store`
  (`id`, `tenant_id`, `embedding VECTOR(384, FLOAT32)`, `payload`). In
  production there is **no Qdrant server** — search reads this table through
  `storage/vector/oracle_vector_adapter.py` (see `core/memory/search_service.py`).
  A backup that skips this table loses the semantic search leg.
- **Not durable state:** the `viking://` context layer is rebuilt from its own
  snapshot at startup (TASK-MEM-010); it is not part of this backup.
- Drill snapshot (2026-11-15 08:13:58 UTC): 436 memory records (406 active /
  28 deleted at probe time), 436 vectors, 1,527 relationships, 4 agents,
  6 namespaces. The store is live, so counts move between snapshots — the
  manifest of each export is the reconciliation source.

## Export (read-only)

On Server 1, with the service venv:

```bash
cd /opt/friday_universe/Memora
MEMORA_EXPORT_DIR=/tmp/mem007/export /opt/friday_universe/venv/bin/python scripts/memora_export.py
tar czf memora_export.tar.gz -C /tmp/mem007 export
sha256sum memora_export.tar.gz
```

The script issues only SELECTs. Output: one JSONL per table, `vectors.bin`
(float32 little-endian, row order in `vectors_index.json`), and
`manifest.json` with per-table counts and per-file sha256. `audit_logs` /
`event_log` content is **not** exported — they are append-only telemetry, not
memory content; their counts are recorded in the manifest
(`counted_not_exported`) so a loss can be reconciled honestly.

Transfer the tarball off-host (workspace backup) and verify the sha256 after
transfer. **The export contains the owner's memory content — never commit it
to git, never upload it to a third-party host.**

## Restore (into a throwaway store)

```bash
cd Memora
MEMORA_ENV=testing \
DATABASE_URL=sqlite:////tmp/restored/memora.db \
MEMORA_EXPORT_DIR=/path/to/export \
python3 scripts/memora_restore.py --load-search-vectors
```

- Rows are re-inserted with their original ids, timestamps, lifecycle states
  and provenance (direct ORM inserts; the write pipeline is bypassed on
  purpose — a restore is a copy, not a re-ingestion, so nothing is
  re-embedded, re-scored or de-duplicated against itself).
- Vectors are written to the target's vector table **and** (with
  `--load-search-vectors`) into the in-process vector adapter, so a local
  instance answers hybrid search immediately. On an Oracle target the native
  VECTOR table is used and search reads it directly.
- The script prints a verification report (counts vs manifest, per-record
  content-hash match rate) and ends with `RESTORE_VERIFY_OK` only when every
  count matches and every content hash matches.
- **Safety gate:** it refuses Oracle targets / production env unless
  `--i-understand-this-is-a-live-target` is passed. A production restore is a
  coordinated operation (stop Memora, restore, start, verify), never a
  default.

## Verify the restored copy answers recall identically

1. **Record fidelity** — the restore report above: counts equal to the
   manifest and content-hash match rate 1.0.
2. **Recall battery** — run the corpus battery: pick active records from the
   export, query each side (production search and the restored instance) with
   a verbatim phrase and a keyword query derived from the record's content,
   and compare the target's position and the top-5 overlap. The drill of
   2026-11-15 (TASK-MEM-007) recorded: see the task's completion comment on
   issue #35 for the measured numbers.
3. **Standard probe set** — the restored store can also be seeded with the
   MEM-002 probe facts (`Memora/benchmarks/recall_probe_set.json`) and run
   through `Memora/benchmarks/recall_benchmark.py` like any other instance,
   because the restore preserves the full write/search surface.

### Known parity caveats (measured, not hidden)

- **Query embeddings:** production generates query embeddings with Gemini
  (`GEMINI_API_KEY` is configured for Memora). A local throwaway without that
  key falls back to deterministic hashing embeddings, so the *semantic* leg's
  absolute scores differ; the restored records and their stored vectors are
  bit-identical, and verbatim/keyword recall positions are the comparison
  that must match exactly. If a future restore needs full semantic parity,
  run the restored instance with the same embedding configuration as
  production.
- **Vector rounding:** the Oracle vector adapter rounds stored vectors to 6
  decimal places on upsert (its existing behaviour); the export preserves
  full float32, so a restore loses nothing beyond what production itself
  stores.
- **Point-in-time:** the export is a snapshot, not a journal. Writes that land
  during the export window may or may not be included; for a coordinated
  backup, quiesce writers first or accept the manifest as the truth of what
  was captured.
- **Provenance-signing secret continuity (measured in the 2026-11-15 drill):**
  every production record carries an `hmac_signature` in its provenance, and
  hybrid search verifies it (Safety Invariant 2 in
  `core/memory/search_service.py`) — a record whose signature fails is
  discarded from results as "tampered". The verification secret
  (`core/security/provenance.get_provenance_secret`) lives in the production
  environment and is deliberately **not** part of the export. A restored
  instance running under any other secret restores byte-faithfully (the
  drill: counts equal, content-hash match rate 1.0, vectors loaded) yet
  returns **nothing** for the restored corpus in search, because all 436
  records fail verification. A real restore must therefore provision the
  production provenance-signing secret on the restored instance (from the
  credentials dossier) before recall can be verified or served; records
  written after the restore sign with the local secret and behave normally.

## If Server 1 is lost

1. Provision the replacement host and the Memora service (same Oracle
   Autonomous Database — the store survives the host; if the *database* is
   what was lost, restore into a fresh Oracle schema with the gated flag).
2. Fetch the latest export tarball, verify sha256 against the manifest.
3. Provision the production provenance-signing secret on the new instance
   (see the parity caveats) — without it, search discards every restored
   record as unverifiable.
4. Run the restore (coordinated, service stopped), start Memora, run the
   recall battery above against the pre-loss baseline numbers.
5. FRIDAY's Memora client needs no changes — it talks to the service, not
   the store.
