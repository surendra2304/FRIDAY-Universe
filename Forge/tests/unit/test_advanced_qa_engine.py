"""
Unit tests for the Advanced Verification & Quality Assurance Engine in Project FORGE.
"""

from pathlib import Path

from app.verification.advanced_battery import (
    AdvancedSecurityVerifier,
    AdvancedVerificationEngine,
)
from app.verification.browser_interactions import BrowserInteractionVerifier
from app.verification.performance import PerformanceVerifier
from app.verification.quality_analyzer import CodeQualityAnalyzer


def test_security_secrets_scanner(tmp_path: Path):
    clean_file = tmp_path / "app.py"
    clean_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    verifier = AdvancedSecurityVerifier(tmp_path)
    res_clean = verifier.scan_secrets()
    assert res_clean.status == "pass"

    # Inject secret
    dirty_file = tmp_path / "secrets.py"
    dirty_file.write_text('OPENAI_KEY = "sk-1234567890abcdef1234567890abcdef"\n', encoding="utf-8")

    res_dirty = verifier.scan_secrets()
    assert res_dirty.status == "fail"
    assert res_dirty.evidence["secrets_found_count"] >= 1
    assert len(res_dirty.fix_suggestions) > 0


def test_security_dangerous_functions_scanner(tmp_path: Path):
    clean_file = tmp_path / "safe.py"
    clean_file.write_text("import json\ndata = json.loads('{}')\n", encoding="utf-8")

    verifier = AdvancedSecurityVerifier(tmp_path)
    res_clean = verifier.scan_dangerous_functions()
    assert res_clean.status == "pass"

    # Inject dangerous eval and os.system
    dangerous_file = tmp_path / "unsafe.py"
    dangerous_file.write_text("import os\neval('2 + 2')\nos.system('dir')\n", encoding="utf-8")

    res_dirty = verifier.scan_dangerous_functions()
    assert res_dirty.status == "fail"
    assert res_dirty.evidence["dangerous_calls_count"] >= 2


def test_dependency_vulnerability_scanner(tmp_path: Path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.18.0\nfastapi==0.110.0\n", encoding="utf-8")

    verifier = AdvancedSecurityVerifier(tmp_path)
    res = verifier.scan_dependency_vulnerabilities()
    assert res.status in ["warn", "fail"]
    assert len(res.evidence["vulnerable_dependencies"]) >= 1


def test_code_quality_complexity_and_lengths(tmp_path: Path):
    complex_py = tmp_path / "complex.py"
    # Generate function with high cyclomatic complexity
    branches = "\n    ".join([f"if x == {i}:\n        print({i})" for i in range(20)])
    code = f"def deep_logic(x):\n    {branches}\n"
    complex_py.write_text(code, encoding="utf-8")

    analyzer = CodeQualityAnalyzer(tmp_path)
    res_complexity = analyzer.analyze_cyclomatic_complexity()
    assert res_complexity.status in ["warn", "fail"]

    res_length = analyzer.analyze_function_and_file_lengths()
    assert res_length.category == "quality"


def test_code_quality_duplicate_and_naming(tmp_path: Path):
    f1 = tmp_path / "module_a.py"
    f2 = tmp_path / "module_b.py"
    duplicate_snippet = (
        "def compute_tax(amount):\n"
        "    rate = 0.15\n"
        "    subtotal = amount * rate\n"
        "    surcharge = 5.0\n"
        "    total = subtotal + surcharge\n"
        "    return total\n"
    )
    f1.write_text(duplicate_snippet, encoding="utf-8")
    f2.write_text(duplicate_snippet, encoding="utf-8")

    analyzer = CodeQualityAnalyzer(tmp_path)
    res_dup = analyzer.analyze_duplicate_code()
    assert res_dup.status == "warn"

    res_naming = analyzer.analyze_naming_conventions()
    assert res_naming.status in ["pass", "warn"]


def test_performance_verifier(tmp_path: Path):
    verifier = PerformanceVerifier(tmp_path)

    # API response time verification
    res_fast = verifier.verify_api_endpoint_latency([50.0, 120.0, 80.0])
    assert res_fast.status == "pass"

    res_slow = verifier.verify_api_endpoint_latency([650.0, 120.0])
    assert res_slow.status == "fail"

    # N+1 query detection
    n1_file = tmp_path / "repo.py"
    n1_file.write_text(
        "async def get_items(db, ids):\n"
        "    results = []\n"
        "    for id_ in ids:\n"
        "        row = await db.execute(f'SELECT * FROM items WHERE id = {id_}')\n"
        "        results.append(row)\n"
        "    return results\n",
        encoding="utf-8",
    )
    res_n1 = verifier.detect_n_plus_one_queries()
    assert res_n1.status in ["warn", "fail"]


def test_browser_interaction_verifier(tmp_path: Path):
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<!DOCTYPE html>\n"
        "<html lang='en'>\n"
        "<head>\n"
        "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n"
        "    <title>Test Page</title>\n"
        "</head>\n"
        "<body>\n"
        "    <a href='https://example.com'>Valid Link</a>\n"
        "    <button id='btnSubmit' type='submit'>Submit</button>\n"
        "    <form id='contactForm'>\n"
        "        <input type='email' required name='email'>\n"
        "    </form>\n"
        "</body>\n"
        "</html>",
        encoding="utf-8",
    )

    verifier = BrowserInteractionVerifier(tmp_path)
    res_interactive = verifier.verify_interactive_elements()
    assert res_interactive.status == "pass"

    res_form = verifier.verify_form_validation()
    assert res_form.status == "pass"

    res_responsive = verifier.verify_responsive_breakpoints()
    assert res_responsive.status in ["pass", "warn"]


def test_full_battery_manifest_generation(tmp_path: Path):
    # Setup standard workspace
    app_file = tmp_path / "main.py"
    app_file.write_text("def run_app():\n    return True\n", encoding="utf-8")

    manifest = AdvancedVerificationEngine.run_full_battery(tmp_path)

    assert manifest.total_checks > 0
    assert manifest.overall_status in ["pass", "warn", "fail"]
    assert (tmp_path / "verification_manifest.json").exists()

    manifest_json = (tmp_path / "verification_manifest.json").read_text(encoding="utf-8")
    assert "overall_status" in manifest_json
    assert "total_checks" in manifest_json
