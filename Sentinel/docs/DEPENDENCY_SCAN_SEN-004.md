# Dependency Vulnerability Scan — TASK-SEN-004 (Sentinel, Wave 5)

**Date:** 2026-11-15 · **Scope:** every agent's Python dependency manifests in this
repo at main `217a2de7` · **Scanner:** OSV database (the upstream `pip-audit`
queries via PyPI), queried 2026-11-15 · **Target platform:** CPython 3.11
(latest patch; the repo's base image is `python:3.11-slim`), Linux x86_64.

## Method (and its limits)

`pip`/`pip-audit` could not be installed in the scanning sandbox (package
installation is blocked there), so the audit was run with a purpose-built
stdlib scanner implementing the same method as `pip-audit -r`:

1. Parse each agent's manifests (`requirements*.txt`, `pyproject.toml`).
2. Resolve every specifier against PyPI the way a fresh install would —
   maximum satisfying version, transitive `requires_dist` closure with
   marker evaluation, pip's yanked-file semantics, and bounded
   backtracking on constraint conflicts.
3. Query OSV `querybatch` for every resolved (name, version); score each
   advisory from its CVSS v3 vector (base score computed locally; where an
   advisory carries only CVSS v4, the band is the advisory's own GHSA
   severity rating).
4. GHSA/PYSEC twin records for the same CVE are deduplicated by CVE id.

Limits: resolution models a *fresh install today*. Servers installed
earlier may hold older versions than the ones resolved here (most
manifests use open `>=` ranges, so the deployed set drifts with install
date). Optional-dependency extras of transitive packages are included
only where a parent requests them. The scanner's full output (resolved
version sets, per-package findings, resolver backtracks) is in the
evidence file `dependency_scan_sen004_evidence.json` next to this report.

## Headline results

Across the fleet: **832 agent-package resolutions** audited.
**9 critical, 50 high, 26 medium, 0 low** unique vulnerabilities
(85 total, deduplicated by CVE).

| Agent | Packages resolved | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| FRIDAY | 166 | 2 | 2 | 0 | 0 |
| Inference | 32 | 0 | 0 | 0 | 0 |
| Memora | 52 | 0 | 0 | 0 | 0 |
| Stratex | 88 | 0 | 0 | 0 | 0 |
| Stratex (mt5 bridge, Windows) | 9 | 0 | 0 | 0 | 0 |
| Futuris | 69 | 0 | 0 | 0 | 0 |
| IntelX | 41 | 0 | 0 | 0 | 0 |
| Forge | 51 | 0 | 0 | 1 | 0 |
| Sentinel | 67 | 1 | 10 | 8 | 0 |
| Cortex | 58 | 0 | 0 | 0 | 0 |
| VyralX | 78 | 6 | 38 | 16 | 0 |
| CI tooling (root requirements-ci.txt) | 121 | 0 | 0 | 1 | 0 |

## Findings

### 1. CRITICAL/HIGH — chromadb 1.5.9 in FRIDAY (direct dependency) — NO FIX AVAILABLE

`chromadb>=0.4.0` is declared directly in `FRIDAY/requirements.txt` and
`FRIDAY/pyproject.toml`; a fresh resolve installs the latest release,
1.5.9, which is affected by four advisories (OSV ranges end at
`last_affected: 1.5.9` — **no fixed release exists as of 2026-11-15**):

| CVE | Severity | Summary |
|---|---|---|
| CVE-2026-45829 (GHSA-f4j7-r4q5-qw2c) | **Critical, CVSS 10.0** | Pre-authentication code injection in the ChromaDB Python project |
| CVE-2026-45833 (GHSA-36p7-vc44-83pf) | **Critical** (GHSA rating; CVSS v4 only) | Code injection vulnerability |
| CVE-2026-45830 (GHSA-2wm9-hf6c-p5cr) | High, CVSS 8.8 | Any authenticated user can read/write/update/delete data in any tenant's collections |
| CVE-2026-45831 (GHSA-xph7-9rjv-w5fr) | High, CVSS 8.8 | SimpleRBACAuthorizationProvider does not check tenant/database/collection scope |

