# TASK-OPS-003 — Oracle sniper allocation loop, end-to-end verification

**Auditor:** Muse 4 · **Date:** 2026-11-22 ~05:53 IST · **Task:** TASK-OPS-003
(MASTER_PLAN §6, pool 2 item 11) · **PR:** #1275 · **Branch:**
`muse4/task-ops-003-oracle-sniper-allocation-loop`

## Verdict

**Verified end-to-end up to the capacity gate.** The allocation loop is alive
and hunting on three runners, its decision logic is traced from inventory to
launch attempt, and the deployed code is byte-identical to main. Allocation
itself has never succeeded: Oracle's free A1 pool in `ap-hyderabad-1` answers
every launch attempt `Out of host capacity`, and the tenancy API throttle
bucket is saturated — 33 of the last 33 systemd-allocator cycles ended in
HTTP 429. The success branch (`launch_accepted` → `PROVISIONING` → `RUNNING`)
is code- and test-verified only; it has never been observed live.

No paid allocation was made, no live change was made, and no allocation was
triggered by this audit. All live evidence below is read-only (bridge
`get_system_info` / `run_shell` status reads, GitHub Actions API reads).

## What it allocates

One `VM.Standard.A1.Flex` instance, display name `FRIDAY Universe ARM`:

| Setting | Value | Source |
|---|---|---|
| Shape | `VM.Standard.A1.Flex` | `FRIDAY/scripts/oci_a1_common.py:6` |
| Size | 2 OCPUs / 12 GB RAM / 50 GB boot | `oci_a1_common.py:7-9` |
| Region / AD | `ap-hyderabad-1` / `qvRd:AP-HYDERABAD-1-AD-1` | `oci_a1_common.py:10-11` |
| Image | Ubuntu 24.04 (`ocid1.image…3nmlua`) | `oci_a1_common.py:13` |
| Subnet | `ocid1.subnet…cfudibq`, public IP assigned | `oci_a1_common.py:12` |
| Compartment | `FRIDAYArmWorkloads` | `FRIDAY/docs/OCI_A1_CONTINUOUS_ALLOCATOR.md` |
| Auth | OCI Instance Principals (systemd allocator); long-lived API key (GitHub snipers) | see §2 |

The 2 OCPU / 12 GB size matches the tenancy's real Always Free A1 limits read
from the OCI Limits API 2026-11-14 (`standard-a1-core-count = 2`,
`standard-a1-memory-count = 12`); Oracle cut the allowance from 4/24 on
2026-06-15. The target is a third host: the fleet's two running VMs are AMD
E2 shapes, not A1.

## How the loop decides

### 1. Systemd allocator — the production mechanism

`FRIDAY/scripts/oci_a1_continuous.py`, run as
`friday-oci-a1-allocator.service` (`FRIDAY/systemd/friday-oci-a1-allocator.service`)
on server 1, `Restart=on-failure`, `RestartSec=15s`. One cycle
(`ContinuousAllocator.attempt_once`, `oci_a1_continuous.py:240`):

1. **Inventory** — lists instances in the tenancy root **and** the target
   compartment (OCI list APIs are not recursive), paginated, de-duplicated by
   OCID (`oci_a1_continuous.py:268-282`).
2. **Existing A1 found** (`find_active_a1`, `oci_a1_common.py:21-28` — any
   non-`TERMINATED` A1):
   - `RUNNING` at target size → `allocated_running`, process exits 0 (service
     stays stopped: success, not a restart case).
   - `STOPPED` → `instance_action(START)`, recheck in 20 s.
   - `PROVISIONING`/`STARTING`/`STOPPING`/`TERMINATING` → recheck in 20 s.
   - Below target size, or an unrelated display name → `manual_review`,
     300 s backoff; never launches a duplicate.
3. **Subnet / image** must be `AVAILABLE` or the cycle records
   `configuration_error` (300 s).
4. **Capacity report** (`create_compute_capacity_report`) for the shape/size.
   - No `AVAILABLE` candidates → launch attempts across all four fault-domain
     candidates (`None`, `FAULT-DOMAIN-1/2/3`), rotated by a persisted cursor
     (`rotate_candidates`, `oci_a1_common.py:59`; cursor in
     `/var/lib/friday-arm-sniper/state.json`).
   - `AVAILABLE` candidates → launch per reported fault domain, same rotation.
5. **Launch** — one `launch_instance` per fault domain with a stable
   per-target/fault-domain idempotency token (SHA-256 of target + subnet +
   image + SSH-key fingerprint; the no-report path additionally buckets by
   minute). `OutOfHostCapacity` → next fault domain. Any other error aborts
   the cycle to the outer handler.
6. **Backoffs** — no capacity 60 s, pending instance 20 s, transient error
   120 s, rate limit (429) 180 s, auth/config error 300 s
   (`oci_a1_continuous.py:38-41`, `error_delay` at `:82`).
