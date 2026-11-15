"""VyralX generated-footage intake (TASK-IG-VYR-07).

The IG reference corpus's generation cluster (DdnNrgtE7HN,
Dee1ZxUybxd, De4XEoLjg_f, DeI_T6dB-uk, DXlFWL5EkaN) promotes free
AI generation tools as production inputs for faceless channels.
VyralX's licence gate (TASK-VYR-004) has one rule that binds
everything: **no provenance, not a candidate**. AI-generated media
is where provenance most often goes missing — a clip appears from
a tool, nobody recorded which model made it, from what prompt,
under what output terms — so generated footage gets its own
intake, stricter than the stock catalogues:

* **Incomplete provenance is refused outright.** Generator, model,
  prompt, generation timestamp, media locator and a terms basis
  are all required; a missing field raises, naming every gap.
* **Terms are evaluated, not assumed.** A clip is marked
  terms-granting only when the caller asserts the generator's
  terms grant commercial + derivative rights in outputs AND
  supplies the terms URL as evidence. An assertion without the
  URL, or no assertion, means the terms are unknown.
* **Complete intakes are recorded** in the VYR-004 provenance
  registry (append-only), so the evidence exists permanently.

And one deliberate stop: **intake does not admit clips as remix
candidates.** The gate's admitted licence classes are
``cc0 / public_domain / cc_by / cc_by_sa / owner``
(``app.services.remix_flow.ALLOWED_LICENSE_CLASSES``); generated
footage classifies here as ``ai_generated_terms`` (terms-granting)
or ``unknown``, and neither is in that set, so
``require_candidate`` refuses it today. Admitting generated
footage is a REMIX_POLICY decision — it needs the policy amended
and the class added by whoever owns the gate — not something an
intake module smuggles in. ``docs/GENERATED_FOOTAGE.md`` specifies
exactly that decision and evaluates every corpus generation
source against the gate, including the LTX-2.5 reject verdict.

No generator is integrated by this module: the corpus tools are
unnamed or comment-gated, and AI video generation is not
available on the channel owner's accounts in any case. This is
the door, built and locked correctly — what may walk through it
is a policy call. Pure validation + registry append; Python 3.10.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.remix_flow import ProvenanceRecord, record_provenance

INTAKE_VERSION = "ig-vyr07-1"
REQUIRED_FIELDS = ("generator", "model", "prompt", "generated_at",
                   "media_url")
RIGHTS_ASSERTION = "commercial_and_derivative"


def evaluate_terms(metadata: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a generated clip's terms basis from its metadata."""
    assertion = str(metadata.get("rights_assertion") or "")
    terms_url = str(metadata.get("terms_url") or "").strip()
    if assertion == RIGHTS_ASSERTION and terms_url:
        return {
            "terms_class": "ai_generated_terms",
            "terms_grant": True,
            "reason": "caller asserts the generator's terms grant "
                      "commercial + derivative rights in outputs, "
                      f"evidenced at {terms_url}",
        }
    if assertion == RIGHTS_ASSERTION and not terms_url:
        return {
            "terms_class": "unknown",
            "terms_grant": False,
            "reason": "rights asserted but no terms URL supplied as "
                      "evidence — an assertion is not provenance",
        }
    return {
        "terms_class": "unknown",
        "terms_grant": False,
        "reason": "no commercial+derivative rights assertion on "
                  "record; the generator's output terms are unknown",
    }


def intake_generated_clip(metadata: dict[str, Any],
                          registry_path: Path | None = None,
                          record: bool = True) -> dict[str, Any]:
    """Validate + record one AI-generated clip's provenance.

    Raises :class:`ValueError` listing every missing required
    field — incomplete provenance never reaches the registry.
    Returns the intake verdict: the provenance record as stored,
    the terms evaluation, and the candidate status under the
    CURRENT gate (always False here, with the reason and the
    policy decision that would change it).
    """
    missing = [f for f in REQUIRED_FIELDS
               if not str(metadata.get(f) or "").strip()]
    if missing:
        raise ValueError(
            "generated-footage intake refused — missing required "
            f"provenance fields: {', '.join(missing)}")
    terms = evaluate_terms(metadata)
    record_obj = ProvenanceRecord(
        platform="ai_generated",
        title=str(metadata.get("title")
                  or f"AI-generated clip ({metadata['generator']})"),
        author=str(metadata.get("creator") or metadata["generator"]),
        source_page_url=str(metadata.get("page_url")
                            or metadata.get("terms_url") or ""),
        media_url=str(metadata.get("media_url") or ""),
        license_name=(f"AI-generated output terms "
                      f"({metadata['generator']})"),
        license_url=str(metadata.get("terms_url") or ""),
        retrieved_at=str(metadata.get("generated_at") or ""),
        license_class=terms["terms_class"],
        allowed=bool(terms["terms_grant"]),
        decision_reason=(f"intake {INTAKE_VERSION}: model="
                         f"{metadata['model']}; prompt recorded; "
                         + terms["reason"]),
    )
    if record:
        record_provenance([record_obj], registry_path)
    return {
        "kind": "generated_footage_intake",
        "intake_version": INTAKE_VERSION,
        "record": record_obj.to_dict(),
        "terms": terms,
        "recorded": bool(record),
        "candidate": False,
        "candidate_reason": (
            "the VYR-004 gate admits only "
            "cc0/public_domain/cc_by/cc_by_sa/owner today; "
            f"'{terms['terms_class']}' is not an admitted class. "
            "Admitting generated footage requires the REMIX_POLICY "
            "amendment specified in docs/GENERATED_FOOTAGE.md."),
        "status": "pending_review",
    }


def intake_batch(items: list[dict[str, Any]],
                 registry_path: Path | None = None) -> dict[str, Any]:
    """Intake several clips; refusals are collected, not fatal."""
    accepted, refused = [], []
    for i, item in enumerate(items):
        try:
            accepted.append(
                intake_generated_clip(item, registry_path))
        except ValueError as exc:
            refused.append({"index": i, "reason": str(exc)})
    return {
        "kind": "generated_footage_intake_batch",
        "intake_version": INTAKE_VERSION,
        "accepted": len(accepted),
        "refused": refused,
        "verdicts": accepted,
    }
