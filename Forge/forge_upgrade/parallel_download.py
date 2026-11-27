"""Parallel range-chunk downloader for Forge (TASK-IG2-FRG-04).

Pattern adopted from Plexo (anmolkapil/plexo, MIT) — only the chunking
pattern transfers to a cloud fleet; Plexo's multi-connection bonding
(Wi-Fi + Ethernet + tethered phone on one desktop) does not apply to
single-uplink VMs, and none of Plexo's code is used.

Behaviour:
* probe the URL once; if the server honours HTTP Range and the total
  size is known and worth splitting, download byte ranges in parallel,
  retrying failed chunks, then reassemble in order;
* if Range is unsupported, ignored, the size is unknown, or the file is
  small, fall back to one plain streaming download — the caller always
  gets either the complete file or an exception, never a partial one
  presented as complete;
* an expected SHA-256, when supplied, is verified after reassembly and
  a mismatch deletes the output and raises.

Per-interface binding (TASK-FRG-021): pass ``interfaces`` with the
names of the host interfaces the chunk streams may use (e.g.
``["eth0", "wlan0"]``). Chunk *i* is fetched on
``interfaces[i % len(interfaces)]`` through a socket bound with
SO_BINDTODEVICE (Linux; needs CAP_NET_RAW, i.e. normally root) — the
per-interface source routing Plexo models. The probe and the plain
fallback use the first named interface. With ``interfaces`` omitted,
behaviour is exactly as before: one unbound transport for every
request, single-link behaviour unchanged.

Stdlib only (urllib + threads): no new dependency, no resident service.
The transport is injectable so tests exercise every branch without a
network.
"""
from __future__ import annotations

import hashlib
import http.client
import socket
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CHUNK_BYTES = 4 * 1024 * 1024
DEFAULT_WORKERS = 4
DEFAULT_MIN_PARALLEL_BYTES = 1024 * 1024  # below this, one stream wins
DEFAULT_RETRIES = 3

# One HTTP GET returning (status, headers, body). Injectable in tests.
Transport = Callable[[str, dict[str, str]], tuple[int, dict[str, str], bytes]]


class DownloadError(RuntimeError):
    """A download failed in a way the fallback could not repair."""


@dataclass(frozen=True, slots=True)
class ProbeResult:
    size: int | None  # None when the server does not disclose a length
    accepts_ranges: bool


@dataclass(slots=True)
class DownloadReport:
    url: str
    dest: str
    size: int
    sha256: str
    mode: str  # "parallel" | "plain"
    chunks: int
    interfaces: tuple[str, ...] = ()  # named interfaces bound, if any


def _request(url: str, headers: dict[str, str] | None = None) -> urllib.request.Request:
    return urllib.request.Request(url, headers=headers or {}, method="GET")


def default_transport(url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    """One HTTP GET returning (status, headers, body). Injectable in tests."""
    with urllib.request.urlopen(_request(url, headers), timeout=120) as resp:
        return resp.status, dict(resp.headers.items()), resp.read()


def _create_bound_socket(
    host: str,
    port: int,
    timeout: float | None,
    interface: str,
    source_address: tuple[str, int] | None = None,
) -> socket.socket:
    """Open a TCP socket to (host, port) bound to ``interface``.

    Sets SO_BINDTODEVICE before connect, so the kernel routes the
    connection out of the named interface. Mirrors
    ``socket.create_connection`` (tries each getaddrinfo result in turn).
    Raises OSError when no address connects — including the EPERM a
    bind without CAP_NET_RAW produces — so the caller can retry or fail
    loudly rather than silently fall back to an unbound socket.
    """
    bind_opt = getattr(socket, "SO_BINDTODEVICE", None)
    if bind_opt is None:
        raise DownloadError("SO_BINDTODEVICE is not available on this platform")
    last_error: OSError | None = None
    for family, socktype, proto, _canon, sockaddr in socket.getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    ):
        sock = socket.socket(family, socktype, proto)
        try:
            sock.setsockopt(socket.SOL_SOCKET, bind_opt, interface.encode("utf-8"))
            if isinstance(timeout, (int, float)):
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()
    raise OSError(
        f"could not connect to {host}:{port} via interface {interface!r}: {last_error}"
    )


def _bound_connection_classes(interface: str):
    """HTTP(S)Connection subclasses whose sockets bind to ``interface``."""
    class BoundHTTPConnection(http.client.HTTPConnection):
        def connect(self) -> None:
            self.sock = _create_bound_socket(
                self.host, self.port, self.timeout, interface, self.source_address
            )
            if self._tunnel_host:
                self._tunnel()

    class BoundHTTPSConnection(http.client.HTTPSConnection):
        def connect(self) -> None:
            self.sock = _create_bound_socket(
                self.host, self.port, self.timeout, interface, self.source_address
            )
            if self._tunnel_host:
                self._tunnel()
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)

    return BoundHTTPConnection, BoundHTTPSConnection


class _BoundHTTPHandler(urllib.request.HTTPHandler):
    """HTTPHandler opening connections bound to one interface."""

    def __init__(self, interface: str, debuglevel: int = 0) -> None:
        super().__init__(debuglevel)
        self._interface = interface

    def http_open(self, req):  # type: ignore[no-untyped-def]
        http_class, _ = _bound_connection_classes(self._interface)
        return self.do_open(http_class, req)


