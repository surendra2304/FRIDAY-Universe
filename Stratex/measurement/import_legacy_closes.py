"""
measurement/import_legacy_closes.py — import the owner-directed legacy closes.

TASK-STR-PHASE2-001. On 2026-11-14 the owner decided to close the daemon's
3 legacy unattributed Binance demo shorts (SOL/UNI/PAXG) for a clean
protocol start. The closes were executed and exchange-verified by the
preceding recon run, which staged the full fill records at
state/legacy_close_records.json. This importer writes them into the fill
ledger as what they are:

    strategy    = LEGACY-UNATTRIBUTED   (nobody knows which strategy opened them)
    engine      = daemon
    exit_reason = OWNER_DIRECTED_CLOSE
    fees_source = broker                (figures come from exchange userTrades fills)

Idempotent: a record whose close_order_id already exists in the ledger
is skipped, so re-running is safe.

Run on the server from the Stratex/ directory:
    python3 -m measurement.import_legacy_closes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from measurement import fill_ledger
except ImportError:  # pragma: no cover - flat layout fallback
    import fill_ledger  # type: ignore

try:
    from logger import get_logger

    logger = get_logger("measurement_legacy_import")
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger("measurement_legacy_import")

LEGACY_FILE = "legacy_close_records.json"


def legacy_records_path() -> Path:
    return fill_ledger.state_dir() / LEGACY_FILE


def staged_records(path: Path | None = None) -> List[Dict[str, Any]]:
    p = path or legacy_records_path()
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh) or {}
    records = data.get("records") or []
    return [r for r in records if isinstance(r, dict)]


def import_records(path: Path | None = None) -> Dict[str, int]:
    """Append staged legacy closes to the fill ledger. Returns counts."""
    counts = {"imported": 0, "skipped_existing": 0, "failed": 0}
    for rec in staged_records(path):
        order_id = str(rec.get("close_order_id") or "")
        if order_id and fill_ledger.fill_exists(order_id=order_id):
            counts["skipped_existing"] += 1
            continue
        closed_ms = float(rec.get("closed_at_ms") or 0.0)
        row = {
            "strategy": "LEGACY-UNATTRIBUTED",
            "engine": "daemon",
            "venue": str(rec.get("venue") or "binance_futures"),
            "symbol": str(rec.get("symbol") or ""),
            "side": str(rec.get("side_closed") or ""),
            "qty": float(rec.get("quantity") or 0.0),
            "entry_price": float(rec.get("entry_price") or 0.0),
            "exit_price": float(rec.get("exit_price") or 0.0),
            "entry_time": 0.0,  # open time unknown — these predate attribution
            "exit_time": closed_ms / 1000.0 if closed_ms else 0.0,
            "gross_pnl": float(rec.get("gross_pnl") or 0.0),
            "fees": float(rec.get("fees") or 0.0),
            "fees_source": "broker",
            "net_pnl": float(rec.get("net_pnl") or 0.0),
            "exit_reason": "OWNER_DIRECTED_CLOSE",
            "order_id": order_id,
            "entry_order_id": "",
            "signal_id": "",
        }
        if fill_ledger.append_fill(row) is not None:
            counts["imported"] += 1
        else:
            counts["failed"] += 1
    logger.info(
        f"[MEASUREMENT] Legacy close import: {counts['imported']} imported, "
        f"{counts['skipped_existing']} already present, {counts['failed']} failed"
    )
    return counts


def main() -> int:
    counts = import_records()
    print(json.dumps(counts))
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
