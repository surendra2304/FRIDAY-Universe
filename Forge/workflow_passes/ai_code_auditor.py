"""Forge workflow pass: AI Code Auditor.

Adopted from The Agency's AI-Generated Code Security Auditor role
(msitarzewski/agency-agents, security/security-ai-generated-code-auditor.md,
MIT): the reviewer who reads code the way an assistant wrote it — fast,
confident, plausible, optimized for the demo rather than production — and
hunts the hardcoded secrets, broken row-level security, and
prompt-injection sinks that coding assistants ship by default.

Rules carried over, implemented as deterministic static checks
(no LLM, no network, read-only — the pass never edits files):

- Evidence over assertion: every finding names the exact line, the exact
  exploit, and the exact fix. No finding without all three.
- Secrets are already burned: a leaked-secret finding always names the
  rotation step; removal from source is never sufficient.
- Never print a raw secret value back in any output — findings carry the
  type, the location, and a redacted preview (variable/key name only).
  The value itself never travels in a result.
- Prefer a false negative to a false positive on heuristic checks: the
  prompt-injection and taint analyses stay conservative; an ambiguous
  flow gets silence, not a guess. Heuristic findings are medium
  confidence and say so.
- Respect the data/instructions boundary: untrusted input in its own
  user-role message with no tools is the documented-safe pattern and
  must never fire.
- Publishable keys are meant to be public (Supabase anon, Stripe
  publishable): they must never fire.
- Findings are keyed to a stable fingerprint so a rescan can tell
  "still here", "resolved", and "newly introduced" apart.
- Every finding maps to a CWE and, for model-facing issues, an OWASP
  LLM Top 10 entry. Coverage is reported honestly: what was checked,
  what was not — never a "% secure" number.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

__all__ = [
    "AICodeAuditor",
    "AuditFinding",
    "AuditReport",
    "RescanDiff",
]

# --- Known secret shapes (CWE-798) -------------------------------------------
_KEY_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9]{8,}"), "OpenAI-style key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "GitHub personal access token"),
    (re.compile(r"gho_[A-Za-z0-9]{20,}"), "GitHub OAuth token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{10,}"), "GitHub fine-grained token"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"AIza[0-9A-Za-z_-]{10,}"), "Google API key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key block"),
)

# Generic secret assignment: <secret-ish name> = "literal value".
_GENERIC_SECRET_ASSIGN = re.compile(
    r"""(?i)\b(api[_-]?key|apikey|secret|token|password|passwd|private[_-]?key)\b
        \s*[:=]\s*["']([^"']{8,})["']""",
    re.VERBOSE,
)

# Values that are obviously placeholders, not live secrets. The auditor
# stays silent on these — a scanner that cries wolf gets muted.
_PLACEHOLDER_HINTS = (
    "xxx", "changeme", "your-", "example", "placeholder", "dummy",
    "redacted", "...", "todo", "insert-", "replace-me",
)

# Client-exposed env prefixes: inlined into the client bundle by design.
_CLIENT_ENV_PREFIXES = ("NEXT_PUBLIC_", "VITE_", "PUBLIC_", "EXPO_PUBLIC_")
_CLIENT_ENV_RE = re.compile(
    r"(?:process\.env|import\.meta\.env)\s*\.?\s*\[?\s*[\"']?"
    r"((?:NEXT_PUBLIC_|VITE_|PUBLIC_|EXPO_PUBLIC_)[A-Z0-9_]+)"
)
# Publishable by design — never flag these.
_PUBLISHABLE_HINTS = ("ANON", "PUBLISHABLE", "PUBLIC_KEY", "PROJECT_ID", "PROJECT_URL")

# Row-level security (CWE-862 / CWE-863).
_RLS_USING_TRUE = re.compile(r"using\s*\(\s*true\s*\)", re.IGNORECASE)
_CREATE_TABLE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_RLS_ENABLE = re.compile(r"enable\s+row\s+level\s+security", re.IGNORECASE)
_USER_METADATA_AUTH = re.compile(r"user_metadata", re.IGNORECASE)
_AUTH_CONTEXT = re.compile(r"\b(role|admin|policy|auth|allow|check|permission)\b", re.IGNORECASE)

# Prompt injection (CWE-1426, OWASP LLM01; +LLM06 with tools).
_REQUEST_SOURCE = re.compile(
    r"\b(?:req\.body|req\.json\(\)|request\.json|request\.form|request\.args|req\.query)\b"
)
_SOURCE_ASSIGN = re.compile(r"(\w+)\s*=\s*.*?(?:req\.body|req\.json\(\)|request\.json|request\.form)")
_DESTRUCTURE_SOURCE = re.compile(
    r"\{\s*([^}]+)\}\s*=\s*(?:await\s+)?(?:req\.json\(\)|req\.body|request\.json)"
)
_LLM_CALL = re.compile(
    r"\b(?:completions\.create|generate_content|chat\.completions|invoke|generate)\b"
)
_TOOLS_PARAM = re.compile(r"\btools\s*[:=]")


def _fingerprint(rule: str, path: str, line: int) -> str:
    """Stable finding identity for rescan continuity."""
    raw = f"{rule}|{path}|{line}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in _PLACEHOLDER_HINTS)


@dataclass
class AuditFinding:
    """One finding: line, exploit, fix — never the raw secret value."""

    fingerprint: str
    path: str
    line: int
    severity: str  # "critical" | "high" | "medium" | "low"
    cwe: str  # e.g. "CWE-798"
    category: str  # e.g. "hardcoded-secret"
    message: str
    exploit: str  # plain-English risk
    fix: str  # one-commit fix, including rotation for secrets
    confidence: str = "high"  # "high" | "medium"
    preview: str = ""  # redacted: name only, never the value

    def render(self) -> str:
        """Worst-first triage line. Contains no secret value by construction."""
        return (
            f"[{self.severity.upper()}] {self.category} — {self.path}:{self.line} "
            f"({self.cwe}, confidence {self.confidence})\n"
            f"  Why: {self.exploit}\n"
            f"  Fix: {self.fix}"
            + (f"\n  Preview: {self.preview}" if self.preview else "")
        )


@dataclass
class RescanDiff:
    """Rescan vs. previous scan, keyed by fingerprint."""

    resolved: list[AuditFinding] = field(default_factory=list)
    still_present: list[AuditFinding] = field(default_factory=list)
    newly_introduced: list[AuditFinding] = field(default_factory=list)


@dataclass
class AuditReport:
    """Result of one audit pass over a set of files."""

    files_scanned: int
    findings: list[AuditFinding] = field(default_factory=list)  # worst-first
    checked: list[str] = field(default_factory=list)
    not_checked: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        """Findings by severity."""
        out = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in self.findings:
            out[finding.severity] = out.get(finding.severity, 0) + 1
        return out

    @property
    def blocking(self) -> list[AuditFinding]:
        """Findings that block the ship: critical + high."""
        return [f for f in self.findings if f.severity in ("critical", "high")]

    def rescan_diff(self, previous: "AuditReport") -> RescanDiff:
        """Diff this scan against a previous one by fingerprint."""
        previous_by_fp = {f.fingerprint: f for f in previous.findings}
        current_by_fp = {f.fingerprint: f for f in self.findings}
        return RescanDiff(
            resolved=[f for fp, f in previous_by_fp.items() if fp not in current_by_fp],
            still_present=[f for fp, f in current_by_fp.items() if fp in previous_by_fp],
            newly_introduced=[f for fp, f in current_by_fp.items() if fp not in previous_by_fp],
        )


class AICodeAuditor:
    """Static, local-first audit over files at rest. Read-only.

    ``files`` maps path -> content; ``client_reachable`` names the paths
    whose code reaches a client (browser bundle, shipped JS). A secret in
    client-reachable code is compromised from the moment it was committed.
    """

    _SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def audit(
        self,
        files: dict[str, str],
        client_reachable: frozenset[str] | set[str] = frozenset(),
    ) -> AuditReport:
        """Scan every file and return findings worst-first."""
        findings: list[AuditFinding] = []
        for path in sorted(files):
            content = files[path]
            findings.extend(self._audit_file(path, content, path in client_reachable))
        # One finding per fingerprint: two rules firing on the same line
        # keep the higher severity, so rescan diffs stay meaningful.
        by_fingerprint: dict[str, AuditFinding] = {}
        for finding in findings:
            previous = by_fingerprint.get(finding.fingerprint)
            if previous is None or (
                self._SEVERITY_ORDER[finding.severity]
                < self._SEVERITY_ORDER[previous.severity]
            ):
                by_fingerprint[finding.fingerprint] = finding
        findings = list(by_fingerprint.values())
        findings.sort(key=lambda f: (self._SEVERITY_ORDER[f.severity], f.path, f.line))
        return AuditReport(
            files_scanned=len(files),
            findings=findings,
            checked=[
                "hardcoded secrets incl. known key formats (CWE-798)",
                "client-exposed env prefixes (CWE-798)",
                "service_role key in client-reachable code (CWE-798)",
                "row-level security: USING (true), missing RLS, user_metadata auth (CWE-862/863)",
                "prompt-injection sinks: untrusted input into system prompt / tool-enabled LLM calls (CWE-1426, LLM01/LLM06)",
            ],
            not_checked=[
                "runtime behaviour, live database policies, deployed bundles",
                "secret rotation state at the provider (verify separately)",
                "prompt-injection flows the taint heuristic cannot see (marked medium confidence)",
            ],
        )

    # -- per-file rules ------------------------------------------------------

    def _audit_file(self, path: str, content: str, is_client: bool) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        lines = content.splitlines()
        for number, line in enumerate(lines, start=1):
            findings.extend(self._check_known_keys(path, number, line, is_client))
            findings.extend(self._check_generic_secret(path, number, line, is_client))
            findings.extend(self._check_client_env(path, number, line))
            findings.extend(self._check_service_role(path, number, line, is_client))
            findings.extend(self._check_rls_using_true(path, number, line))
            findings.extend(self._check_user_metadata(path, number, line))
        findings.extend(self._check_missing_rls(path, content))
        findings.extend(self._check_prompt_injection(path, lines))
        return findings

    def _check_known_keys(
        self, path: str, number: int, line: str, is_client: bool
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        for pattern, kind in _KEY_PATTERNS:
            if pattern.search(line):
                # A private-key block is a finding wherever it sits; a key
                # literal in client code is critical, elsewhere high.
                severity = "critical" if is_client else "high"
                findings.append(
                    AuditFinding(
                        fingerprint=_fingerprint("hardcoded-secret-known", path, number),
                        path=path,
                        line=number,
                        severity=severity,
                        cwe="CWE-798",
                        category="hardcoded-secret",
                        message=f"{kind} hardcoded in source.",
                        exploit=(
                            f"A {kind} is inlined in {path}:{number}. "
                            + (
                                "Client-reachable code ships it to every browser; "
                                "open DevTools and it is right there."
                                if is_client
                                else "Anyone with read access to this repo can use it."
                            )
                        ),
                        fix=(
                            "Move the value to a server-only secret store / "
                            "environment variable and ROTATE it at the provider — "
                            "deleting it from source does not un-leak it."
                        ),
                        preview=f"{kind} [REDACTED]",
                    )
                )
                break  # one finding per line for known key shapes
        return findings

    def _check_generic_secret(
        self, path: str, number: int, line: str, is_client: bool
    ) -> list[AuditFinding]:
        match = _GENERIC_SECRET_ASSIGN.search(line)
        if not match:
            return []
        # A known key shape on the same line is already reported by the
        # known-key rule — one finding per secret, not two.
        if any(pattern.search(line) for pattern, _ in _KEY_PATTERNS):
            return []
        name, value = match.group(1), match.group(2)
        if _is_placeholder(value):
            return []
        # Env reads never reach this regex: after `=` there is no quoted
        # literal (os.environ[...] / process.env.X), so a match here is a
        # real inline literal.
        severity = "critical" if is_client else "high"
        return [
            AuditFinding(
                fingerprint=_fingerprint("hardcoded-secret-generic", path, number),
                path=path,
                line=number,
                severity=severity,
                cwe="CWE-798",
                category="hardcoded-secret",
                message=f"Secret assigned as a literal: {name}.",
                exploit=(
                    f"The {name} value is written inline at {path}:{number}. "
                    + (
                        "Client-reachable code ships it to every visitor."
                        if is_client
                        else "It lives in source control as a usable credential."
                    )
                ),
                fix=(
                    "Read it from a server-only environment variable and "
                    "ROTATE the value at the provider — it is already compromised."
                ),
                preview=f"{name} [REDACTED]",
            )
        ]

    def _check_client_env(self, path: str, number: int, line: str) -> list[AuditFinding]:
        match = _CLIENT_ENV_RE.search(line)
        if not match:
            return []
        var_name = match.group(1)
        upper = var_name.upper()
        if any(hint in upper for hint in _PUBLISHABLE_HINTS):
            return []  # publishable/anon keys are meant to be public
        if not any(word in upper for word in ("KEY", "SECRET", "TOKEN", "PRIVATE")):
            return []
        return [
            AuditFinding(
                fingerprint=_fingerprint("client-secret", path, number),
                path=path,
                line=number,
                severity="high",
                cwe="CWE-798",
                category="client-secret",
                message=f"Secret behind a client-exposed env prefix: {var_name}.",
                exploit=(
                    f"{var_name} is read through a client-exposed env prefix, "
                    "which is inlined into the client bundle by design — the "
                    "value is public to anyone who loads the page."
                ),
                fix=(
                    "Move the call to a server route and read the secret "
                    "server-side; ROTATE the value at the provider."
                ),
                preview=f"{var_name} [REDACTED]",
            )
        ]

    def _check_service_role(
        self, path: str, number: int, line: str, is_client: bool
    ) -> list[AuditFinding]:
        if not is_client or "service_role" not in line.lower():
            return []
        return [
            AuditFinding(
                fingerprint=_fingerprint("service-role-client", path, number),
                path=path,
                line=number,
                severity="critical",
                cwe="CWE-798",
                category="service-role-client",
                message="service_role key in client-reachable code.",
                exploit=(
                    "The service_role key bypasses row-level security entirely; "
                    "in client code it hands every row to anyone."
                ),
                fix=(
                    "Move it to a server route; use the anon key on the client. "
                    "ROTATE the key in the provider dashboard."
                ),
                preview="service_role [REDACTED]",
            )
        ]

    def _check_rls_using_true(self, path: str, number: int, line: str) -> list[AuditFinding]:
        if not _RLS_USING_TRUE.search(line):
            return []
        return [
            AuditFinding(
                fingerprint=_fingerprint("rls-using-true", path, number),
                path=path,
                line=number,
                severity="high",
                cwe="CWE-862",
                category="rls-using-true",
                message='Row-level security policy allows the whole world: USING (true).',
                exploit=(
                    'RLS is "on" but the policy allows every row to every caller — '
                    "the dashboard says locked while the table is wide open."
                ),
                fix="Scope the policy to the authenticated user's identity, e.g. auth.uid() = user_id.",
                preview="USING (true) policy",
            )
        ]

    def _check_user_metadata(self, path: str, number: int, line: str) -> list[AuditFinding]:
        if not _USER_METADATA_AUTH.search(line):
            return []
        if not _AUTH_CONTEXT.search(line):
            return []
        return [
            AuditFinding(
                fingerprint=_fingerprint("user-metadata-auth", path, number),
                path=path,
                line=number,
                severity="high",
                cwe="CWE-862",
                category="user-metadata-auth",
                message="Authorization trusts user_metadata, which the user controls.",
                exploit=(
                    "A signed-in user can edit their own user_metadata through "
                    "the auth API and grant themselves any role, so a check on "
                    "it is not an authorization gate."
                ),
                fix="Gate on the server-only app_metadata / authenticated identity (auth.uid()) instead.",
                preview="user_metadata authorization",
            )
        ]

    def _check_missing_rls(self, path: str, content: str) -> list[AuditFinding]:
        tables = _CREATE_TABLE.findall(content)
        if not tables or _RLS_ENABLE.search(content):
            return []
        findings: list[AuditFinding] = []
        seen: set[str] = set()
        for table in tables:
            if table in seen:
                continue
            seen.add(table)
            line_no = next(
                (n for n, line in enumerate(content.splitlines(), start=1)
                 if table in line and "create" in line.lower()),
                1,
            )
            findings.append(
                AuditFinding(
                    fingerprint=_fingerprint("rls-missing", path, line_no),
                    path=path,
                    line=line_no,
                    severity="high",
                    cwe="CWE-863",
                    category="rls-missing",
                    message=f"Public table {table} has no row-level security.",
                    exploit=(
                        f"Table {table} is created with no RLS — with the anon "
                        "key, anyone reads every row."
                    ),
                    fix=f"Enable RLS on {table} and add an identity-scoped policy (auth.uid() = user_id).",
                    confidence="medium",
                    preview=f"CREATE TABLE {table} (no RLS)",
                )
            )
        return findings

    def _check_prompt_injection(self, path: str, lines: list[str]) -> list[AuditFinding]:
        """Taint-lite, conservative by design (prefer a false negative).

        Sources: variables assigned from request input (req.body, req.json(),
        request.json/form) plus direct source expressions. Sinks, both
        checked inside a window so a *user-role* message on the same line
        as a system message does NOT fire (that is the documented-safe
        pattern):
        - the tainted value appears inside a system-role message's content
          (medium; high when tools are attached in the same region), or
        - the tainted value appears in an LLM call that also configures
          tools (high — excessive agency, LLM06).
        """
        sources: set[str] = set()
        for line in lines:
            match = _SOURCE_ASSIGN.search(line)
            if match:
                sources.add(match.group(1))
            destructure = _DESTRUCTURE_SOURCE.search(line)
            if destructure:
                for name in destructure.group(1).split(","):
                    name = name.strip().split(":")[0].strip()
                    if name:
                        sources.add(name)
        if not sources and not any(_REQUEST_SOURCE.search(line) for line in lines):
            return []

        def tainted(text: str) -> bool:
            if _REQUEST_SOURCE.search(text):
                return True
            return any(re.search(rf"\b{re.escape(var)}\b", text) for var in sources)

        content = "\n".join(lines)
        # Role keys are quoted in Python dicts but bare in JS object
        # literals (`{ role: "system", ... }`) — accept both.
        role_marker = re.compile(r"""["']?role["']?\s*:\s*["'](system|user|assistant)["']""")
        findings: list[AuditFinding] = []
        seen_lines: dict[int, str] = {}  # line -> highest severity seen

        def add_finding(number: int, severity: str, tools: bool) -> None:
            previous = seen_lines.get(number)
            order = {"medium": 0, "high": 1}
            if previous is not None and order[previous] >= order[severity]:
                return
            seen_lines[number] = severity
            findings.append(
                AuditFinding(
                    fingerprint=_fingerprint("prompt-injection", path, number),
                    path=path,
                    line=number,
                    severity=severity,
                    cwe="CWE-1426",
                    category="prompt-injection",
                    message=(
                        "Untrusted input reaches the model's instructions"
                        + (" on a tool-enabled call (excessive agency)." if tools else ".")
                    ),
                    exploit=(
                        "Request-shaped input lands in the system prompt"
                        + (
                            " on a call that also grants the model tools — a "
                            "successful injection can trigger real actions, not just bad text."
                            if tools
                            else " — an attacker can steer the model's instructions."
                        )
                        + " Heuristic detection: verify manually."
                    ),
                    fix=(
                        "Move the input to its own user-role message and validate "
                        "it first; never concatenate untrusted input into a system "
                        "prompt or a single instruction string"
                        + ("; gate tools behind confirmation." if tools else ".")
                    ),
                    confidence="medium",
                    preview="untrusted input -> system prompt",
                )
            )

        # --- Sink 1: tainted value inside a system-role message. ---
        markers = list(role_marker.finditer(content))
        for index, marker in enumerate(markers):
            if marker.group(1) != "system":
                continue
            window_end = (
                markers[index + 1].start() if index + 1 < len(markers) else marker.end() + 400
            )
            window = content[marker.start() : min(window_end, marker.end() + 400)]
            if not tainted(window):
                continue
            line_no = content.count("\n", 0, marker.start()) + 1
            tools_nearby = any(
                _TOOLS_PARAM.search(other)
                for other in lines[line_no - 1 : line_no + 10]
            )
            add_finding(line_no, "high" if tools_nearby else "medium", tools_nearby)

        # --- Sink 2: tainted value in a tool-enabled LLM call. ---
        # A system-role sink in the same call region is already reported
        # (at high severity when tools are attached) — do not double-report.
        system_sink_lines = {
            content.count("\n", 0, marker.start()) + 1
            for marker in markers
            if marker.group(1) == "system"
        }
        for number, line in enumerate(lines, start=1):
            if not _LLM_CALL.search(line):
                continue
            window = "\n".join(lines[number - 1 : number + 15])
            if not tainted(window):
                continue
            if not _TOOLS_PARAM.search(window):
                continue
            if any(number <= sink <= number + 15 for sink in system_sink_lines):
                continue
            add_finding(number, "high", True)
        return findings