7. **Observability** — journal via `friday.oci_a1_allocator` logger; latest
   non-secret outcome atomically written to
   `/var/lib/friday-arm-sniper/state.json` (`persist_state`).

Preflight (`FRIDAY/scripts/oci_a1_preflight.py`, fail-closed, run by the
installer) checks inventory, subnet, image and capacity-report permission
before the service is enabled; it never launches. Installer:
`FRIDAY/scripts/install_oci_a1_continuous.sh` (pins `oci==2.188.0`).

### 2. GitHub Actions snipers — still running in parallel

`FRIDAY/scripts/oracle_retry.py`, driven by two hourly staggered workflows
(`.github/workflows/oracle-capacity-sniper.yml` on the hour,
`oracle-capacity-sniper-worker2.yml` at :30), each up to 6 h per job
(`RUN_DURATION_MINUTES: 320`) with a relay dispatch to the next runner at
the threshold. Differences from the systemd allocator:

- Four-rung size ladder (2/12, 1/6, 2/8, 1/4) with live in-place upgrade to
  2/12 once a smaller instance is secured.
- Authenticates with long-lived OCI API-key secrets
  (`OCI_USER_OCID` / `OCI_KEY_CONTENT` / `OCI_FINGERPRINT`, plus a `_2` set
  for worker 2) instead of Instance Principals.
- Success path posts a GitHub issue titled `Oracle Ampere ARM Server Claimed
  (<public-ip>)` and writes the job summary. **No such issue exists**
  (GitHub search, 2026-11-22 ~05:50 IST: 0 results) — no allocation has ever
  succeeded through either mechanism.
- Its cloud-init installs Dokploy and opens ports 80/443/3000 — stale against
  current production (systemd + Caddy; Dokploy not running, per repo
  `AGENTS.md`).

## Live evidence (read-only, 2026-11-22 ~05:47–05:53 IST)

- **Fleet:** both Oracle servers ONLINE (bridge `get_system_info`).
- **Systemd allocator, server 1:** `active (running)` since Tue 2026-11-17
  20:11:06 IST (4+ days), main PID 3077924,
  `/opt/friday-arm-sniper/venv/bin/python -m scripts.oci_a1_continuous`,
  1.0M memory, CPU 1h 30min, `NRestarts=0`.
- **Current state** (`/var/lib/friday-arm-sniper/state.json`,
  `updated_at 2026-11-22T00:16:30Z`): outcome `retrying_after_error`,
  `http_status 429`, `diagnostic_code TooManyRequests`, `retry_seconds 180`,
  `candidate_cursor 2`, target 2 OCPU / 12 GB / 50 GB, region
  `ap-hyderabad-1`, shape `VM.Standard.A1.Flex`.
- **Recent journal** (retained window only, see G5): 33 of 33 cycles in the
  window ended `retrying_after_error` (429, 180 s backoff). 10 launch
  attempts got through, all answered `Out of host capacity` — 4×
  `FAULT-DOMAIN-1`, 3× `FAULT-DOMAIN-2`, 3× `FAULT-DOMAIN-3`. Zero
  `launch_accepted`, `allocated_running`, `manual_review`,
  `configuration_error` or `capacity_report_unusable` outcomes in the window.
- **Deployed code == main:** SHA-256 of the installed
  `oci_a1_continuous.py`, `oci_a1_common.py`, `oci_a1_preflight.py` and the
  service unit on server 1 match main `ecea58ef` exactly (installed
  2026-11-17 20:02; `oci` 2.188.0 as pinned; `/etc/friday-arm-sniper.env`
  root-owned, mode 0600).
- **GitHub snipers:** worker 1 run 44947536172 `in_progress` since
  2026-11-21T20:40:39Z; worker 2 run 44949876243 `in_progress` since
  2026-11-21T21:07:27Z; a scheduled worker-1 run 44962738003 `pending`.
  Latest completed worker-1 run 44918363063 `success` 2026-11-21 15:17–20:40Z
  (5h23m ≈ the 320-minute relay threshold — a relay handoff, not a claim).
- **Tests:** all 34 allocator tests pass on main
  (`test_oci_a1_common.py` 5, `test_oci_a1_continuous.py` 16,
  `test_oci_a1_fd_rotation.py` 9, `test_oci_a1_preflight.py` 4) — run locally
  2026-11-22 ~05:52 IST in a throwaway venv (`--noconftest`; the FRIDAY
  conftest needs the app venv). The files carry no pytest markers, so FRIDAY
  CI (`pytest -m "not live and not hardware and not windows"`,
  `FRIDAY/.github/workflows/ci.yml:50`) collects them; the installer syntax
  is also checked there (`ci.yml:46-47`).

## Gaps filed (exact file/line)

