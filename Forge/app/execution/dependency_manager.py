"""
Dependency Management Subsystem for Project FORGE.
Extracts imported modules via AST parsing, resolves PyPI/npm package names,
pins versions, auto-generates requirements.txt/package.json, and flags vulnerable or banned libraries.
"""

import ast
import json
import re
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger("execution.dependency_manager")

# Standard library modules in Python 3.11+
PYTHON_STDLIB: set[str] = {
    "abc",
    "argparse",
    "array",
    "ast",
    "asyncio",
    "base64",
    "bisect",
    "builtins",
    "calendar",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "collections",
    "colorsys",
    "compileall",
    "concurrent",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "csv",
    "ctypes",
    "curses",
    "dataclasses",
    "datetime",
    "dbm",
    "decimal",
    "difflib",
    "dis",
    "doctest",
    "email",
    "encodings",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "fractions",
    "ftplib",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "graphlib",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "imaplib",
    "imghdr",
    "importlib",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "keyword",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "multiprocessing",
    "netrc",
    "nntplib",
    "numbers",
    "operator",
    "optparse",
    "os",
    "pathlib",
    "pdb",
    "pickle",
    "pickletools",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "posixpath",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtpd",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "spwd",
    "sqlite3",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symtable",
    "sys",
    "sysconfig",
    "syslog",
    "tarfile",
    "telnetlib",
    "tempfile",
    "termios",
    "test",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "tkinter",
    "token",
    "tokenize",
    "tomllib",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "turtle",
    "turtledemo",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "winreg",
    "winsound",
    "wsgiref",
    "xdrlib",
    "xml",
    "xmlrpc",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
    "_thread",
}

# Known top-level module to PyPI package mappings
MODULE_TO_PYPI: dict[str, str] = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "dotenv": "python-dotenv",
    "fastapi": "fastapi",
    "flask": "flask",
    "git": "GitPython",
    "httpx": "httpx",
    "jwt": "PyJWT",
    "PIL": "pillow",
    "pydantic": "pydantic",
    "pytest": "pytest",
    "requests": "requests",
    "rich": "rich",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "sqlalchemy": "SQLAlchemy",
    "torch": "torch",
    "uvicorn": "uvicorn",
    "yaml": "PyYAML",
}

# Known recommended pinned versions for stable reproducibility
PINNED_VERSIONS: dict[str, str] = {
    "fastapi": ">=0.100.0",
    "uvicorn": ">=0.22.0",
    "pydantic": ">=2.0.0",
    "httpx": ">=0.24.0",
    "pytest": ">=7.4.0",
    "requests": ">=2.31.0",
    "rich": ">=13.4.0",
    "SQLAlchemy": ">=2.0.0",
    "beautifulsoup4": ">=4.12.0",
    "python-dotenv": ">=1.0.0",
    "PyYAML": ">=6.0",
}

# Known high-risk or banned libraries (e.g., deprecated or inherently unsafe)
KNOWN_VULNERABLE_OR_BANNED: dict[str, str] = {
    # Python
    "telnetlib": "Insecure unencrypted remote access protocol.",
    "crypto": "Deprecated and unmaintained package (use pycryptodome or cryptography).",
    "pycrypto": "Unmaintained with known security vulnerabilities (use pycryptodome).",
    # Node / npm
    "event-stream": "Compromised npm package (flatmap-stream malicious payload, CVE-2018-16387).",
    "flatmap-stream": "Malicious npm package used in the event-stream compromise.",
    "ua-parser-js": "Widely compromised npm package (multiple malicious releases, CVE-2021-27292).",
    "coa": "Compromised npm package (CVE-2021-23341).",
    "rc": "Compromised npm package (CVE-2021-23341).",
    "colors": "Compromised npm package (sabotaged release, CVE-2022-0122).",
    "faker": "Compromised npm package (sabotaged release, CVE-2022-0122).",
    "node-ipc": "Compromised npm package (protestware, CVE-2022-23812).",
    "peacenotwar": "Protestware dependency.",
    # Go
    "github.com/unknwon/cae": "Known malicious Go module (CVE-2021-3845).",
    # Java / Maven
    "log4j:log4j": "Log4Shell (CVE-2021-44228) -- upgrade to log4j 2.17.1+.",
    "org.apache.logging.log4j:log4j-core": "Log4Shell (CVE-2021-44228) -- upgrade to 2.17.1+.",
    "com.fasterxml.jackson.core:jackson-databind": "Multiple deserialization RCE CVEs; pin >= 2.13.2.1.",
}


