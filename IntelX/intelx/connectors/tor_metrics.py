"""INTELX — Tor Metrics as a network-monitoring source (TASK-INT-047).

Tor Metrics data (public relay/traffic/censorship metrics only) is
fetchable through the Onionoo protocol — Tor's public, keyless, REST/JSON
API at ``https://onionoo.torproject.org/`` (spec:
``https://metrics.torproject.org/onionoo.html``). No key, no account, no
Tor binary, no onion routing: this module only reads the public
metrics documents. It does NOT download Tor, route traffic through Tor,
or touch onion services.

What is fetched (all public, all keyless):

  * ``/summary`` — relay/bridge summaries (nickname, fingerprint,
    addresses, running). The relay census / network-status metric.
  * ``/bandwidth`` — per-relay bandwidth history (write/read histories).
    The traffic metric.
  * ``/weights`` — per-relay consensus weight. The traffic-share metric.
  * ``/clients`` — estimated Tor users per bridge (average clients).
    The censorship metric: a bridge's client count is the observable
    that moves when access is blocked or restored. NOTE (live Onionoo
    8.0, verified 2026-11-27): the document carries per-BRIDGE average
    clients only — entries have ``fingerprint`` + ``average_clients``
    (a period-keyed history map) and NO country field, and ``relays``
    is empty. There is no per-country breakdown in this endpoint, so
    the snapshot reports bridge client totals and no country rows
    (TASK-INT-047-FIX-01).
  * ``/uptime`` — per-relay uptime history. The reliability metric.

Fail-closed, throughout: a non-200 response, malformed JSON, or a
document missing the required ``version`` / ``relays`` fields raises
``TorMetricsUnavailable`` (never a synthetic substitute). A relay that
Onionoo does not know returns an empty list — reported as not-found,
never dressed up. Numbers are reported only when the document actually
carries them (``None`` otherwise) — never fabricated.

Cited by an IntelX report type: ``TorNetworkMetrics.to_source()`` and
``TorNetworkMetrics.to_claims()`` build the exact shapes the report
pipeline consumes (``intelx.core.report`` reads sources and claims via
``_get_val``, dict or object): a source record (``id`` / ``title`` /
``domain`` / ``trust_tier`` / ``retrieved_at`` / ``published_at`` /
``url`` / ``text``) and claim dicts (``id`` / ``text`` / ``source_id`` /
``status: ACTIVE``), each claim a factual sentence grounded in the
fetched document, so ``filter_and_ground_findings`` grounds findings on
them and ``render_report_markdown`` / ``export_text_citations`` render
them as ``[S:<source-id>]`` citations. The source text is the verbatim
metrics text, stored with its Onionoo URL and fetch time, so any later
quote can be checked against what was fetched.

Python 3.10 compatible. Fetchers injectable for hermetic tests.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable
from urllib.parse import quote, urlencode

logger = logging.getLogger("intelx.tor_metrics")

UTC = timezone.utc

ONIONOO_BASE = "https://onionoo.torproject.org"
METRICS_HOME = "https://metrics.torproject.org"

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]  # (status, final_url, body)


class TorMetricsUnavailable(RuntimeError):
    """Tor Metrics data could not be fetched; the message says why."""


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TorRelaySummary:
    """One relay (or bridge) from an Onionoo summary document."""

    nickname: str
    fingerprint: str
    addresses: list[str]
    running: bool

    def to_dict(self) -> dict:
        return {
            "nickname": self.nickname,
            "fingerprint": self.fingerprint,
            "addresses": list(self.addresses),
            "running": self.running,
        }


@dataclass(frozen=True)
class TorHistory:
    """One Onionoo history series (bandwidth / uptime).

    Onionoo history objects are keyed by period (``3_days`` / ``1_week`` /
    ``1_month`` / ``3_months`` / ``1_year`` / ``5_years``); ``period``
    records which one this series came from.
    """

    period: str
    first: str
    last: str
    interval: int
    factor: float
    values: list[int]

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "first": self.first,
            "last": self.last,
            "interval": self.interval,
            "factor": self.factor,
            "values": list(self.values),
        }


@dataclass(frozen=True)
class TorBandwidth:
    """Bandwidth history for one relay."""

    fingerprint: str
    nickname: str
    write_history: TorHistory | None
    read_history: TorHistory | None

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "nickname": self.nickname,
            "write_history": self.write_history.to_dict() if self.write_history else None,
            "read_history": self.read_history.to_dict() if self.read_history else None,
        }


@dataclass(frozen=True)
class TorWeights:
    """Consensus weight for one relay.

    Live Onionoo 8.0 serves ``consensus_weight`` /
    ``consensus_weight_fraction`` as period-keyed history maps, not
    plain numbers (TASK-INT-047-FIX-01). The scalar fields are the
    latest value of the best period's history, scaled by its factor
    (``value * factor`` per the Onionoo spec); the history fields keep
    the full series so the evidence is not discarded.
    """

    fingerprint: str
    nickname: str
    consensus_weight: int | None
    consensus_weight_fraction: float | None
    consensus_weight_history: TorHistory | None = None
    consensus_weight_fraction_history: TorHistory | None = None

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "nickname": self.nickname,
            "consensus_weight": self.consensus_weight,
            "consensus_weight_fraction": self.consensus_weight_fraction,
            "consensus_weight_history": self.consensus_weight_history.to_dict()
            if self.consensus_weight_history
            else None,
            "consensus_weight_fraction_history": self.consensus_weight_fraction_history.to_dict()
            if self.consensus_weight_fraction_history
            else None,
        }


@dataclass(frozen=True)
class TorUptime:
    """Uptime history for one relay."""

    fingerprint: str
    nickname: str
    uptime: TorHistory | None

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "nickname": self.nickname,
            "uptime": self.uptime.to_dict() if self.uptime else None,
        }


@dataclass(frozen=True)
class TorCountryClients:
    """Estimated Tor users in one country (from the clients document).

    Retained for the snapshot shape. NOTE: the live Onionoo 8.0
    ``/clients`` document carries NO country field at all (entries are
    per-bridge ``fingerprint`` + ``average_clients``), so this is
    always empty from live data — see :class:`TorBridgeClients`
    (TASK-INT-047-FIX-01).
    """

    country: str
    average_clients: int | None

    def to_dict(self) -> dict:
        return {"country": self.country, "average_clients": self.average_clients}


@dataclass(frozen=True)
class TorBridgeClients:
    """Estimated Tor users of one bridge (from the clients document).

    Live Onionoo 8.0 ``/clients`` entries carry only ``fingerprint``
    and ``average_clients`` (a period-keyed history map, no country).
    ``average_clients`` is the latest value of the best period's
    history, scaled by its factor (``value * factor`` per the Onionoo
    spec); ``None`` when the bridge carries no parseable history.
    """

    fingerprint: str
    average_clients: int | None

    def to_dict(self) -> dict:
        return {"fingerprint": self.fingerprint, "average_clients": self.average_clients}


@dataclass(frozen=True)
class TorNetworkMetrics:
    """A network-monitoring snapshot: relay census + traffic + clients.

    Built by :meth:`TorMetricsClient.network_snapshot` from a summary
    search and the clients document. ``relays_published`` is the
    Onionoo consensus timestamp (when the data was valid); ``fetched_at``
    is when this process fetched it. ``source_urls`` lists every Onionoo
    URL the snapshot was read from, so the snapshot is checkable.
    """

    query: str
    relays: list[TorRelaySummary]
    running_relays: int
    running_bridges: int
    countries: list[TorCountryClients]
    total_average_clients: int | None
    version: str
    relays_published: str
    bridges_published: str
    fetched_at: datetime
    source_urls: list[str] = field(default_factory=list)
    # Per-bridge average clients from the live /clients document
    # (TASK-INT-047-FIX-01). ``total_average_clients`` is the sum of
    # these (users connecting via bridges); ``countries`` is empty from
    # live data because /clients carries no country field.
    bridge_clients: list[TorBridgeClients] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "relays": [r.to_dict() for r in self.relays],
            "running_relays": self.running_relays,
            "running_bridges": self.running_bridges,
            "countries": [c.to_dict() for c in self.countries],
            "bridge_clients": [b.to_dict() for b in self.bridge_clients],
            "total_average_clients": self.total_average_clients,
            "version": self.version,
            "relays_published": self.relays_published,
            "bridges_published": self.bridges_published,
            "fetched_at": self.fetched_at.isoformat(),
            "source_urls": list(self.source_urls),
        }

    @property
    def source_id(self) -> str:
        return f"tor-metrics:{self.query or 'network'}"

    def source_text(self) -> str:
        """Verbatim metrics text for the report citation."""
        lines = [
            f"Tor Metrics network snapshot for query {self.query!r} "
            f"(Onionoo protocol version {self.version}; "
            f"relays published {self.relays_published}).",
            f"Running relays in this snapshot: {self.running_relays}; "
            f"running bridges: {self.running_bridges}.",
        ]
        for relay in self.relays:
            lines.append(
                f"Relay {relay.nickname} ({relay.fingerprint}): "
                f"running={str(relay.running).lower()}, "
                f"addresses={', '.join(relay.addresses) or 'none listed'}."
            )
        if self.total_average_clients is not None:
            lines.append(
                f"Estimated Tor users connecting via bridges (average "
                f"clients): {self.total_average_clients}."
            )
            if not self.countries:
                lines.append(
                    "No per-country breakdown is published in the "
                    "Onionoo clients document (entries carry fingerprint "
                    "and average clients only)."
                )
        for country in self.countries[:10]:
            if country.average_clients is not None:
                lines.append(
                    f"Estimated Tor users in {country.country}: "
                    f"{country.average_clients} (average clients)."
                )
        return "\n".join(lines)

    def to_source(self) -> dict:
        """A source record for the IntelX report pipeline.

        Shape matches what ``intelx.core.report`` reads via ``_get_val``:
        ``id`` / ``title`` / ``domain`` / ``trust_tier`` /
        ``retrieved_at`` / ``published_at`` / ``url`` / ``text``.
        """
        return {
            "id": self.source_id,
            "title": f"Tor Metrics network snapshot for {self.query!r}",
            "domain": "onionoo.torproject.org",
            "trust_tier": "STANDARD",
            "retrieved_at": self.fetched_at.isoformat(),
            "published_at": self.relays_published,
            "url": self.source_urls[0] if self.source_urls else ONIONOO_BASE,
            "text": self.source_text(),
            "injection_risk": False,
            "license_note": "Tor Metrics data is public; Onionoo documents are published by the Tor Project.",
        }

    def to_claims(self) -> list[dict]:
        """Claim dicts grounded in this snapshot, for the report pipeline.

        Each claim is a factual sentence drawn only from the fetched
        documents, with ``status: ACTIVE`` and the snapshot's source id,
        so ``filter_and_ground_findings`` grounds findings on them.
        """
        claims: list[dict] = []
        base = self.source_id
        claims.append(
            {
                "id": f"{base}-census",
                "text": (
                    f"As of the Onionoo consensus published "
                    f"{self.relays_published}, {self.running_relays} relays "
                    f"and {self.running_bridges} bridges matching "
                    f"{self.query!r} were running."
                ),
                "source_id": base,
                "status": "ACTIVE",
            }
        )
        for relay in self.relays:
            claims.append(
                {
                    "id": f"{base}-relay-{relay.fingerprint[:8]}",
                    "text": (
                        f"Relay {relay.nickname} ({relay.fingerprint}) was "
                        f"{'running' if relay.running else 'not running'} "
                        f"as of {self.relays_published}."
                    ),
                    "source_id": base,
                    "status": "ACTIVE",
                }
            )
        if self.total_average_clients is not None:
            claims.append(
                {
                    "id": f"{base}-clients-total",
                    "text": (
                        f"Estimated Tor users connecting via bridges "
                        f"averaged {self.total_average_clients} (Onionoo "
                        f"clients document, relays published "
                        f"{self.relays_published})."
                    ),
                    "source_id": base,
                    "status": "ACTIVE",
                }
            )
        for country in self.countries[:10]:
            if country.average_clients is not None:
                claims.append(
                    {
                        "id": f"{base}-clients-{country.country}",
                        "text": (
                            f"Estimated Tor users in {country.country} "
                            f"averaged {country.average_clients}."
                        ),
                        "source_id": base,
                        "status": "ACTIVE",
                    }
                )
        return claims


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


_HISTORY_PERIODS = (
    "1_month",
    "1_week",
    "3_days",
    "3_months",
    "6_months",
    "1_year",
    "5_years",
)


def _entry_fingerprint(entry: dict) -> str:
    """A relay entry's fingerprint.

    Live Onionoo 8.0 /bandwidth, /weights and /uptime key entries by
    ``fingerprint``; the short key ``f`` exists only in /summary
    (TASK-INT-047-FIX-01). Prefer ``fingerprint``, fall back to ``f``
    so older / assumed shapes still match.
    """
    return str(entry.get("fingerprint", "") or entry.get("f", ""))


def _latest_value(raw: object) -> float | None:
    """Latest value of a scalar or a period-keyed history map.

    Plain numbers pass through. Dicts are parsed as Onionoo histories
    (best period first) and the latest value is scaled by the
    history's factor (``value * factor`` per the Onionoo spec:
    "Factor by which subsequent data values need to be multiplied to
    obtain original values"). Returns None when the value is absent,
    empty, or unparseable — never fabricated.
    """
    if isinstance(raw, (int, float)):
        return float(raw)
    history = _parse_history(raw if isinstance(raw, dict) else None)
    if history is None or not history.values:
        return None
    return history.values[-1] * history.factor


def _parse_history(raw: dict | None) -> TorHistory | None:
    """Parse one Onionoo history object, or the best period of a
    period-keyed history map (``1_month`` first, then ``1_week`` ...)."""
    if not isinstance(raw, dict):
        return None
    # Period-keyed map: pick the best available period.
    if "values" not in raw:
        for period in _HISTORY_PERIODS:
            candidate = raw.get(period)
            if isinstance(candidate, dict) and isinstance(candidate.get("values"), list):
                return _parse_history({**candidate, "_period": period})
        return None
    values = raw.get("values")
    if not isinstance(values, list):
        return None
    return TorHistory(
        period=str(raw.get("_period", "")),
        first=str(raw.get("first", "")),
        last=str(raw.get("last", "")),
        interval=int(raw.get("interval", 0) or 0),
        factor=float(raw.get("factor", 1.0) or 1.0),
        values=[int(v) for v in values if isinstance(v, (int, float))],
    )


class TorMetricsClient:
    """Fetch public Tor Metrics (Onionoo) documents. Keyless, fail-closed."""

    def __init__(self, fetch: FetchBytes | None = None) -> None:
        self._fetch = fetch or _default_fetch

    async def _get_document(self, path: str, params: dict | None = None) -> dict:
        url = f"{ONIONOO_BASE}{path}"
        if params:
            url += "?" + urlencode(params)
        status, _, body = await self._fetch(url)
        if status != 200:
            raise TorMetricsUnavailable(f"Onionoo {path} returned HTTP {status}")
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise TorMetricsUnavailable(f"Onionoo {path} returned unparseable JSON: {exc}") from exc
        if not isinstance(payload, dict) or "version" not in payload:
            raise TorMetricsUnavailable(
                f"Onionoo {path} returned a document without a protocol version"
            )
        return payload

    @staticmethod
    def _relays(payload: dict) -> list[dict]:
        relays = payload.get("relays") or []
        bridges = payload.get("bridges") or []
        if not isinstance(relays, list):
            relays = []
        if not isinstance(bridges, list):
            bridges = []
        return relays, bridges

    async def search_relays(
        self, query: str, limit: int = 10, running_only: bool = True
    ) -> list[TorRelaySummary]:
        """Search relays/bridges by nickname or fingerprint (summary doc)."""
        query = (query or "").strip()
        if not query:
            raise TorMetricsUnavailable("a search query is required")
        params: dict[str, str] = {"search": query, "limit": str(max(1, min(limit, 50)))}
        if running_only:
            params["running"] = "true"
        payload = await self._get_document("/summary", params)
        relays, bridges = self._relays(payload)
        out: list[TorRelaySummary] = []
        for entry in relays + bridges:
            fingerprint = str(entry.get("f", ""))
            if not fingerprint:
                continue
            addresses = entry.get("a") or []
            out.append(
                TorRelaySummary(
                    nickname=str(entry.get("n", "")),
                    fingerprint=fingerprint,
                    addresses=[str(a) for a in addresses if a],
                    running=bool(entry.get("r", False)),
                )
            )
        return out

    async def relay_bandwidth(self, fingerprint: str) -> TorBandwidth:
        """Bandwidth history for one relay (bandwidth doc)."""
        fingerprint = (fingerprint or "").strip()
        if not fingerprint:
            raise TorMetricsUnavailable("a relay fingerprint is required")
        payload = await self._get_document(
            "/bandwidth", {"search": fingerprint, "limit": "1"}
        )
        relays, _ = self._relays(payload)
        entry = next(
            (r for r in relays if _entry_fingerprint(r) == fingerprint), None
        )
        if entry is None:
            raise TorMetricsUnavailable(
                f"Onionoo has no bandwidth document for relay {fingerprint!r}"
            )
        return TorBandwidth(
            fingerprint=fingerprint,
            nickname=str(entry.get("n", "")),
            write_history=_parse_history(entry.get("write_history")),
            read_history=_parse_history(entry.get("read_history")),
        )

    async def relay_weights(self, fingerprint: str) -> TorWeights:
        """Consensus weight for one relay (weights doc).

        Live Onionoo 8.0 serves ``consensus_weight`` /
        ``consensus_weight_fraction`` as period-keyed history maps, not
        plain numbers — they are parsed as histories and the scalars
        are the latest values scaled by the history factor
        (TASK-INT-047-FIX-01).
        """
        fingerprint = (fingerprint or "").strip()
        if not fingerprint:
            raise TorMetricsUnavailable("a relay fingerprint is required")
        payload = await self._get_document(
            "/weights", {"search": fingerprint, "limit": "1"}
        )
        relays, _ = self._relays(payload)
        entry = next(
            (r for r in relays if _entry_fingerprint(r) == fingerprint), None
        )
        if entry is None:
            raise TorMetricsUnavailable(
                f"Onionoo has no weights document for relay {fingerprint!r}"
            )
        weight_hist = _parse_history(entry.get("consensus_weight"))
        fraction_hist = _parse_history(entry.get("consensus_weight_fraction"))
        weight = _latest_value(entry.get("consensus_weight"))
        fraction = _latest_value(entry.get("consensus_weight_fraction"))
        return TorWeights(
            fingerprint=fingerprint,
            nickname=str(entry.get("n", "")),
            consensus_weight=int(round(weight)) if weight is not None else None,
            consensus_weight_fraction=float(fraction) if fraction is not None else None,
            consensus_weight_history=weight_hist,
            consensus_weight_fraction_history=fraction_hist,
        )

    async def relay_uptime(self, fingerprint: str) -> TorUptime:
        """Uptime history for one relay (uptime doc)."""
        fingerprint = (fingerprint or "").strip()
        if not fingerprint:
            raise TorMetricsUnavailable("a relay fingerprint is required")
        payload = await self._get_document(
            "/uptime", {"search": fingerprint, "limit": "1"}
        )
        relays, _ = self._relays(payload)
        entry = next(
            (r for r in relays if _entry_fingerprint(r) == fingerprint), None
        )
        if entry is None:
            raise TorMetricsUnavailable(
                f"Onionoo has no uptime document for relay {fingerprint!r}"
            )
        return TorUptime(
            fingerprint=fingerprint,
            nickname=str(entry.get("n", "")),
            uptime=_parse_history(entry.get("uptime")),
        )

    async def network_clients(self) -> list[TorBridgeClients]:
        """Estimated Tor users per bridge (clients doc).

        Live Onionoo 8.0 /clients carries per-BRIDGE average clients
        only: ``relays`` is empty and bridge entries have
        ``fingerprint`` + ``average_clients`` (a period-keyed history
        map), no country field (TASK-INT-047-FIX-01). There is no
        per-country breakdown in this endpoint; the returned rows are
        per-bridge, latest value scaled by the history factor.
        """
        payload = await self._get_document("/clients")
        _, bridges = self._relays(payload)
        out: list[TorBridgeClients] = []
        for entry in bridges:
            fingerprint = _entry_fingerprint(entry)
            if not fingerprint:
                continue
            value = _latest_value(entry.get("average_clients"))
            out.append(
                TorBridgeClients(
                    fingerprint=fingerprint,
                    average_clients=int(round(value)) if value is not None else None,
                )
            )
        return out

    async def network_snapshot(
        self, query: str, limit: int = 10
    ) -> TorNetworkMetrics:
        """A network-monitoring snapshot: relay census + bridge clients.

        Two Onionoo calls: ``/summary`` (the relay census for the query)
        and ``/clients`` (per-bridge average clients — the censorship
        metric). Live /clients carries no per-country breakdown, so
        ``countries`` is empty and ``total_average_clients`` is the sum
        of per-bridge average clients (users connecting via bridges)
        (TASK-INT-047-FIX-01).
        """
        query = (query or "").strip()
        if not query:
            raise TorMetricsUnavailable("a search query is required")
        summary_url = (
            f"{ONIONOO_BASE}/summary?"
            + urlencode({"search": query, "limit": str(max(1, min(limit, 50))), "running": "true"})
        )
        clients_url = f"{ONIONOO_BASE}/clients"
        summary = await self._get_document(
            "/summary",
            {"search": query, "limit": str(max(1, min(limit, 50))), "running": "true"},
        )
        relays, bridges = self._relays(summary)
        summaries: list[TorRelaySummary] = []
        running_relays = 0
        running_bridges = 0
        for entry in relays:
            fingerprint = str(entry.get("f", ""))
            if not fingerprint:
                continue
            running = bool(entry.get("r", False))
            if running:
                running_relays += 1
            summaries.append(
                TorRelaySummary(
                    nickname=str(entry.get("n", "")),
                    fingerprint=fingerprint,
                    addresses=[str(a) for a in (entry.get("a") or []) if a],
                    running=running,
                )
            )
        for entry in bridges:
            if str(entry.get("f", "")) and bool(entry.get("r", False)):
                running_bridges += 1
        client_rows = await self.network_clients()
        countries: list[TorCountryClients] = []
        total: int | None = None
        running_total = 0
        saw_any = False
        for row in client_rows:
            if row.average_clients is not None:
                running_total += row.average_clients
                saw_any = True
        if saw_any:
            total = running_total
        return TorNetworkMetrics(
            query=query,
            relays=summaries,
            running_relays=running_relays,
            running_bridges=running_bridges,
            countries=countries,
            bridge_clients=client_rows,
            total_average_clients=total,
            version=str(summary.get("version", "")),
            relays_published=str(summary.get("relays_published", "")),
            bridges_published=str(summary.get("bridges_published", "")),
            fetched_at=datetime.now(UTC),
            source_urls=[summary_url, clients_url],
        )


__all__ = [
    "ONIONOO_BASE",
    "METRICS_HOME",
    "TorBandwidth",
    "TorBridgeClients",
    "TorCountryClients",
    "TorHistory",
    "TorMetricsClient",
    "TorMetricsUnavailable",
    "TorNetworkMetrics",
    "TorRelaySummary",
    "TorUptime",
    "TorWeights",
]
