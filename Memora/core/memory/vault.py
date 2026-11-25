"""Obsidian-vault second-brain presentation over Memora's store (TASK-MEM-030).

Renders Memora memory records as a plain-Markdown Obsidian vault so the
whole second brain is readable, linkable and greppable without the service
running: one note per memory, filed into the seven vault folders the board
record names (Inbox, Daily Logs, Projects, Areas, Resources, Memories,
Archive), plus one note per agent and a root index note.

Design constraints (deliberate, see the TASK-MEM-030 evidence doc):

* Stdlib only. The vault must render from a dead-simple export of the
  store (a JSON list of record dicts) with no database, no service and no
  network, so the nightly job and any offline read work the same way.
* Reader-agnostic. ``build_vault`` takes record dicts (or objects with
  the same attributes — the fields of ``MemoryRecordRead`` /
  ``storage.relational.models.MemoryRecord``). The caller owns fetching
  and scope enforcement; this module only renders what it is handed.
* Fail-closed on scope. A record whose scope is PRIVATE — or whose scope
  is unknown and cannot be derived from its namespace — is EXCLUDED
  unless the caller passes ``include_private=True``. A personal vault
  must never silently publish an agent-private memory.
* Deterministic and idempotent. Same records in, same files out; a
  re-run overwrites the same notes, so the nightly job can run over the
  same vault directory every night.
* No secrets work here. Content is rendered exactly as stored: secret
  scrubbing is the write pipeline's job
  (``core.memory.capture_service.scrub_secrets`` / the write pipeline's
  scanner) and the vault never re-introduces anything the store does
  not already hold.

Routing (first match wins):
  archived / superseded / deleted lifecycle -> Archive
  lifecycle candidate (unreviewed)          -> Inbox
  memory_type project, or namespace /projects/ -> Projects
  semantic / procedural / tool / system     -> Resources
  preference / decision / relationship      -> Areas
  episodic / experience / working           -> Memories
  anything else                             -> Memories
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

#: The seven vault folders named by the TASK-MEM-030 acceptance line.
VAULT_FOLDERS = (
    "Inbox",
    "Daily Logs",
    "Projects",
    "Areas",
    "Resources",
    "Memories",
    "Archive",
)

#: Canonical agent handles: the ten top-level agent directories of the
#: monorepo (FRIDAY, Memora, Cortex, Forge, Futuris, Inference, IntelX,
#: Sentinel, Stratex, VyralX), lower-cased to the Memora agent-handle form
#: (``AgentCreate.name``, e.g. ``'friday'``, ``'forge'``).
AGENTS = (
    "friday",
    "memora",
    "cortex",
    "forge",
    "futuris",
    "inference",
    "intelx",
    "sentinel",
    "stratex",
    "vyralx",
)

_ARCHIVE_STATES = {"archived", "superseded", "deleted"}
_PROJECT_TYPES = {"project"}
_RESOURCE_TYPES = {"semantic", "procedural", "tool", "system"}
_AREA_TYPES = {"preference", "decision", "relationship"}
_MEMORY_TYPES = {"episodic", "experience", "working"}

_PRIVATE_NAMESPACES = {"agent-private", "project-private"}
_SHARED_NAMESPACES = {"team-shared"}
_UNIVERSAL_NAMESPACES = {"universe-global", "public"}

_FILENAME_BAD = re.compile(r"[^A-Za-z0-9_.\-]+")
_WHITESPACE = re.compile(r"\s+")


def safe_filename(record_id: str) -> str:
    """A filesystem-safe note stem for a record id.

    Anything outside ``[A-Za-z0-9_.-]`` becomes ``_``, so an id can never
    smuggle a path separator (``../``) into the vault tree.
    """
    cleaned = _FILENAME_BAD.sub("_", (record_id or "").strip())
    cleaned = cleaned.strip("._")
    return cleaned or "untitled"


def _yaml_str(value: Any) -> str:
    """Single-quoted YAML scalar (''-escaped); safe for frontmatter."""
    text = "" if value is None else str(value)
    return "'" + text.replace("'", "''") + "'"


def _get(raw: Any, *names: str, default: Any = None) -> Any:
    """Read a field from a dict or an object, first name that exists."""
    for name in names:
        if isinstance(raw, Mapping):
            if name in raw and raw[name] is not None:
                return raw[name]
        else:
            value = getattr(raw, name, None)
            if value is not None:
                return value
    return default


def _iso(value: Any) -> str:
    """Normalise a created_at value to an ISO-8601 string ('' if unknown)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text


def _date_of(value: Any) -> str:
    """``YYYY-MM-DD`` prefix of a created_at value ('' if unparsable)."""
    text = _iso(value)
    if len(text) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}$", text[:10]):
        return text[:10]
    return ""