- **G1 — Doc says the GitHub sniper schedules "are removed"; they are not.**
  `FRIDAY/docs/OCI_A1_CONTINUOUS_ALLOCATOR.md:7`: "The former primary and
  fallback workflow schedules are removed to prevent duplicate allocation
  attempts." Both workflow files still exist and both have live runs right
  now (worker 1 run 44947536172, worker 2 run 44949876243, both
  `in_progress`). The same doc contradicts itself at line 11 ("The GitHub
  snipers still run in parallel for now — retiring them is a separate
  decision"). Fix: correct line 7 to the live state, or retire the workflows;
  the retirement decision is still open.
- **G2 — Auth failure can be misreported as no-capacity.**
  `FRIDAY/scripts/oci_a1_continuous.py:69-77` (`is_capacity_error`) treats
  status 404 with "not authorized or not found" in the message as a capacity
  error, and the no-report-candidates launch loop (`:436`) swallows it as
  capacity exhaustion and records `no_capacity` (`:450-458`). That
  contradicts the doc (`OCI_A1_CONTINUOUS_ALLOCATOR.md:16`): "An
  authorization failure … is not misreported as unavailable capacity."
  (The available-candidates path does not share this: a 404 there raises to
  the outer handler and retries as a transient error.) Fix: exclude
  auth/404 from `is_capacity_error`, or record a distinct
  `authorization_error` outcome in that loop. Also note `capacity_exhausted`
  (`:373`, set `True` at `:442`) is never read — the record is `no_capacity` either way.
- **G3 — GitHub sniper's duplicate guard is weaker than the systemd
  allocator's.** `FRIDAY/scripts/oracle_retry.py:67-73`
  (`check_active_arm_instance`): single-compartment, single-page
  `list_instances` (no pagination helper, tenancy root not listed), and the
  lifecycle filter `["PROVISIONING", "RUNNING", "STARTING"]` misses a
  `STOPPED` A1 — a stopped target would be treated as "no instance" and a
  duplicate launch attempted (the tenancy limit may or may not reject it;
  the code itself has no guard). The systemd allocator fixed both points
  (lists root + target compartment with pagination; any non-`TERMINATED` A1
  counts, `STOPPED` triggers `START`). Fix: port the same guard, or retire
  the GitHub snipers (see G1/G6).
- **G4 — Telemetry helper is broken as written.**
  `scripts/oci_arm_sniper.py:13`: `SSH_KEY = r"USER_HOME\.ssh\friday_universe_oracle.key"`
  is a literal Windows-style path, not an existing key file on Linux, so
  `ssh -i` fails and the "24/7 OCI ARM SNIPER TELEMETRY" output is empty.
  `CLOUD_HOST` (`:14`) is hardcoded to `140.245.208.100`. Fix: expand the
  real key path (or drop the helper in favour of the bridge `run_shell`
  status read used by this audit).
- **G5 — Allocator journal history is ~2 hours deep.**
  On server 1 the `friday-oci-a1-allocator` journal retains only 80 lines,
  earliest 2026-11-22 04:03:23 IST (~105 min before this audit). Only the
  latest outcome survives in `state.json`, so allocator behaviour older
  than ~2 h cannot be reconstructed from the host. Fix (follow-up): persist
  a compact outcome history (e.g. append outcomes to a rotated log, or keep
  `state.json` history) if multi-day diagnosis is wanted.
- **G6 — Throttle contention: three hunters, one bucket, no coordination.**
  The doc acknowledges the shared tenancy API throttle bucket
  (`OCI_A1_CONTINUOUS_ALLOCATOR.md:11`) and claims the 180 s backoff
  "absorbs the contention" — the live data says otherwise: 33/33 recent
  systemd cycles ended in 429, so the allocator's effective cadence is
  ~3.2 min per attempt instead of the designed 60 s, and only ~10 launch
  attempts got through in ~105 min. The two GitHub snipers (both `in_progress`,
  ~30–45 s cycles each) are the likely main consumers of the bucket.
  Fix (follow-up, owner/coordinator decision): retire the GitHub snipers now
  that the systemd allocator is the production mechanism (see G1), or
  stagger/throttle them; re-measure the 429 rate afterwards.

## Acceptance

- [x] Sniper allocation loop verified end-to-end with evidence (above) — up
  to the capacity gate; the precise blocker is Oracle free-pool capacity
  (`Out of host capacity` on every launch attempt) compounded by throttle
  contention (G6). The success branch is unobserved live, by the same
  blocker.
- [x] Gaps filed with the exact file/line and the fix or follow-up (G1–G6
  above).

## Scope notes

- Free-only: no paid allocation, no live change, no allocation triggered.
  No secret was read, printed, logged or stored. The SSH public key and
  resource OCIDs quoted are the non-secret values already in the repo.
- Not verified live: the `launch_accepted` → `PROVISIONING` → `RUNNING`
  path (needs Oracle to grant capacity); the tenancy A1 limits (taken from
  the 2026-11-14 Limits-API read recorded in the allocator doc, not re-read).
