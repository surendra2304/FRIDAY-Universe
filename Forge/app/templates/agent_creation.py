"""TASK-IG2-FRG-07: the REAL one-prompt agent-creation flow.

Supervisor correction C-1 on the Forge baseline (A12): until this
module, the "one-prompt agent creation" item (corpus DfHw7hsIfvd) was
a TEMPLATE SCAFFOLD ONLY — ``ONE_PROMPT_AGENT`` in
``app/templates/ig_templates.py`` describes the shape (the FRG-004
manifest contract) but nothing in Forge actually turned a prompt into
an agent. This module is the flow itself:

    prompt in -> configured agent project on disk -> real checks run
    -> registered in Forge's created-agent registry with the honest
    outcome recorded.

What "real" means here, concretely:

* The generated ``agent.py`` is a working agent, not a sketch: it
  assembles its system prompt, runs a bounded tool loop against
  FRIDAY's Inference gateway (OpenAI-compatible ``/v1/chat/completions``),
  and raises ``InferenceUnavailable`` — loudly — when the gateway
  cannot serve it. A canned reply would be a defect (the template's
  own note says so).
* The system prompt is the owner's prompt VERBATIM, followed by the
  fleet rules and the prompt fragments of the Forge skills the
  derived specialist carries (``app/agents/skill_registry.py``) — the
  same registry Forge's own build roles are composed from.
* The checks actually execute: the file set must equal the template
  manifest exactly, both Python files must compile, the generated
  code is imported in a subprocess and its tools exercised
  (including the path-traversal guard), and the agent is probed
  against a dead Inference port where the ONLY acceptable outcome is
  the loud failure.
* Registration records every attempt — ``tested`` only when every
  check passed, otherwise ``failed`` with the failing checks named.
  A failed creation is a recorded fact, never a silent drop and
  never a success.
* Generation is deterministic (no timestamps, no randomness inside
  the generated files), so an agent can be rebuilt from its stored
  prompt byte-identically — the template's step 4, made checkable:
  :meth:`CreatedAgentRegistry.rebuild` proves it.
"""
from __future__ import annotations

import hashlib
import json
import keyword
import py_compile
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.agents.skill_registry import DEFAULT_REGISTRY, SkillRegistry
from app.templates.ig_templates import ONE_PROMPT_AGENT

TEMPLATE_NAME = ONE_PROMPT_AGENT.name  # "one-prompt-agent"
MANIFEST_PATHS: Tuple[str, ...] = tuple(ONE_PROMPT_AGENT.manifest_paths())

# ---------------------------------------------------------------------------
# Derivation: prompt -> agent name, specialist, system prompt
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "a", "an", "the", "that", "which", "who", "for", "to", "of", "in",
        "on", "and", "or", "with", "me", "my", "i", "you", "it", "its",
        "is", "are", "be", "an", "agent", "bot", "assistant", "ai",
    }
)


def slugify_agent_name(prompt: str) -> str:
    """Deterministic agent name from the prompt: the first three
    content words, snake_cased. Falls back to ``custom_agent`` when the
    prompt carries no usable words; the result is always a valid
    Python-identifier-safe slug."""
    words = re.findall(r"[a-z0-9]+", prompt.lower())
    content = [w for w in words if w not in _STOPWORDS]
    picked = content[:3] or ["custom"]
    slug = "_".join(picked)
    if slug[0].isdigit():
        slug = "agent_" + slug
    if keyword.iskeyword(slug):
        slug += "_agent"
    return slug


