#!/usr/bin/env python3
"""I6 dead-code audit (ZAI Agent 2): find tools registered in the default
registry that are NOT routed to by the capability router, NOT called by any
fast-path, and NOT referenced by any agent skill. Conservative — a tool is
only "unreachable" if ALL three checks fail.

Outputs a JSON report to stdout + a human-readable summary.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS_PY = REPO / "FRIDAY" / "src" / "friday" / "agent" / "mixins" / "tools.py"
ROUTER_PY = REPO / "FRIDAY" / "src" / "friday" / "routing" / "capability_router.py"
FAST_PATHS_PY = REPO / "FRIDAY" / "src" / "friday" / "agent" / "mixins" / "fast_paths.py"
BUILTIN_DIR = REPO / "FRIDAY" / "src" / "friday" / "tools" / "builtin"
SRC_ROOT = REPO / "FRIDAY" / "src"


def extract_registered_tool_names() -> set[str]:
    """Tool class names registered via registry.register(ToolName())."""
    src = TOOLS_PY.read_text(encoding="utf-8")
    return set(re.findall(r"registry\.register\((\w+)\(\)\)", src))


def extract_tool_name_attribute() -> dict[str, str]:
    """Map each builtin tool FILE -> its `name = "..."` attribute."""
    mapping: dict[str, str] = {}
    for py in BUILTIN_DIR.glob("*.py"):
        if py.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Assign) and len(item.targets) == 1:
                        target = item.targets[0]
                        if isinstance(target, ast.Name) and target.id == "name":
                            if isinstance(item.value, ast.Constant):
                                mapping[py.stem] = item.value.value
    return mapping


def find_references(name: str) -> list[str]:
    """Files under FRIDAY/src that reference `name` (class or string)."""
    try:
        proc = subprocess.run(
            ["grep", "-rl", "--include=*.py", name, str(SRC_ROOT)],
            capture_output=True, text=True, timeout=30,
        )
        files = [Path(f).relative_to(REPO).as_posix() for f in proc.stdout.splitlines() if f.strip()]
        return [f for f in files if "__pycache__" not in f]
    except Exception:
        return []


def is_routed(tool_name_attr: str) -> bool:
    """Does the capability router reference this tool name in required_tools?"""
    src = ROUTER_PY.read_text(encoding="utf-8")
    return f'"{tool_name_attr}"' in src or f"'{tool_name_attr}'" in src


def is_fast_path_referenced(class_name: str) -> bool:
    """Does any fast-path import or instantiate this tool class?"""
    try:
        src = FAST_PATHS_PY.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return class_name in src


def main() -> int:
    registered = extract_registered_tool_names()
    file_to_attr = extract_tool_name_attribute()

    # Map class name -> (file, tool_name_attribute)
    # We need to resolve class name to file. Parse __init__.py for the import map.
    init_src = (BUILTIN_DIR / "__init__.py").read_text(encoding="utf-8")
    class_to_file: dict[str, str] = {}
    for m in re.finditer(r"from friday\.tools\.builtin\.(\w+) import (\w+)", init_src):
        class_to_file[m.group(2)] = m.group(1)

    report: list[dict] = []
    for class_name in sorted(registered):
        file_stem = class_to_file.get(class_name, "")
        tool_attr = file_to_attr.get(file_stem, "")
        if not tool_attr:
            # Tool without a `name` attribute — skip (can't route anyway).
            continue
        refs = find_references(class_name)
        routed = is_routed(tool_attr)
        fast_path = is_fast_path_referenced(class_name)
        # A tool is "reachable" if it's routed, OR called by a fast-path,
        # OR referenced by more than just __init__/tools.py (some agent skill uses it).
        non_registration_refs = [r for r in refs if r not in (
            f"FRIDAY/src/friday/tools/builtin/{file_stem}.py",
            "FRIDAY/src/friday/tools/builtin/__init__.py",
            "FRIDAY/src/friday/agent/mixins/tools.py",
        )]
        reachable = routed or fast_path or bool(non_registration_refs)
        report.append({
            "class": class_name,
            "file": file_stem,
            "tool_name": tool_attr,
            "routed": routed,
            "fast_path": fast_path,
            "other_refs": non_registration_refs[:3],
            "reachable": reachable,
            "verdict": "reachable" if reachable else "UNREACHABLE",
        })

    unreachable = [r for r in report if not r["reachable"]]
    print(f"=== I6 dead-code audit ===")
    print(f"Registered tools: {len(report)}")
    print(f"Reachable: {len(report) - len(unreachable)}")
    print(f"UNREACHABLE: {len(unreachable)}")
    print()
    if unreachable:
        print("=== UNREACHABLE tools (candidates for removal or wiring) ===")
        for r in unreachable:
            print(f"  - {r['class']} (tool_name={r['tool_name']}, file={r['file']})")
    print()
    print("=== Full report (JSON) ===")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
