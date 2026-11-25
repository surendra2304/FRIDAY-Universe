#!/usr/bin/env python3
"""Nightly Obsidian-vault build (TASK-MEM-030).

Reads a Memora store export — a JSON list (or JSONL) of memory records,
one object per ``MemoryRecordRead`` — and rebuilds the vault view plus
that night's per-agent work summaries into an Obsidian vault directory:

    python3 Memora/scripts/nightly_vault.py --records export.json \\
        --date 2026-11-25 --out /path/to/vault

The natural export is ``Memora/scripts/memora_export.py`` (TASK-MEM-007,
read-only dump of the live store): its ``memory_records.jsonl`` is
exactly the JSONL this script reads, field for field.
Private-scope records are excluded unless ``--include-private`` is
passed. Prints the run manifest as JSON on stdout.

Exit 0: vault + summaries written. Exit 2: bad arguments / unreadable
export / bad date.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from the repo root as ``python3 Memora/scripts/...`` and
# from inside Memora/ as ``python3 scripts/...``.
for _candidate in (Path(__file__).resolve().parent.parent, Path.cwd()):
    if (_candidate / "core" / "memory" / "vault.py").exists():
        sys.path.insert(0, str(_candidate))
        break

from core.memory.nightly_summary import load_records_json, run_daily_cycle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, help="JSON/JSONL store export")
    parser.add_argument("--date", required=True, help="Night to summarise (YYYY-MM-DD)")
    parser.add_argument("--out", required=True, help="Vault directory to build into")
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Also render PRIVATE-scope records (default: excluded)",
    )
    args = parser.parse_args(argv)
    try:
        records = load_records_json(args.records)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("nightly_vault: cannot read export: %s" % (exc,), file=sys.stderr)
        return 2
    try:
        manifest = run_daily_cycle(
            records, args.date, args.out, include_private=args.include_private
        )
    except ValueError as exc:
        print("nightly_vault: %s" % (exc,), file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
