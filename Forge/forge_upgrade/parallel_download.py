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

Per-interface binding (TASK-FRG-021, modelled on Plexo's bonding
shape): chunk streams are distributed across named interfaces,
round-robin, one stream per interface. The binding is SO_BINDTODEVICE
on Linux where permitted, with a source-address bind to the
interface's IPv4 address as the unprivileged fallback; when neither
is possible a chunk still goes out unbound rather than failing the
download. With no interfaces named, ``download()`` takes the
byte-identical code path it takes today.

Stdlib only (urllib + threads): no new dependency, no resident service.
The transport is injectable so tests exercise every branch without a
network.
"""
from __future__ import annotations

import hashlib
import http.client
import socket
import struct
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no fcntl, source-address fallback unavailable
    fcntl = None

DEFAULT_CHUNK_BYTES = 4 * 1024 * 1024
DEFAULT_WORKERS = 4
DEFAULT_MIN_PARALLEL_BYTES = 1024 * 1024  # below this, one stream wins
DEFAULT_RETRIES = 3

SO_BINDTODEVICE = getattr(socket, "SO_BINDTODEVICE", None)  # Linux only
_SIOCGIFADDR = 0x8915  # Linux ioctl: fetch an interface's IPv4 address


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


def _request(url: str, headers: dict[str, str] | None = None) -> urllib.request.Request:
    return urllib.request.Request(url, headers=headers or {}, method="GET")


def available_interfaces() -> list[str]:
    """Names of the host's network interfaces, via ``socket.if_nameindex``."""
    try:
        return [name for _, name in socket.if_nameindex()]
    except (OSError, AttributeError):
        return []


def validate_interfaces(interfaces: list[str]) -> list[str]:
    """Fail fast on unknown interface names; returns the list unchanged.

    Runs once, up front in ``download()`` — before any byte is fetched —
    so a typo never costs a partial download.
    """
    known = set(available_interfaces())
    unknown = [name for name in interfaces if name not in known]
    if unknown:
        raise DownloadError(
            f"unknown network interface(s): {', '.join(unknown)} "
            f"(available: {', '.join(sorted(known)) or 'none'})"
        )
    return list(interfaces)


def _interface_address(name: str) -> str | None:
    """Primary IPv4 address of a named interface (Linux ioctl), else None."""
    if fcntl is None:
        return None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            packed = fcntl.ioctl(
                sock.fileno(), _SIOCGIFADDR, struct.pack("256s", name.encode()[:15])
            )
        finally:
            sock.close()
        return socket.inet_ntoa(packed[20:24])
    except OSError:
        return None


def try_bind_socket(sock: socket.socket, interface: str) -> bool:
    """Best-effort bind of an unconnected socket to a named interface.

    SO_BINDTODEVICE first (needs CAP_NET_RAW); then a source-address
    bind to the interface's IPv4 address. Returns False when neither
    is possible — the caller then proceeds unbound rather than failing
    the download.
    """
    if SO_BINDTODEVICE is not None:
        try:
            sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, interface.encode())
            return True
        except OSError:
            pass
    address = _interface_address(interface)
    if address is not None:
        try:
            sock.bind((address, 0))
            return True
        except OSError:
            pass
    return False


def _bound_socket(host: str, port: int, interface: str, timeout) -> socket.socket:
    """A connected socket to (host, port), bound to ``interface`` first."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    family, _, _, _, sockaddr = infos[0]
    sock = socket.socket(family, socket.SOCK_STREAM)
    try_bind_socket(sock, interface)
    sock.settimeout(timeout)
    sock.connect(sockaddr)
    return sock


class _BoundHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection whose socket binds to a named interface first."""

    _interface: str | None = None

    def connect(self) -> None:
        self.sock = _bound_socket(self.host, self.port, self._interface or "", self.timeout)