# Ordered (first match wins) keyword rules mapping a prompt onto one of
# Forge's registered specialists. The specialist's role + skill set is
# what configures the generated agent — this is "registered the way
# Forge registers agents": composition from the skill registry, not a
# free-floating prompt.
_SPECIALIST_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("red team", "red-team", "attack", "exploit", "penetration"), "red-teamer"),
    (("security", "vulnerab", "audit", "owasp", "injection", "xss"), "security-reviewer"),
    (("test", "pytest", "coverage", "regression"), "test-engineer"),
    (("review", "lint", "code quality"), "code-reviewer"),
    (("document", "readme", "docs", "write up", "write-up"), "docs-writer"),
    (("deploy", "systemd", "server", "devops", "ci/cd", "pipeline"), "devops-engineer"),
    (("performance", "slow", "memory", "latency", "profile"), "performance-reviewer"),
    (("website", "web page", "frontend", "front-end", "landing page", "html"), "web-developer"),
    (("architect", "design a system", "system design"), "architect"),
)

_DEFAULT_SPECIALIST = "python-developer"


def derive_specialist(prompt: str, registry: SkillRegistry = DEFAULT_REGISTRY) -> str:
    lowered = prompt.lower()
    for needles, specialist in _SPECIALIST_RULES:
        if any(n in lowered for n in needles):
            return specialist
    return _DEFAULT_SPECIALIST


_FLEET_RULES = (
    "Fleet rules (non-negotiable):\n"
    "- Model access is via FRIDAY's Inference gateway only; never call a "
    "provider directly and never ask for a provider API key.\n"
    "- Fail loudly: when a tool or the gateway cannot do what was asked, "
    "say so with the concrete error. Never invent a result, a file "
    "content, or a success you did not observe.\n"
    "- Stay inside your remit as described in the owner's prompt above; "
    "for anything outside it, say what you cannot do and why."
)


def build_system_prompt(
    prompt: str,
    skill_ids: Tuple[str, ...],
    registry: SkillRegistry = DEFAULT_REGISTRY,
) -> str:
    """The generated agent's system prompt: the owner's prompt verbatim,
    then the fleet rules, then the exact skill fragments the derived
    specialist carries in Forge's registry."""
    parts = [prompt.strip(), "", _FLEET_RULES]
    fragments = registry.prompt_fragments(skill_ids)
    if fragments:
        parts += ["", "Skills you carry (from Forge's skill registry):", fragments]
    return "\n".join(parts)


@dataclass(frozen=True)
class AgentConfig:
    name: str
    prompt: str
    specialist: str
    role: str
    skill_ids: Tuple[str, ...]
    system_prompt: str


def derive_config(
    prompt: str, registry: SkillRegistry = DEFAULT_REGISTRY
) -> AgentConfig:
    if not prompt or not prompt.strip():
        raise ValueError("prompt is required: a one-prompt agent needs its one prompt")
    specialist_name = derive_specialist(prompt, registry)
    specialist = registry.specialist(specialist_name)
    system_prompt = build_system_prompt(prompt, specialist.skill_ids, registry)
    return AgentConfig(
        name=slugify_agent_name(prompt),
        prompt=prompt,
        specialist=specialist.name,
        role=specialist.role,
        skill_ids=tuple(specialist.skill_ids),
        system_prompt=system_prompt,
    )


# ---------------------------------------------------------------------------
# File generation (deterministic: same prompt -> same bytes)
# ---------------------------------------------------------------------------

