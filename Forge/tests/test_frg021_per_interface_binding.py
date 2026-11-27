"""TASK-FRG-021: per-interface binding in the parallel range-chunk downloader.

Fake-transport tests run with no network and no privileges (interface
names are stubbed via ``socket.if_nameindex``); the loopback smoke
tests at the end bind to ``lo`` for real against a local HTTP(S)
server. The acceptance's "where more than one exists" is proven by
the fake-transport distribution test plus the loopback smoke test —
S1/S2 are single-uplink VMs, so no real two-uplink host test exists.
"""
from __future__ import annotations

import hashlib
import http.server
import socket
import ssl
import subprocess
import threading

import pytest

from forge_upgrade import parallel_download
from forge_upgrade.parallel_download import (
    SO_BINDTODEVICE,
    DownloadError,
    _BoundHTTPSConnection,
    _interface_address,
    available_interfaces,
    default_transport,
    download,
    try_bind_socket,
)

PAYLOAD = bytes(range(256)) * 64  # 16 KiB of deterministic content
SHA = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://example.invalid/asset.bin"


def range_transport(url, headers, interface=None):
    """A Range-honouring server over PAYLOAD."""
    range_header = headers.get("Range")
    if range_header:
        spec = range_header.removeprefix("bytes=")
        start_s, end_s = spec.split("-")
        start, end = int(start_s), int(end_s)
        return (
            206,
            {"Content-Range": f"bytes {start}-{end}/{len(PAYLOAD)}"},
            PAYLOAD[start : end + 1],
        )
    return 200, {"Content-Length": str(len(PAYLOAD))}, PAYLOAD


def plain_transport(url, headers):
    """A server with no Range support at all (strict 2-arg signature)."""
    return 200, {"Content-Length": str(len(PAYLOAD))}, PAYLOAD


class RecordingTransport:
    """Range server that records (range, interface) for every call."""

    def __init__(self):
        self.calls: list[tuple[str | None, str | None]] = []

    def __call__(self, url, headers, interface=None):
        self.calls.append((headers.get("Range"), interface))
        return range_transport(url, headers, interface)


def _stub_if_nameindex(monkeypatch, names=("eth0", "wlan0")):
    calls = {"n": 0}

    def fake():
        calls["n"] += 1
        return [(i + 1, name) for i, name in enumerate(names)]

    monkeypatch.setattr(socket, "if_nameindex", fake)
    return calls


def test_chunks_distributed_round_robin(monkeypatch, tmp_path) -> None:
    _stub_if_nameindex(monkeypatch)
    transport = RecordingTransport()
    dest = tmp_path / "asset.bin"
    report = download(
        URL,
        dest,
        expected_sha256=SHA,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        interfaces=["eth0", "wlan0"],
        transport=transport,
    )
    assert report.mode == "parallel"
    assert report.chunks == 4
    assert dest.read_bytes() == PAYLOAD
    chunk_calls = sorted(
        ((rng, iface) for rng, iface in transport.calls if rng != "bytes=0-0"),
        key=lambda ri: int(ri[0].removeprefix("bytes=").split("-")[0]),
    )
    assert [iface for _, iface in chunk_calls] == [
        "eth0",
        "wlan0",
        "eth0",
        "wlan0",
    ]


def test_no_interfaces_is_unbound(tmp_path) -> None:
    """No interfaces named: the transport is called exactly as before
    (2-arg signature — passing an interface kwarg would TypeError)."""
    dest = tmp_path / "asset.bin"
    report = download(
        URL,
        dest,
        expected_sha256=SHA,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        transport=range_transport,
    )
    assert report.mode == "parallel"
    assert report.chunks == 4
    assert dest.read_bytes() == PAYLOAD


def test_plain_mode_ignores_interfaces(monkeypatch, tmp_path) -> None:
    _stub_if_nameindex(monkeypatch)
    dest = tmp_path / "asset.bin"
    report = download(
        URL,
        dest,
        interfaces=["eth0", "wlan0"],
        transport=plain_transport,  # strict 2-arg: any interface kwarg fails
    )
    assert report.mode == "plain"
    assert dest.read_bytes() == PAYLOAD


def test_invalid_interface_fails_fast(monkeypatch, tmp_path) -> None:
    _stub_if_nameindex(monkeypatch, names=("lo",))
    transport = RecordingTransport()
    dest = tmp_path / "asset.bin"
    with pytest.raises(DownloadError, match="unknown network interface.*nosuch0"):
        download(
            URL,
            dest,
            interfaces=["nosuch0"],
            transport=transport,
        )
    assert transport.calls == []  # probe never ran: nothing downloaded
    assert not dest.exists()


def test_interfaces_validated_once(monkeypatch, tmp_path) -> None:
    calls = _stub_if_nameindex(monkeypatch)
    dest = tmp_path / "asset.bin"
    download(
        URL,
        dest,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        interfaces=["eth0", "wlan0"],
        transport=range_transport,
    )
    assert calls["n"] == 1


