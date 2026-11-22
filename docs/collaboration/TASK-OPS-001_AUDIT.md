# TASK-OPS-001 — OCI secrets audit (names only)

- **Task:** TASK-OPS-001 — OCI secrets present in the repo (names verified; values unverified) — MASTER_PLAN §6, standing backlog, pool 2 item 9.
- **Owner:** Muse 7. **Claim:** issue #35 comment 7070542215; claim PR #1272 merged 04:39 IST 2026-11-22 (f64e0fa9).
- **Audit run:** 2026-11-22 ~05:25–06:00 IST. **Base:** main 485df534 (board blob 96145079, 13,331 lines).
- **Rule obeyed throughout:** NAMES ONLY. No secret value was read, printed, logged, stored, or posted anywhere. Resource identifiers below are described by kind and length only, never by value.

## Method and scope

- GitHub code search for every OCI credential-name candidate (`OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_FINGERPRINT`, `OCI_KEY_CONTENT`, `OCI_REGION`, `OCI_COMPARTMENT_OCID`, `OCI_SUBNET_ID`, `OCI_IMAGE_ID`, `OCI_AVAILABILITY_DOMAIN`, `OCI_SSH_PUBLIC_KEY`, `OCI_PRIVATE_KEY`, `OCI_CONFIG`, `OCI_API_KEY`, `OCI_KEY_FILE`, `OCI_PROFILE`, `PRIVATE_KEY_PATH`, `ocid1.`, `tenancy`, `fingerprint`), plus combined `OCI+getenv` / `OCI+environ` sweeps.
- 40 files read in full via the git blobs API (scripts, workflows, docs, tests, `.env.example`, `.gitleaks.toml`, `.gitignore`, service unit).
- Full recursive tree (8,109 entries, not truncated) checked for committed key/config filenames (`.pem`, `.key`, `.oci`, `CREDENTIALS`).
- Live checks: GitHub Actions secrets listed via API (names only); bridge `get_system_info` (both Oracle servers ONLINE); S1 allocator service and env-file presence probed via bridge `run_shell` (keys-only listing; see §7).
- **Scope is the current main tree.** Git history was not swept in this audit (see F7). Test fixtures were classified separately and are not findings.

## 1. OCI secret names present in the repo

Every name below is referenced by name only — read from the environment or from GitHub Secrets. No value appears in the repo for any of them.

