"""
tests/test_gitleaks_config.py — Regression tests for the gitleaks configuration.

TASK-CI-SECRETSCAN-002 (ZAI Agent 1, 2026-11-13): main's Secret Scanning
workflow (gitleaks-action@v3, gitleaks 8.30.1) went RED on head 9544300
because docs/verification/WF014_SOURCE_BOUND_RECEIPTS.md line 30 carries a
labeled ``Source SHA256:``<64-hex> content digest in the same line as the
words "owner credential" — the generic-api-key entropy rule treats any
high-entropy hex near a secret keyword as a leak. The digest is a project
artifact, not a credential.

The fix is the repo-root ``.gitleaks.toml`` (``[extend] useDefault = true``
plus ONE line-targeted allowlist regex). These tests pin that contract so it
cannot silently regress:

- the config must keep ALL default gitleaks rules loaded (``useDefault``),
- the allowlist must be line-targeted (label and digest on the finding's line),
- every labeled SHA-256 digest line in docs/verification/ must be covered,
- unlabeled hex secrets, tokens and keys must NOT match (real leaks stay caught),
- the allowlist must stay narrow (64-hex digests only; MD5/SHA-1/SHA-512 and
  label-less hex are not covered).
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / ".gitleaks.toml"
VERIFICATION_DOCS_DIR = ROOT / "docs" / "verification"

# The exact false-positive line class from the WF-014 receipt (structure kept,
# digest replaced by a synthetic one — the real digest stays in the real doc).
CANONICAL_FALSE_POSITIVE = (
    "Live route:`GET /api/v1/forge/tasks/task1/status` on Forge, with configured "
    "owner credential. Source SHA256:`05a2dc8990bc8327a4e299177c4f689b63190943b4d6c3acba7f61515ba89738`. "
    "Original converter tasks and ZIP unchanged."
)

HEX64 = "05a2dc8990bc8327a4e299177c4f689b63190943b4d6c3acba7f61515ba89738"
HEX64_B = "489dbcf0e3317da250545dff2baa4ebe6ecc0d0c1c3ce82359404879b4ee1d32"
HEX128 = (
    "05a2dc8990bc8327a4e299177c4f689b63190943b4d6c3acba7f61515ba89738"
    "489dbcf0e3317da250545dff2baa4ebe6ecc0d0c1c3ce82359404879b4ee1d32"
)
HEX40 = "a55b63fc448d10ff8bfbc02adf736b0ff242b873"
HEX32 = "0123456789abcdef0123456789abcdef"


def _load_config():
    if not CONFIG_PATH.exists():
        pytest.fail(
            ".gitleaks.toml is missing from the repo root — the Secret Scanning "
            "workflow has no labeled-digest allowlist and the WF-014 false "
            "positive class will redden CI again."
        )
    import tomllib

    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def _allowlist_regex():
    cfg = _load_config()
    allowlist = cfg.get("allowlist")
    assert isinstance(allowlist, dict), "missing [allowlist] table in .gitleaks.toml"
    regexes = allowlist.get("regexes")
    assert isinstance(regexes, list) and regexes, (
        "[allowlist] must define at least one regex"
    )
    # Go RE2 and Python re share the syntax used here (no lookarounds), so
    # compiling in Python is a faithful stand-in for the gitleaks check.
    return re.compile(regexes[0])


# ---------------------------------------------------------------------------
# Config structure
# ---------------------------------------------------------------------------

def test_config_extends_default_rules():
    """useDefault must stay true: all built-in gitleaks rules remain active.

    A bare top-level ``useDefault = true`` (pre-[extend] syntax) is silently
    IGNORED by gitleaks 8.30.1 and disables every rule — the config must use
    the ``[extend]`` table.
    """
    cfg = _load_config()
    extend = cfg.get("extend")
    assert isinstance(extend, dict), (
        "missing [extend] table — top-level useDefault is silently ignored by "
        "gitleaks 8.30.1 and disables all default rules"
    )
    assert extend.get("useDefault") is True


def test_allowlist_is_line_targeted():
    """regexTarget must be "line": the label must appear on the finding's line."""
    cfg = _load_config()
    assert cfg["allowlist"]["regexTarget"] == "line"


def test_no_path_or_commit_allowlist_entries():
    """The allowlist must not blanket-exclude files, paths or commits."""
    cfg = _load_config()
    allowlist = cfg["allowlist"]
    assert not allowlist.get("paths"), "path-based allowlist is too broad here"
    assert not allowlist.get("commits"), "commit-based allowlist is too broad here"


# ---------------------------------------------------------------------------
# The false-positive class is covered
# ---------------------------------------------------------------------------

def test_canonical_false_positive_line_matches():
    """The exact WF-014 line class that reddened main must be allowed."""
    assert _allowlist_regex().search(CANONICAL_FALSE_POSITIVE)


