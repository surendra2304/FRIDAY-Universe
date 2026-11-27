# TASK-FRG-021 — Checkpoint 1: scope + file map + test plan

- Task: Forge — per-interface binding in the parallel range-chunk downloader
- Board record (main 8de8e3ed, WORK_BOARD.yaml lines 19911–19929): AVAILABLE / muse_11 / branch null / pr null, P2, created 2026-11-24, updated 2026-11-25T12:47:00+05:30
- Claim: branch-recorded (branch muse11/task-frg-021-per-interface-binding @ main 8de8e3ed, verified via ref GET); hub announcement PENDING — hub #1483 froze at 2,500 comments (HTTP 403, ~06:14 IST 2026-11-27); successor hub owed by the coordinator. When it is declared, post the claim + FRG-030 completion status there.
- Acceptance (board, verbatim): "parallel_download can bind chunk streams to named interfaces (per-interface source routing / SO_BINDTODEVICE, modelled on Plexo) where more than one exists, with tests; single-link behaviour unchanged."
- Source (board evidence): filed by Muse (coordinator) 2026-11-24 under the owner's implementation-push order (19:38 IST); GAP-LIST.md section 2, TASK-FRG-BIND (IG package F-D1); assigned to Muse 11 by the coordinator (watch085), queue position 3 behind STR-078 and FRG-030.

## 1. Scope

In scope:
- `Forge/forge_upgrade/parallel_download.py` — interface binding only.
- One new test file + workflow wiring for it.
- This evidence doc.

The binding, as designed for CP2:
- Chunk streams are distributed across the named interfaces, round-robin, one stream per interface — the Plexo bonding shape (Plexo bonds Wi-Fi + Ethernet + tethered phone on one desktop; here the streams are the unit that moves across interfaces).
- Mechanism: SO_BINDTODEVICE on Linux where permitted, with source-address binding (bind the socket to the interface's IP) as the unprivileged fallback; per-chunk graceful fallback to unbound when binding is not possible, so one bad interface never fails the download.
- Interface names are validated once, up front — an invalid name fails fast with a clear error before any byte is downloaded.

Out of scope:
- Plexo code: none vendored — pattern only, per the INT-044 disposition (main 98b1ce8d: "pattern-mined ... no upstream code vendored").
- Any change to chunking, reassembly, checksum, retry or fallback logic.
- Any change to single-link behaviour: with no interfaces named, `download()` takes the byte-identical code path it takes today.
- Live multi-uplink proof on the fleet: S1/S2 are single-uplink VMs. The live leg is a loopback binding smoke test (see section 4); a real two-uplink host test is out of scope for this task.

Flag (not blocking): the board evidence cites GAP-LIST.md section 2 TASK-FRG-BIND, but no GAP-LIST.md exists in the tree at main 8de8e3ed and no FRG-BIND reference is found anywhere under docs/. The board record is the authoritative acceptance.

## 2. Current state (verified first-hand on main 8de8e3ed)

- `Forge/forge_upgrade/parallel_download.py` (blob sha 4bd7f2dfad4a9661d427fcd29ad693398326b36b, 6,444 B): stdlib-only (urllib + threads), injectable transport. Flow: probe (Range bytes=0-0) → plan_chunks → ThreadPoolExecutor parallel fetch → reassemble in order → SHA-256 verify. `default_transport` opens sockets through `urllib.request.urlopen` with a 120 s timeout and no interface selection.
- No SO_BINDTODEVICE, bind_to_device, or source_address anywhere in Forge — the binding is greenfield.
- `Forge/tests/test_ig2_frg04_parallel_download.py`: 8 tests, all against in-memory fake transports, no network (parallel reassembly, checksum + deletion on mismatch, chunk retries, plain fallback when Range is unsupported or ignored, small-file plain mode, persistent chunk failure). These must pass unmodified.
- `.github/workflows/owner-workflows.yml` (line ~179) lists `Forge/tests/test_frg030_gradio_layer.py` in the "Generated-code ingestion" pytest list — the new FRG-021 test file must be added there in the same work PR (REL-068 guard; PR #1815 lesson).
- `Forge/forge_upgrade/__init__.py` carries no exports — no export change needed. No requirements change (stdlib only: `socket` is stdlib).

## 3. File map

- `Forge/forge_upgrade/parallel_download.py` — MODIFY (CP2): add an `interfaces` parameter to `download()`; a binding helper (resolve a named interface; SO_BINDTODEVICE with source-address fallback); a transport factory that binds each chunk stream to an interface round-robin; fail-fast validation of interface names; per-chunk unbound fallback on binding failure.
- `Forge/tests/test_frg021_per_interface_binding.py` — NEW (CP2): the tests in section 4. Add to the contracts workflow pytest list in the same PR.
- `docs/collaboration/TASK-FRG-021-CHECKPOINT-1.md` — this doc.
- No other files.

## 4. Test plan

Fake-transport unit tests (no network, no privileges — a fake transport records which interface each chunk was bound to):
1. Interfaces named → chunk streams distributed across them round-robin.
2. No interfaces named / one interface → unbound; the 8 IG2-FRG-04 tests pass unmodified (single-link behaviour unchanged).
3. Binding failure on one interface → that chunk falls back to unbound; the download still completes.
4. Plain-mode fallback ignores interfaces (single stream, unbound).
5. Invalid interface name → clear error before any download (fail fast).
6. Interface list validated once, not per chunk.

Loopback live smoke test (the live leg): bind to `lo` and download from a local HTTP server on 127.0.0.1 — proves the SO_BINDTODEVICE path end-to-end on Linux without needing two real uplinks. Skips cleanly where SO_BINDTODEVICE is unavailable (non-Linux / unprivileged) — skip, not fail.

Live multi-uplink proof is NOT available on the fleet (S1/S2 single-uplink). The acceptance's "where more than one exists" is proven by the fake-transport distribution test plus the loopback smoke test.

## 5. States

implemented NO / tested NO / merged NO / deployed N/A / production-verified NO.

Next: CP2 — implementation + tests + live loopback smoke test.
