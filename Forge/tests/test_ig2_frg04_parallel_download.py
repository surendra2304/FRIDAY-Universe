"""TASK-IG2-FRG-04: parallel range-chunk downloader (Plexo pattern).

All tests run against an in-memory fake transport — no network. Pins:
parallel reassembly in order, checksum verification (and deletion of
the bad outcome via exception, with nothing written), chunk retries,
and the plain-download fallback when Range is unsupported or ignored.
"""
from __future__ import annotations

import hashlib

import pytest

from forge_upgrade.parallel_download import (
    DownloadError,
    download,
    plan_chunks,
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


def range_ignoring_transport(url, headers):
    """Answers Range probes with 200 + full body (Range ignored)."""
    return 200, {"Content-Length": str(len(PAYLOAD))}, PAYLOAD


def test_plan_chunks_covers_exactly() -> None:
    chunks = plan_chunks(10, chunk_bytes=4)
    assert chunks == [(0, 3), (4, 7), (8, 9)]
    assert plan_chunks(0) == []


def test_parallel_download_reassembles_and_verifies(tmp_path) -> None:
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
    assert report.sha256 == SHA
    assert dest.read_bytes() == PAYLOAD


def test_fallback_when_range_unsupported(tmp_path) -> None:
    dest = tmp_path / "asset.bin"
    report = download(
        URL, dest, chunk_bytes=4096, min_parallel_bytes=1024,
        transport=plain_transport,
    )
    assert report.mode == "plain"
    assert dest.read_bytes() == PAYLOAD


def test_fallback_when_range_ignored_by_server(tmp_path) -> None:
    dest = tmp_path / "asset.bin"
    report = download(
        URL, dest, chunk_bytes=4096, min_parallel_bytes=1024,
        transport=range_ignoring_transport,
    )
    assert report.mode == "plain"
    assert dest.read_bytes() == PAYLOAD


def test_small_file_uses_plain_even_with_range_support(tmp_path) -> None:
    dest = tmp_path / "asset.bin"
    report = download(URL, dest, transport=range_transport)
    assert report.mode == "plain"  # 16 KiB < default 1 MiB threshold


def test_checksum_mismatch_raises_and_writes_nothing(tmp_path) -> None:
    dest = tmp_path / "asset.bin"
    with pytest.raises(DownloadError):
        download(
            URL, dest, expected_sha256="0" * 64, transport=plain_transport
        )
    assert not dest.exists()


def test_flaky_chunk_is_retried(tmp_path) -> None:
    calls = {"n": 0}

    def flaky(url, headers):
        if headers.get("Range", "").startswith("bytes=8192-"):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("tail chunk stalled")
        return range_transport(url, headers)

    dest = tmp_path / "asset.bin"
    report = download(
        URL, dest, chunk_bytes=4096, min_parallel_bytes=1024, transport=flaky
    )
    assert report.mode == "parallel"
    assert dest.read_bytes() == PAYLOAD
    assert calls["n"] >= 2


def test_persistent_chunk_failure_raises(tmp_path) -> None:
    def broken(url, headers):
        if headers.get("Range") and not headers["Range"].startswith("bytes=0-0"):
            return 500, {}, b""
        return range_transport(url, headers)

    dest = tmp_path / "asset.bin"
    with pytest.raises(DownloadError):
        download(
            URL, dest, chunk_bytes=4096, min_parallel_bytes=1024,
            retries=2, transport=broken,
        )
    assert not dest.exists()
