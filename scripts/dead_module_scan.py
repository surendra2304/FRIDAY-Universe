#!/usr/bin/env python3
"""
dead_module_scan.py — checklist I6 helper: find candidate dead modules.

A module is a DEAD CANDIDATE when no other file in the repo imports it
(no `import X`, `from X import`, `from X.Y import`), it is not a test,
not a script entrypoint (has `if __name__ == "__main__"` or lives in scripts/),
not registered dynamically via string (checked with a raw substring scan of
every file for the module's basename).

Output: one candidate per line with the reason it was flagged. This is a
TRIAGE list, not a delete list — a human/agent verifies each before removal.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SCAN_ROOTS = [
    "FRIDAY/apps/core/src",
    "Inference/app",
    "Memora/apps/api",
    "Stratex",
    "Forge/app/services",
    "Sentinel/app/services",
    "IntelX/intelx/services",
    "Futuris/futuris/core",
    "VyralX/app/services",
]

SKIP_DIR_NAMES = {"__pycache__", "node_modules", ".venv", "venv", "tests", "data",
                  "logs", "backups", "docs", "notes", "audit", "diary"}
IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+([\.A-Za-z_][\.A-Za-z0-9_]*)", re.MULTILINE
)


def iter_package_files() -> list[Path]:
    out = []
    for root in SCAN_ROOTS:
        base = REPO / root
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            out.append(p)
    return out


def main() -> int:
    pkg_files = iter_package_files()
    all_files = [p for p in REPO.rglob("*")
                 if p.suffix in (".py", ".yml", ".yaml", ".toml", ".cfg", ".md",
                                 ".json", ".sh", ".html", ".js", ".ts")
                 and not any(part in SKIP_DIR_NAMES | {".git"} for part in p.parts)]

    # Pre-read all non-package files (config/docs/reference material)
    reference_blobs: list[str] = []
    for f in all_files:
        try:
            reference_blobs.append(f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    reference_text = "\n".join(reference_blobs)

    # Map: module stem -> set of files that import it by module path
    imported_names: set[str] = set()
    for f in pkg_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in IMPORT_RE.finditer(text):
            for part in match.group(1).lstrip(".").split("."):
                if part:
                    imported_names.add(part)

    candidates = []
    for p in pkg_files:
        stem = p.stem
        if stem.startswith(("test_", "conftest", "mock_")):
            continue
        rel = p.relative_to(REPO)
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        has_main = "__main__" in text
        in_scripts = "scripts" in p.parts
        # dynamic reference: basename appears anywhere outside its own file
        dyn_hits = reference_text.count(stem) - text.count(stem) if reference_text.count(stem) else 0
        if stem in imported_names or stem in reference_text:
            continue
        reason = []
        if not has_main and not in_scripts:
            reason.append("no importer, no __main__, not a script")
        elif has_main:
            reason.append("no importer (has __main__ — maybe a manual entrypoint)")
        else:
            reason.append("no importer (in scripts/)")
        candidates.append(f"{rel}  [{'; '.join(reason)}]")

    for c in sorted(candidates):
        print(c)
    print(f"--- {len(candidates)} dead-module candidates of {len(pkg_files)} package files ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