class _FakeSocket:
    """A socket whose setsockopt always fails (unprivileged host)."""

    def __init__(self):
        self.bind_calls: list[tuple] = []

    def setsockopt(self, *args):
        raise PermissionError("not permitted")

    def bind(self, addr):
        self.bind_calls.append(addr)


def test_try_bind_socket_source_address_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        parallel_download, "_interface_address", lambda name: "192.0.2.9"
    )
    sock = _FakeSocket()
    assert try_bind_socket(sock, "eth0") is True
    assert sock.bind_calls == [("192.0.2.9", 0)]


def test_try_bind_socket_returns_false_when_nothing_works(monkeypatch) -> None:
    monkeypatch.setattr(parallel_download, "_interface_address", lambda name: None)
    sock = _FakeSocket()
    assert try_bind_socket(sock, "eth0") is False
    assert sock.bind_calls == []


def test_so_bindtodevice_attempted_on_lo() -> None:
    """The kernel path is real: SO_BINDTODEVICE on ``lo`` either succeeds
    (privileged) or is refused with EPERM (unprivileged) — both prove the
    setsockopt is issued; anything else is a real failure."""
    if SO_BINDTODEVICE is None:
        pytest.skip("SO_BINDTODEVICE unavailable (non-Linux)")
    if "lo" not in available_interfaces():
        pytest.skip("no loopback interface")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, b"lo")
    except PermissionError:
        pass  # expected unprivileged; the source-address fallback carries it
    except OSError as exc:
        pytest.fail(f"SO_BINDTODEVICE on lo failed unexpectedly: {exc}")
    finally:
        sock.close()


def test_interface_address_of_lo() -> None:
    if "lo" not in available_interfaces():
        pytest.skip("no loopback interface")
    assert _interface_address("lo") == "127.0.0.1"


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    """Range-honouring handler serving PAYLOAD on 127.0.0.1."""

    def do_GET(self):
        range_header = self.headers.get("Range")
        if range_header:
            spec = range_header.removeprefix("bytes=")
            start_s, end_s = spec.split("-")
            start, end = int(start_s), int(end_s)
            body = PAYLOAD[start : end + 1]
            self.send_response(206)
            self.send_header(
                "Content-Range", f"bytes {start}-{end}/{len(PAYLOAD)}"
            )
        else:
            body = PAYLOAD
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def loopback_server():
    """A local HTTP server on 127.0.0.1; yields its base URL."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/asset.bin"
    finally:
        server.shutdown()
        server.server_close()


def _binding_available() -> bool:
    """True when binding to ``lo`` actually works on this host."""
    if "lo" not in available_interfaces():
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return try_bind_socket(sock, "lo")
    except OSError:
        return False
    finally:
        sock.close()


def test_loopback_smoke_bind_lo(loopback_server, tmp_path) -> None:
    """Live leg: bind chunk streams to ``lo`` and download from a local
    server on 127.0.0.1 through the real default transport."""
    if not _binding_available():
        pytest.skip("interface binding unavailable on this host")
    dest = tmp_path / "asset.bin"
    report = download(
        loopback_server,
        dest,
        expected_sha256=SHA,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        interfaces=["lo"],
        transport=default_transport,
    )
    assert report.mode == "parallel"
    assert report.chunks == 4
    assert report.sha256 == SHA
    assert dest.read_bytes() == PAYLOAD


def test_loopback_unbound_fallback_when_binding_fails(
    monkeypatch, loopback_server
) -> None:
    """When binding is impossible, the request still goes out unbound
    rather than failing the download."""
    monkeypatch.setattr(parallel_download, "try_bind_socket", lambda sock, iface: False)
    status, _, body = default_transport(loopback_server, {}, interface="lo")
    assert status == 200
    assert body == PAYLOAD


@pytest.fixture
def tls_loopback_server(tmp_path):
    """A local TLS server on 127.0.0.1 with a self-signed cert."""
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    proc = subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-nodes", "-subj", "/CN=127.0.0.1",
        ],
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        pytest.skip("openssl self-signed cert generation failed")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert), str(key))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def test_https_connection_binds_then_wraps(tls_loopback_server) -> None:
    """The HTTPS connect path binds the socket to ``lo`` before the TLS
    wrap, and the handshake then succeeds."""
    if not _binding_available():
        pytest.skip("interface binding unavailable on this host")
    ctx = ssl._create_unverified_context()
    conn = _BoundHTTPSConnection(
        "127.0.0.1", tls_loopback_server, context=ctx, timeout=10
    )
    conn._interface = "lo"
    try:
        conn.connect()
        conn.request("GET", "/asset.bin")
        resp = conn.getresponse()
        assert resp.status == 200
        assert resp.read() == PAYLOAD
    finally:
        conn.close()
