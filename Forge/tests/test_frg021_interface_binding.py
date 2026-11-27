"""TASK-FRG-021: per-interface binding in the parallel range-chunk downloader.

All tests run against in-memory fake transports — no network, no root.
Pins: chunk streams distribute round-robin across the named interfaces,
the probe + plain fallback use the first named interface, the default
(no interfaces) path is untouched, a failing bind fails loudly, and the
SO_BINDTODEVICE socket setup itself issues the right setsockopt call
before connect.
"""
from __future__ import annotations

import hashlib
import socket

import pytest

from forge_upgrade.parallel_download import (
    DownloadError,
    _bound_connection_classes,
    _create_bound_socket,
    download,
)

PAYLOAD = bytes(range(256)) * 64  # 16 KiB of deterministic content
SHA = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://example.invalid/asset.bin"


def range_transport(url, headers):
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
    """A server with no Range support at all."""
    return 200, {"Content-Length": str(len(PAYLOAD))}, PAYLOAD


class RecordingFactory:
    """Builds one recording transport per interface; records (interface, Range)."""

    def __init__(self, base=range_transport):
        self.calls: list[tuple[str, str | None]] = []
        self.base = base

    def __call__(self, interface):
        def transport(url, headers):
            self.calls.append((interface, headers.get("Range")))
            return self.base(url, headers)

        return transport


def _chunk_start(range_header):
    return int(range_header.removeprefix("bytes=").split("-")[0])


def test_chunks_distribute_round_robin_across_interfaces(tmp_path) -> None:
    factory = RecordingFactory()
    dest = tmp_path / "asset.bin"
    report = download(
        URL,
        dest,
        expected_sha256=SHA,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        transport=range_transport,
        interfaces=["eth0", "wlan0"],
        interface_transport=factory,
    )
    assert report.mode == "parallel"
    assert report.chunks == 4
    assert report.interfaces == ("eth0", "wlan0")
    assert report.sha256 == SHA
    assert dest.read_bytes() == PAYLOAD
    # Probe rides the first interface; chunk i rides interfaces[i % 2].
    probe_calls = [c for c in factory.calls if c[1] == "bytes=0-0"]
    assert probe_calls == [("eth0", "bytes=0-0")]
    chunk_calls = {(_chunk_start(r), iface) for iface, r in factory.calls if r != "bytes=0-0"}
    assert chunk_calls == {
        (0, "eth0"),
        (4096, "wlan0"),
        (8192, "eth0"),
        (12288, "wlan0"),
    }


def test_single_interface_binds_every_chunk(tmp_path) -> None:
    factory = RecordingFactory()
    dest = tmp_path / "asset.bin"
    report = download(
        URL,
        dest,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        transport=range_transport,
        interfaces=["eth0"],
        interface_transport=factory,
    )
    assert report.mode == "parallel"
    assert report.interfaces == ("eth0",)
    assert dest.read_bytes() == PAYLOAD
    assert {iface for iface, _ in factory.calls} == {"eth0"}


def test_no_interfaces_uses_plain_transport_unchanged(tmp_path) -> None:
    def exploding_factory(interface):
        raise AssertionError("no bound transport may be built without interfaces")

    dest = tmp_path / "asset.bin"
    report = download(
        URL,
        dest,
        expected_sha256=SHA,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        transport=range_transport,
        interface_transport=exploding_factory,
    )
    assert report.mode == "parallel"
    assert report.interfaces == ()
    assert dest.read_bytes() == PAYLOAD


def test_plain_fallback_uses_first_interface(tmp_path) -> None:
    factory = RecordingFactory(base=plain_transport)
    dest = tmp_path / "asset.bin"
    report = download(
        URL,
        dest,
        chunk_bytes=4096,
        min_parallel_bytes=1024,
        transport=plain_transport,
        interfaces=["eth0", "wlan0"],
        interface_transport=factory,
    )
    assert report.mode == "plain"
    assert report.interfaces == ("eth0", "wlan0")
    assert dest.read_bytes() == PAYLOAD
    # Probe + plain download both ride the first named interface only.
    assert {iface for iface, _ in factory.calls} == {"eth0"}


def test_bind_failure_raises_and_writes_nothing(tmp_path) -> None:
    def failing_factory(interface):
        def transport(url, headers):
            if headers.get("Range", "").startswith("bytes=0-0"):
                return range_transport(url, headers)
            raise PermissionError("SO_BINDTODEVICE needs CAP_NET_RAW")

        return transport

    dest = tmp_path / "asset.bin"
    with pytest.raises(DownloadError):
        download(
            URL,
            dest,
            chunk_bytes=4096,
            min_parallel_bytes=1024,
            retries=2,
            transport=range_transport,
            interfaces=["eth0"],
            interface_transport=failing_factory,
        )
    assert not dest.exists()


@pytest.mark.parametrize(
    "bad",
    ["eth0", [""], [123], ["eth0", None]],
)
def test_invalid_interfaces_rejected(bad, tmp_path) -> None:
    with pytest.raises(ValueError):
        download(
            URL,
            tmp_path / "asset.bin",
            transport=range_transport,
            interfaces=bad,
            interface_transport=RecordingFactory(),
        )


class _FakeSocket:
    """Records setsockopt/connect; stands in for socket.socket."""

    def __init__(self, *args, **kwargs):
        self.calls: list = []

    def setsockopt(self, level, opt, value):
        self.calls.append((level, opt, value))

    def settimeout(self, timeout):
        pass

    def bind(self, address):
        pass

    def connect(self, address):
        self.calls.append(("connect", address))

    def close(self):
        pass


def _patch_socket(monkeypatch):
    fake = _FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *a, **k: fake)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 80))],
    )
    return fake


def test_bound_socket_sets_bindtodevice_before_connect(monkeypatch) -> None:
    fake = _patch_socket(monkeypatch)
    sock = _create_bound_socket("example.invalid", 80, 30, "eth0")
    assert sock is fake
    bind_call = (socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"eth0")
    assert bind_call in fake.calls
    assert fake.calls.index(bind_call) < fake.calls.index(("connect", ("93.184.216.34", 80)))


def test_bound_connection_class_binds_before_connect(monkeypatch) -> None:
    fake = _patch_socket(monkeypatch)
    http_cls, _ = _bound_connection_classes("wlan0")
    conn = http_cls("example.invalid", 80, timeout=30)
    conn.connect()
    assert (socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"wlan0") in fake.calls
    assert conn.sock is fake