class _BoundHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPSHandler opening connections bound to one interface."""

    def __init__(self, interface: str, debuglevel: int = 0, context=None, check_hostname=None) -> None:
        super().__init__(debuglevel, context, check_hostname)
        self._interface = interface

    def https_open(self, req):  # type: ignore[no-untyped-def]
        _, https_class = _bound_connection_classes(self._interface)
        return self.do_open(
            https_class, req, context=self._context, check_hostname=self._check_hostname
        )


def make_bound_transport(interface: str) -> Transport:
    """Build a transport whose sockets are bound to ``interface``.

    Linux only; binding needs CAP_NET_RAW (normally root). A bind
    failure surfaces from the transport as OSError and is retried /
    raised by the chunk fetcher like any other transport failure —
    never silently downgraded to an unbound socket.
    """
    opener = urllib.request.build_opener(
        _BoundHTTPHandler(interface), _BoundHTTPSHandler(interface)
    )

    def bound_transport(url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        with opener.open(_request(url, headers), timeout=120) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()

    return bound_transport


def probe(url: str, transport=default_transport) -> ProbeResult:
    """Ask for byte 0 only and learn size + Range support from the reply."""
    status, headers, _ = transport(url, {"Range": "bytes=0-0"})
    lowered = {k.lower(): v for k, v in headers.items()}
    if status == 206:
        # Content-Range: bytes 0-0/<total>
        total = lowered.get("content-range", "").rsplit("/", 1)[-1]
        return ProbeResult(
            size=int(total) if total.isdigit() else None, accepts_ranges=True
        )
    length = lowered.get("content-length", "")
    return ProbeResult(
        size=int(length) if length.isdigit() else None, accepts_ranges=False
    )


def plan_chunks(size: int, chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> list[tuple[int, int]]:
    """Split ``size`` bytes into inclusive (start, end) range chunks."""
    if size <= 0:
        return []
    return [
        (start, min(start + chunk_bytes, size) - 1)
        for start in range(0, size, chunk_bytes)
    ]


def _fetch_chunk(
    url: str, start: int, end: int, transport, retries: int
) -> bytes:
    expected = end - start + 1
    last_error: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            status, _, body = transport(url, {"Range": f"bytes={start}-{end}"})
            if status == 200 and len(body) == expected:
                # Server ignored Range but returned exactly this slice —
                # only possible for a single-chunk file; accept it.
                return body
            if status != 206:
                raise DownloadError(f"range request answered with HTTP {status}")
            if len(body) != expected:
                raise DownloadError(
                    f"chunk {start}-{end}: got {len(body)} of {expected} bytes"
                )
            return body
        except Exception as exc:  # retry slow/failed tail chunks
            last_error = exc
    raise DownloadError(f"chunk {start}-{end} failed after retries: {last_error}")


def _plain_download(url: str, transport) -> bytes:
    status, _, body = transport(url, {})
    if status != 200:
        raise DownloadError(f"plain download answered with HTTP {status}")
    return body


def download(
    url: str,
    dest: str | Path,
    expected_sha256: str | None = None,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
    workers: int = DEFAULT_WORKERS,
    min_parallel_bytes: int = DEFAULT_MIN_PARALLEL_BYTES,
    retries: int = DEFAULT_RETRIES,
    transport=default_transport,
    interfaces: Sequence[str] | None = None,
    interface_transport: Callable[[str], Transport] | None = None,
) -> DownloadReport:
    """Download ``url`` to ``dest``, in parallel chunks when worthwhile.

    Falls back to a plain download whenever Range cannot be used.
    Raises DownloadError on failure or checksum mismatch; on raise,
    no file is left at ``dest``.

    ``interfaces`` names the host interfaces chunk streams may use
    (TASK-FRG-021): chunk *i* is fetched on
    ``interfaces[i % len(interfaces)]`` through a socket bound with
    SO_BINDTODEVICE; the probe and the plain fallback use the first
    named interface. Omit it for the single-link behaviour (one
    unbound transport for every request). ``interface_transport`` is
    the factory building a transport bound to one interface
    (default ``make_bound_transport``); tests inject a recording
    factory instead of real sockets.
    """
    if interfaces is not None:
        if isinstance(interfaces, str):
            raise ValueError("interfaces must be a sequence of names, not a single string")
        interfaces = tuple(interfaces)
        for iface in interfaces:
            if not isinstance(iface, str) or not iface:
                raise ValueError(
                    f"interface names must be non-empty strings, got {iface!r}"
                )
    bound: list[Transport] | None = None
    if interfaces:
        factory = interface_transport or make_bound_transport
        bound = [factory(iface) for iface in interfaces]
    first_transport = bound[0] if bound else transport

    dest = Path(dest)
    info = probe(url, first_transport)
    chunks = plan_chunks(info.size or 0, chunk_bytes)
    use_parallel = (
        info.accepts_ranges
        and info.size is not None
        and info.size >= min_parallel_bytes
        and len(chunks) > 1
    )
    if use_parallel:
        mode = "parallel"
        jobs = [
            (chunk, bound[i % len(bound)] if bound else transport)
            for i, chunk in enumerate(chunks)
        ]

        def _run(job):  # type: ignore[no-untyped-def]
            (start, end), chunk_transport = job
            return _fetch_chunk(url, start, end, chunk_transport, retries)

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            parts = list(pool.map(_run, jobs))
        data = b"".join(parts)
        if len(data) != info.size:
            raise DownloadError(
                f"reassembled {len(data)} bytes, expected {info.size}"
            )
    else:
        mode = "plain"
        data = _plain_download(url, first_transport)
        chunks = [(0, len(data) - 1)] if data else []

    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise DownloadError(
            f"sha256 mismatch: got {digest}, expected {expected_sha256.lower()}"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return DownloadReport(
        url=url,
        dest=str(dest),
        size=len(data),
        sha256=digest,
        mode=mode,
        chunks=len(chunks),
        interfaces=tuple(interfaces) if interfaces else (),
    )
