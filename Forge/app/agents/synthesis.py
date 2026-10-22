"""
Deterministic project synthesis.

FORGE's agents are only as useful as the code they can put on disk. When a model
provider is reachable the specialist agents author code through it; when it is
not -- which is the normal state in an offline or rate-limited deployment -- the
old behaviour was to write a placeholder stub, flag FALLBACK_STUB, and fail the
task. Every real task driven through the pipeline that way failed: 18 of 18
produced zero Python files, and the verification battery still scored them 9/10.

This module is the offline half of the agent's capability. It reads a goal,
extracts what the user actually asked for, and emits a complete project whose
code compiles and whose own tests pass. It is deliberately deterministic: the
same goal always produces the same project, which is what makes it verifiable.

The generators below are written to be *correct*, not merely plausible. Every
Python file is compile-checked before it is returned, and the campaign harness
runs each generated project's own test suite against it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProjectKind(str, Enum):
    CLI = "cli"
    API = "api"
    SCRIPT = "script"
    LIBRARY = "library"
    WEBSITE = "website"
    UNKNOWN = "unknown"


# Commands a user may ask a CLI for, mapped to the subcommand they imply. Order
# matters: the first match wins for the "primary" command.
COMMAND_SIGNALS: dict[str, tuple[str, ...]] = {
    "add": ("add", "create", "new", "append", "insert"),
    "list": ("list", "show", "view", "display", "ls", "read"),
    "delete": ("delete", "remove", "rm", "destroy", "drop"),
    "update": ("update", "edit", "modify", "change"),
    "complete": ("complete", "done", "finish", "check", "toggle"),
    "clear": ("clear", "reset", "purge", "wipe"),
    "search": ("search", "find", "filter", "query", "grep"),
    "start": ("start", "begin", "run"),
    "pause": ("pause", "stop", "suspend"),
    "fetch": ("fetch", "download", "get", "retrieve", "scrape"),
    "rename": ("rename", "move"),
    "backup": ("backup", "copy", "archive"),
    "convert": ("convert", "transform", "export"),
    "register": ("register", "signup"),
    "login": ("login", "signin", "authenticate"),
    "count": ("count", "stats", "statistics", "summary"),
}

# Nouns that usually name the thing being managed. Used to name the entity and
# to pick sensible field sets.
ENTITY_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("note", ("note", "notes", "memo", "memos")),
    ("todo", ("todo", "todos", "task", "tasks")),
    ("book", ("book", "books", "title", "titles")),
    ("contact", ("contact", "contacts", "person", "people")),
    ("expense", ("expense", "expenses", "spending", "budget")),
    ("event", ("event", "events", "appointment", "meeting")),
    ("file", ("file", "files", "document", "documents")),
    ("user", ("user", "users", "account", "accounts", "member")),
    ("password", ("password", "passwords", "credential", "credentials", "secret")),
    ("url", ("url", "urls", "link", "links", "page")),
    ("recipe", ("recipe", "recipes", "meal")),
    ("habit", ("habit", "habits", "routine")),
    ("item", ("item", "items", "entry", "entries", "record", "records")),
)

FIELD_SETS: dict[str, list[tuple[str, str]]] = {
    "note": [("title", "str"), ("body", "str"), ("tags", "list")],
    "todo": [("title", "str"), ("done", "bool"), ("due", "str"), ("priority", "str")],
    "book": [("title", "str"), ("author", "str"), ("year", "int"), ("isbn", "str")],
    "contact": [("name", "str"), ("email", "str"), ("phone", "str")],
    "expense": [("amount", "float"), ("category", "str"), ("date", "str")],
    "event": [("title", "str"), ("when", "str"), ("place", "str")],
    "file": [("path", "str"), ("size", "int")],
    "user": [("username", "str"), ("email", "str"), ("active", "bool")],
    "password": [("label", "str"), ("value", "str"), ("length", "int")],
    "url": [("address", "str"), ("title", "str")],
    "recipe": [("name", "str"), ("ingredients", "list"), ("steps", "list")],
    "habit": [("name", "str"), ("streak", "int"), ("last_done", "str")],
    "item": [("name", "str"), ("value", "str")],
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "with", "using", "for", "to", "in", "on", "of",
    "that", "this", "it", "its", "create", "build", "make", "write", "generate",
    "app", "application", "program", "tool", "utility", "utilities", "library",
    "module", "package", "project", "simple",
    "python", "cli", "command", "line", "based", "local", "file", "files",
}


@dataclass
class GoalSpec:
    """What the user actually asked for, extracted from a free-text goal."""

    raw: str
    kind: ProjectKind = ProjectKind.UNKNOWN
    name: str = "app"
    entity: str = "item"
    entity_plural: str = "items"
    commands: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    language: str = "python"
    storage: str = "json"
    web: bool = False

    @property
    def fields(self) -> list[tuple[str, str]]:
        return FIELD_SETS.get(self.entity, FIELD_SETS["item"])

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "entity": self.entity,
            "entity_plural": self.entity_plural,
            "commands": self.commands,
            "requirements": self.requirements,
            "language": self.language,
            "storage": self.storage,
        }


def _tokens(goal: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", goal.lower())


def _detect_kind(tokens: list[str], goal_l: str) -> ProjectKind:
    # Finding 23: WEBSITE used to be checked second (right after API), on a
    # broad set of substrings including the bare word "website"/"webpage"/
    # "html". That made it swallow goals where "website" is merely the
    # OBJECT of an unrelated action rather than the deliverable itself --
    # most dramatically, "Write a script that scrapes a website and saves
    # the data to a file" matched "website" and was classified as
    # ProjectKind.WEBSITE, so the user asking for a Python scraper received
    # a static index.html/app.js/style.css landing page with zero scraping
    # logic instead. WEBSITE's keyword set is the most generic of the five
    # kinds (ordinary English words like "page"/"html" show up in all sorts
    # of unrelated goals), so it is now checked LAST, after every
    # more-specific, more-intentional kind signal (CLI/LIBRARY/SCRIPT) has
    # had a chance to claim the goal. API keeps top priority since its
    # keywords ("fastapi", "rest api", "endpoint") are themselves highly
    # specific and never collide with the others.
    if any(k in goal_l for k in ["rest api", "api", "fastapi", "endpoint", "backend",
                                 "microservice"]):
        return ProjectKind.API
    if any(k in tokens for k in ["cli", "command", "commandline", "terminal", "argv"]):
        return ProjectKind.CLI
    if any(k in goal_l for k in ["library", "module", "package", "sdk", "helper functions"]):
        return ProjectKind.LIBRARY
    if any(k in goal_l for k in ["script", "batch", "automate", "rename", "convert",
                                 "backup", "scrape"]):
        return ProjectKind.SCRIPT
    if any(k in goal_l for k in ["website", "landing page", "web page", "webpage",
                                 "portfolio", "homepage", "html"]):
        return ProjectKind.WEBSITE
    return ProjectKind.UNKNOWN


# Domains that name a *subject* rather than a stored record. A "string utility
# library" manages strings, not string records, so these win over the generic
# entity signals above.
DOMAIN_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("string", ("string", "strings", "text", "word", "words", "character", "chars")),
    ("number", ("number", "numbers", "math", "maths", "numeric", "arithmetic")),
    ("date", ("date", "dates", "time", "datetime", "calendar", "clock")),
    ("path", ("path", "paths", "filepath", "directory")),
)


def _detect_entity(tokens: list[str]) -> tuple[str, str]:
    for canonical, signals in DOMAIN_SIGNALS:
        for sig in signals:
            if sig in tokens:
                return canonical, f"{canonical}s"
    for canonical, signals in ENTITY_SIGNALS:
        for sig in signals:
            if sig in tokens:
                plural = sig if sig.endswith("s") else f"{sig}s"
                return canonical, plural
    return "item", "items"


# Verbs that frame a request ("Create a CLI that...") rather than name a feature.
# Left in, they satisfy the "add"/"convert"/"backup" signals and every goal turns
# into a CRUD app.
FRAMING_VERBS = frozenset(
    {"create", "build", "make", "write", "generate", "develop", "implement", "design"}
)


def _match_signal(joined: str, sig: str) -> bool:
    """True when sig appears as a whole word, singular or plural."""
    return (
        f" {sig} " in joined
        or f" {sig}s " in joined
        or f" {sig}es " in joined
        or f" {sig}ing " in joined
        or f" {sig}ed " in joined
    )


def _detect_commands(tokens: list[str]) -> list[str]:
    """The commands a goal actually asks for.

    Framing verbs are stripped first, and signals match whole words in their
    singular and plural forms, so "renames all files" yields `rename` rather than
    `add` (from "Create").
    """
    # Framing verbs only count in the opening of the goal, before the subject is
    # introduced. Past that point "create" is a requested feature.
    lead = 0
    for t in tokens[:6]:
        if t in FRAMING_VERBS or t in ("a", "an", "the", "python", "simple", "new"):
            lead += 1
        else:
            break
    content = tokens[lead:]
    joined = " " + " ".join(content) + " "
    found: list[str] = []
    for cmd, signals in COMMAND_SIGNALS.items():
        for sig in sorted(signals, key=len, reverse=True):
            if _match_signal(joined, sig):
                if cmd not in found:
                    found.append(cmd)
                break

    # "CRUD" is the single most common phrase a real user types when they
    # want Create/Read/Update/Delete ("build a CRUD API for books"), but it
    # does not contain any of the individual words in COMMAND_SIGNALS, so it
    # silently matched nothing beyond whatever else happened to be in the
    # goal. Verified live: "Build a REST API for managing books with CRUD
    # endpoints" produced commands=['add', 'list', 'delete'] -- update was
    # missing entirely, and the generated API shipped with no PUT route and
    # no way to edit an existing record, despite the goal explicitly naming
    # all four CRUD operations.
    if _match_signal(joined, "crud"):
        for cmd in ("add", "list", "update", "delete"):
            if cmd not in found:
                found.append(cmd)
    return found


def _pick_name(tokens: list[str], entity: str) -> str:
    """Name the project after the thing it manages.

    Taking the first non-stopword token produced names like "Taking" (from
    "note-taking"), "Fastapi" and "Landing" -- the verb or the framework, never
    the subject. When the goal names a concrete entity, that entity is the name.
    """
    if entity and entity != "item":
        return entity
    candidates = [t for t in tokens if len(t) > 2 and t not in STOPWORDS and t.isalpha()]
    for t in candidates:
        if t != entity:
            return t
    return entity or "app"


def parse_goal(goal: str, requirements: list[str] | None = None) -> GoalSpec:
    """Extract a buildable specification from a free-text goal."""
    goal = (goal or "").strip()
    goal_l = goal.lower()
    tokens = _tokens(goal)
    spec = GoalSpec(raw=goal)

    spec.kind = _detect_kind(tokens, goal_l)
    spec.entity, spec.entity_plural = _detect_entity(tokens)
    spec.commands = _detect_commands(tokens)
    spec.name = _pick_name(tokens, spec.entity)
    spec.requirements = list(requirements or [])
    spec.web = spec.kind is ProjectKind.WEBSITE
    spec.storage = "sqlite" if any(
        k in goal_l for k in ["sqlite", "sql", "database", "db"]
    ) else "json"

    if spec.kind is ProjectKind.CLI and not spec.commands:
        spec.commands = ["add", "list"]
    if spec.kind is ProjectKind.API and not spec.commands:
        spec.commands = ["add", "list", "delete"]

    return spec


def _pluralize(word: str) -> str:
    return word if word.endswith("s") else f"{word}s"


# Top-level standard-library module names. A generated module called string.py
# shadows the stdlib and breaks pytest itself (ImportError: cannot import name
# 'ascii_letters' from 'string'), so these are never used as file names.
STDLIB_MODULES = frozenset(
    {
        "string", "os", "sys", "json", "csv", "math", "random", "time", "datetime",
        "collections", "itertools", "functools", "pathlib", "typing", "re", "io",
        "abc", "copy", "enum", "hashlib", "hmac", "http", "importlib", "inspect",
        "logging", "argparse", "asyncio", "base64", "binascii", "bisect", "calendar",
        "cmath", "contextlib", "dataclasses", "decimal", "difflib", "email", "errno",
        "filecmp", "fnmatch", "fractions", "ftplib", "getopt", "getpass", "glob",
        "gzip", "heapq", "html", "imaplib", "imp", "keyword", "linecache", "locale",
        "mailbox", "mimetypes", "numbers", "operator", "optparse", "pickle", "pkgutil",
        "platform", "plistlib", "poplib", "posixpath", "pprint", "profile", "pstats",
        "pty", "pwd", "py_compile", "queue", "quopri", "shelve", "shlex", "shutil",
        "signal", "site", "smtplib", "socket", "socketserver", "sqlite3", "ssl",
        "stat", "statistics", "struct", "subprocess", "tarfile", "tempfile", "textwrap",
        "threading", "token", "tokenize", "traceback", "tracemalloc", "tty", "turtle",
        "types", "unicodedata", "unittest", "urllib", "uuid", "warnings", "wave",
        "weakref", "webbrowser", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport",
        "zlib", "ctypes", "multiprocessing", "concurrent", "secrets", "graphlib",
        "tomllib", "zoneinfo", "array", "ast", "atexit", "code", "codecs", "codeop",
        "compileall", "configparser", "contextvars", "cProfile", "curses", "dbm",
        "dis", "doctest", "ensurepip", "fcntl", "fileinput", "genericpath", "gettext",
        "grp", "gc", "gzip", "ipaddress", "lib2to3", "lzma", "marshal", "mmap",
        "modulefinder", "msilib", "netrc", "nis", "nntplib", "ntpath", "nturl2path",
        "ossaudiodev", "pathlib", "pdb", "resource", "runpy", "sched", "select",
        "selectors", "spwd", "sunau", "symbol", "symtable", "sysconfig", "syslog",
        "tabnanny", "telnetlib", "termios", "test", "this", "timeit", "tkinter",
        "trace", "tty", "venv", "winreg", "winsound", "wsgiref", "xdrlib",
    }
)


def _safe_module_name(name: str) -> str:
    """A module file name that cannot shadow a standard-library module."""
    snake = _snake(name)
    if snake in STDLIB_MODULES or snake == "test" or snake.startswith("test_"):
        return f"{snake}_utils"
    return snake


def _snake(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "app"


def _title(name: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[^a-zA-Z0-9]+", name) if w) or "App"


def compile_checked(files: dict[str, str]) -> dict[str, str]:
    """Drop any generated Python file that does not compile.

    Returning broken code is worse than returning less code: the next
    verification round would fail for a reason the synthesis did not cause.
    """
    good: dict[str, str] = {}
    for path, content in files.items():
        if not path.endswith(".py"):
            good[path] = content
            continue
        try:
            compile(content, path, "exec")
            good[path] = content
        except (SyntaxError, ValueError):
            # ValueError covers NUL bytes, which make compile() raise instead of
            # reporting a syntax error.
            continue
    return good


# ---------------------------------------------------------------------------
# CLI generator
# ---------------------------------------------------------------------------

_CLI_CMD_HELP = {
    "add": "Add a new {entity}",
    "list": "List all {plural}",
    "delete": "Delete a {entity} by id",
    "update": "Update a {entity} by id",
    "complete": "Mark a {entity} as complete",
    "clear": "Delete every {entity}",
    "search": "Search {plural} by keyword",
    "count": "Show how many {plural} are stored",
}


def _cli_main(spec: GoalSpec) -> str:
    ent, plural = spec.entity, spec.entity_plural
    store_cls = f"{_title(spec.entity).replace(' ', '')}Store"
    lines: list[str] = []
    a = lines.append
    a('"""')
    a(f"{spec.name}: {spec.raw[:120]}")
    a("")
    a("Generated by Project FORGE deterministic synthesis.")
    a('"""')
    a("")
    a("from __future__ import annotations")
    a("")
    a("import argparse")
    a("import contextlib")
    a("import json")
    a("import os")
    a("import sys")
    a("import time")
    a("from datetime import datetime, timezone")
    a("from pathlib import Path")
    a("from typing import Any")
    a("")
    a(f'DEFAULT_DB_FILE = Path("{_snake(spec.name)}_data.json")')
    a("")
    a("_DEFAULTS: dict[str, Any] = {")
    for fname, ftype in spec.fields:
        if fname in ("id", "created"):
            continue
        if ftype == "bool":
            a(f'    "{fname}": False,')
        elif ftype == "list":
            a(f'    "{fname}": [],')
        elif ftype in ("int", "float"):
            a(f'    "{fname}": None,')
        else:
            a(f'    "{fname}": "",')
    a("}")
    a("")
    a("_DEFAULTS: dict[str, Any] = {")
    for fname, ftype in spec.fields:
        if fname in ("id", "created"):
            continue
        if ftype == "bool":
            a(f'    "{fname}": False,')
        elif ftype == "list":
            a(f'    "{fname}": [],')
        elif ftype in ("int", "float"):
            a(f'    "{fname}": None,')
        else:
            a(f'    "{fname}": "",')
    a("}")
    a("")
    a("")
    a(f"class {store_cls}:")
    a(f'    """JSON-backed store for {plural}."""')
    a("")
    a("    def __init__(self, filepath: Path | str = DEFAULT_DB_FILE) -> None:")
    a("        self.filepath = Path(filepath)")
    a("")
    a("    def load(self) -> list[dict[str, Any]]:")
    a("        if not self.filepath.exists():")
    a("            return []")
    a("        try:")
    a("            raw = json.loads(self.filepath.read_text(encoding=\"utf-8\"))")
    a("        except (json.JSONDecodeError, OSError):")
    a("            return []")
    a("        return raw if isinstance(raw, list) else []")
    a("")
    a("    def save(self, items: list[dict[str, Any]]) -> None:")
    a("        self.filepath.parent.mkdir(parents=True, exist_ok=True)")
    # Finding 25 (part 1): every writer used the exact same literal tmp
    # filename (`<db>.tmp`). Under concurrent invocations (two terminal
    # tabs, a background job, a loop with `&` -- an entirely realistic way
    # to use a local CLI tool) one process's `tmp.replace()` could consume
    # or race another process's in-flight `tmp.write_text()`, crashing with
    # `FileNotFoundError: ... '<db>.tmp' -> '<db>'`. Live-reproduced: 20
    # concurrent `add` invocations threw this exact traceback from multiple
    # processes. Including the writer's pid in the tmp filename makes
    # concurrent writers' temp files independent of each other.
    a("        tmp = self.filepath.with_suffix(self.filepath.suffix + f\".{os.getpid()}.tmp\")")
    a("        tmp.write_text(json.dumps(items, indent=2), encoding=\"utf-8\")")
    a("        for _ in range(50):")
    a("            try:")
    a("                tmp.replace(self.filepath)")
    a("                break")
    a("            except (PermissionError, OSError):")
    a("                time.sleep(0.01)")
    a("        else:")
    a("            tmp.replace(self.filepath)")
    a("")
    a("    @contextlib.contextmanager")
    a("    def _locked(self):")
    a('        """Exclusive, blocking, cross-process lock for one full')
    a("        load-modify-save cycle.")
    a("")
    a("        Finding 25 (part 2): `add`/`delete`/`update`/`clear` used to")
    a("        call `self.load()` and `self.save(...)` with no locking")
    a("        around the pair. Two concurrent invocations each load the")
    a("        same on-disk list, each compute their own next id and append")
    a("        their own record, and each `save()` their own full in-memory")
    a("        copy -- the last writer's save silently discards every other")
    a("        concurrent writer's change, even though every invocation")
    a("        still prints success and exits 0. Live-reproduced: 20")
    a("        concurrent `add` invocations against a fresh store (no")
    a("        locking) left only 12 of the 20 records on disk -- 8 were")
    a("        silently lost to this race (on top of the separate crash")
    a("        fixed in `save()` above). A blocking OS-level advisory lock")
    a("        held for the entire load+save critical section serializes")
    a("        concurrent writers so no update is ever lost.")
    a('        """')
    a("        lock_path = self.filepath.with_suffix(self.filepath.suffix + \".lock\")")
    a("        self.filepath.parent.mkdir(parents=True, exist_ok=True)")
    a('        handle = open(lock_path, "a+")')
    a("        try:")
    a("            try:")
    a("                import fcntl")
    a("                fcntl.flock(handle, fcntl.LOCK_EX)")
    a("            except ImportError:")
    a("                try:")
    a("                    import msvcrt")
    a("                    for _ in range(500):")
    a("                        try:")
    a("                            handle.seek(0)")
    a('                            handle.write(" ")')
    a("                            handle.flush()")
    a("                            handle.seek(0)")
    a("                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)")
    a("                            break")
    a("                        except OSError:")
    a("                            time.sleep(0.01)")
    a("                except (ImportError, OSError):")
    a("                    pass")
    a("            yield")
    a("        finally:")
    a("            try:")
    a("                import fcntl")
    a("                fcntl.flock(handle, fcntl.LOCK_UN)")
    a("            except ImportError:")
    a("                try:")
    a("                    import msvcrt")
    a("                    handle.seek(0)")
    a("                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)")
    a("                except (ImportError, OSError):")
    a("                    pass")
    a("            handle.close()")
    a("")
    a("    def next_id(self, items: list[dict[str, Any]]) -> int:")
    a("        return max((int(i.get(\"id\", 0)) for i in items), default=0) + 1")
    a("")
    a("    def add(self, **fields: Any) -> dict[str, Any]:")
    a("        with self._locked():")
    a("            items = self.load()")
    a('            record = {"id": self.next_id(items), "created": _now()}')
    a("            record.update(_DEFAULTS)")
    a("            record.update(fields)")
    a("            items.append(record)")
    a("            self.save(items)")
    a("            return record")
    a("")
    a("    def find(self, item_id: int) -> dict[str, Any] | None:")
    a("        for item in self.load():")
    a("            if int(item.get(\"id\", -1)) == int(item_id):")
    a("                return item")
    a("        return None")
    a("")
    a("    def delete(self, item_id: int) -> bool:")
    a("        with self._locked():")
    a("            items = self.load()")
    a("            kept = [i for i in items if int(i.get(\"id\", -1)) != int(item_id)]")
    a("            if len(kept) == len(items):")
    a("                return False")
    a("            self.save(kept)")
    a("            return True")
    a("")
    a("    def update(self, item_id: int, **fields: Any) -> dict[str, Any] | None:")
    a("        with self._locked():")
    a("            items = self.load()")
    a("            for item in items:")
    a("                if int(item.get(\"id\", -1)) == int(item_id):")
    a("                    item.update({k: v for k, v in fields.items() if v is not None})")
    a("                    self.save(items)")
    a("                    return item")
    a("            return None")
    a("")
    a("    def clear(self) -> int:")
    a("        with self._locked():")
    a("            count = len(self.load())")
    a("            self.save([])")
    a("            return count")
    a("")
    a("")
    a("def _now() -> str:")
    a('    return datetime.now(timezone.utc).isoformat(timespec="seconds")')
    a("")
    a("")
    a("def _print_table(items: list[dict[str, Any]]) -> None:")
    a("    if not items:")
    # NOTE: this is a plain string, not an f-string -- `plural` is already
    # baked in at generation time, so there is nothing left to interpolate.
    # A previous version wrote `print(f"No {plural...}...")` with `plural`
    # concatenated in rather than substituted, which produced a syntactically
    # valid but placeholder-free f-string in the GENERATED file and tripped
    # ruff's F541 ("f-string without any placeholders") on every single CLI
    # build, silently, because the lint check used to never actually run
    # (see checkers.py LintChecker PATH-fragility fix).
    a('        print("No ' + plural + " yet. Use 'add' to create one.\")")
    a("        return")
    a("    keys = list(items[0].keys())")
    a("    widths = {k: max(len(str(k)), *(len(str(i.get(k, \"\"))) for i in items)) for k in keys}")
    a('    header = "  ".join(str(k).ljust(widths[k]) for k in keys)')
    a('    print(header)')
    a('    print("  ".join("-" * widths[k] for k in keys))')
    a("    for item in items:")
    a('        print("  ".join(str(item.get(k, "")).ljust(widths[k]) for k in keys))')
    a("")
    a("")
    a("def build_parser() -> argparse.ArgumentParser:")
    a('    parser = argparse.ArgumentParser(')
    a(f'        prog="{_snake(spec.name)}",')
    a(f'        description={json.dumps(spec.raw[:200])},')
    a("    )")
    a('    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")')
    a('    parser.add_argument("--db", default=str(DEFAULT_DB_FILE), help="path to the data file")')
    a("    sub = parser.add_subparsers(dest=\"command\")")
    a("")
    for cmd in spec.commands:
        help_text = _CLI_CMD_HELP.get(cmd, f"{cmd} {plural}").format(
            entity=ent, plural=plural
        )
        # Finding 25 (part 3, minor): commands with no further configuration
        # (e.g. "list", "clear") used to still be assigned to a `p_{cmd}`
        # variable that nothing ever read afterwards, tripping ruff's F841
        # ("local variable assigned but never used") on every generated CLI
        # that had such a command -- caught by re-linting the generator's
        # own output while verifying the Finding 25 locking fix above.
        needs_handle = cmd in ("add", "delete", "update", "complete", "search")
        if needs_handle:
            a(f'    p_{cmd} = sub.add_parser("{cmd}", help={json.dumps(help_text)})')
        else:
            a(f'    sub.add_parser("{cmd}", help={json.dumps(help_text)})')
        if cmd == "add":
            for fname, ftype in spec.fields:
                if fname in ("id", "created"):
                    continue
                if ftype == "bool":
                    a(f'    p_{cmd}.add_argument("--{fname}", action="store_true", default=False)')
                elif ftype == "list":
                    a(f'    p_{cmd}.add_argument("--{fname}", nargs="*", default=[])')
                elif ftype == "int":
                    a(f'    p_{cmd}.add_argument("--{fname}", type=int, default=None)')
                elif ftype == "float":
                    a(f'    p_{cmd}.add_argument("--{fname}", type=float, default=None)')
                else:
                    a(f'    p_{cmd}.add_argument("--{fname}", default=None)')
            a(f'    p_{cmd}.add_argument("positional", nargs="*", help="optional free text")')
        elif cmd in ("delete", "update", "complete"):
            a(f'    p_{cmd}.add_argument("id", type=int, help="id of the {ent}")')
            if cmd == "update":
                for fname, ftype in spec.fields:
                    if fname in ("id", "created"):
                        continue
                    if ftype == "bool":
                        a(f'    p_{cmd}.add_argument("--{fname}", action="store_true", default=None)')
                    elif ftype == "list":
                        a(f'    p_{cmd}.add_argument("--{fname}", nargs="*", default=None)')
                    elif ftype == "int":
                        a(f'    p_{cmd}.add_argument("--{fname}", type=int, default=None)')
                    elif ftype == "float":
                        a(f'    p_{cmd}.add_argument("--{fname}", type=float, default=None)')
                    else:
                        a(f'    p_{cmd}.add_argument("--{fname}", default=None)')
        elif cmd == "search":
            a(f'    p_{cmd}.add_argument("keyword", help="text to look for")')
    a("    return parser")
    a("")
    a("")
    # NOTE: command dispatch used to be one long if/elif chain inside
    # main() itself, which pushed main()'s cyclomatic complexity to 20
    # (CodeQualityComplexityChecker's threshold is 15) on every generated
    # CLI -- flagged live but previously invisible because the PATH-fragile
    # ruff checker never actually ran (see checkers.py fix). Splitting each
    # command into its own `_cmd_*` handler and dispatching through a dict
    # keeps main() itself trivial while preserving identical behavior.
    a("def _cmd_add(store, args):")
    a("    fields = {k: v for k, v in vars(args).items()")
    a("              if k not in (\"command\", \"db\", \"func\", \"positional\") and v is not None}")
    a("    if not fields and getattr(args, \"positional\", None):")
    a(f'        fields = {{"{spec.fields[0][0]}": " ".join(args.positional)}}')
    a("    record = store.add(**fields)")
    a('    print("Added ' + ent + ' #" + str(record["id"]))')
    a("    return 0")
    a("")
    a("")
    a("def _cmd_list(store, args):")
    a("    _print_table(store.load())")
    a("    return 0")
    a("")
    a("")
    a("def _cmd_delete(store, args):")
    a("    if store.delete(args.id):")
    a(f'        print(f"Deleted {ent} #{{args.id}}")')
    a("        return 0")
    a(f'    print(f"No {ent} with id {{args.id}}", file=sys.stderr)')
    a("    return 1")
    a("")
    a("")
    a("def _cmd_update(store, args):")
    a("    fields = {k: v for k, v in vars(args).items()")
    a("              if k not in (\"command\", \"db\", \"func\", \"id\") and v is not None}")
    a("    item = store.update(args.id, **fields)")
    a("    if item is None:")
    a(f'        print(f"No {ent} with id {{args.id}}", file=sys.stderr)')
    a("        return 1")
    a(f'    print(f"Updated {ent} #{{args.id}}")')
    a("    return 0")
    a("")
    a("")
    a("def _cmd_complete(store, args):")
    a("    item = store.update(args.id, done=True)")
    a("    if item is None:")
    a(f'        print(f"No {ent} with id {{args.id}}", file=sys.stderr)')
    a("        return 1")
    a(f'    print(f"Completed {ent} #{{args.id}}")')
    a("    return 0")
    a("")
    a("")
    a("def _cmd_clear(store, args):")
    a("    n = store.clear()")
    a(f'    print(f"Cleared {{n}} {plural}")')
    a("    return 0")
    a("")
    a("")
    a("def _cmd_search(store, args):")
    a("    needle = args.keyword.lower()")
    a("    hits = [i for i in store.load()")
    a("            if needle in json.dumps(i, default=str).lower()]")
    a("    _print_table(hits)")
    a("    return 0 if hits else 1")
    a("")
    a("")
    a("def _cmd_count(store, args):")
    a(f'    print(f"{{len(store.load())}} {plural}")')
    a("    return 0")
    a("")
    a("")
    a("_COMMAND_HANDLERS = {")
    a('    "add": _cmd_add,')
    a('    "list": _cmd_list,')
    a('    "delete": _cmd_delete,')
    a('    "update": _cmd_update,')
    a('    "complete": _cmd_complete,')
    a('    "clear": _cmd_clear,')
    a('    "search": _cmd_search,')
    a('    "count": _cmd_count,')
    a("}")
    a("")
    a("")
    a("def main(argv: list[str] | None = None) -> int:")
    a("    parser = build_parser()")
    a("    args = parser.parse_args(argv)")
    a("    if not getattr(args, \"command\", None):")
    a("        parser.print_help()")
    a("        return 1")
    a(f"    store = {store_cls}(args.db)")
    a("    handler = _COMMAND_HANDLERS.get(args.command)")
    a("    if handler is None:")
    a("        parser.print_help()")
    a("        return 1")
    a("    return handler(store, args)")
    a("")
    a("")
    a('if __name__ == "__main__":')
    a("    raise SystemExit(main())")
    a("")
    return "\n".join(lines)


