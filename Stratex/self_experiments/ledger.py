"""The experiment ledger — pre-declaration enforced by record format.

Append-only JSONL in the loop's data directory. The discipline the
research programme kept by convention (declare before you run) is
enforced here structurally:

- declare() writes the full proposal (hypothesis, variant, members,
  data window) plus the sha256 of its canonical form BEFORE any run.
- The runner path (loop.run_declared) looks the declaration up and
  recomputes the hash; a proposal with no prior declaration, or whose
  hash does not match the declared record, is REFUSED — an
  undeclared result does not count and cannot be admitted.

Record kinds: declaration, evaluation (compact, for greedy's internal
candidate evaluations — each one a counted trial), result (the full
judgement of one declared experiment), admission, revocation, skip.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bounds import assert_no_risk_touch

UTC = timezone.utc


class DeclarationRequired(Exception):
    """A run was attempted without a matching prior declaration."""


def canonical_hash(payload: Any) -> str:
    """sha256 of the canonical JSON form of a payload."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ExperimentLedger:
    """Append-only record of everything the loop declares and does."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "experiments.jsonl"

    # -- low level ------------------------------------------------------

    def _append(self, row: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # -- declarations -----------------------------------------------------

    def declare(self, proposal: dict[str, Any]) -> str:
        """Write a pre-declaration record; returns the declaration id.

        The proposal is risk-scanned first: a proposal naming a risk
        parameter is refused here and never reaches the ledger.
        """
        assert_no_risk_touch(proposal)
        proposal_hash = canonical_hash(proposal)
        seq = sum(1 for r in self.rows() if r.get("kind") == "declaration")
        declaration_id = f"decl_{seq + 1:04d}_{proposal_hash[:10]}"
        self._append(
            {
                "kind": "declaration",
                "ts": _now(),
                "declaration_id": declaration_id,
                "proposal": proposal,
                "proposal_hash": proposal_hash,
            }
        )
        return declaration_id

    def get_declaration(self, declaration_id: str) -> dict[str, Any] | None:
        for row in self.rows():
            if row.get("kind") == "declaration" and (
                row.get("declaration_id") == declaration_id
            ):
                return row
        return None

    def require_declaration(
        self, declaration_id: str, proposal: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the declaration record or raise DeclarationRequired.

        The proposal being run must hash to exactly the declared hash:
        swapping the variant after declaring is the same offence as
        never declaring.
        """
        record = self.get_declaration(declaration_id)
        if record is None:
            raise DeclarationRequired(
                f"no declaration on record for {declaration_id!r}: "
                f"self-experiments never run undeclared work"
            )
        if record.get("proposal_hash") != canonical_hash(proposal):
            raise DeclarationRequired(
                f"proposal hash mismatch for {declaration_id!r}: the "
                f"work being run is not the work that was declared"
            )
        return record

    def declared_hashes(self) -> set[str]:
        return {
            str(r["proposal_hash"])
            for r in self.rows()
            if r.get("kind") == "declaration" and r.get("proposal_hash")
        }

    # -- outcomes ---------------------------------------------------------

    def record_evaluation(self, row: dict[str, Any]) -> None:
        self._append({"kind": "evaluation", "ts": _now(), **row})

    def record_result(self, row: dict[str, Any]) -> None:
        self._append({"kind": "result", "ts": _now(), **row})

    def record_admission(self, row: dict[str, Any]) -> None:
        self._append({"kind": "admission", "ts": _now(), **row})

    def record_revocation(self, row: dict[str, Any]) -> None:
        self._append({"kind": "revocation", "ts": _now(), **row})

    def results_today(self) -> int:
        today = datetime.now(UTC).date().isoformat()
        return sum(
            1
            for r in self.rows()
            if r.get("kind") == "result" and str(r.get("ts", "")).startswith(today)
        )
