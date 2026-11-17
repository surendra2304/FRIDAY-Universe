"""
Durable provenance re-signing for master-key rotation (TASK-MEM-010).

Every memory record carries an HMAC-SHA256 provenance signature keyed by
Memora's master key (``core.security.provenance``). Both read paths — the
search service's admissibility filter and the hybrid vector/relational
search — DISCARD any record whose signature fails verification, so rotating
the master key without re-signing makes the whole store silently vanish
from recall. The MEM-005 live env pass (2026-11-17) proved this the hard
way: no re-signing routine existed in the code, and 471 production records
had to be re-signed by a one-off maintenance script while the service was
stopped. This module is that step as a real, tested tool, built strictly on
the deployed primitives (``verify_memory_signature`` /
``compute_memory_signature``).

Safety contract:

* The NEW signing key is never supplied by the caller. It must be the
  ``MEMORA_MASTER_KEY`` currently in force: :func:`resolve_rotation_keys`
  refuses to run when the master is unset, or when the key settings
  actually resolve for provenance is not that master (break-glass only —
  re-signing to a per-agent key would strand the store again at the next
  rotation).
* The OLD key reaches the tool only through the caller's environment
  (``MEMORA_OLD_MASTER_KEY``), never as a function-of-record value that
  could end up in logs, and old == new is refused as a no-op rotation.
* A record is re-signed ONLY when its signature fails under the new key
  and verifies under the old one — the same gate the one-off script used.
  Records that verify under the new key already are skipped (which is what
  makes a second run a no-op). Records that verify under NEITHER key —
  including content-tampered records, which the primitive's
  content-hash check rejects under every key — are NEVER force-signed:
  they are reported by id and left byte-identical, because a signature
  that matches no known master is evidence of tampering, not of rotation.
  Records carrying no signature at all are reported separately and are
  likewise never signed (signing them would fabricate provenance).
* Progress is logged as per-batch COUNTS only. Record contents and key
  material never appear in logs or in the report; the report carries the
  ids of refused records only, so an operator can investigate them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.config import settings
from core.security.provenance import (
    SIGNATURE_VERSION,
    compute_memory_signature,
    verify_memory_signature,
)
from storage.relational.models import MemoryRecord

logger = logging.getLogger(__name__)

TASK_ID = "TASK-MEM-010"
OLD_KEY_ENV = "MEMORA_OLD_MASTER_KEY"
APPLY_ENV = "MEMORA_RESIGN_APPLY"

CLASS_CURRENT = "current"
CLASS_RESIGNABLE = "resignable"
CLASS_UNVERIFIABLE = "unverifiable"
CLASS_UNSIGNED = "unsigned"

DEFAULT_BATCH_SIZE = 100


class ResignRefused(RuntimeError):
    """The tool must not run. Messages never contain key material."""


def resolve_rotation_keys(old_secret: Optional[str]) -> Tuple[str, str]:
    """Validate the rotation preconditions; return ``(old_secret, new_secret)``.

    ``new_secret`` is derived, never passed in: it is the MEMORA_MASTER_KEY
    currently in force, and settings must resolve the provenance secret to
    exactly that value. Anything else means the master is not installed as
    the signing key, and re-signing would target a key the service is not
    actually using.
    """
    master = settings.MEMORA_MASTER_KEY
    if not master:
        raise ResignRefused(
            "MEMORA_MASTER_KEY is not set in Memora's environment; refusing "
            "to re-sign — the current master key (break-glass) is the only "
            "authorized new signing key."
        )
    new_secret = settings.get_memora_api_key()
    if new_secret != master:
        raise ResignRefused(
            "settings.get_memora_api_key() does not resolve to "
            "MEMORA_MASTER_KEY; refusing to re-sign to a key that is not "
            "the master in force."
        )
    if not old_secret:
        raise ResignRefused(
            f"{OLD_KEY_ENV} is not set; supply the previous master key via "
            "that environment variable (never as a command-line argument)."
        )
    if old_secret == new_secret:
        raise ResignRefused(
            "The old key supplied via "
            f"{OLD_KEY_ENV} is identical to the current master key; "
            "there is nothing to rotate."
        )
    return old_secret, new_secret


def classify_record(record: MemoryRecord, old_secret: str, new_secret: str) -> str:
    """Classify one record against the two rotation keys.

    Order matters: the new key is checked first so already-rotated records
    classify as current (idempotency), then the old key. Verification is
    the deployed primitive, so its content-tamper check applies here too:
    a record whose content_text no longer matches its content_hash fails
    under both keys and lands in the unverifiable class.
    """
    provenance = record.provenance or {}
    signature = provenance.get("hmac_signature")
    if not signature or not isinstance(signature, str):
        return CLASS_UNSIGNED
    if verify_memory_signature(record, secret=new_secret):
        return CLASS_CURRENT
    if verify_memory_signature(record, secret=old_secret):
        return CLASS_RESIGNABLE
    return CLASS_UNVERIFIABLE


@dataclass
class ResignReport:
    scanned: int = 0
    current: int = 0
    resignable: int = 0
    resigned: int = 0
    unverifiable: int = 0
    unsigned: int = 0
    unverifiable_ids: List[str] = field(default_factory=list)
    unsigned_ids: List[str] = field(default_factory=list)
    dry_run: bool = True

    def counts(self) -> Dict:
        return {
            "scanned": self.scanned,
            "already_current": self.current,
            "resignable": self.resignable,
            "resigned": self.resigned,
            "unverifiable": self.unverifiable,
            "unsigned": self.unsigned,
        }


def _resign_record(record: MemoryRecord, new_secret: str) -> None:
    """Replace the record's signature with one under ``new_secret``.

    The signature is recomputed through the same primitive verification
    uses, so the field extraction can never drift from the read paths.
    All other provenance keys are preserved; the fresh dict assignment is
    what makes the JSON column register the change.
    """
    provenance = dict(record.provenance or {})
    provenance["hmac_signature"] = compute_memory_signature(record, secret=new_secret)
    provenance["signature_version"] = SIGNATURE_VERSION
    provenance["resigned_by"] = TASK_ID
    provenance["resigned_at"] = datetime.now(timezone.utc).isoformat()
    record.provenance = provenance


def load_record_ids(
    db: Session, tenant_id: Optional[str] = None
) -> List[str]:
    """All memory record ids in stable order, optionally tenant-scoped.

    Scope is the whole store by default: the read paths discard
    unverifiable records regardless of lifecycle state, and a superseded
    record can return to live use, so a rotation must cover every row —
    exactly the census the MEM-005 one-off took.
    """
    query = db.query(MemoryRecord.id)
    if tenant_id:
        query = query.filter(MemoryRecord.tenant_id == tenant_id)
    return [row[0] for row in query.order_by(MemoryRecord.id).all()]


def resign_records(
    db: Session,
    old_secret: str,
    new_secret: str,
    *,
    dry_run: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
    tenant_id: Optional[str] = None,
) -> ResignReport:
    """Re-sign every old-key record in the store to the new master key.

    Dry-run (the default) classifies and reports without writing. When
    applying, each batch commits separately so progress survives an
    interruption and a later run simply resumes (already-resigned records
    classify as current). A record whose fresh signature somehow fails
    verification rolls its whole batch back and raises — the tool never
    commits a signature the read paths would reject.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    report = ResignReport(dry_run=dry_run)
    ids = load_record_ids(db, tenant_id=tenant_id)
    for start in range(0, len(ids), batch_size):
        batch_ids = ids[start : start + batch_size]
        records = (
            db.query(MemoryRecord)
            .filter(MemoryRecord.id.in_(batch_ids))
            .all()
        )
        by_id = {record.id: record for record in records}
        batch_resigned = 0
        for record_id in batch_ids:
            record = by_id.get(record_id)
            if record is None:
                continue  # deleted between the id scan and the batch load
            report.scanned += 1
            classification = classify_record(record, old_secret, new_secret)
            if classification == CLASS_CURRENT:
                report.current += 1
            elif classification == CLASS_RESIGNABLE:
                report.resignable += 1
                if not dry_run:
                    _resign_record(record, new_secret)
                    if not verify_memory_signature(record, secret=new_secret):
                        db.rollback()
                        raise ResignRefused(
                            "Post-resign verification failed for a record in "
                            f"batch starting at offset {start}; the batch "
                            "was rolled back and no signature from it was "
                            "committed."
                        )
                    batch_resigned += 1
                    report.resigned += 1
            elif classification == CLASS_UNVERIFIABLE:
                report.unverifiable += 1
                report.unverifiable_ids.append(record_id)
            else:  # CLASS_UNSIGNED
                report.unsigned += 1
                report.unsigned_ids.append(record_id)
        if not dry_run and batch_resigned:
            db.commit()
        logger.info(
            "resign batch offset=%d size=%d resigned=%d | cumulative "
            "scanned=%d already_current=%d resignable=%d unverifiable=%d "
            "unsigned=%d mode=%s",
            start,
            len(batch_ids),
            batch_resigned,
            report.scanned,
            report.current,
            report.resignable,
            report.unverifiable,
            report.unsigned,
            "dry-run" if dry_run else "apply",
        )
    return report