def _agent_of(raw: Any) -> str:
    """Canonical agent handle for a record.

    agent_id, then owner_agent, then the ``memora://<agent>/...`` namespace
    segment, else ``'universe'`` for unowned (service-wide) records.
    """
    agent = _get(raw, "agent_id", "owner_agent")
    if agent:
        return str(agent).strip().lower()
    namespace = str(_get(raw, "namespace_path") or "")
    match = re.match(r"^memora://([^/]+)/", namespace)
    if match:
        return match.group(1).strip().lower()
    return "universe"


def derive_scope(raw: Any) -> str:
    """Visibility tier for a record: explicit scope, else namespace-derived.

    Unknown scope with no derivable namespace is PRIVATE (fail closed).
    """
    scope = _get(raw, "scope")
    if scope:
        return str(scope).strip().upper()
    namespace = str(_get(raw, "namespace_path") or "")
    namespace_type = str(_get(raw, "namespace_type") or "").strip().lower()
    for candidate in (namespace_type, namespace):
        lowered = candidate.lower()
        if any(token in lowered for token in _PRIVATE_NAMESPACES):
            return "PRIVATE"
        if any(token in lowered for token in _SHARED_NAMESPACES):
            return "SHARED"
        if any(token in lowered for token in _UNIVERSAL_NAMESPACES):
            return "UNIVERSAL"
    return "PRIVATE"