class DependencyManager:
    """Detects, inspects, and manages project dependencies in isolated sandboxes."""

    def __init__(self, workspace_root: Path | None = None):
        self.workspace_root = workspace_root

    def extract_python_imports(self, code: str) -> set[str]:
        """Parse Python AST and extract top-level import module names."""
        modules = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_pkg = alias.name.split(".")[0]
                        modules.add(top_pkg)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_pkg = node.module.split(".")[0]
                        modules.add(top_pkg)
        except Exception as e:
            logger.debug(f"AST parsing failed for dependency extraction: {e}")
            # Fallback to regex import detection
            for match in re.finditer(r"^(?:from|import)\s+([a-zA-Z0-9_]+)", code, re.MULTILINE):
                modules.add(match.group(1))

        return modules

    def detect_workspace_dependencies(self, project_dir: Path) -> set[str]:
        """Scan all Python, JS/TS and manifest files for external dependencies.

        This used to walk `**/*.py` only, so a JavaScript/TypeScript project
        reported no dependencies at all and check_security() silently approved
        every npm package -- including the compromised ones above.
        """
        external_deps: set[str] = set()
        if not project_dir.exists():
            return external_deps

        # 0. Declared manifests are authoritative -- read them first.
        external_deps |= self._read_package_json(project_dir)
        external_deps |= self._read_requirements_txt(project_dir)
        external_deps |= self._read_go_mod(project_dir)

        # 1. Scan python files
        for py_file in project_dir.glob("**/*.py"):
            try:
                code = py_file.read_text(encoding="utf-8", errors="ignore")
                imports = self.extract_python_imports(code)
                for mod in imports:
                    if (
                        mod not in PYTHON_STDLIB
                        and not (project_dir / f"{mod}.py").exists()
                        and not (project_dir / mod).is_dir()
                    ):
                        pypi_pkg = MODULE_TO_PYPI.get(mod, mod)
                        external_deps.add(pypi_pkg)
            except Exception as e:
                logger.debug(f"Error scanning {py_file} for dependencies: {e}")

        # 2. Scan JS/TS sources for bare imports (complements package.json, and
        #    catches dependencies used but never declared).
        external_deps |= self._scan_js_imports(project_dir)

        return external_deps

    @staticmethod
    def _read_package_json(project_dir: Path) -> set[str]:
        deps: set[str] = set()
        manifest = project_dir / "package.json"
        if not manifest.is_file():
            return deps
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            logger.debug(f"Unable to parse {manifest}: {e}")
            return deps
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            for name in (data.get(section) or {}):
                if isinstance(name, str) and name:
                    deps.add(name)
        return deps

    @staticmethod
    def _read_requirements_txt(project_dir: Path) -> set[str]:
        deps: set[str] = set()
        manifest = project_dir / "requirements.txt"
        if not manifest.is_file():
            return deps
        try:
            for line in manifest.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.split("#", 1)[0].strip()
                if not stripped or stripped.startswith("-"):
                    continue
                name = re.split(r"[=<>!~\[;]", stripped, maxsplit=1)[0].strip()
                if name:
                    deps.add(name)
        except Exception as e:
            logger.debug(f"Unable to parse {manifest}: {e}")
        return deps

    @staticmethod
    def _read_go_mod(project_dir: Path) -> set[str]:
        deps: set[str] = set()
        manifest = project_dir / "go.mod"
        if not manifest.is_file():
            return deps
        try:
            for line in manifest.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped.startswith("require ") or stripped.startswith("\t"):
                    parts = stripped.replace("require ", "", 1).split()
                    if parts and "/" in parts[0]:
                        deps.add(parts[0])
        except Exception as e:
            logger.debug(f"Unable to parse {manifest}: {e}")
        return deps

    @classmethod
    def _scan_js_imports(cls, project_dir: Path) -> set[str]:
        deps: set[str] = set()
        for src in list(project_dir.glob("**/*.js")) + list(project_dir.glob("**/*.ts")):
            if "node_modules" in str(src):
                continue
            try:
                text = src.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for match in re.finditer(
                r"""(?:import\s+[^'"]*from\s*|require\(\s*|import\s*\(\s*)['"]([^'"]+)['"]""",
                text,
            ):
                spec = match.group(1)
                if spec.startswith(".") or spec.startswith("/"):
                    continue
                parts = spec.split("/")
                pkg = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
                if pkg:
                    deps.add(pkg)
        return deps

    def generate_requirements_txt(self, dependencies: set[str]) -> str:
        """Generate formatted and pinned requirements.txt content."""
        lines = []
        for dep in sorted(dependencies):
            version_pin = PINNED_VERSIONS.get(dep, ">=1.0.0")
            lines.append(f"{dep}{version_pin}")
        return "\n".join(lines) + ("\n" if lines else "")

    def check_security(self, dependencies: set[str]) -> list[dict[str, Any]]:
        """Check list of dependencies for known vulnerabilities or blocked packages."""
        issues = []
        for dep in dependencies:
            dep_lower = dep.lower()
            if dep_lower in KNOWN_VULNERABLE_OR_BANNED:
                issues.append(
                    {
                        "package": dep,
                        "severity": "HIGH",
                        "reason": KNOWN_VULNERABLE_OR_BANNED[dep_lower],
                    }
                )
        return issues
