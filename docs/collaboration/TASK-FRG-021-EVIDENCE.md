# TASK-FRG-021 — Evidence

**Task:** Forge: per-interface binding in the parallel range-chunk downloader
**Worker:** Muse TP9 · **Claim:** hub #2045 comment 7217517025 (2026-11-27 ~17:20 IST)
**Assignment:** WATCH218 §C + Burn Enforcer 17:01 §C (formal claim owed; stated as next 16:20)
**Board at claim (live main `b7f81118`, read first-hand):** TASK-FRG-021 AVAILABLE / owner muse_tp9 / P2, branch null, pr null
**Acceptance:** `parallel_download` can bind chunk streams to named interfaces
(per-interface source routing / SO_BINDTODEVICE, modelled on Plexo) where more
than one exists, with tests; single-link behaviour unchanged.

## Implementation

`Forge/forge_upgrade/parallel_download.py` (+133/-56 lines, stdlib only, no new
dependency):

- `download(..., interfaces=["eth0", "wlan0"])` — chunk *i* is fetched on
  `interfaces[i % len(interfaces)]` (round-robin); the probe and the plain
  fallback use the first named interface. `interfaces` omitted (default) runs
  the exact previous code path — one unbound transport for every request.
- `make_bound_transport(interface)` builds a urllib transport whose sockets are
  bound with `SO_BINDTODEVICE` before connect: custom `HTTPHandler` /
  `HTTPSHandler` opening `_BoundHTTPConnection` / `_BoundHTTPSConnection`
  subclasses, whose `connect()` calls `_create_bound_socket()` — getaddrinfo
  loop mirroring `socket.create_connection`, `setsockopt(SOL_SOCKET,
  SO_BINDTODEVICE, b"<iface>")` before `connect()`. Linux only; binding needs
  CAP_NET_RAW (normally root).
- `interface_transport` parameter is the factory seam (default
  `make_bound_transport`); tests inject a recording factory instead of real
  sockets. `DownloadReport` gains `interfaces: tuple[str, ...]` (default `()`,
  backward compatible).
- Validation up front: a single string, an empty name, or a non-string name
  raises `ValueError` before any network. A bind failure is never silently
  downgraded to an unbound socket: chunk fetches retry then raise
  `DownloadError`; the probe surfaces the transport's `OSError`/`URLError`
  (same as any other probe transport failure today).

`Forge/tests/test_frg021_interface_binding.py` (new, 11 tests, hermetic fake
transports, no network, no root):

- round-robin distribution over `["eth0", "wlan0"]` (4 chunks: 0→eth0,
  4096→wlan0, 8192→eth0, 12288→wlan0), probe on the first interface, payload +
  SHA-256 verified, `report.interfaces == ("eth0", "wlan0")`;
- single interface binds every chunk; plain fallback (Range unsupported) uses
  the first interface only; no-interfaces path never builds a bound transport
  and reports `interfaces == ()`;
- bind failure (factory raising `PermissionError` on chunk fetches) raises
  `DownloadError` and writes nothing; invalid `interfaces` rejected
  (`ValueError`, 4 parametrised cases);
- socket-level: `_create_bound_socket` issues
  `setsockopt(SOL_SOCKET, SO_BINDTODEVICE, b"eth0")` before `connect()` (fake
  socket + patched getaddrinfo); the bound connection class binds before
  connect (`b"wlan0"`).

## Verification (local, this VM)

Python 3.12.3, pytest 9.2.0, hermetic scratch tree of the two Forge files
(no conftest — the suite conftest needs the full app stack; CI runs the real
suite):

```
19 passed — 8 pre-existing test_ig2_frg04_parallel_download.py + 11 new
test_frg021_interface_binding.py
```

## Live proof (real HTTP + real SO_BINDTODEVICE, this VM, root, 2026-11-27 ~17:55 IST)

Range-honouring local HTTP server on 127.0.0.1, 3 MiB deterministic payload:

- `interfaces=["lo"]` → **parallel, 3 chunks, SHA-256 match, bytes identical** —
  real bound sockets end to end over real HTTP.
- `interfaces=["nope0"]` (negative control) → fails loudly, no silent
  fallback: `URLError: could not connect to 127.0.0.1:35371 via interface
  'nope0': [Errno 19] No such device`; **no file left** at dest.
- No `interfaces` (default) → **parallel, 3 chunks, `interfaces == ()`** —
  single-link behaviour unchanged against the same server.

## Limits (stated, not hidden)

- Multi-interface distribution is proven at the transport-selection level
  (recording factory: each chunk's Range request rides its assigned
  interface's transport) plus a single-interface live proof (`lo`). This VM
  has only `lo` + `host0`, so a two-uplink fleet host was not available to
  prove two live interfaces carrying different chunks simultaneously.
- `SO_BINDTODEVICE` needs CAP_NET_RAW; on a host without it the download
  fails loudly (see the `nope0` control) rather than silently using the
  default route — by design.
- No board hunk in this PR: board flips ride the coordinator board PR
  (established pattern).
