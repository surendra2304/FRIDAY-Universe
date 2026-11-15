"""TASK-IG-VYR-07: generated-footage intake (IG corpus generation cluster).

Behaviour pinned here:

* incomplete provenance is refused outright, naming every missing
  field, and nothing partial reaches the registry;
* terms are evaluated, not assumed: a commercial+derivative
  assertion WITH a terms URL grants; the same assertion without
  the URL does not;
* complete intakes are recorded in the VYR-004 provenance registry
  with generator/model/terms in the record;
* intake never admits a clip as a remix candidate under the
  current gate — the verdict says so and names the policy decision
  that would change it (no smuggled admission);
* batch intake collects refusals instead of dying on the first.

On clean main every test fails: app.services.generated_footage
does not exist.
"""
from __future__ import annotations

import pytest

from app.services import generated_footage as gf
from app.services import remix_flow as rf

GOOD = {
    "generator": "ExampleGen",
    "model": "example-2.1",
    "prompt": "a nebula timelapse, slow push-in",
    "generated_at": "2026-11-15T10:00:00Z",
    "media_url": "https://cdn.example.com/clip1.mp4",
    "rights_assertion": "commercial_and_derivative",
    "terms_url": "https://example.com/terms",
    "source_id": "gen-clip-1",
}


def test_complete_intake_records_and_evaluates_terms(tmp_path):
    registry = tmp_path / "prov.jsonl"
    verdict = gf.intake_generated_clip(GOOD, registry)
    assert verdict["terms"]["terms_grant"] is True
    assert verdict["terms"]["terms_class"] == "ai_generated_terms"
    records = rf.load_provenance(registry)
    assert len(records) == 1
    rec = records[0]
    assert rec.platform == "ai_generated"
    assert rec.license_class == "ai_generated_terms"
    assert "example-2.1" in rec.decision_reason


def test_intake_never_admits_candidate_under_current_gate(tmp_path):
    verdict = gf.intake_generated_clip(GOOD, tmp_path / "p.jsonl")
    assert verdict["candidate"] is False
    assert "REMIX_POLICY" in verdict["candidate_reason"]
    record = rf.ProvenanceRecord.from_dict(verdict["record"])
    with pytest.raises(ValueError):
        record.require_candidate()


def test_incomplete_provenance_refused_and_names_gaps(tmp_path):
    bad = {"generator": "ExampleGen"}
    with pytest.raises(ValueError) as excinfo:
        gf.intake_generated_clip(bad, tmp_path / "p.jsonl")
    message = str(excinfo.value)
    for field in ("model", "prompt", "generated_at", "media_url"):
        assert field in message
    assert rf.load_provenance(tmp_path / "p.jsonl") == []


def test_assertion_without_terms_url_is_not_a_grant(tmp_path):
    meta = dict(GOOD, terms_url="")
    verdict = gf.intake_generated_clip(meta, tmp_path / "p.jsonl")
    assert verdict["terms"]["terms_grant"] is False
    assert verdict["terms"]["terms_class"] == "unknown"
    assert "not provenance" in verdict["terms"]["reason"]


def test_no_assertion_means_terms_unknown():
    terms = gf.evaluate_terms({"generator": "X"})
    assert terms["terms_grant"] is False
    assert terms["terms_class"] == "unknown"


def test_batch_collects_refusals(tmp_path):
    out = gf.intake_batch([GOOD, {"generator": "Y"}, dict(GOOD, source_id="gen-clip-2")],
                          tmp_path / "p.jsonl")
    assert out["accepted"] == 2
    assert len(out["refused"]) == 1
    assert out["refused"][0]["index"] == 1