_AGENT_PY = '''"""Agent: __AGENT_NAME__ — generated by Forge's one-prompt creation flow.

Regenerate from the originating prompt (stored verbatim in README.md);
do not hand-edit the system prompt here — change the prompt and rebuild.
Model calls go through FRIDAY's Inference gateway only.
"""
from __future__ import annotations

import json
import os
import sys

import httpx

import tools as _tools

AGENT_NAME = __AGENT_NAME_REPR__
SPECIALIST = __SPECIALIST_REPR__
SYSTEM_PROMPT = __SYSTEM_PROMPT_REPR__
MAX_TOOL_ROUNDS = 8


class InferenceUnavailable(RuntimeError):
    """The Inference gateway could not serve a call. Raised loudly —
    this agent never invents a reply when the gateway is down."""


def _chat_completion(messages):
    base = os.environ.get("INFERENCE_BASE_URL", "").rstrip("/")
    if not base:
        raise InferenceUnavailable("INFERENCE_BASE_URL is not set")
    headers = {}
    key = os.environ.get("INFERENCE_API_KEY", "")
    if key:
        headers["Authorization"] = "Bearer " + key
    payload = {
        "model": os.environ.get("AGENT_MODEL", "default"),
        "messages": messages,
        "tools": _tools.TOOL_SCHEMAS,
    }
    try:
        response = httpx.post(
            base + "/v1/chat/completions", json=payload, headers=headers, timeout=60.0
        )
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        # InvalidURL is NOT an HTTPError subclass in httpx 0.28 — a
        # malformed base URL or proxy env must still fail loudly here,
        # never escape as a raw traceback or be answered around.
        raise InferenceUnavailable(f"Inference gateway call failed: {exc}") from exc
    if response.status_code >= 400:
        raise InferenceUnavailable(
            f"Inference gateway returned HTTP {response.status_code}: {response.text[:200]}"
        )
    try:
        return response.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise InferenceUnavailable(
            f"Inference gateway returned an unusable reply: {exc}"
        ) from exc


def chat(user_text):
    """One user turn: system prompt + tool loop until the model answers
    with content or the round budget runs out (a loud failure, not a
    fabricated answer)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    for _ in range(MAX_TOOL_ROUNDS):
        message = _chat_completion(messages)
        messages.append(message)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            content = message.get("content")
            if not content:
                raise InferenceUnavailable("Inference gateway returned an empty reply")
            return content
        for call in tool_calls:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except ValueError:
                arguments = {}
            result = _tools.run_tool(function.get("name", ""), arguments)
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id", ""), "content": result}
            )
    raise InferenceUnavailable(
        f"tool loop did not settle within {MAX_TOOL_ROUNDS} rounds"
    )


def main(argv):
    text = " ".join(argv[1:]).strip()
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        print("usage: python agent.py <message>", file=sys.stderr)
        return 2
    try:
        print(chat(text))
    except InferenceUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
'''

_TOOLS_PY = '''"""Tools for agent __AGENT_NAME__.

Each tool is a small typed function with a docstring contract. Tools
return real results or raise; run_tool converts a raise into a JSON
error the model can see — never into a fabricated success.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parent


def read_file(path: str) -> str:
    """Read a UTF-8 text file inside this agent's project directory.
    Paths that escape the project directory are refused."""
    target = (_PROJECT_ROOT / path).resolve()
    if target != _PROJECT_ROOT and _PROJECT_ROOT not in target.parents:
        raise ValueError(f"path escapes the project directory: {path}")
    return target.read_text(encoding="utf-8")


def ask_inference(prompt: str) -> str:
    """Ask the Inference gateway one direct question (no tools) and
    return its reply. Raises RuntimeError when the gateway cannot
    serve the call — the failure is the result, never a canned text."""
    base = os.environ.get("INFERENCE_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("INFERENCE_BASE_URL is not set")
    headers = {}
    key = os.environ.get("INFERENCE_API_KEY", "")
    if key:
        headers["Authorization"] = "Bearer " + key
    payload = {
        "model": os.environ.get("AGENT_MODEL", "default"),
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        response = httpx.post(
            base + "/v1/chat/completions", json=payload, headers=headers, timeout=60.0
        )
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        # InvalidURL is NOT an HTTPError subclass in httpx 0.28.
        raise RuntimeError(f"Inference gateway call failed: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(
            f"Inference gateway returned HTTP {response.status_code}: {response.text[:200]}"
        )
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"Inference gateway returned an unusable reply: {exc}"
        ) from exc


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the agent project directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_inference",
            "description": "Ask the Inference gateway one direct question and return its reply.",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
            },
        },
    },
]

_DISPATCH = {"read_file": read_file, "ask_inference": ask_inference}


def run_tool(name: str, arguments: dict) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        result = fn(**arguments)
    except Exception as exc:  # surfaced to the model as data, not hidden
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    return result if isinstance(result, str) else json.dumps(result)
'''

