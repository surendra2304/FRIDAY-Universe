"""TASK-IG2-FRG-07: the real one-prompt agent-creation flow.

These tests run the flow end to end: a prompt goes in, a project comes
out, the generated code is imported and probed by the flow's own
checks, and the registry record is read back. The dead-gateway honesty
probe is part of the flow itself, so a "tested" status here means the
generated agent demonstrably fails loudly without Inference.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.templates.agent_creation import (
    MANIFEST_PATHS,
    CreatedAgentRegistry,
    create_agent,
    derive_config,
    render_files,
    slugify_agent_name,
)
from app.templates.ig_templates import ONE_PROMPT_AGENT

PROMPT = "Track my crypto portfolio and alert me when a coin moves fast"
SEC_PROMPT = "Review code for security vulnerabilities and audit SQL queries"


def test_manifest_matches_template_contract():
    assert sorted(MANIFEST_PATHS) == sorted(ONE_PROMPT_AGENT.manifest_paths())


def test_slug_is_identifier_safe_and_deterministic():
    assert slugify_agent_name(PROMPT) == "track_crypto_portfolio"
    assert slugify_agent_name(PROMPT) == slugify_agent_name(PROMPT)
    assert slugify_agent_name("123 go").startswith("agent_")
    assert slugify_agent_name("!!!").isidentifier()


def test_specialist_derivation_uses_the_skill_registry():
    sec = derive_config(SEC_PROMPT)
    assert sec.specialist == "security-reviewer"
    assert sec.role == "security_reviewer"
    assert "sec.sql-injection" in sec.skill_ids
    default = derive_config(PROMPT)
    assert default.specialist == "python-developer"
    # The owner's prompt leads the system prompt, verbatim.
    assert default.system_prompt.startswith(PROMPT)
    assert SEC_PROMPT in derive_config(SEC_PROMPT).system_prompt


def test_empty_prompt_is_refused():
    with pytest.raises(ValueError):
        derive_config("   ")


def test_render_is_deterministic():
    config = derive_config(PROMPT)
    assert render_files(config) == render_files(config)
    assert sorted(render_files(config)) == sorted(MANIFEST_PATHS)


def test_create_agent_end_to_end_tested_and_registered(tmp_path):
    result = create_agent(PROMPT, tmp_path)
    assert result.status == "tested", [c.to_dict() for c in result.checks]
    assert all(c.passed for c in result.checks)
    project = Path(result.project_dir)
    on_disk = sorted(
        p.relative_to(project).as_posix()
        for p in project.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    assert on_disk == sorted(MANIFEST_PATHS)
    # The prompt survives verbatim in the README (the rebuild source).
    assert PROMPT in (project / "README.md").read_text(encoding="utf-8")
    # Registry record: honest status + per-file hashes that match disk.
    registry = CreatedAgentRegistry(tmp_path / "created_agents.json")
    record = registry.get(result.name)
    assert record["status"] == "tested"
    assert record["template"] == "one-prompt-agent"
    import hashlib

    for rel, digest in record["files"].items():
        actual = hashlib.sha256((project / rel).read_bytes()).hexdigest()
        assert actual == digest


def test_rebuild_from_stored_prompt_is_byte_identical(tmp_path):
    result = create_agent(PROMPT, tmp_path / "first")
    registry = CreatedAgentRegistry(tmp_path / "first" / "created_agents.json")
    comparison = registry.rebuild(result.name, tmp_path / "second")
    assert comparison == {rel: True for rel in MANIFEST_PATHS}


def test_failed_creation_is_recorded_not_hidden(tmp_path):
    # A stray file in the target project dir breaks the exact-manifest
    # contract; the flow must record the attempt as failed, not pass it
    # and not drop it.
    name = slugify_agent_name(PROMPT)
    project = tmp_path / name
    project.mkdir(parents=True)
    (project / "stray.txt").write_text("not part of the manifest", encoding="utf-8")
    result = create_agent(PROMPT, tmp_path)
    assert result.status == "failed"
    failing = [c.name for c in result.checks if not c.passed]
    assert "manifest_exact" in failing
    record = CreatedAgentRegistry(tmp_path / "created_agents.json").get(name)
    assert record["status"] == "failed"
    assert any(
        c["name"] == "manifest_exact" and not c["passed"] for c in record["checks"]
    )


def test_registry_round_trip_and_unknown_name(tmp_path):
    create_agent(PROMPT, tmp_path)
    create_agent(SEC_PROMPT, tmp_path)
    registry = CreatedAgentRegistry(tmp_path / "created_agents.json")
    names = [r["name"] for r in registry.all()]
    assert names == sorted(names) and len(names) == 2
    with pytest.raises(KeyError):
        registry.get("no-such-agent")
    # The registry file is plain JSON data — auditable, not a black box.
    data = json.loads((tmp_path / "created_agents.json").read_text(encoding="utf-8"))
    assert set(data["agents"]) == set(names)
