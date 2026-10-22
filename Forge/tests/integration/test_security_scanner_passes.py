"""
Integration Test: Security Scanner Allows Clean, Secure Deliverables.
"""

import tempfile
from pathlib import Path

import pytest

from app.verification.security_scanner import (
    OutputSecurityScanner,
)


@pytest.fixture
def clean_workspace():
    """Create a temporary workspace following strict secure coding standards."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        # 1. Clean service file using environment variables and Pydantic validation
        py_code = """
import os
from pydantic import BaseModel, Field

class CreateItemRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0.0)

API_KEY = os.getenv("FORGE_API_KEY", "default-test-key")

def calculate_tax(price: float) -> float:
    return round(price * 0.15, 2)
"""
        (ws / "service.py").write_text(py_code, encoding="utf-8")

        # 2. Clean database layer with parameterized SQL bindings
        db_code = """
import sqlite3
from typing import Optional, Tuple

def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[Tuple]:
    cursor = conn.cursor()
    # Parameterized query - safe from injection
    cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()
"""
        (ws / "database.py").write_text(db_code, encoding="utf-8")

        # 3. Clean requirements with safe versions
        (ws / "requirements.txt").write_text(
            "fastapi>=0.110.0\npydantic>=2.6.0\n", encoding="utf-8"
        )

        yield ws


def test_security_scanner_passes_clean_project(clean_workspace: Path):
    """Verify that a clean, secure project produces zero blocking security findings and passes delivery."""
    scanner = OutputSecurityScanner(clean_workspace)
    report = scanner.scan_all()

    # 1. Must pass and allow delivery
    assert report.passed is True
    assert report.blocks_delivery is False
    assert report.critical_count == 0
    assert report.high_count == 0
    assert len(report.findings) == 0