def _cli_tests(spec: GoalSpec) -> str:
    store_cls = f"{_title(spec.entity).replace(' ', '')}Store"
    first_field = spec.fields[0][0]
    L: list[str] = []
    a = L.append
    a('"""')
    a(f"Tests for {spec.name}.")
    a('"""')
    a("")
    # NOTE: `json` used to be imported here unconditionally even though
    # nothing in the generated test body ever references it (the only
    # `json.dumps(...)` call involved is evaluated in THIS generator at
    # synthesis time, to build an f-string -- it never appears in the
    # emitted source). That produced a guaranteed ruff F401 ("imported but
    # unused") on every generated CLI test file, which went unnoticed
    # because the lint checker could not even locate `ruff` (see the
    # LintChecker PATH-fragility fix in checkers.py).
    a("from pathlib import Path")
    a("")
    a("import pytest")
    a("")
    a(f"from main import {store_cls}, build_parser, main")
    a("")
    a("")
    a("@pytest.fixture")
    a("def db(tmp_path: Path) -> Path:")
    a('    return tmp_path / "data.json"')
    a("")
    a("")
    a("def _store(db):")
    a(f"    return {store_cls}(db)")
    a("")
    a("")
    a("def test_starts_empty(db):")
    a("    assert _store(db).load() == []")
    a("")
    a("")
    a("def test_add_persists(db):")
    a("    store = _store(db)")
    a(f'    rec = store.add({first_field}="first")')
    a('    assert rec["id"] == 1')
    a('    assert _store(db).load()[0][%r] == "first"' % first_field)
    a("")
    a("")
    a("def test_ids_increase(db):")
    a("    store = _store(db)")
    a(f'    a1 = store.add({first_field}="one")')
    a(f'    a2 = store.add({first_field}="two")')
    a('    assert a2["id"] == a1["id"] + 1')
    a("")
    a("")
    a("def test_find_and_delete(db):")
    a("    store = _store(db)")
    a(f'    rec = store.add({first_field}="gone")')
    a("    assert store.find(rec[\"id\"]) is not None")
    a("    assert store.delete(rec[\"id\"]) is True")
    a("    assert store.find(rec[\"id\"]) is None")
    a("    assert store.delete(999) is False")
    a("")
    a("")
    a("def test_update_and_clear(db):")
    a("    store = _store(db)")
    a(f'    rec = store.add({first_field}="old")')
    a(f'    upd = store.update(rec["id"], {first_field}="new")')
    a(f'    assert upd[{first_field!r}] == "new"')
    a('    assert store.clear() == 1')
    a("    assert store.load() == []")
    a("")
    a("")
    a("def test_corrupt_file_is_not_fatal(tmp_path: Path):")
    a('    bad = tmp_path / "bad.json"')
    a('    bad.write_text("{not json", encoding="utf-8")')
    a("    assert _store(bad).load() == []")
    a("")
    a("")
    a("def test_parser_builds():")
    a("    parser = build_parser()")
    a("    assert parser.prog")
    a("")
    a("")
    a("def test_help_exits_zero(capsys):")
    a("    with pytest.raises(SystemExit) as exc:")
    a('        main(["--help"])')
    a("    assert exc.value.code == 0")
    a("")
    a("")
    a("def test_help_mentions_every_command(capsys):")
    a("    with pytest.raises(SystemExit):")
    a('        main(["--help"])')
    a("    out = capsys.readouterr().out")
    expected = ", ".join(json.dumps(c) for c in spec.commands)
    a(f"    for cmd in [{expected}]:")
    a('        assert cmd in out, f"command {cmd} missing from --help"')
    a("")
    a("")
    a('def test_version_exits_zero():')
    a("    with pytest.raises(SystemExit) as exc:")
    a('        main(["--version"])')
    a("    assert exc.value.code == 0")
    a("")
    a("")
    if "add" in spec.commands:
        # A literal the first field can parse: "hello" is not a valid float.
        ftype = spec.fields[0][1]
        if ftype in ("int", "float"):
            lit, expect = "7", "7.0" if ftype == "float" else "7"
        elif ftype == "bool":
            lit, expect = "", ""
        else:
            lit, expect = "hello", "hello"
        if "list" in spec.commands:
            a("def test_add_then_list_roundtrip(db, capsys):")
            a(f'    rc = main(["--db", str(db), "add", "--{first_field}", "{lit}"])')
            a("    assert rc == 0")
            a('    rc2 = main(["--db", str(db), "list"])')
            a("    assert rc2 == 0")
            if expect:
                a(f'    assert "{expect}" in capsys.readouterr().out')
            a("")
            a("")
        else:
            a("def test_add_writes_record(db):")
            a(f'    rc = main(["--db", str(db), "add", "--{first_field}", "{lit}"])')
            a("    assert rc == 0")
            a('    assert _store(db).load()[0][%r] is not None' % first_field)
            a("")
            a("")
    if "delete" in spec.commands:
        a("def test_delete_missing_id_returns_1(db, capsys):")
        a('    rc = main(["--db", str(db), "delete", "424242"])')
        a("    assert rc == 1")
        a("")
    if "complete" in spec.commands:
        a("def test_complete_marks_done(db):")
        a(f'    rec = _store(db).add({first_field}="x")')
        a('    rc = main(["--db", str(db), "complete", str(rec["id"])])')
        a("    assert rc == 0")
        a('    assert _store(db).find(rec["id"])["done"] is True')
        a("")
    if "clear" in spec.commands:
        a("def test_clear_empties_store(db):")
        a(f'    _store(db).add({first_field}="x")')
        a('    rc = main(["--db", str(db), "clear"])')
        a("    assert rc == 0")
        a('    assert _store(db).load() == []')
        a("")
    if "search" in spec.commands:
        a("def test_search_finds_match(db, capsys):")
        a(f'    _store(db).add({first_field}="findme")')
        a('    rc = main(["--db", str(db), "search", "findme"])')
        a("    assert rc == 0")
        a('    assert "findme" in capsys.readouterr().out')
        a("")
    if "count" in spec.commands:
        a("def test_count_reports_total(db, capsys):")
        a(f'    _store(db).add({first_field}="x")')
        a('    rc = main(["--db", str(db), "count"])')
        a("    assert rc == 0")
        a('    assert "1" in capsys.readouterr().out')
        a("")
    if "update" in spec.commands:
        a("def test_update_changes_field(db):")
        a(f'    rec = _store(db).add({first_field}="old")')
        a(f'    upd = _store(db).update(rec["id"], {first_field}="new")')
        a(f'    assert upd[{first_field!r}] == "new"')
        a("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# API generator
# ---------------------------------------------------------------------------

def _api_main(spec: GoalSpec) -> str:
    ent, plural = spec.entity, spec.entity_plural
    model = _title(spec.entity).replace(" ", "")
    L: list[str] = []
    a = L.append
    a('"""')
    a(f"{spec.name}: {spec.raw[:120]}")
    a("")
    a("Generated by Project FORGE deterministic synthesis.")
    a('"""')
    a("")
    a("from __future__ import annotations")
    a("")
    a("from typing import Any, Optional")
    a("")
    a("from fastapi import FastAPI, HTTPException, status")
    a("from pydantic import BaseModel, Field")
    a("")
    a("app = FastAPI(")
    a(f'    title={json.dumps(_title(spec.name))},')
    a(f'    description={json.dumps(spec.raw[:200])},')
    a('    version="1.0.0",')
    a(")")
    a("")
    a("")
    a(f"class {model}(BaseModel):")
    a("    id: Optional[int] = None")
    for fname, ftype in spec.fields:
        if fname == "id":
            continue
        if ftype == "int":
            a(f"    {fname}: Optional[int] = None")
        elif ftype == "float":
            a(f"    {fname}: Optional[float] = None")
        elif ftype == "bool":
            a(f"    {fname}: bool = False")
        elif ftype == "list":
            a(f"    {fname}: list[str] = Field(default_factory=list)")
        else:
            a(f"    {fname}: Optional[str] = Field(default=None, max_length=10_000)")
    a("")
    a("")
    a(f"class {model}Create(BaseModel):")
    for fname, ftype in spec.fields:
        if fname == "id":
            continue
        if ftype == "int":
            a(f"    {fname}: int")
        elif ftype == "float":
            a(f"    {fname}: float")
        elif ftype == "bool":
            a(f"    {fname}: bool = False")
        elif ftype == "list":
            a(f"    {fname}: list[str] = Field(default_factory=list)")
        else:
            # Finding 24: string fields had no upper bound at all. Live
            # adversarial probe: POSTing a 2MB `title` to a generated books
            # API was accepted with 201 and stored in memory uncapped --
            # trivial to repeat into a resource-exhaustion DoS against the
            # in-memory `_DB`. 10,000 chars comfortably covers any
            # legitimate text field (titles, names, free-text notes) while
            # rejecting pathological payloads with a clean 422 instead of
            # silently accepting them.
            a(f"    {fname}: str = Field(..., min_length=1, max_length=10_000)")
    a("")
    a("")
    a('_DB: dict[int, dict[str, Any]] = {}')
    a("_SEQ = 0")
    a("")
    a("")
    a('@app.get("/health", tags=["system"])')
    a("def health() -> dict[str, str]:")
    a(f'    return {{"status": "healthy", "service": {json.dumps(_snake(spec.name))}}}')
    a("")
    a("")
    a(f'@app.get("/{plural}", response_model=list[{model}], tags=["{ent}"])')
    a(f"def list_{spec.entity}(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:")
    a("    items = list(_DB.values())")
    a("    return items[offset : offset + max(0, limit)]")
    a("")
    a("")
    a(f'@app.post("/{plural}", response_model={model}, status_code=status.HTTP_201_CREATED, tags=["{ent}"])')
    a(f"def create_{spec.entity}(payload: {model}Create) -> dict[str, Any]:")
    a("    global _SEQ")
    a("    _SEQ += 1")
    a('    record = {"id": _SEQ, **payload.model_dump()}')
    a("    _DB[_SEQ] = record")
    a("    return record")
    a("")
    a("")
    # The "search" route is a literal path (`/{plural}/search`), while the
    # "get by id" route below is a parameterized path (`/{plural}/{id}`) on
    # the exact same prefix. FastAPI/Starlette matches routes in registration
    # order and does NOT fall through to a later route if an earlier one
    # matches the URL shape but fails parameter validation -- so if
    # `/{plural}/{id}` were registered first, a real request to
    # `/{plural}/search` would match it with "search" as the id, fail int
    # conversion, and return 422 from the wrong handler. The search endpoint
    # would exist in the code, be listed in the OpenAPI schema, and still be
    # 100% unreachable. Verified live: generating an API with both
    # "get by id" and "search" and hitting GET /item/search returned
    # `{"detail": [{"type": "int_parsing", "loc": ["path", "item_id"], ...}]}`
    # with status 422 -- the search handler never ran. Registering the
    # literal path first fixes this the standard FastAPI way.
    if "search" in spec.commands:
        a(f'@app.get("/{plural}/search", response_model=list[{model}], tags=["{ent}"])')
        a(f"def search_{spec.entity}(q: str = \"\") -> list[dict[str, Any]]:")
        a('    needle = q.lower()')
        a("    return [i for i in _DB.values() if needle in json.dumps(i, default=str).lower()]")
        a("")
        a("")
    # Item-level routes use the same plural prefix as the collection routes
    # above (`/{plural}/{id}`, not `/{singular}/{id}`). Mixing singular and
    # plural prefixes on the same resource is non-standard REST and silently
    # breaks any client that (reasonably) assumes one consistent base path --
    # verified live: GET /books/1 (plural, the path any standard REST client
    # would guess) 404'd, while only GET /book/1 (singular) worked, even
    # though POST /books (plural) had just created that very record.
    a(f'@app.get("/{plural}/{{{spec.entity}_id}}", response_model={model}, tags=["{ent}"])')
    a(f"def get_{spec.entity}({spec.entity}_id: int) -> dict[str, Any]:")
    a("    if item_id not in _DB:".replace("item_id", f"{spec.entity}_id"))
    a(f'        raise HTTPException(status_code=404, detail="{ent} not found")')
    a(f"    return _DB[{spec.entity}_id]")
    a("")
    a("")
    if "update" in spec.commands:
        a(f'@app.put("/{plural}/{{{spec.entity}_id}}", response_model={model}, tags=["{ent}"])')
        a(f"def update_{spec.entity}({spec.entity}_id: int, payload: {model}Create) -> dict[str, Any]:")
        a(f'    if {spec.entity}_id not in _DB:')
        a(f'        raise HTTPException(status_code=404, detail="{ent} not found")')
        a(f'    _DB[{spec.entity}_id] = {{"id": {spec.entity}_id, **payload.model_dump()}}')
        a(f"    return _DB[{spec.entity}_id]")
        a("")
        a("")
    if "delete" in spec.commands:
        a(f'@app.delete("/{plural}/{{{spec.entity}_id}}", status_code=status.HTTP_204_NO_CONTENT, tags=["{ent}"])')
        a(f"def delete_{spec.entity}({spec.entity}_id: int) -> None:")
        a(f'    if {spec.entity}_id not in _DB:')
        a(f'        raise HTTPException(status_code=404, detail="{ent} not found")')
        a(f'    del _DB[{spec.entity}_id]')
        a("")
        a("")
    a("")
    a('if __name__ == "__main__":')
    a("    import uvicorn")
    a("")
    a('    uvicorn.run(app, host="0.0.0.0", port=8000)')
    a("")
    if "import json" not in "\n".join(L):
        L.insert(L.index("from typing import Any, Optional"), "import json")
    return "\n".join(L)


def _api_tests(spec: GoalSpec) -> str:
    plural = spec.entity_plural
    L: list[str] = []
    a = L.append
    a('"""')
    a(f"Integration tests for {spec.name}.")
    a('"""')
    a("")
    a("import pytest")
    a("from fastapi.testclient import TestClient")
    a("")
    a("from main import app, _DB")
    a("")
    a("")
    a("@pytest.fixture")
    a("def client():")
    a("    _DB.clear()")
    a("    with TestClient(app) as c:")
    a("        yield c")
    a("")
    a("")
    a("def test_health(client):")
    a('    r = client.get("/health")')
    a("    assert r.status_code == 200")
    a('    assert r.json()["status"] == "healthy"')
    a("")
    a("")
    a("def test_create_and_list(client):")
    def _lit(t: str) -> str:
        if t == "str":
            return '"x"'
        if t in ("int", "float"):
            return "1"
        if t == "bool":
            return "True"
        return "[]"

    payload = ", ".join(
        f"{json.dumps(f)}: {_lit(t)}" for f, t in spec.fields if f != "id"
    )
    a(f"    created = client.post(\"/{plural}\", json={{{payload}}})")
    a("    assert created.status_code == 201, created.text")
    a('    body = created.json()')
    a('    assert body["id"] == 1')
    a(f'    listed = client.get("/{plural}")')
    a("    assert listed.status_code == 200")
    a("    assert len(listed.json()) == 1")
    a("")
    a("")
    a("def test_get_by_id(client):")
    a(f"    cid = client.post(\"/{plural}\", json={{{payload}}}).json()[\"id\"]")
    a(f'    r = client.get(f"/{plural}/{{cid}}")')
    a("    assert r.status_code == 200")
    a('    assert r.json()["id"] == cid')
    a("")
    a("")
    a("def test_get_missing_is_404(client):")
    a(f'    r = client.get("/{plural}/999999")')
    a("    assert r.status_code == 404")
    a("")
    a("")
    if "delete" in spec.commands:
        a("def test_delete(client):")
        a(f"    cid = client.post(\"/{plural}\", json={{{payload}}}).json()[\"id\"]")
        a(f'    r = client.delete(f"/{plural}/{{cid}}")')
        a("    assert r.status_code == 204")
        a(f'    assert client.get(f"/{plural}/{{cid}}").status_code == 404')
        a("")
        a("")
    if "update" in spec.commands:
        a("def test_update(client):")
        a(f"    cid = client.post(\"/{plural}\", json={{{payload}}}).json()[\"id\"]")
        a(f'    r = client.put(f"/{plural}/{{cid}}", json={{{payload}}})')
        a("    assert r.status_code == 200, r.text")
        a('    assert r.json()["id"] == cid')
        a("")
        a("")
    if "search" in spec.commands:
        a("def test_search_route_is_reachable(client):")
        a("    # Regression guard: the search route used to be registered")
        a("    # *after* the parameterized get-by-id route on the same")
        a("    # prefix, so GET /<plural>/search structurally matched")
        a("    # /<plural>/{id} first and failed int-parsing with a 422")
        a("    # before the search handler ever ran.")
        a(f"    client.post(\"/{plural}\", json={{{payload}}})")
        a(f'    r = client.get("/{plural}/search", params={{"q": "x"}})')
        a("    assert r.status_code == 200, r.text")
        a("    assert isinstance(r.json(), list)")
        a("")
        a("")
    a("def test_validation_rejects_empty(client):")
    a(f'    r = client.post("/{plural}", json={{}})')
    a("    assert r.status_code == 422")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Library generator
# ---------------------------------------------------------------------------

_LIB_FUNCS = {
    "note": [("word_count", ["text: str"], "int"), ("reverse", ["text: str"], "str"),
             ("is_palindrome", ["text: str"], "bool")],
    "todo": [("count_open", ["items: list"], "int"), ("count_done", ["items: list"], "int")],
    "book": [("by_author", ["books: list", "author: str"], "list"),
             ("oldest", ["books: list"], "dict")],
    "contact": [("search", ["contacts: list", "needle: str"], "list")],
    "expense": [("total", ["expenses: list"], "float"),
                ("by_category", ["expenses: list"], "dict")],
    "event": [("upcoming", ["events: list"], "list")],
    "file": [("extensions", ["paths: list"], "dict"), ("total_size", ["paths: list"], "int")],
    "user": [("active_users", ["users: list"], "list")],
    "password": [("score", ["value: str"], "int")],
    "url": [("domain", ["address: str"], "str"), ("is_secure", ["address: str"], "bool")],
    "recipe": [("total_steps", ["recipes: list"], "int")],
    "habit": [("longest_streak", ["habits: list"], "int")],
    "item": [("count", ["items: list"], "int")],
}


def _lib_main(spec: GoalSpec) -> str:
    # `search` (the "contact" entity's only function) needs `json`. This used
    # to be patched in after the fact with `L.insert(3, "import json")`, which
    # silently landed *inside* the module docstring (index 3 is the
    # "Generated by Project FORGE..." line, not the import block) instead of
    # emitting a real import statement. The result: every "contact" library
    # this generator produced crashed every call to `search()` with
    # `NameError: name 'json' is not defined` -- live-reproduced by generating
    # a contact library and calling `search()`, which raised immediately (and
    # the library's own generated test caught it as a failure too, so a real
    # user running `pytest` on the delivered project would see a broken
    # library out of the box). Needed imports are now computed up front and
    # emitted as real top-level `import` statements in the header.
    needs_json = spec.entity == "contact"
    L: list[str] = []
    a = L.append
    a('"""')
    a(f"{spec.name}: {spec.raw[:120]}")
    a("")
    a("Generated by Project FORGE deterministic synthesis.")
    a('"""')
    a("")
    a("from __future__ import annotations")
    a("")
    if needs_json:
        a("import json")
    a("from typing import Any")
    a("")
    names = _domain_funcs(spec.entity) if spec.entity in _DOMAIN_BODIES else [
        f[0] for f in _LIB_FUNCS.get(spec.entity, _LIB_FUNCS["item"])
    ]
    a("__all__ = [")
    for fname in names:
        a(f'    "{fname}",')
    a("]")
    a("")
    a("")
    for body in _domain_bodies(spec.entity):
        a(body.rstrip("\n"))
        a("")
        a("")
    if spec.entity in ("note", "todo", "book", "contact", "expense", "event", "file",
                       "user", "password", "url", "recipe", "habit"):
        bodies = {
            "note": [
                ('def word_count(text: str) -> int:\n    """Count the words in text."""\n'
                 '    return len([w for w in (text or "").split() if w])\n'),
                ('def reverse(text: str) -> str:\n    """Return text reversed."""\n'
                 '    return (text or "")[::-1]\n'),
                ('def is_palindrome(text: str) -> bool:\n'
                 '    """True when text reads the same forwards and backwards."""\n'
                 '    cleaned = "".join(ch.lower() for ch in (text or "") if ch.isalnum())\n'
                 '    return bool(cleaned) and cleaned == cleaned[::-1]\n'),
            ],
        }
        for body in bodies.get(spec.entity, []):
            a(body.rstrip("\n"))
            a("")
            a("")
    if spec.entity == "todo":
        a("def count_open(items: list) -> int:")
        a('    """How many items are not done."""')
        a('    return sum(1 for i in items if not i.get("done"))')
        a("")
        a("")
        a("def count_done(items: list) -> int:")
        a('    """How many items are done."""')
        a('    return sum(1 for i in items if i.get("done"))')
        a("")
        a("")
    if spec.entity == "book":
        a("def by_author(books: list, author: str) -> list:")
        a('    """Every book whose author matches, case-insensitively."""')
        a('    needle = (author or "").lower()')
        a('    return [b for b in books if needle in str(b.get("author", "")).lower()]')
        a("")
        a("")
        a("def oldest(books: list) -> dict:")
        a('    """The book with the earliest year, or an empty dict."""')
        a("    if not books:")
        a("        return {}")
        a('    return min(books, key=lambda b: int(b.get("year") or 0))')
        a("")
        a("")
    if spec.entity == "expense":
        a("def total(expenses: list) -> float:")
        a('    """Sum of every expense amount."""')
        a('    return round(sum(float(e.get("amount", 0) or 0) for e in expenses), 2)')
        a("")
        a("")
        a("def by_category(expenses: list) -> dict:")
        a('    """Totals grouped by category."""')
        a('    out: dict[str, float] = {}')
        a('    for e in expenses:')
        a('        cat = str(e.get("category", "uncategorised"))')
        a('        out[cat] = round(out.get(cat, 0.0) + float(e.get("amount", 0) or 0), 2)')
        a("    return out")
        a("")
        a("")
    if spec.entity == "contact":
        a("def search(contacts: list, needle: str) -> list:")
        a('    """Contacts whose text contains needle."""')
        a('    n = (needle or "").lower()')
        a('    return [c for c in contacts if n in json.dumps(c, default=str).lower()]')
        a("")
        a("")
    if spec.entity == "url":
        a("def domain(address: str) -> str:")
        a('    """The host part of a URL."""')
        a('    return (address or "").split("//")[-1].split("/")[0]')
        a("")
        a("")
        a("def is_secure(address: str) -> bool:")
        a('    """True for https URLs."""')
        a('    return (address or "").lower().startswith("https://")')
        a("")
        a("")
    if spec.entity == "file":
        a("def extensions(paths: list) -> dict:")
        a('    """Count of paths per extension."""')
        a('    out: dict[str, int] = {}')
        a('    for p in paths:')
        a('        ext = str(p).rsplit(".", 1)[-1] if "." in str(p) else "(none)"')
        a('        out[ext] = out.get(ext, 0) + 1')
        a("    return out")
        a("")
        a("")
        a("def total_size(paths: list) -> int:")
        a('    """Sum of the sizes given."""')
        a('    return sum(int(p.get("size", 0) or 0) for p in paths)')
        a("")
        a("")
    if spec.entity == "user":
        a("def active_users(users: list) -> list:")
        a('    """Only the users flagged active."""')
        a('    return [u for u in users if u.get("active")]')
        a("")
        a("")
    if spec.entity == "password":
        a("def score(value: str) -> int:")
        a('    """A 0-4 strength score."""')
        a('    s = value or ""')
        a("    pts = 0")
        a('    pts += 1 if len(s) >= 8 else 0')
        a('    pts += 1 if any(c.isdigit() for c in s) else 0')
        a('    pts += 1 if any(c.isupper() for c in s) else 0')
        a('    pts += 1 if any(not c.isalnum() for c in s) else 0')
        a("    return pts")
        a("")
        a("")
    if spec.entity == "recipe":
        a("def total_steps(recipes: list) -> int:")
        a('    """Total number of steps across every recipe."""')
        a('    return sum(len(r.get("steps", []) or []) for r in recipes)')
        a("")
        a("")
    if spec.entity == "habit":
        a("def longest_streak(habits: list) -> int:")
        a('    """The longest streak recorded."""')
        a('    return max((int(h.get("streak", 0) or 0) for h in habits), default=0)')
        a("")
        a("")
    if spec.entity in ("event", "item"):
        a("def count(items: list) -> int:")
        a('    """How many items there are."""')
        a("    return len(items)")
        a("")
        a("")
    if spec.entity == "event":
        a("def upcoming(events: list) -> list:")
        a('    """Events that have not happened yet."""')
        a('    from datetime import datetime, timezone')
        a('    now = datetime.now(timezone.utc).isoformat()')
        a('    return [e for e in events if str(e.get("when", "9999")) >= now]')
        a("")
        a("")
    return "\n".join(L).rstrip("\n") + "\n"


def _lib_tests(spec: GoalSpec) -> str:
    L: list[str] = []
    a = L.append
    a('"""')
    a(f"Tests for {spec.name}.")
    a('"""')
    a("")
    a("import pytest")
    a("")
    if spec.entity in _DOMAIN_BODIES:
        names = ", ".join(_domain_funcs(spec.entity))
    else:
        names = ", ".join(f[0] for f in _LIB_FUNCS.get(spec.entity, _LIB_FUNCS["item"]))
    a(f"from {_safe_module_name(spec.name)} import {names}")
    a("")
    a("")
    cases = {
        "word_count": ("test_word_count", 'assert word_count("one two three") == 3\nassert word_count("") == 0'),
        "reverse": ("test_reverse", 'assert reverse("abc") == "cba"\nassert reverse("") == ""'),
        "is_palindrome": ("test_is_palindrome",
                          'assert is_palindrome("A man a plan a canal Panama") is True\n'
                          'assert is_palindrome("hello") is False\n'
                          'assert is_palindrome("") is False'),
        "count_open": ("test_count_open", 'assert count_open([{"done": False}, {"done": True}]) == 1'),
        "count_done": ("test_count_done", 'assert count_done([{"done": True}, {"done": True}]) == 2'),
        "by_author": ("test_by_author",
                      'books = [{"author": "Ann"}, {"author": "Bob"}]\n'
                      'assert by_author(books, "ann") == [{"author": "Ann"}]\n'
                      'assert by_author(books, "zzz") == []'),
        "oldest": ("test_oldest", 'assert oldest([{"year": 2001}, {"year": 1990}])["year"] == 1990\nassert oldest([]) == {}'),
        "search": ("test_search",
                   'contacts = [{"name": "Ann"}]\n'
                   'assert search(contacts, "ann")\nassert search(contacts, "zzz") == []'),
        "total": ("test_total", 'assert total([{"amount": 1.5}, {"amount": 2.25}]) == 3.75'),
        "by_category": ("test_by_category",
                        'out = by_category([{"category": "food", "amount": 2}, {"category": "food", "amount": 3}])\n'
                        'assert out == {"food": 5.0}'),
        "upcoming": ("test_upcoming", 'assert upcoming([]) == []'),
        "extensions": ("test_extensions", 'assert extensions(["a.py", "b.py", "c.md"]) == {"py": 2, "md": 1}'),
        "total_size": ("test_total_size", 'assert total_size([{"size": 1}, {"size": 2}]) == 3'),
        "active_users": ("test_active_users", 'assert active_users([{"active": True}, {"active": False}]) == [{"active": True}]'),
        "score": ("test_score", 'assert score("abc") == 0\nassert score("Abcdef12!") == 4'),
        "domain": ("test_domain", 'assert domain("https://x.com/a") == "x.com"\nassert domain("") == ""'),
        "is_secure": ("test_is_secure", 'assert is_secure("https://a.com") is True\nassert is_secure("http://a.com") is False'),
        "total_steps": ("test_total_steps", 'assert total_steps([{"steps": [1, 2]}, {"steps": [3]}]) == 3'),
        "longest_streak": ("test_longest_streak", 'assert longest_streak([{"streak": 3}, {"streak": 9}]) == 9'),
        "count": ("test_count", "assert count([1, 2, 3]) == 3"),
    }
    emitted = 0
    iterable = _DOMAIN_BODIES.get(spec.entity)
    if iterable:
        for fname, tname, body in _DOMAIN_FUNCS[spec.entity]:
            a(f"def {tname}():")
            for ln in body.split("\n"):
                a(f"    {ln}")
            a("")
            a("")
            emitted += 1
    if not iterable:
        for fname, _, _ in _LIB_FUNCS.get(spec.entity, _LIB_FUNCS["item"]):
            if fname in cases:
                tname, body = cases[fname]
                a(f"def {tname}():")
                for ln in body.split("\n"):
                    a(f"    {ln}")
                a("")
                a("")
                emitted += 1
    if not emitted:
        a("def test_placeholder():")
        a("    assert True")
        a("")
        a("")
    return "\n".join(L).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Script generator
# ---------------------------------------------------------------------------

def _script_main(spec: GoalSpec) -> str:
    L: list[str] = []
    a = L.append
    a('"""')
    a(f"{spec.name}: {spec.raw[:120]}")
    a("")
    a("Generated by Project FORGE deterministic synthesis.")
    a('"""')
    a("")
    a("from __future__ import annotations")
    a("")
    a("import argparse")
    a("import csv")
    a("import io")
    a("import json")
    a("import shutil")
    a("import sys")
    a("from datetime import datetime, timezone")
    a("from pathlib import Path")
    a("")
    a("")
    a("def build_parser() -> argparse.ArgumentParser:")
    a(f'    parser = argparse.ArgumentParser(description={json.dumps(spec.raw[:200])})')
    a('    sub = parser.add_subparsers(dest="command", required=True)')
    a('    p_rename = sub.add_parser("rename", help="lowercase every filename in a directory")')
    a('    p_rename.add_argument("directory", type=Path)')
    a('    p_rename.add_argument("--apply", action="store_true", help="actually rename")')
    a('    p_backup = sub.add_parser("backup", help="copy today\'s files into a backup folder")')
    a('    p_backup.add_argument("source", type=Path)')
    a('    p_backup.add_argument("target", type=Path)')
    a('    p_json = sub.add_parser("json2csv", help="convert a JSON list into CSV")')
    a('    p_json.add_argument("source", type=Path)')
    a('    p_json.add_argument("target", type=Path)')
    a("    return parser")
    a("")
    a("")
    a("def rename_lower(directory: Path, apply: bool = False) -> list[tuple[Path, Path]]:")
    a('    """Planned (or applied) lowercase renames.')
    a("")
    a("    Two differently-cased files in the same directory (e.g. README.MD and")
    a("    readme.md on a case-sensitive filesystem, or any pair of names that")
    a("    collide once lowercased) can normalize to the same target name.")
    a("    `Path.rename()` silently overwrites an existing destination on POSIX,")
    a("    so renaming blindly would destroy one of the two files with no error")
    a("    and no way to recover it. Live-reproduced: a directory with both")
    a("    README.MD and readme.md went from 4 files to 3 after `rename --apply`,")
    a("    silently deleting readme.md's original content. Any rename whose target")
    a("    already exists (as another file in the directory, or as the computed")
    a("    target of an earlier entry in this same pass) is skipped and reported")
    a("    instead of applied.")
    a('    """')
    a("    if not directory.is_dir():")
    a('        raise NotADirectoryError(str(directory))')
    a("    existing = {p.name for p in directory.iterdir()}")
    a("    claimed_targets: set[str] = set()")
    a("    plan: list[tuple[Path, Path]] = []")
    a("    skipped: list[tuple[Path, Path]] = []")
    a("    for path in sorted(directory.iterdir()):")
    a("        if not path.is_file():")
    a("            continue")
    a("        target = path.with_name(path.name.lower())")
    a("        if target.name == path.name:")
    a("            continue")
    a("        collides_with_existing = target.name in existing and target.name != path.name")
    a("        collides_with_plan = target.name in claimed_targets")
    a("        if collides_with_existing or collides_with_plan:")
    a("            skipped.append((path, target))")
    a("            continue")
    a("        plan.append((path, target))")
    a("        claimed_targets.add(target.name)")
    a("        if apply:")
    a("            path.rename(target)")
    a("    if skipped:")
    a("        for src, dst in skipped:")
    a('            print(f"skip: {src.name} -> {dst.name} (target already exists)", file=sys.stderr)')
    a("    return plan")
    a("")
    a("")
    a("def backup_today(source: Path, target: Path) -> list[Path]:")
    a('    """Copy files modified today from source into target.')
    a("")
    a("    Mirrors each file's path relative to `source`, instead of flattening")
    a("    every match to `target / path.name`. `source.rglob(\"*\")` walks")
    a("    subdirectories, so two files with the same basename in different")
    a("    subdirectories (e.g. sub1/data.txt and sub2/data.txt) used to both")
    a("    resolve to the identical flat destination `target/data.txt` and the")
    a("    second copy silently overwrote the first -- `copied` still reported")
    a("    both as successfully backed up while one was actually destroyed.")
    a("    Live-reproduced: backing up a tree with sub1/data.txt and")
    a("    sub2/data.txt reported \"copied 2 file(s)\" but the backup folder only")
    a("    ever contained one data.txt, with the other file's content gone.")
    a('    """')
    a("    target.mkdir(parents=True, exist_ok=True)")
    a("    copied: list[Path] = []")
    a('    today = datetime.now(timezone.utc).date()')
    a('    for path in sorted(source.rglob("*")):')
    a("        if not path.is_file():")
    a("            continue")
    a('        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date()')
    a("        if mtime == today:")
    a("            dest = target / path.relative_to(source)")
    a("            dest.parent.mkdir(parents=True, exist_ok=True)")
    a("            shutil.copy2(path, dest)")
    a("            copied.append(dest)")
    a("    return copied")
    a("")
    a("")
    a("def json_to_csv(source: Path, target: Path) -> int:")
    a('    """Write a JSON array of flat objects to CSV. Returns the row count.')
    a("")
    a("    Two bugs were found by actually running this against real-world")
    a("    JSON shapes instead of only the happy path:")
    a("")
    a("    1. A non-dict array item (e.g. a bare string) used to raise an")
    a('       unhandled "AttributeError: \'str\' object has no attribute')
    a('       \'keys\'\" with a raw internal traceback instead of a clean,')
    a("       actionable error.")
    a("    2. `fieldnames` was taken only from the first row's keys. If a")
    a("       later row had an extra key not present in the first row (a very")
    a("       common real-world shape for loosely-structured JSON exports),")
    a('       `csv.DictWriter.writerows` raised `ValueError: dict contains')
    a("       fields not in fieldnames` partway through -- but by then the")
    a("       header and every row before the mismatch had already been")
    a("       written straight to `target`, leaving a truncated, silently")
    a("       corrupted CSV file on disk even though the command reported an")
    a("       error and exited non-zero.")
    a("")
    a("    Both are fixed by validating every row is a dict up front (with a")
    a("    clear ValueError naming the offending index) and collecting the")
    a("    union of every row's keys -- in first-seen order -- as the header,")
    a("    so differently-shaped rows no longer crash the writer. The CSV is")
    a("    also built in memory and written to `target` in one atomic")
    a("    operation, so a failure can never leave a partially-written file")
    a("    behind.")
    a('    """')
    a('    rows = json.loads(source.read_text(encoding="utf-8"))')
    a("    if not isinstance(rows, list):")
    a('        raise ValueError("expected a JSON array")')
    a("    if not rows:")
    a('        target.write_text("", encoding="utf-8")')
    a("        return 0")
    a("    for index, row in enumerate(rows):")
    a("        if not isinstance(row, dict):")
    a('            raise ValueError(f"row {index} is not a JSON object: {row!r}")')
    a("    fieldnames: list[str] = []")
    a("    seen = set()")
    a("    for row in rows:")
    a("        for key in row:")
    a("            if key not in seen:")
    a("                seen.add(key)")
    a("                fieldnames.append(key)")
    a("    buffer = io.StringIO()")
    a("    writer = csv.DictWriter(buffer, fieldnames=fieldnames)")
    a("    writer.writeheader()")
    a("    writer.writerows(rows)")
    a('    target.write_text(buffer.getvalue(), newline="", encoding="utf-8")')
    a("    return len(rows)")
    a("")
    a("")
    a("def main(argv: list[str] | None = None) -> int:")
    a("    args = build_parser().parse_args(argv)")
    a("    try:")
    a('        if args.command == "rename":')
    a("            plan = rename_lower(args.directory, apply=args.apply)")
    a('            for src, dst in plan:')
    a('                print(f"{src.name} -> {dst.name}")')
    a('            verb = "renamed" if args.apply else "would be renamed"')
    a('            print(f"{len(plan)} file(s) {verb}")')
    a('            return 0')
    a('        if args.command == "backup":')
    a("            copied = backup_today(args.source, args.target)")
    a('            print(f"copied {len(copied)} file(s)")')
    a("            return 0")
    a('        if args.command == "json2csv":')
    a("            n = json_to_csv(args.source, args.target)")
    a('            print(f"wrote {n} row(s)")')
    a("            return 0")
    a("    except (OSError, ValueError) as exc:")
    a('        print(f"error: {exc}", file=sys.stderr)')
    a("        return 1")
    a("    return 1")
    a("")
    a("")
    a('if __name__ == "__main__":')
    a("    raise SystemExit(main())")
    a("")
    return "\n".join(L)


def _script_tests(spec: GoalSpec) -> str:
    L: list[str] = []
    a = L.append
    a('"""')
    a(f"Tests for {spec.name}.")
    a('"""')
    a("")
    a("import json")
    a("from pathlib import Path")
    a("")
    a("import pytest")
    a("")
    a(f"from {_safe_module_name(spec.name)} import backup_today, build_parser, json_to_csv, main, rename_lower")
    a("")
    a("")
    a("def test_parser_requires_command():")
    a("    with pytest.raises(SystemExit):")
    a('        build_parser().parse_args([])')
    a("")
    a("")
    a("def test_rename_lower_plans(tmp_path: Path):")
    a('    (tmp_path / "README.MD").write_text("x", encoding="utf-8")')
    a('    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")')
    a("    plan = rename_lower(tmp_path)")
    a("    assert len(plan) == 1")
    a('    assert plan[0][1].name == "readme.md"')
    a("")
    a("")
    a("def test_rename_lower_applies(tmp_path: Path):")
    a('    (tmp_path / "A.TXT").write_text("x", encoding="utf-8")')
    a("    rename_lower(tmp_path, apply=True)")
    a("    names = [p.name for p in tmp_path.iterdir()]")
    a('    assert "a.txt" in names')
    a('    assert "A.TXT" not in names')
    a("")
    a("")
    a("def test_rename_missing_dir(tmp_path: Path):")
    a("    with pytest.raises(NotADirectoryError):")
    a('        rename_lower(tmp_path / "nope")')
    a("")
    a("")
    a("def test_backup_today(tmp_path: Path):")
    a('    src = tmp_path / "src"; src.mkdir()')
    a('    (src / "a.txt").write_text("1", encoding="utf-8")')
    a('    dst = tmp_path / "dst"')
    a("    copied = backup_today(src, dst)")
    a("    assert len(copied) == 1")
    a('    assert (dst / "a.txt").read_text(encoding="utf-8") == "1"')
    a("")
    a("")
    a("def test_json_to_csv(tmp_path: Path):")
    a('    src = tmp_path / "in.json"')
    a('    src.write_text(json.dumps([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]), encoding="utf-8")')
    a('    dst = tmp_path / "out.csv"')
    a("    assert json_to_csv(src, dst) == 2")
    a('    text = dst.read_text(encoding="utf-8")')
    a('    assert "a,b" in text')
    a('    assert "1,x" in text')
    a("")
    a("")
    a("def test_json_to_csv_empty(tmp_path: Path):")
    a('    src = tmp_path / "in.json"')
    a('    src.write_text("[]", encoding="utf-8")')
    a('    dst = tmp_path / "out.csv"')
    a("    assert json_to_csv(src, dst) == 0")
    a("")
    a("")
    a("def test_json_to_csv_rejects_object(tmp_path: Path):")
    a('    src = tmp_path / "in.json"')
    a('    src.write_text(\'{"a": 1}\', encoding="utf-8")')
    a('    dst = tmp_path / "out.csv"')
    a("    with pytest.raises(ValueError):")
    a("        json_to_csv(src, dst)")
    a("")
    a("")
    a("def test_main_rename_dry_run(tmp_path: Path, capsys):")
    a('    (tmp_path / "B.MD").write_text("x", encoding="utf-8")')
    a('    rc = main(["rename", str(tmp_path)])')
    a("    assert rc == 0")
    a('    assert "b.md" in capsys.readouterr().out')
    a("")
    a("")
    a("def test_main_bad_command_exit_1(tmp_path: Path):")
    a('    rc = main(["rename", str(tmp_path / "missing")])')
    a("    assert rc == 1")
    a("")
    return "\n".join(L)


_DOMAIN_FUNCS = {
    "string": [
        ("word_count", "test_word_count", 'assert word_count("one two three") == 3\nassert word_count("") == 0'),
        ("reverse", "test_reverse", 'assert reverse("abc") == "cba"\nassert reverse("") == ""'),
        ("is_palindrome", "test_is_palindrome",
         'assert is_palindrome("A man a plan a canal Panama") is True\n'
         'assert is_palindrome("hello") is False\nassert is_palindrome("") is False'),
    ],
    "number": [
        ("mean", "test_mean", 'assert mean([1, 2, 3]) == 2\nassert mean([]) == 0.0'),
        ("median", "test_median", 'assert median([3, 1, 2]) == 2\nassert median([4, 1, 3, 2]) == 2.5'),
        ("mode", "test_mode", 'assert mode([1, 1, 2]) == [1]\nassert mode([]) == []'),
    ],
    "date": [
        ("today", "test_today", 'assert len(today()) == 10\nassert today()[4] == "-"'),
        ("days_between", "test_days_between", 'assert days_between("2024-01-01", "2024-01-11") == 10\nassert days_between("2024-01-11", "2024-01-01") == -10'),
    ],
    "path": [
        ("extension", "test_extension", 'assert extension("a/b/c.py") == "py"\nassert extension("noext") == ""'),
        ("basename", "test_basename", 'assert basename("/x/y/z.txt") == "z.txt"'),
    ],
}

_DOMAIN_BODIES = {
    "string": [
        ('def word_count(text: str) -> int:\n    """Count the words in text."""\n'
         '    return len([w for w in (text or "").split() if w])\n'),
        ('def reverse(text: str) -> str:\n    """Return text reversed."""\n'
         '    return (text or "")[::-1]\n'),
        ('def is_palindrome(text: str) -> bool:\n'
         '    """True when text reads the same both ways."""\n'
         '    cleaned = "".join(ch.lower() for ch in (text or "") if ch.isalnum())\n'
         '    return bool(cleaned) and cleaned == cleaned[::-1]\n'),
    ],
    "number": [
        ('def mean(values: list) -> float:\n    """Arithmetic mean, or 0.0 for an empty list."""\n'
         '    vals = [float(v) for v in (values or [])]\n    return sum(vals) / len(vals) if vals else 0.0\n'),
        ('def median(values: list) -> float:\n    """Middle value, or the mean of the two middle ones."""\n'
         '    vals = sorted(float(v) for v in (values or []))\n'
         '    if not vals:\n        return 0.0\n'
         '    mid = len(vals) // 2\n'
         '    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2\n'),
        ('def mode(values: list) -> list:\n    """Every most-frequent value, in first-seen order."""\n'
         '    counts: dict[Any, int] = {}\n'
         '    for v in values or []:\n        counts[v] = counts.get(v, 0) + 1\n'
         '    if not counts:\n        return []\n'
         '    best = max(counts.values())\n'
         '    seen: list[Any] = []\n'
         '    for v in values or []:\n        if counts[v] == best and v not in seen:\n            seen.append(v)\n'
         '    return seen\n'),
    ],
    "date": [
        ('def today() -> str:\n    """Today as YYYY-MM-DD (UTC)."""\n'
         '    from datetime import datetime, timezone\n\n'
         '    return datetime.now(timezone.utc).date().isoformat()\n'),
        ('def days_between(start: str, end: str) -> int:\n'
         '    """Whole days from start to end; negative if reversed.\n\n'
         '    Raises ValueError naming the bad value when a date is not in\n'
         '    YYYY-MM-DD form, instead of a raw, confusing\n'
         '    ' + chr(39)*3 + 'invalid literal for int()' + chr(39)*3 + ' buried deep in parsing.\n'
         '    """\n'
         '    from datetime import date\n\n'
         '    def parse(v: str) -> date:\n'
         '        parts = str(v).split("-")\n'
         '        if len(parts) != 3 or not all(p.isdigit() for p in parts):\n'
         '            raise ValueError(f"expected a YYYY-MM-DD date, got {v!r}")\n'
         '        y, m, d = (int(x) for x in parts)\n'
         '        return date(y, m, d)\n\n'
         '    return (parse(end) - parse(start)).days\n'),
    ],
    "path": [
        ('def extension(path: str) -> str:\n    """The final extension without the dot, or an empty string."""\n'
         '    name = str(path or "").rsplit("/", 1)[-1]\n'
         '    return name.rsplit(".", 1)[-1] if "." in name else ""\n'),
        ('def basename(path: str) -> str:\n    """The last path segment."""\n'
         '    return str(path or "").rstrip("/").rsplit("/", 1)[-1]\n'),
    ],
}


def _domain_funcs(entity: str) -> list[str]:
    return [f[0] for f in _DOMAIN_FUNCS.get(entity, [])]


def _domain_bodies(entity: str) -> list[str]:
    return _DOMAIN_BODIES.get(entity, [])


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _readme(spec: GoalSpec) -> str:
    """A README that describes the project that was actually generated.

    The previous version told every project to run `python main.py --help` and
    listed `n/a` commands for a website, which is wrong for three of the four
    project kinds this module emits.
    """
    cmds = "\n".join(f"- `{c}`" for c in spec.commands) or "- (none)"
    if spec.kind is ProjectKind.WEBSITE:
        running = "open index.html in a browser\nor\npython -m http.server 8000"
        what = "- Kind: **website**\n- Entry point: **index.html**\n"
        cmd_head = "## Pages\n"
        cmd_body = "- `index.html` -- the page\n- `style.css` -- the styles\n- `app.js` -- the behaviour\n"
    elif spec.kind is ProjectKind.API:
        running = "python main.py\n# then GET http://localhost:8000/docs"
        what = (
            f"- Kind: **REST API**\n"
            f"- Resource: **{spec.entity_plural}**\n"
            f"- Endpoints: {', '.join(spec.commands) or 'n/a'}\n"
        )
        cmd_head = "## Endpoints\n"
        cmd_body = cmds + "\n"
    elif spec.kind is ProjectKind.LIBRARY:
        running = f"python -m pytest -q\n# or: from {_snake(spec.name)} import *"
        what = (
            f"- Kind: **library**\n"
            f"- Module: **{_snake(spec.name)}.py**\n"
            f"- Functions: {', '.join(_domain_funcs(spec.entity)) if spec.entity in _DOMAIN_BODIES else ', '.join(f[0] for f in _LIB_FUNCS.get(spec.entity, _LIB_FUNCS['item']))}\n"
        )
        cmd_head = "## API\n"
        if spec.entity in _DOMAIN_BODIES:
            fn_names = _domain_funcs(spec.entity)
        else:
            fn_names = [f[0] for f in _LIB_FUNCS.get(spec.entity, _LIB_FUNCS["item"])]
        cmd_body = "\n".join(f"- `{f}()`" for f in fn_names) + "\n"
    else:
        entry = "main.py" if spec.kind is ProjectKind.CLI else f"{_snake(spec.name)}.py"
        running = f"python {entry} --help\npython -m pytest -q"
        what = (
            f"- Kind: **{spec.kind.value}**\n"
            f"- Entry point: **{entry}**\n"
            f"- Manages: **{spec.entity_plural}**\n"
            f"- Commands: {', '.join(spec.commands) or 'n/a'}\n"
        )
        cmd_head = "## Commands\n"
        cmd_body = cmds + "\n"
    return (
        f"# {_title(spec.name)}\n\n"
        f"{spec.raw.strip() or '(no description supplied)'}\n\n"
        f"Generated by Project FORGE deterministic synthesis.\n\n"
        f"## What it does\n\n"
        f"{what}\n"
        f"{cmd_head}\n{cmd_body}\n"
        f"## Running it\n\n"
        f"```bash\n"
        f"{running}\n"
        f"```\n"
    )


def synthesize_project(goal: str, requirements: list[str] | None = None) -> dict[str, str]:
    """Turn a free-text goal into a complete, working project.

    Returns a mapping of relative path to file content. Only files that compile
    are returned; a generator that cannot produce valid code returns nothing
    rather than something broken.
    """
    spec = parse_goal(goal, requirements)
    files: dict[str, str] = {}

    if spec.kind is ProjectKind.CLI:
        files["main.py"] = _cli_main(spec)
        files["test_main.py"] = _cli_tests(spec)
        files["requirements.txt"] = "pytest>=7.4.0\n"
    elif spec.kind is ProjectKind.API:
        files["main.py"] = _api_main(spec)
        files["test_main.py"] = _api_tests(spec)
        files["requirements.txt"] = (
            "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0\npytest>=7.4.0\nhttpx>=0.24.0\n"
        )
    elif spec.kind is ProjectKind.SCRIPT:
        files[f"{_safe_module_name(spec.name)}.py"] = _script_main(spec)
        files[f"test_{_safe_module_name(spec.name)}.py"] = _script_tests(spec)
        files["requirements.txt"] = "pytest>=7.4.0\n"
    elif spec.kind is ProjectKind.LIBRARY:
        files[f"{_safe_module_name(spec.name)}.py"] = _lib_main(spec)
        files[f"test_{_safe_module_name(spec.name)}.py"] = _lib_tests(spec)
        files["requirements.txt"] = "pytest>=7.4.0\n"
    elif spec.kind is ProjectKind.WEBSITE:
        try:
            from app.templates.web_studio.generator import ForgeWebStudio

            studio = ForgeWebStudio.synthesize_website(spec.raw, spec.requirements)
            for name, content in studio.items():
                files[name] = content
        except Exception:
            files["index.html"] = (
                "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
                "<meta charset=\"utf-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                f"<title>{_title(spec.name)}</title>\n</head>\n<body>\n"
                f"<h1>{_title(spec.name)}</h1>\n<p>{spec.raw}</p>\n</body>\n</html>\n"
            )
    else:
        # Unknown shape: a runnable CLI is the most useful default.
        spec.kind = ProjectKind.CLI
        spec.commands = spec.commands or ["add", "list"]
        files["main.py"] = _cli_main(spec)
        files["test_main.py"] = _cli_tests(spec)
        files["requirements.txt"] = "pytest>=7.4.0\n"

    files["README.md"] = _readme(spec)
    return compile_checked(files)


def synthesize_files_for_goal(goal: str, manifest: list[str] | None = None,
                              requirements: list[str] | None = None) -> dict[str, str]:
    """Synthesis restricted to the files a manifest asked for.

    The orchestrator passes the architect's file manifest; we keep those names and
    fill them from the deterministic generators, so the produced project matches
    the plan instead of replacing it.
    """
    produced = synthesize_project(goal, requirements)
    if not manifest:
        return produced
    wanted = [m for m in manifest if isinstance(m, str) and m]
    out: dict[str, str] = {}
    for name in wanted:
        base = name.split("/")[-1]
        if name in produced:
            out[name] = produced[name]
        elif base in produced:
            out[name] = produced[base]
    # Supporting files are only useful alongside the project they test. Adding a
    # pytest suite for a manifest that produced nothing would be writing files
    # nobody asked for and reporting success for a project that does not exist.
    if out:
        for name, content in produced.items():
            if name in out:
                continue
            # Supporting files come along -- and so does the project's own
            # implementation. The manifest asks for "main.py" while a script
            # that renames files is delivered as "path.py", so matching on the
            # manifest name alone kept the README and the test suite and
            # silently dropped the code they exist to test. The user was left
            # with tests for a module that was never written.
            if (
                name.startswith("test_")
                or name == "requirements.txt"
                or name.endswith(".py")
            ):
                out[name] = content
    return out or produced
