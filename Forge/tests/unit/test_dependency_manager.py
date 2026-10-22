"""
Unit tests for Dependency Management Subsystem.
"""

from pathlib import Path

from app.execution.dependency_manager import DependencyManager


def test_extract_python_imports():
    code = """
import os
import sys
from fastapi import FastAPI, HTTPException
import pydantic
from bs4 import BeautifulSoup
from .local_mod import helper
"""
    dep_mgr = DependencyManager()
    imports = dep_mgr.extract_python_imports(code)

    assert "os" in imports
    assert "sys" in imports
    assert "fastapi" in imports
    assert "pydantic" in imports
    assert "bs4" in imports


def test_detect_workspace_dependencies(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    main_code = """
import httpx
import rich
from pydantic import BaseModel
"""
    (project_dir / "main.py").write_text(main_code, encoding="utf-8")

    dep_mgr = DependencyManager()
    deps = dep_mgr.detect_workspace_dependencies(project_dir)

    assert "httpx" in deps
    assert "rich" in deps
    assert "pydantic" in deps
    assert "os" not in deps  # Stdlib ignored

    req_txt = dep_mgr.generate_requirements_txt(deps)
    assert "httpx>=" in req_txt
    assert "rich>=" in req_txt


def test_check_security():
    dep_mgr = DependencyManager()
    safe_deps = {"fastapi", "pytest", "rich"}
    issues = dep_mgr.check_security(safe_deps)
    assert len(issues) == 0

    vulnerable_deps = {"fastapi", "pycrypto", "telnetlib"}
    issues_vuln = dep_mgr.check_security(vulnerable_deps)
    assert len(issues_vuln) == 2
    vuln_names = [i["package"] for i in issues_vuln]
    assert "pycrypto" in vuln_names
    assert "telnetlib" in vuln_names