def normalize_record(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalise one store record to the vault's dict shape.

    Returns ``None`` for records without an id — they cannot own a note
    and are counted as skipped by :func:`build_vault`, never guessed at.
    """
    record_id = _get(raw, "id")
    if record_id is None or str(record_id).strip() == "":
        return None
    content = _get(raw, "content_text", "content", default="") or ""
    content = str(content)
    provenance = _get(raw, "provenance") or {}
    if not isinstance(provenance, Mapping):
        provenance = {}
    title_source = _get(raw, "title") or ""
    if not title_source:
        first_line = content.strip().splitlines()[0] if content.strip() else ""
        title_source = first_line.lstrip("#").strip()
    title = _WHITESPACE.sub(" ", str(title_source)).strip()[:80] or (
        "Untitled memory " + str(record_id)[:12]
    )
    return {
        "id": str(record_id),
        "title": title,
        "content": content,
        "memory_type": str(_get(raw, "memory_type", default="episodic") or "episodic").lower(),
        "lifecycle_state": str(
            _get(raw, "lifecycle_state", default="candidate") or "candidate"
        ).lower(),
        "namespace_path": str(_get(raw, "namespace_path") or ""),
        "agent": _agent_of(raw),
        "created_at": _iso(_get(raw, "created_at")),
        "confidence": _get(raw, "confidence", default=""),
        "importance": _get(raw, "importance", default=""),
        "scope": derive_scope(raw),
        "source": str(_get(raw, "source") or ""),
        "session_id": str(provenance.get("session_id") or ""),
        "event_kind": str(provenance.get("event_kind") or ""),
    }


def route(record: Mapping[str, Any]) -> str:
    """Vault folder for a normalised record (first match wins)."""
    if record["lifecycle_state"] in _ARCHIVE_STATES:
        return "Archive"
    if record["lifecycle_state"] == "candidate":
        return "Inbox"
    if record["memory_type"] in _PROJECT_TYPES or "/projects/" in record["namespace_path"]:
        return "Projects"
    if record["memory_type"] in _RESOURCE_TYPES:
        return "Resources"
    if record["memory_type"] in _AREA_TYPES:
        return "Areas"
    return "Memories"


def render_memory_note(record: Mapping[str, Any]) -> str:
    """Full Markdown text of one memory note (frontmatter + body)."""
    tags = sorted({record["agent"], record["memory_type"], record["lifecycle_state"]})
    lines = [
        "---",
        "id: " + _yaml_str(record["id"]),
        "agent: " + _yaml_str(record["agent"]),
        "type: " + _yaml_str(record["memory_type"]),
        "lifecycle: " + _yaml_str(record["lifecycle_state"]),
        "scope: " + _yaml_str(record["scope"]),
        "namespace: " + _yaml_str(record["namespace_path"]),
        "created: " + _yaml_str(record["created_at"]),
        "confidence: " + _yaml_str(record["confidence"]),
        "importance: " + _yaml_str(record["importance"]),
        "source: " + _yaml_str(record["source"]),
    ]
    if record["session_id"]:
        lines.append("session: " + _yaml_str(record["session_id"]))
    if record["event_kind"]:
        lines.append("event_kind: " + _yaml_str(record["event_kind"]))
    lines.append("tags: [" + ", ".join(_yaml_str(tag) for tag in tags) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + record["title"])
    lines.append("")
    lines.append(record["content"])
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Agent: [[" + record["agent"] + "]] · Vault index: [[00 - Second Brain]]")
    lines.append("")
    return "\n".join(lines)


def render_agent_note(agent: str, records: Sequence[Mapping[str, Any]]) -> str:
    """Hub note for one agent: its memories, grouped by vault folder."""
    by_folder: Dict[str, List[Mapping[str, Any]]] = {folder: [] for folder in VAULT_FOLDERS}
    for record in records:
        by_folder[route(record)].append(record)
    lines = [
        "---",
        "agent: " + _yaml_str(agent),
        "kind: 'agent'",
        "---",
        "",
        "# " + agent,
        "",
        "Memora agent hub note. Memories filed under this agent:",
        "",
    ]
    total = 0
    for folder in VAULT_FOLDERS:
        notes = by_folder[folder]
        total += len(notes)
        if not notes:
            continue
        lines.append("## " + folder + " (" + str(len(notes)) + ")")
        lines.append("")
        for record in sorted(notes, key=lambda r: (r["created_at"], r["id"])):
            lines.append(
                "- [[" + safe_filename(record["id"]) + "]] — " + record["title"]
            )
        lines.append("")
    if total == 0:
        lines.append("No memories filed for this agent yet.")
        lines.append("")
    lines.append("Vault index: [[00 - Second Brain]]")
    lines.append("")
    return "\n".join(lines)


def render_index(manifest: Mapping[str, Any]) -> str:
    """Root index note (``00 - Second Brain.md``) for a built vault."""
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    folders = manifest.get("folders", {})
    agents = manifest.get("agents", {})
    lines = [
        "---",
        "kind: 'second-brain-index'",
        "generated: " + _yaml_str(generated),
        "---",
        "",
        "# Second Brain",
        "",
        "Obsidian-vault presentation over Memora's store (TASK-MEM-030). "
        "One note per memory; private-scope memories are excluded unless "
        "the build explicitly opts in.",
        "",
        "## Folders",
        "",
    ]
    for folder in VAULT_FOLDERS:
        count = folders.get(folder, 0)
        lines.append("- [[" + folder + "]] — " + str(count) + " note(s)")
    lines.append("")
    lines.append("## Agents")
    lines.append("")
    for agent in AGENTS:
        count = agents.get(agent, 0)
        lines.append("- [[" + agent + "]] — " + str(count) + " note(s)")
    extra_agents = sorted(set(agents) - set(AGENTS))
    for agent in extra_agents:
        lines.append("- [[" + agent + "]] — " + str(agents[agent]) + " note(s)")
    lines.append("")
    lines.append(
        "Daily work summaries live in [[Daily Logs]] — one note per agent "
        "per night (see `nightly_summary.run_nightly`). One hub note per "
        "agent lives in Areas/Agents/."
    )
    lines.append("")
    return "\n".join(lines)


def build_vault(
    records: Iterable[Any],
    out_dir: Any,
    *,
    include_private: bool = False,
) -> Dict[str, Any]:
    """Render ``records`` into an Obsidian vault tree under ``out_dir``.

    Creates the seven vault folders, one note per (renderable) memory,
    one hub note per agent (all ten canonical agents, even silent ones),
    and the root index note. Returns a manifest::

        {"folders": {folder: note_count, ...},
         "agents": {agent: note_count, ...},
         "written": [relative paths...],
         "skipped_private": n, "skipped_no_id": n}
    """
    root = Path(out_dir)
    for folder in VAULT_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)

    normalised: List[Dict[str, Any]] = []
    skipped_private = 0
    skipped_no_id = 0
    for raw in records:
        record = normalize_record(raw)
        if record is None:
            skipped_no_id += 1
            continue
        if record["scope"] == "PRIVATE" and not include_private:
            skipped_private += 1
            continue
        normalised.append(record)
    normalised.sort(key=lambda r: (r["created_at"], r["id"]))

    folders: Dict[str, int] = {folder: 0 for folder in VAULT_FOLDERS}
    agents: Dict[str, int] = {agent: 0 for agent in AGENTS}
    written: List[str] = []
    for record in normalised:
        folder = route(record)
        filename = safe_filename(record["id"]) + ".md"
        (root / folder / filename).write_text(
            render_memory_note(record), encoding="utf-8"
        )
        folders[folder] += 1
        agents.setdefault(record["agent"], 0)
        agents[record["agent"]] += 1
        written.append(folder + "/" + filename)

    for agent in sorted(set(AGENTS) | {r["agent"] for r in normalised}):
        agent_records = [r for r in normalised if r["agent"] == agent]
        # Hub notes live in Areas/Agents/ so they can never collide with a
        # memory note filed in Areas/ (a record id equal to an agent
        # handle would otherwise overwrite its hub note).
        (root / "Areas" / "Agents").mkdir(parents=True, exist_ok=True)
        (root / "Areas" / "Agents" / agent + ".md").write_text(
            render_agent_note(agent, agent_records), encoding="utf-8"
        )
        written.append("Areas/Agents/" + agent + ".md")

    manifest: Dict[str, Any] = {
        "folders": folders,
        "agents": agents,
        "written": sorted(written),
        "skipped_private": skipped_private,
        "skipped_no_id": skipped_no_id,
    }
    (root / "00 - Second Brain.md").write_text(
        render_index(manifest), encoding="utf-8"
    )
    manifest["written"] = sorted(written + ["00 - Second Brain.md"])
    return manifest
