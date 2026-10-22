"""
Integration Test: Full End-to-End Build with Security Scanner & Advanced Battery Verification.
"""

import tempfile
from pathlib import Path

import pytest

from app.verification.advanced_battery import AdvancedVerificationEngine
from app.verification.security_scanner import OutputSecurityScanner


@pytest.fixture
def synthesized_project():
    """Create a synthesized web application workspace with verification files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        # 1. Clean secure FastAPI service
        main_py = """
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="Secure Task API", version="1.0.0")

class Item(BaseModel):
    id: int
    name: str = Field(..., min_length=1)

items_db = {}

@app.get("/items/{item_id}", response_model=Item)
def read_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]

@app.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(item: Item):
    items_db[item.id] = item
    return item
"""
        (ws / "main.py").write_text(main_py, encoding="utf-8")

        # 2. Pytest test suite
        test_py = """
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_and_read_item():
    res = client.post("/items", json={"id": 1, "name": "Test Item"})
    assert res.status_code == 201
    assert res.json()["name"] == "Test Item"

    get_res = client.get("/items/1")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == 1
"""
        (ws / "test_main.py").write_text(test_py, encoding="utf-8")

        # 3. Requirements file
        (ws / "requirements.txt").write_text(
            "fastapi>=0.110.0\npydantic>=2.6.0\npytest>=8.0.0\n", encoding="utf-8"
        )

        yield ws


def test_full_build_with_security_and_manifest(synthesized_project: Path):
    """Verify that end-to-end battery includes security scanning and writes verification_manifest.json."""
    # 1. Run Pre-Verification Security Scanner
    sec_scanner = OutputSecurityScanner(synthesized_project)
    sec_report = sec_scanner.scan_all()
    assert sec_report.blocks_delivery is False
    assert sec_report.critical_count == 0

    # 2. Run Full Advanced Verification Battery
    manifest = AdvancedVerificationEngine.run_full_battery(synthesized_project)

    # 3. Validate Manifest Output
    manifest_path = synthesized_project / "verification_manifest.json"
    assert manifest_path.exists()
    assert manifest.total_checks > 0

    # Ensure security checks are captured in manifest
    sec_checks = [c for c in manifest.checks if c.category == "security"]
    assert len(sec_checks) >= 1
    assert any(c.status == "pass" for c in sec_checks)
