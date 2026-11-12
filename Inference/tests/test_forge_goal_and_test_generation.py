"""Explicit provider fixtures; prove objective preservation and actual test-source parsing."""
from types import SimpleNamespace
import pytest
from app.services.code_generation import CodeGenerationRequest, CodeGenerationService
from app.services.test_generation import TestGenerationRequest, TestGenerationService
from app.providers.unified_manager import unified_provider_manager


def test_objective_is_explicit_in_generation_prompt():
    request = CodeGenerationRequest(filename="main.py", context={"project_goal": "CSV to JSON converter, quoted commas and empty input"})
    assert request.context["project_goal"] in CodeGenerationService()._build_prompt(request)


def test_code_cache_separates_related_file_and_architecture_changes():
    service = CodeGenerationService()
    first = CodeGenerationRequest(filename="main.py", context={"project_goal": "same goal", "related_files": {"types.py": "class A: pass"}})
    second = first.model_copy(deep=True)
    second.context["related_files"]["types.py"] = "class B: pass"
    third = first.model_copy(deep=True)
    third.context["architecture_spec"] = "new contract"
    assert len({service._get_cache_key(x) for x in [first, second, third]}) == 3


def test_forge_sibling_context_is_not_silently_dropped():
    context = CodeGenerationService()._prune_context({"project_goal": "g" * 800, "sibling_files": {"types.py": "class Contract: pass"}})
    assert len(context["project_goal"]) == 800
    assert context["related_files"]["types.py"] == "class Contract: pass"


@pytest.mark.asyncio
@pytest.mark.parametrize("reply,framework,expected", [
    ("Here is an exhaustive suite.\n```python\ndef test_convert():\n    assert 1 == 1\n```", "pytest", "generated"),
    ("def test_convert():\n    assert 1 == 1", "pytest", "generated"),
    ("Here is an exhaustive suite.", "pytest", "invalid_output"),
    ("```python\ndef invalid(\n```", "pytest", "invalid_output"),
    ("import unittest\nclass TestConvert(unittest.TestCase):\n    def test_convert(self):\n        self.assertEqual(1, 1)", "unittest", "generated"),
    ("def test_convert():\n    assert 1 == 1", "unittest", "invalid_output"),
    ("# No actual tests", "pytest", "invalid_output"),
])
async def test_narration_is_not_test_code_and_coverage_is_not_invented(monkeypatch, reply, framework, expected):
    captured = []
    async def provider(request):
        captured.append(request)
        return SimpleNamespace(content=reply, degraded=False, error=None)
    monkeypatch.setattr(unified_provider_manager, "execute", provider)
    # Put the actual function after the historical 3000-character cutoff.
    source = "# padding\n" * 400 + "def csv_to_json():\n    return []\n"
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=source, test_framework=framework,
        project_goal="CSV to JSON: quoted commas and empty input", requirements=["standard library only"]))
    assert result.generation_status == expected
    assert result.coverage_estimate is None
    assert "def csv_to_json" in captured[0].prompt
    assert "quoted commas" in captured[0].prompt
    assert "standard library only" in captured[0].prompt
    if expected == "generated":
        assert "Here is" not in result.test_code
        assert "not measured" in result.test_strategy
    else:
        assert result.test_code == ""


@pytest.mark.asyncio
async def test_degraded_test_provider_returns_no_suite(monkeypatch):
    async def provider(request):
        return SimpleNamespace(content="", degraded=True, error="provider unavailable")
    monkeypatch.setattr(unified_provider_manager, "execute", provider)
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code="def run(): pass"))
    assert result.generation_status == "degraded"
    assert result.test_code == ""
    assert result.coverage_estimate is None
