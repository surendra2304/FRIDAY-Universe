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

Stdlib only (urllib + threads): no new dependency, no resident service.
The transport is injectable so tests exercise every branch without a
network.
"""
from __future__ import annotations

import hashlib
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CHUNK_BYTES = 4 * 1024 * 1024
DEFAULT_WORKERS = 4
DEFAULT_MIN_PARALLEL_BYTES = 1024 * 1024  # below this, one stream wins
DEFAULT_RETRIES = 3


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


def default_transport(url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    """One HTTP GET returning (status, headers, body). Injectable in tests."""
    with urllib.request.urlopen(_request(url, headers), timeout=120) as resp:
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
) -> DownloadReport:
    """Download ``url`` to ``dest``, in parallel chunks when worthwhile.

    Falls back to a plain download whenever Range cannot be used.
    Raises DownloadError on failure or checksum mismatch; on raise,
    no file is left at ``dest``.
    """
    dest = Path(dest)
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
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            parts = list(
                pool.map(
                    lambda se: _fetch_chunk(url, se[0], se[1], transport, retries),
                    chunks,
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