FRIDAY imports chromadb in `FRIDAY/src/friday/memory/vector_store.py`.
The two code-injection advisories concern Chroma's server/API surface;
exposure depends on whether a Chroma HTTP server is reachable in the
deployment — the embedded client alone does not open that surface. This
needs a coordinator decision, not a version bump (there is nothing to
bump to): options are (a) migrate FRIDAY's vector store to Memora/Oracle
native vector (the fleet's existing direction), (b) remove the chromadb
dependency if `vector_store.py` is dead code in production, or
(c) accept-and-monitor for a fixed upstream release with the Chroma
server surface kept unexposed. **No upgrade PR is possible for this
finding.**

### 2. CRITICAL/HIGH/MEDIUM — Sentinel's pinned trio (fixable; upgrade PR landed)

`Sentinel/requirements.txt` pins three vulnerable versions (the
`pyproject.toml` ranges already admit the fixed versions, so only the
pins move):

| Package | Pinned | Findings | Fixed in |
|---|---|---|---|
| pyjwt | 2.13.0 | **1 critical** (CVE-2026-102268, CVSS 9.1, asymmetric-PEM detection bypass), **6 high** (incl. CVE-2026-102275, 8.2, OKP key confusion; five 7.4 token-forgery class), 7 medium | 2.14.0 / 2.15.0 |
| dnspython | 2.8.0 | 2 high (CVE-2026-114605, CVE-2026-128089, both 7.5, CPU/memory exhaustion in DNS wire parsing) | 2.9.0 / 2.9.2 |
| weasyprint | 69.0 | 1 high (CVE-2026-106443, 8.8, EPS images reach the Ghostscript interpreter → RCE), 1 medium (CVE-2026-55073, SSRF) | 70.0 |

Upgrade PR: **pyjwt==2.15.0, dnspython==2.9.2, weasyprint==70.0**.
Each target version was queried directly against OSV after selection
and returns **zero** known vulnerabilities (this also covers
CVE-2026-103001, a pyjwt medium whose record lists no explicit fixed
version but whose affected range ends before 2.15.0). dnspython is
imported by Sentinel's DNS modules; no direct `jwt`/`weasyprint`
imports exist in Sentinel's Python code. This crew could not run
Sentinel's test suite (the scanning sandbox cannot install packages) —
the PR asks for CI green before merge.

### 3. CRITICAL/HIGH/MEDIUM — Pillow 11.3.0 in VyralX (fixable; upgrade PR landed)

`VyralX/pyproject.toml` caps `Pillow>=10.0,<12.0`, which resolves to
11.3.0 — carrying **60 unique CVEs: 6 critical, 38 high, 16 medium**
(the accumulated advisory backlog for that release line). The criticals:

| CVE | CVSS | Summary |
|---|---|---|
| CVE-2026-112398 | 9.8 | Heap buffer overflow in FlashPix (FPX) JPEG decoding → code execution |
| CVE-2026-112403 | 9.8 | Heap buffer overflow in ImagingJpegDecode |
| CVE-2026-96639 | 9.8 | Multi-frame loaders reuse stale native image storage after mode transitions |
| CVE-2026-112900 | — | Argument injection in the Ghostscript call → potential RCE |
| CVE-2026-112902 | 9.1 | Memory disclosure and segfault in the libtiff encoder via crafted TIFF tags |
| CVE-2026-112393 | — | Heap buffer overflow in _tiffWriteProc when saving TIFF to BytesIO |

VyralX processes untrusted media, so image-decoder flaws sit directly
in its attack surface. Upgrade PR: **`Pillow>=13.0,<14.0`**. All 60
advisories list a fixed version ≤ 13.0.0 (42 are fixed only in 13.0.0);
Pillow 13.0.0 was queried directly against OSV and returns **zero**
known vulnerabilities, and it requires Python ≥3.11, matching VyralX's
`requires-python`. (Pillow 12.0.0 still carries 100 advisory records —
a partial raise is not sufficient.) Same test caveat as Sentinel: CI
green requested before merge.

### 4. MEDIUM — pytest 8.4.2 in CI tooling and Forge's verification env

CVE-2025-71176 (GHSA-6w46-j5rx-g56g), CVSS 6.8 — vulnerable tmpdir
handling; fixed in pytest 9.0.3. Both `requirements-ci.txt` and
`Forge/requirements-verification.txt` cap `pytest>=8.3,<9`, so the fix
requires raising the cap to `<10`. Test-tooling surface only (no
production exposure). Recommended as a separate, deliberate change: the
suites should be run under pytest 9 before the cap is raised. Not
bundled into this task's upgrade PRs.

### 5. Conditional note — soupsieve (transitive via beautifulsoup4)

At the fleet's Python target (≥3.11.5) a fresh resolve installs
soupsieve 4.1.1, which is **not** affected. On a Python **older than
3.11.5**, the resolver would land on soupsieve 2.10, which carries three
advisories (CVE-2026-126191 High 7.5 ReDoS, CVE-2026-126190 High 7.5
DoS, CVE-2026-126193 Medium 5.3 stack exhaustion; fixed in 3.0.2/4.0.0).
Keeping server Python patch levels current (≥3.11.5) closes this;
nothing in the manifests needs to change.

### 6. Resolvability defect — FRIDAY's python-dateutil conflict

FRIDAY's transitive graph contains an unconditional conflict at maximum
versions: `chromadb → kubernetes 37.0.2` requires
`python-dateutil>=3.0.0`, while `recurring-ical-events 3.8.2` requires
`python-dateutil<3.0.0,>=2.8.1`. A real installer resolves this only by
backtracking to an older kubernetes (34–36.x spot-checked: no known
vulnerabilities) or an older calendar stack. python-dateutil itself
(2.9.0.post0 / 3.0.0 / 4.0.0 spot-checked) has no known vulnerabilities.
Worth knowing for install reproducibility: FRIDAY's manifest set does
not resolve at newest versions, and `Stratex/requirements.txt` references
a `requirements.lock` file that does not exist in the repo.

## Upgrade PRs landed by this task

1. **Sentinel pins** — pyjwt 2.13.0→2.15.0, dnspython 2.8.0→2.9.2,
   weasyprint 69.0→70.0 in `Sentinel/requirements.txt`
   (branch `claude/task-sen-004-sentinel-dep-upgrades`).
2. **VyralX Pillow** — `Pillow>=10.0,<12.0` → `Pillow>=13.0,<14.0` in
   `VyralX/pyproject.toml`
   (branch `claude/task-sen-004-vyralx-pillow-upgrade`).

No PR for chromadb (no fixed release exists) or pytest (medium,
test tooling, cap change needs a suite run under pytest 9 first).
The coordinator merges; this crew does not merge.

## Per-agent detail

Full resolved version sets and per-finding records (advisory ids, CVSS
vectors, fixed versions, summaries) are in
`dependency_scan_sen004_evidence.json`. Agents with zero findings were
audited over their full transitive closure at the versions listed there
— "clean" means no resolved (name, version) pair matched any OSV record
for the PyPI ecosystem on 2026-11-15, not that the code was reviewed.