class _BoundHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection with the same interface binding, then a TLS wrap."""

    _interface: str | None = None

    def connect(self) -> None:
        if self._tunnel_host:
            # Proxy tunnel: the stdlib path owns the socket; stay unbound.
            super().connect()
            return
        sock = _bound_socket(self.host, self.port, self._interface or "", self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _BoundHTTPHandler(urllib.request.AbstractHTTPHandler):
    """http_open via a connection bound to one interface."""

    handler_order = 400  # before the default HTTPHandler (500)

    def __init__(self, interface: str):
        super().__init__()
        self._conn_cls = type(
            "BoundHTTPConnection",
            (_BoundHTTPConnection,),
            {"_interface": interface},
        )

    def http_open(self, req):
        return self.do_open(self._conn_cls, req)


class _BoundHTTPSHandler(urllib.request.HTTPSHandler):
    """https_open via a connection bound to one interface."""

    handler_order = 400  # before the default HTTPSHandler (500)

    def __init__(self, interface: str, context=None, check_hostname=None):
        super().__init__(context=context, check_hostname=check_hostname)
        self._conn_cls = type(
            "BoundHTTPSConnection",
            (_BoundHTTPSConnection,),
            {"_interface": interface},
        )

    def https_open(self, req):
        return self.do_open(
            self._conn_cls,
            req,
            context=self._context,
            check_hostname=self._check_hostname,
        )


def bound_opener(interface: str) -> urllib.request.OpenerDirector:
    """An opener whose HTTP(S) connections bind to one interface."""
    return urllib.request.build_opener(
        _BoundHTTPHandler(interface), _BoundHTTPSHandler(interface)
    )


def default_transport(
    url: str, headers: dict[str, str], interface: str | None = None
) -> tuple[int, dict[str, str], bytes]:
    """One HTTP GET returning (status, headers, body). Injectable in tests.

    With ``interface`` set, the connection binds to that interface first
    (SO_BINDTODEVICE, else source-address); when binding is impossible
    the request still goes out unbound rather than failing. With no
    interface, this is the exact path used before TASK-FRG-021.
    """
    if interface is None:
        with urllib.request.urlopen(_request(url, headers), timeout=120) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    opener = bound_opener(interface)
    with opener.open(_request(url, headers), timeout=120) as resp:
        return resp.status, dict(resp.headers.items()), resp.read()


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
    url: str, start: int, end: int, transport, retries: int, interface: str | None = None
) -> bytes:
    expected = end - start + 1
    last_error: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            if interface is None:
                status, _, body = transport(url, {"Range": f"bytes={start}-{end}"})
            else:
                status, _, body = transport(
                    url, {"Range": f"bytes={start}-{end}"}, interface=interface
                )
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
    interfaces: list[str] | None = None,
) -> DownloadReport:
    """Download ``url`` to ``dest``, in parallel chunks when worthwhile.

    Falls back to a plain download whenever Range cannot be used.
    Raises DownloadError on failure or checksum mismatch; on raise,
    no file is left at ``dest``.

    ``interfaces`` names the network interfaces chunk streams bind to,
    round-robin (TASK-FRG-021). Names are validated once, up front —
    an unknown name raises before any byte is downloaded. Plain-mode
    downloads ignore ``interfaces`` (one unbound stream). With no
    interfaces named, the code path is the one used before TASK-FRG-021.
    """
    dest = Path(dest)
    bound_interfaces = validate_interfaces(interfaces) if interfaces else None
    info = probe(url, transport)
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
            (
                chunk,
                bound_interfaces[i % len(bound_interfaces)]
                if bound_interfaces
                else None,
            )
            for i, chunk in enumerate(chunks)
        ]
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            parts = list(
                pool.map(
                    lambda job: _fetch_chunk(
                        url, job[0][0], job[0][1], transport, retries,
                        interface=job[1],
                    ),
                    jobs,
                )
            )
        data = b"".join(parts)
        if len(data) != info.size:
            raise DownloadError(
                f"reassembled {len(data)} bytes, expected {info.size}"
            )
    else:
        mode = "plain"
        data = _plain_download(url, transport)
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
    )