_REQUIREMENTS_TXT = "httpx>=0.27\n"


def render_files(config: AgentConfig) -> Dict[str, str]:
    """The exact ONE_PROMPT_AGENT manifest, generated from the config.
    Deterministic: no timestamps or randomness, so a rebuild from the
    same prompt produces byte-identical files."""
    agent_py = (
        _AGENT_PY.replace("__AGENT_NAME__", config.name)
        .replace("__AGENT_NAME_REPR__", repr(config.name))
        .replace("__SPECIALIST_REPR__", repr(config.specialist))
        .replace("__SYSTEM_PROMPT_REPR__", repr(config.system_prompt))
    )
    tools_py = _TOOLS_PY.replace("__AGENT_NAME__", config.name)
    readme = "\n".join(
        [
            f"# {config.name}",
            "",
            "Generated by Forge's one-prompt agent-creation flow "
            f"(template: {TEMPLATE_NAME}).",
            f"Forge specialist composition: {config.specialist} "
            f"(role: {config.role}), skills: {', '.join(config.skill_ids)}.",
            "",
            "## Originating prompt (verbatim — rebuild from this)",
            "",
            config.prompt.strip(),
            "",
            "## Run",
            "",
            "```",
            "pip install -r requirements.txt",
            "INFERENCE_BASE_URL=<gateway base URL> AGENT_MODEL=<model> \\",
            "  python agent.py \"your message\"",
            "```",
            "",
            "Environment variables (names only — values come from your "
            "environment): INFERENCE_BASE_URL, INFERENCE_API_KEY, AGENT_MODEL.",
            "",
            "## What it can and cannot do",
            "",
            "Can: answer through the Inference gateway with its system "
            "prompt, read files inside its own project directory, and ask "
            "the gateway direct sub-questions (the two tools in tools.py).",
            "Cannot: do anything when the Inference gateway is unreachable "
            "— it fails loudly with InferenceUnavailable instead of "
            "inventing a reply. It has no other tools and no direct "
            "provider access.",
            "",
            "## Rebuild",
            "",
            "Re-running Forge's creation flow with the originating prompt "
            "above regenerates this project byte-identically (generation "
            "is deterministic; the registry stores a SHA-256 per file).",
            "",
        ]
    )
    return {
        "agent.py": agent_py,
        "tools.py": tools_py,
        "requirements.txt": _REQUIREMENTS_TXT,
        "README.md": readme,
    }