def test_labeled_digest_line_variants_match():
    """Label formats used across project receipt docs are all covered."""
    rx = _allowlist_regex()
    variants = [
        f"Source SHA256:`{HEX64}`.",                      # backticked, no space
        f"zip sha256: {HEX64_B}",                          # lowercase, spaced
        f"SHA-256:{HEX64}",                                # hyphenated label
        f"checksum sha256 = {HEX64}",                      # equals form
        f"SHA256: {HEX64}",                                # colon + space
        f"inventory SHA256: '{HEX64_B}'",                  # single-quoted
        f"verified sha256: \"{HEX64}\"",                   # double-quoted
    ]
    for line in variants:
        assert rx.search(line), f"labeled digest line not covered: {line!r}"


def test_all_labeled_digests_in_verification_docs_are_covered():
    """Every labeled SHA-256 digest line under docs/ must match the allowlist.

    If a future verification receipt introduces a labeled-digest format the
    allowlist regex does not cover, this fails and the regex must be widened
    (label forms only — never bare hex).
    """
    rx = _allowlist_regex()
    labeled = re.compile(r"(?i)sha-?256")
    checked = 0
    for doc in VERIFICATION_DOCS_DIR.glob("*.md"):
        for line in doc.read_text(encoding="utf-8").splitlines():
            if labeled.search(line) and re.search(r"[0-9a-fA-F]{64}", line):
                assert rx.search(line), (
                    f"{doc.name} has a labeled 64-hex digest line the gitleaks "
                    f"allowlist does not cover: {line!r}"
                )
                checked += 1
    assert checked >= 1, "no labeled digest lines found under docs/verification/"


# ---------------------------------------------------------------------------
# Real secrets are NOT suppressed
# ---------------------------------------------------------------------------

def test_unlabeled_hex_secrets_do_not_match():
    """Unlabeled hex values near secret keywords must stay flagged by gitleaks."""
    rx = _allowlist_regex()
    leaks = [
        f'production_api_key = "{HEX64}"',
        f"token: {HEX64_B}",
        f'password = "{HEX64}"',
        f"the configured owner credential is {HEX64_B}",
        f"secret={HEX64}",
    ]
    for line in leaks:
        assert not rx.search(line), f"allowlist would suppress a real secret: {line!r}"


def test_label_without_full_digest_does_not_match():
    """Partial/short digests are not covered — the allowlist stays narrow."""
    rx = _allowlist_regex()
    not_covered = [
        f"sha1: {HEX40}",            # 40-hex SHA-1
        f"md5: {HEX32}",             # 32-hex MD5
        f"sha512: {HEX128}",         # 128-hex SHA-512
        f"sha256: {HEX32}",          # sha256 label, but not a full digest
        "sha256: not-a-digest",
        f"digest {HEX64}",           # hex without any label
    ]
    for line in not_covered:
        assert not rx.search(line), f"allowlist is wider than designed: {line!r}"


def test_real_secret_not_suppressed_by_neighbor_label():
    """A labeled digest and a DIFFERENT bare secret on the same line.

    Documents the accepted residual tradeoff honestly: gitleaks matches the
    keyword-adjacent value; when the matched value is the labeled digest the
    finding is suppressed. A separate bare ``api_key = "<hex>"`` assignment
    without a sha256 label must never match the allowlist.
    """
    rx = _allowlist_regex()
    # The labeled digest finding (allowed — this is the receipt class):
    assert rx.search(f"Source SHA256:`{HEX64}`")
    # A bare key assignment elsewhere on the line (must stay flagged):
    assert not rx.search(f'api_key = "{HEX64_B}"')


# ---------------------------------------------------------------------------
# Optional live integration: runs only when the gitleaks binary is available
# (CI test runners do not install it; local verification uses 8.30.1, the
# version pinned in .github/workflows/secret-scan.yml).
# ---------------------------------------------------------------------------

def _gitleaks_binary():
    return shutil.which("gitleaks")


@pytest.mark.skipif(_gitleaks_binary() is None, reason="gitleaks binary not installed")
def test_live_gitleaks_allows_receipt_and_flags_real_secret(tmp_path):
    """End-to-end proof with the real binary: doc line allowed, secret caught."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "doc.md").write_text(CANONICAL_FALSE_POSITIVE + "\n", encoding="utf-8")
    (repo / "secret.txt").write_text(
        f'production_api_key = "{HEX64}"\n', encoding="utf-8"
    )
    subprocess.run(
        ["git", "init", "-q"], cwd=repo, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "fixtures"], cwd=repo, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    proc = subprocess.run(
        [
            _gitleaks_binary(), "git", "--no-banner", "--redact", "-v",
            "--config", str(CONFIG_PATH), ".",
        ],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    output = proc.stdout + proc.stderr
    # Verbose mode prints one block per finding; the labeled digest in doc.md
    # must be absent, the bare api_key in secret.txt must be present.
    assert "doc.md" not in output, "labeled digest was flagged (allowlist broken)"
    assert "secret.txt" in output, "real secret was NOT flagged (rules disabled?)"
    assert "leaks found: 1" in output
