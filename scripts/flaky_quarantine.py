"""Flaky-test quarantine loader/validator (TASK-REL-121).

The human-readable list is docs/collaboration/FLAKY_TEST_QUARANTINE.md;
the machine-readable list is docs/collaboration/FLAKY_TEST_QUARANTINE.yaml
(TASK-REL-108). This module is the single reader of the YAML list:

- tests/conftest.py uses it to skip quarantined nodeids in PR CI
  (GITHUB_EVENT_NAME=pull_request, or FRIDAY_FLAKY_QUARANTINE_MODE=pr);
- the nightly workflow (.github/workflows/flaky-quarantine-nightly.yml)
  runs the same tests unskipped (mode=nightly) so a recurrence is caught
  on the nightly gate instead of blocking PRs;
- expiry is enforced, never silently extended: an expired quarantined
  entry fails validation (and CI collection) until the entry owner files
  the fix-or-remove decision.

PyYAML is used when importable; a small fallback parser covers the
controlled subset of YAML this file uses, so collection never depends on
an optional dependency being installed.
"""

import datetime
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LIST_PATH = os.path.join(
    REPO_ROOT, "docs", "collaboration", "FLAKY_TEST_QUARANTINE.yaml"
)

QUARANTINED_STATUSES = ("quarantined", "watch")
REQUIRED_FIELDS = ("test", "nodeids", "owner", "expiry", "status")


def _parse_scalar(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    return raw


def _fallback_parse(text):
    """Parse the controlled YAML subset used by the quarantine list."""
    entries = []
    current = None
    list_key = None
    in_entries = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "entries:":
            in_entries = True
            continue
        if not in_entries:
            continue
        if stripped.startswith("- test:"):
            current = {"test": _parse_scalar(stripped[len("- test:"):])}
            entries.append(current)
            list_key = None
            continue
        if current is None:
            continue
        if stripped.startswith("- ") and list_key:
            current.setdefault(list_key, []).append(_parse_scalar(stripped[2:]))
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                current[key] = _parse_scalar(value)
                list_key = None
            else:
                current[key] = []
                list_key = key
    return {"entries": entries}


def load_entries(path=None, force_fallback=False):
    """Return the quarantine entries (list of dicts) from the YAML list."""
    path = path or DEFAULT_LIST_PATH
    with open(path, encoding="utf-8") as f:
        text = f.read()
    data = None
    if not force_fallback:
        try:
            import yaml  # noqa: PLC0415 - optional dependency

            data = yaml.safe_load(text)
        except ImportError:
            data = None
    if data is None:
        data = _fallback_parse(text)
    entries = data.get("entries") or []
    for entry in entries:
        nodeids = entry.get("nodeids") or []
        if isinstance(nodeids, str):
            nodeids = [nodeids]
        entry["nodeids"] = [str(n) for n in nodeids]
        # Normalize scalars to str so the PyYAML and fallback parses agree
        # (PyYAML yields ints/dates for unquoted values; the fallback str).
        for field, value in list(entry.items()):
            if field != "nodeids" and value is not None and not isinstance(value, list):
                entry[field] = str(value)
    return entries


def validate_entries(entries, today=None):
    """Return a list of validation errors (empty when the list is sound).

    Every entry must name its test surface, nodeids, owner, expiry and
    status. A quarantined entry past its expiry is an error: expiry
    forces the owner's fix-or-remove decision, it never extends itself.
    """
    today = today or datetime.date.today()
    errors = []
    for i, entry in enumerate(entries):
        label = entry.get("test") or "entry %d" % i
        for field in REQUIRED_FIELDS:
            if not entry.get(field):
                errors.append("%s: missing required field %r" % (label, field))
        expiry_raw = entry.get("expiry")
        if expiry_raw:
            try:
                expiry = datetime.date.fromisoformat(str(expiry_raw))
            except ValueError:
                errors.append("%s: expiry %r is not an ISO date" % (label, expiry_raw))
            else:
                if entry.get("status") in QUARANTINED_STATUSES and today > expiry:
                    errors.append(
                        "%s: quarantine expired %s (owner %s) — fix-or-remove "
                        "decision owed, expiry never extends itself"
                        % (label, expiry_raw, entry.get("owner"))
                    )
    return errors


def quarantined_nodeids(entries):
    """Nodeids of entries currently under quarantine."""
    nodeids = []
    for entry in entries:
        if entry.get("status") in QUARANTINED_STATUSES:
            nodeids.extend(entry.get("nodeids") or [])
    return nodeids


def matching_entry(nodeid, entries):
    """Return the quarantined entry covering *nodeid*, or None."""
    for entry in entries:
        if entry.get("status") not in QUARANTINED_STATUSES:
            continue
        for prefix in entry.get("nodeids") or []:
            if nodeid == prefix or nodeid.startswith(prefix + "::"):
                return entry
    return None


def current_mode(env=None):
    """Quarantine mode: 'pr' skips quarantined tests; anything else runs them."""
    env = os.environ if env is None else env
    override = env.get("FRIDAY_FLAKY_QUARANTINE_MODE", "").strip().lower()
    if override in ("pr", "nightly", "local"):
        return override
    event = env.get("GITHUB_EVENT_NAME", "").strip().lower()
    if event == "pull_request":
        return "pr"
    if event in ("schedule", "workflow_dispatch"):
        return "nightly"
    return "local"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    entries = load_entries()
    if "--nodeids" in argv:
        for nodeid in quarantined_nodeids(entries):
            print(nodeid)
        return 0
    errors = validate_entries(entries)
    if errors:
        for error in errors:
            print("FLAKY QUARANTINE INVALID: %s" % error)
        return 1
    print(
        "FLAKY QUARANTINE VALID: %d entries, %d quarantined nodeids"
        % (len(entries), len(quarantined_nodeids(entries)))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