| Name | Where it appears (file:line) | How it is consumed |
|---|---|---|
| `OCI_USER_OCID` | `FRIDAY/scripts/oracle_retry.py:153,161`; `.github/workflows/oracle-capacity-sniper.yml:54`; `.github/workflows/oracle-capacity-sniper-worker2.yml:60` | `os.environ.get`; workflow injects `secrets.OCI_USER_OCID` / `secrets.OCI_USER_OCID_2` |
| `OCI_TENANCY_OCID` | `FRIDAY/scripts/oracle_retry.py:156,164`; `FRIDAY/scripts/oci_a1_continuous.py:246`; `oracle-capacity-sniper.yml:57`; `oracle-capacity-sniper-worker2.yml:63` | `os.environ.get`; workflow injects `secrets.OCI_TENANCY_OCID` |
| `OCI_FINGERPRINT` | `FRIDAY/scripts/oracle_retry.py:155,163`; `oracle-capacity-sniper.yml:56`; `oracle-capacity-sniper-worker2.yml:62` | `os.environ.get`; workflow injects `secrets.OCI_FINGERPRINT` / `secrets.OCI_FINGERPRINT_2` |
| `OCI_KEY_CONTENT` | `FRIDAY/scripts/oracle_retry.py:154,162`; `oracle-capacity-sniper.yml:55`; `oracle-capacity-sniper-worker2.yml:61` | `os.environ.get`; the API private-key PEM, held in GitHub Secrets (`secrets.OCI_KEY_CONTENT` / `secrets.OCI_KEY_CONTENT_2`); passed in-memory to `oci.config.validate_config` (`oracle_retry.py:174-180`), never written to disk or printed |
| `OCI_REGION` | `FRIDAY/scripts/oracle_retry.py:157`; `FRIDAY/scripts/oci_a1_continuous.py:159,187,589`; `FRIDAY/scripts/oci_a1_preflight.py:18,87`; `FRIDAY/systemd/friday-oci-a1-allocator.service:14`; `oracle-capacity-sniper.yml:58`; `oracle-capacity-sniper-worker2.yml:64`; tests | `os.environ.get` (default `ap-hyderabad-1`); region name, not a credential |
| `OCI_COMPARTMENT_OCID` | `FRIDAY/scripts/oracle_retry.py:158`; `FRIDAY/scripts/oci_a1_continuous.py:256`; `FRIDAY/scripts/oci_a1_preflight.py:19,109`; `FRIDAY/tests/test_oci_a1_continuous.py:335`; doc template `FRIDAY/docs/OCI_A1_CONTINUOUS_ALLOCATOR.md:53` (placeholder) | `os.environ.get`, falls back to tenancy OCID |
| `OCI_SUBNET_ID` | `FRIDAY/scripts/oci_a1_continuous.py:192`; `FRIDAY/scripts/oci_a1_preflight.py:21,88`; doc template `FRIDAY/docs/OCI_A1_CONTINUOUS_ALLOCATOR.md:54` (placeholder); `FRIDAY/tests/test_oci_a1_preflight.py:47,55` | `os.environ.get`, falls back to the literal default in `FRIDAY/scripts/oci_a1_common.py:14` (see F1) |
| `OCI_IMAGE_ID` | `FRIDAY/scripts/oci_a1_continuous.py:193`; `FRIDAY/scripts/oci_a1_preflight.py:22,89` | `os.environ.get`, falls back to the literal default in `FRIDAY/scripts/oci_a1_common.py:15` (see F2) |
| `OCI_AVAILABILITY_DOMAIN` | `FRIDAY/scripts/oci_a1_continuous.py:189`; `FRIDAY/scripts/oci_a1_preflight.py:20,91` | `os.environ.get` (default `qvRd:AP-HYDERABAD-1-AD-1`) |
| `OCI_SSH_PUBLIC_KEY` | `FRIDAY/scripts/oci_a1_continuous.py:195`; `FRIDAY/scripts/oci_a1_preflight.py:23` | `os.environ.get`; a **public** key — not a secret |
| `OCI_USER_OCID_2` | `.github/workflows/oracle-capacity-sniper-worker2.yml:60`; `docs/ARCHITECTURE_AS_BUILT.md:74` | GitHub secret name only (second API key's user OCID) |
| `OCI_KEY_CONTENT_2` | `.github/workflows/oracle-capacity-sniper-worker2.yml:61`; `docs/ARCHITECTURE_AS_BUILT.md:74` | GitHub secret name only (second API key's PEM) |
| `OCI_FINGERPRINT_2` | `.github/workflows/oracle-capacity-sniper-worker2.yml:62`; `docs/ARCHITECTURE_AS_BUILT.md:74` | GitHub secret name only (second API key's fingerprint) |

`docs/ARCHITECTURE_AS_BUILT.md:74` lists all eight GitHub secret names; all eight were verified live via the Actions secrets API (names only) — see §6.

## 2. OCI secret names absent from the repo

| Name | Result | Note |
|---|---|---|
| `OCI_PRIVATE_KEY` | 0 matches | The private key travels as `OCI_KEY_CONTENT`, not under this name |
| `OCI_CONFIG` | 0 matches | No config-file env var; the OCI config file is referenced only as a local-machine path (see below) |
| `OCI_API_KEY` | 0 matches | No such name is used |
| `OCI_KEY_FILE` | 0 matches | No key-file env var |
| `OCI_PROFILE` | 0 matches | No CLI-profile env var |
| `PRIVATE_KEY_PATH` (OCI) | 0 OCI matches | The only hits are Binance, not OCI: `Stratex/exchanges/binance_futures_adapter.py:170` (`BINANCE_PRIVATE_KEY_PATH`) and a constructor parameter in `tools/universe_external_integrations.py` |

Config-file references: `scripts/check_storage.py:3` and `scripts/resize_boot_volume.py:4` call `oci.config.from_file("C:/Users/Surendra/.oci/config")` — a path on the owner's local Windows machine. No `.oci` directory or config file exists in the repo tree.

## 3. Real values found — resource identifiers, not credentials

Five distinct real-format OCIDs (verified by format and length only; values never reproduced here), in 9 occurrences. An OCID identifies a cloud resource; on its own it cannot authenticate anything. The repo itself labels the first two "non-secret resource identifiers" (`FRIDAY/scripts/oci_a1_common.py:13`).

| Resource | Length | Occurrences (file:line) |
|---|---|---|
| Subnet OCID | 92 chars | `FRIDAY/scripts/oci_a1_common.py:14`; `FRIDAY/scripts/oracle_retry.py:9`; `docs/AUDIT_REPORT.md:44` (same value, 3 places) |
| Ubuntu 24.04 image OCID | 91 chars | `FRIDAY/scripts/oci_a1_common.py:15`; `FRIDAY/scripts/oracle_retry.py:10`; `FRIDAY/docs/OCI_A1_CONTINUOUS_ALLOCATOR.md:39` (same value, 3 places) |
| Ubuntu 22.04 image OCID | 91 chars | `FRIDAY/scripts/oracle_retry.py:11` |
| Boot volume OCID | 96 chars | `scripts/resize_boot_volume.py:7` |
| Instance OCID (interim host) | 94 chars | `docs/AUDIT_REPORT.md:26` |

Also present: `DEFAULT_SSH_PUBLIC_KEY` (`FRIDAY/scripts/oci_a1_common.py:16-18`) — a full ssh-rsa **public** key. Public keys are designed to be shared and are not secrets; cited by name and line only, value not reproduced.

**No credential values were found:** no API-key value, no fingerprint value (no colon-hex fingerprint pattern in any of the 40 files read), and no private-key block (the only `BEGIN ... PRIVATE KEY` matches are scrubber regexes — see §5). Test fixtures use obviously fake OCIDs (`ocid1.tenancy.test`, `ocid1.compartment.target`, `ocid1.tenancy`, `ocid1.user`, fingerprint `aa:bb:cc:dd`) and are not findings.

## 4. Findings (file/line + fix or follow-up)

- **F1 — Real subnet OCID committed in 3 files** (`FRIDAY/scripts/oci_a1_common.py:14`, `FRIDAY/scripts/oracle_retry.py:9`, `docs/AUDIT_REPORT.md:44`). Follow-up: replace the literals with the `OCI_SUBNET_ID` env/config path the code already supports; keep the value out of source. No rotation applies — an OCID is an immutable resource ID, not a credential.
- **F2 — Real image OCIDs committed** (`FRIDAY/scripts/oci_a1_common.py:15`, `FRIDAY/scripts/oracle_retry.py:10-11`, `FRIDAY/docs/OCI_A1_CONTINUOUS_ALLOCATOR.md:39`). Follow-up: same as F1, via `OCI_IMAGE_ID`.
- **F3 — Real boot-volume OCID committed** (`scripts/resize_boot_volume.py:7`). Follow-up: move to a CLI argument or env var; the same script hardcodes a local Windows config path (line 4) — make both configurable.
- **F4 — Real instance OCID in a doc** (`docs/AUDIT_REPORT.md:26`, interim host). Follow-up: redact to a placeholder; the host identifier does not need to be in the report.
- **F5 — `.env.example` documents no OCI names** (29 lines; no `OCI_*` entry). Follow-up: add placeholder entries for the ten env names in §1 so a new checkout documents the whole OCI surface.
- **F6 — `.gitignore` has no `.oci/` entry** (`*.pem`, `*.key`, `*.env*` are covered, lines 65, 79-86). Follow-up: add `.oci/` so a local OCI config directory can never be committed by accident.
- **F7 — Git history not swept by this audit.** `secret-scan.yml` scans changed commits only (PR/push range), and the legacy leak in commit `46034a4` is already tracked separately by TASK-SEC-002. Follow-up: coordinator decision on a one-off full-history gitleaks scan for OCI material.
- **F8 — Key PEM lives in exactly one place.** The API private-key PEM is held only in GitHub Secrets (`OCI_KEY_CONTENT` / `OCI_KEY_CONTENT_2`); the server-side `CREDENTIALS.md` holds the user OCID, tenancy OCID and fingerprint but **not** the PEM (`docs/handoff.md:79`, owner action already open). No repo action; recorded here for the coordinator.

No credential rotation is required by this audit: no credential value is present in the repo, so there is nothing to rotate. F1–F4 concern resource identifiers, which cannot be rotated — only moved out of source.

## 5. Hygiene verified (guards already in place)

- `FRIDAY/scripts/oracle_retry.py:154-180` — key content is used in-memory only (`validate_config` → SDK clients); missing variables fail closed naming names only (lines 161-168). Nothing is written to disk or printed.
- `FRIDAY/scripts/oci_a1_preflight.py:1-7,15-23` — env file is allow-listed to six keys (`OCI_REGION`, `OCI_COMPARTMENT_OCID`, `OCI_AVAILABILITY_DOMAIN`, `OCI_SUBNET_ID`, `OCI_IMAGE_ID`, `OCI_SSH_PUBLIC_KEY`); the preflight "never emits SDK response bodies, OCIDs, tokens, or other credential material".
- `FRIDAY/tests/test_oci_a1_continuous.py:102` — guard test asserting `OCI_KEY_CONTENT` never appears in the allocator's `state.json`.
- `scripts/server_vm.py:58`, `scripts/oracle_cloud_mcp.py:49` — output sanitizers redact private-key blocks (plus GitHub tokens, JWTs, password-like assignments).
- `scripts/guard_secrets_pre_push.py:36` — pre-push hook pattern for private-key blocks.
- `.gitleaks.toml` — default rules plus one narrow allowlist (labeled SHA-256 digests only); `secret-scan.yml` runs gitleaks on PRs and pushes to main.
- `FRIDAY/scripts/install_oci_a1_continuous.sh` — the allocator env file must be root-owned mode `0600`; the installer states the service "uses OCI Instance Principals; it does not store an OCI private API key". The persistent allocator authenticates by instance principals (`oci_a1_preflight.py:100`), not by API key.
- Tree check: no `.pem` / `.key` file, no `.oci` directory, no `CREDENTIALS` file anywhere in the 8,109-entry tree.
- Workflows pass secrets as environment variables only; the key PEM is never echoed, written to a file, or posted to an issue.

## 6. Live verification (names only)

- GitHub Actions secrets API, 2026-11-22 ~05:50 IST: 17 secrets total; all eight OCI names present — `OCI_USER_OCID`, `OCI_KEY_CONTENT`, `OCI_FINGERPRINT`, `OCI_TENANCY_OCID`, `OCI_REGION`, `OCI_USER_OCID_2`, `OCI_KEY_CONTENT_2`, `OCI_FINGERPRINT_2` — matching `docs/ARCHITECTURE_AS_BUILT.md:74` exactly.
- Bridge `get_system_info` (v1.30.0): both Oracle servers ONLINE.
- Server 1: `friday-oci-a1-allocator` service is **enabled**; `/etc/friday-arm-sniper.env` exists, root-owned mode `0600`, 326 bytes (2026-11-14). Server 2: no such service or file.

## 7. Limitations

- The live allocator env-file **key names could not be verified**: the bridge shell runs as `ubuntu` and the file is root-owned `0600`, so the keys-only listing was refused (permission denied). The preflight allow-list (§5) bounds what the file may contain; the actual keys live on Server 1 only.
- Git history was not swept (F7); this audit covers the current main tree at 485df534.
- Code search returns at most 100 files per query; the name-by-name searches plus the `OCI+getenv` / `OCI+environ` sweeps and the full-tree filename check were used to close that gap, and every credential-relevant file found was read in full.

## Verdict

Audit complete. **No OCI credential value is present in the repo** — only names, plus five real resource OCIDs and one public SSH key, which are identifiers, not credentials. Eight findings filed above (F1–F8); none requires credential rotation. Follow-ups are config hygiene (F1–F6), a coordinator decision (F7), and a recorded distribution note (F8).