# ---------------------------------------------------------------------------
# Checks — every check executes; a check that cannot run is a failure
# with the reason named, never a pass.
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def _check_manifest(project_dir: Path) -> CheckResult:
    found = sorted(
        p.relative_to(project_dir).as_posix()
        for p in project_dir.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    expected = sorted(MANIFEST_PATHS)
    if found == expected:
        return CheckResult("manifest_exact", True, f"file set == template manifest: {expected}")
    return CheckResult(
        "manifest_exact", False, f"expected {expected}, found {found}"
    )


def _check_compile(project_dir: Path) -> CheckResult:
    failures = []
    with tempfile.TemporaryDirectory(prefix="forge-create-check-") as tmp:
        for name in ("agent.py", "tools.py"):
            try:
                py_compile.compile(
                    str(project_dir / name),
                    cfile=str(Path(tmp) / (name + ".pyc")),
                    doraise=True,
                )
            except py_compile.PyCompileError as exc:
                failures.append(f"{name}: {exc.msg.strip()}")
    if failures:
        return CheckResult("py_compile", False, "; ".join(failures))
    return CheckResult("py_compile", True, "agent.py and tools.py compile")


_IMPORT_PROBE = """
import json, sys
import agent, tools

out = {}
out["prompt_verbatim"] = __PROMPT_REPR__ in agent.SYSTEM_PROMPT
out["tool_names"] = sorted(s["function"]["name"] for s in tools.TOOL_SCHEMAS)
readme = tools.read_file("README.md")
out["readme_has_prompt"] = __PROMPT_REPR__ in readme
try:
    tools.read_file("../escape.txt")
    out["traversal_blocked"] = False
except ValueError:
    out["traversal_blocked"] = True
err = json.loads(tools.run_tool("no_such_tool", {}))
out["unknown_tool_is_error"] = "error" in err
print(json.dumps(out))
"""


def _run_probe(project_dir: Path, code: str, extra_env: Dict[str, str]) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env.pop("INFERENCE_BASE_URL", None)
    env.pop("INFERENCE_API_KEY", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _check_import_and_tools(project_dir: Path, config: AgentConfig) -> CheckResult:
    code = _IMPORT_PROBE.replace("__PROMPT_REPR__", repr(config.prompt.strip()))
    try:
        proc = _run_probe(project_dir, code, {})
    except subprocess.TimeoutExpired:
        return CheckResult("import_and_tools", False, "import probe timed out after 60s")
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        return CheckResult(
            "import_and_tools", False,
            f"import probe exited {proc.returncode}: {tail[-1] if tail else 'no stderr'}",
        )
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return CheckResult("import_and_tools", False, f"unparseable probe output: {proc.stdout[:200]!r}")
    problems = []
    if not out.get("prompt_verbatim"):
        problems.append("system prompt does not contain the owner's prompt verbatim")
    if out.get("tool_names") != ["ask_inference", "read_file"]:
        problems.append(f"tool schemas are {out.get('tool_names')}, expected the two starter tools")
    if not out.get("readme_has_prompt"):
        problems.append("README does not carry the originating prompt verbatim")
    if not out.get("traversal_blocked"):
        problems.append("read_file did NOT block a path escaping the project directory")
    if not out.get("unknown_tool_is_error"):
        problems.append("run_tool did not surface an error for an unknown tool")
    if problems:
        return CheckResult("import_and_tools", False, "; ".join(problems))
    return CheckResult(
        "import_and_tools", True,
        "imports clean; prompt verbatim in system prompt + README; both starter tools registered; traversal blocked; unknown tool errors",
    )


def _check_honest_failure(project_dir: Path) -> CheckResult:
    """Point the generated agent at a dead Inference port. The ONLY
    passing outcome is the loud InferenceUnavailable failure — a reply
    of any kind here would mean the agent fabricates answers."""
    code = (
        "import agent\n"
        "try:\n"
        "    agent.chat('hello')\n"
        "except agent.InferenceUnavailable as exc:\n"
        "    print(f'LOUD-FAILURE: {exc}')\n"
    )
    try:
        proc = _run_probe(project_dir, code, {"INFERENCE_BASE_URL": "http://127.0.0.1:9"})
    except subprocess.TimeoutExpired:
        return CheckResult("honest_failure", False, "dead-gateway probe timed out after 60s")
    if "LOUD-FAILURE:" in proc.stdout:
        return CheckResult(
            "honest_failure", True,
            "agent raised InferenceUnavailable against a dead gateway instead of replying",
        )
    return CheckResult(
        "honest_failure", False,
        f"agent did not fail loudly against a dead gateway (rc={proc.returncode}, "
        f"stdout={proc.stdout[:120]!r}, stderr={(proc.stderr or '')[-200:]!r})",
    )


def run_creation_checks(project_dir: Path, config: AgentConfig) -> List[CheckResult]:
    return [
        _check_manifest(project_dir),
        _check_compile(project_dir),
        _check_import_and_tools(project_dir, config),
        _check_honest_failure(project_dir),
    ]


# ---------------------------------------------------------------------------
# Registry — the record of created agents, Forge's way: declarative,
# validated, and honest about failed attempts.
# ---------------------------------------------------------------------------


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class CreatedAgentRegistry:
    """JSON-file-backed registry of agents created by this flow.

    Mirrors the shape of ``app/agents/skill_registry.py``: pure data +
    validation + lookup. Every creation attempt is recorded with its
    per-check outcomes; ``status`` is ``tested`` only when all checks
    passed, else ``failed``. Nothing is registered as tested on
    assertion."""

    path: Path

    def _load(self) -> dict:
        if not self.path.is_file():
            return {"agents": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError:
            return {"agents": {}}
        if not isinstance(data, dict) or not isinstance(data.get("agents"), dict):
            return {"agents": {}}
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def register(self, record: dict) -> dict:
        data = self._load()
        data["agents"][record["name"]] = record
        self._save(data)
        return record

    def get(self, name: str) -> dict:
        record = self._load()["agents"].get(name)
        if record is None:
            raise KeyError(f"unknown created agent: {name}")
        return record

    def all(self) -> List[dict]:
        agents = self._load()["agents"]
        return [agents[name] for name in sorted(agents)]

    def rebuild(self, name: str, target_root: Path) -> Dict[str, bool]:
        """Regenerate the agent from its stored prompt into
        ``target_root`` and compare every file's SHA-256 with the
        registered record. Returns ``{path: identical}`` — the
        template's 'rebuilt identically' promise, as a check."""
        record = self.get(name)
        config = derive_config(record["prompt"])
        files = render_files(config)
        target = Path(target_root) / name
        target.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        return {
            rel: _sha256_text(content) == record["files"].get(rel, "")
            for rel, content in files.items()
        }


# ---------------------------------------------------------------------------
# The flow
# ---------------------------------------------------------------------------


@dataclass
class CreationResult:
    name: str
    project_dir: str
    specialist: str
    role: str
    skill_ids: List[str]
    status: str  # "tested" | "failed"
    checks: List[CheckResult] = field(default_factory=list)
    files: Dict[str, str] = field(default_factory=dict)  # path -> sha256

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "project_dir": self.project_dir,
            "specialist": self.specialist,
            "role": self.role,
            "skill_ids": self.skill_ids,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
            "files": self.files,
        }


def create_agent(
    prompt: str,
    output_root: Path,
    *,
    registry_path: Optional[Path] = None,
    skill_registry: SkillRegistry = DEFAULT_REGISTRY,
) -> CreationResult:
    """One prompt in -> a working, tested agent scaffold out, registered.

    Writes the project under ``output_root/<agent-name>/``, runs the
    real checks, records the attempt (tested or failed) in the
    registry at ``registry_path`` (default:
    ``output_root/created_agents.json``), and returns the outcome.
    Raises ValueError only for an empty prompt — every other failure
    is reported in the result, not raised over."""
    config = derive_config(prompt, skill_registry)
    output_root = Path(output_root)
    project_dir = output_root / config.name
    project_dir.mkdir(parents=True, exist_ok=True)

    files = render_files(config)
    for rel, content in files.items():
        dest = project_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    checks = run_creation_checks(project_dir, config)
    status = "tested" if all(c.passed for c in checks) else "failed"
    file_hashes = {rel: _sha256_text(content) for rel, content in files.items()}

    registry = CreatedAgentRegistry(
        Path(registry_path) if registry_path else output_root / "created_agents.json"
    )
    registry.register(
        {
            "name": config.name,
            "prompt": config.prompt,
            "prompt_sha256": _sha256_text(config.prompt),
            "template": TEMPLATE_NAME,
            "specialist": config.specialist,
            "role": config.role,
            "skill_ids": list(config.skill_ids),
            "files": file_hashes,
            "checks": [c.to_dict() for c in checks],
            "status": status,
            "project_dir": str(project_dir),
        }
    )
    return CreationResult(
        name=config.name,
        project_dir=str(project_dir),
        specialist=config.specialist,
        role=config.role,
        skill_ids=list(config.skill_ids),
        status=status,
        checks=checks,
        files=file_hashes,
    )
