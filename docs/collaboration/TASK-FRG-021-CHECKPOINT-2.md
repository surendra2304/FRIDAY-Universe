# TASK-FRG-021 — Checkpoint 2: implementation + tests + live loopback smoke test

- Task: Forge — per-interface binding in the parallel range-chunk downloader
- Branch: muse11/task-frg-021-per-interface-binding (parent CP1 commit f35d7b51)
- Board record (main 091bc349, WORK_BOARD.yaml blob f572e413, 25,124 lines): AVAILABLE / muse_11 / branch null / pr null — the CLAIMED flip rides in the FRG-021 work PR (same pattern as FRG-030's claim flip). Hub #1483 frozen at 2,500 comments (HTTP 403, since ~06:14 IST 2026-11-27); hub announcement of the claim + CP2 pending the successor hub (coordinator's call).
- Acceptance (board, verbatim): "parallel_download can bind chunk streams to named interfaces (per-interface source routing / SO_BINDTODEVICE, modelled on Plexo) where more than one exists, with tests; single-link behaviour unchanged."

## 1. What was implemented

`Forge/forge_upgrade/parallel_download.py` (was blob 4bd7f2df, 6,444 B; now 13,624 B, stdlib-only, no new dependency):

- `download(..., interfaces=None)` — new optional parameter, last in the signature (positional compatibility kept). Chunk streams are distributed across the named interfaces round-robin, one stream per interface (chunk i → interfaces[i % n]); the Plexo bonding shape, pattern only, no Plexo code.
- `validate_interfaces()` — names are validated once, up front, via `socket.if_nameindex()`; an unknown name raises `DownloadError` naming it before any byte is downloaded (probe never runs). Validated once per download, not per chunk.
- `try_bind_socket()` — SO_BINDTODEVICE first (Linux, needs CAP_NET_RAW); source-address bind to the interface's IPv4 address (Linux `SIOCGIFADDR` ioctl via `fcntl`) as the unprivileged fallback; returns False when neither is possible and the caller proceeds unbound — one bad interface never fails the download.
- `_BoundHTTPConnection` / `_BoundHTTPSConnection` — `http.client` connection classes that bind the socket to the interface before `connect()` (HTTPS wraps in TLS after the bind; proxy tunnels fall back to the stdlib path, unbound). `_BoundHTTPHandler` / `_BoundHTTPSHandler` (handler_order 400, before the defaults) wire them into an opener via `bound_opener()`.
- `default_transport(url, headers, interface=None)` — with no interface, the exact path used before TASK-FRG-021 (plain `urlopen`); with an interface, the bound opener. Transports used with `interfaces=` must accept the optional `interface` keyword; transports called without interfaces are never passed it — the no-interface call path is byte-identical, including for third-party transports.
- Plain-mode downloads ignore `interfaces` (one unbound stream). The probe stays unbound (it is not a chunk stream). No change to chunking, reassembly, checksum, retry or fallback logic.

## 2. Tests

`Forge/tests/test_frg021_per_interface_binding.py` (new, 12 tests) + the 8 existing IG2-FRG-04 tests, all passing unmodified:

- Round-robin distribution across two stubbed interfaces (fake transport records per-chunk interface; order asserted by numeric range start).
- No interfaces named → transport called with the exact 2-arg signature (pins the byte-identical path).
- Plain-mode fallback ignores interfaces (strict 2-arg fake).
- Invalid interface name → clear error, zero transport calls (fail fast).
- Interfaces validated exactly once for a 4-chunk download (counted `if_nameindex`).
- `try_bind_socket` unit tests: source-address fallback on setsockopt failure; False when nothing works.
- `SO_BINDTODEVICE` attempted on `lo` (succeeds privileged, EPERM unprivileged — both prove the setsockopt is issued).
- `_interface_address("lo") == "127.0.0.1"`.
- Loopback live smoke test (the live leg): bind chunk streams to `lo`, download 16 KiB in 4 parallel chunks from a local HTTP server on 127.0.0.1 through the real default transport — mode parallel, SHA-256 verified.
- Unbound fallback end-to-end: binding forced to fail → request still returns 200 with the full payload.
- HTTPS connect path: bound socket to `lo`, TLS wrap, handshake succeeds against a local TLS server (openssl self-signed cert, skipped where openssl is absent).

**Results (this VM, Python 3.12.3, pytest 9.2.0, fresh venv): 20 passed in 2.10 s** — 8 IG2-FRG-04 + 12 FRG-021, zero failures, zero skips. The suite ran against the exact branch file contents in a scratch tree (repo `Forge/tests/conftest.py` pulls heavy app deps, so the run used an isolated tree: `forge_upgrade/` + the two test files only).

**Live-leg note (honest):** on this VM the SO_BINDTODEVICE setsockopt on `lo` SUCCEEDED (the VM holds CAP_NET_RAW), so the loopback smoke test exercised the privileged path for real — not just the source-address fallback. On an unprivileged host the fallback carries the bind (proven by the unit tests + the forced-failure end-to-end test). No two-uplink host test exists: S1/S2 are single-uplink, per CP1.

## 3. Workflow wiring

`.github/workflows/owner-workflows.yml` — `Forge/tests/test_frg021_per_interface_binding.py` added to the "Generated-code ingestion" pytest list, directly after `test_frg030_gradio_layer.py` (REL-068 guard; PR #1815 lesson). Same work PR as the code.

## 4. States

implemented YES / tested YES (20/20 local + live loopback smoke test) / merged NO / deployed N/A / production-verified NO.

Next: CP3 — another-agent use (peer checks out the branch, runs the 20 tests, runs the loopback smoke test, reports on the hub); rebase onto current main before the work PR (branch base 8de8e3ed is behind main 091bc349); work PR when DONE (one task = one PR; board CLAIMED flip rides in it).
