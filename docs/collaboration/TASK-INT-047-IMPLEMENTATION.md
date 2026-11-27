# TASK-INT-047 — IntelX: Tor Metrics as a network-monitoring source in the OSINT source kit

## What changed

A Tor Metrics source that fetches PUBLIC Tor Metrics data (relay /
traffic / censorship metrics only) through the Onionoo protocol and
wires it so an IntelX report type can cite it.

- **New `IntelX/intelx/connectors/tor_metrics.py`** — `TorMetricsClient`
  (Onionoo API, `https://onionoo.torproject.org/`, public and keyless).
  Methods: `search_relays(query, limit)` (summary doc — relay census),
  `relay_bandwidth(fingerprint)` (bandwidth history — traffic),
  `relay_weights(fingerprint)` (consensus weight — traffic share),
  `relay_uptime(fingerprint)` (uptime history — reliability),
  `network_clients()` (users by country — censorship metric), and
  `network_snapshot(query, limit)` (relay census + client counts in one
  `TorNetworkMetrics` snapshot). Fetchers injectable; fail-closed
  (non-200, unparseable JSON, or a document without a protocol version
  raises `TorMetricsUnavailable`; an unknown relay returns an empty
  list, never a synthetic substitute; numbers are `None` when the
  document does not carry them). No Tor binary, no onion routing, no
  onion services — public metrics documents only.
- **Citation seam** — `TorNetworkMetrics.to_source()` and
  `to_claims()` build the exact shapes `intelx.core.report` consumes
  (`_get_val`, dict or object): a source record (`id` / `title` /
  `domain` / `trust_tier` / `retrieved_at` / `published_at` / `url` /
  `text`) and claim dicts (`id` / `text` / `source_id` / `status:
  ACTIVE`), each claim a factual sentence grounded in the fetched
  document. `filter_and_ground_findings` grounds findings on them and
  `render_report_markdown` / `export_text_citations` render them as
  `[S:<source-id>]` citations.
- **`IntelX/intelx/connectors/named_sources.py`** — "Tor Metrics"
  registered as `api_keyless` (home `https://metrics.torproject.org`).
- **`IntelX/intelx/core/settings.py`** — `ENABLE_TOR_METRICS` flag
  (default `False`).
- **`IntelX/intelx/api/v1/osint_tools.py`** — `GET
  /api/v1/osint/tor-metrics?q=<query>&limit=<n>[&fingerprint=<fp>]`
  (flag-gated, 503 while the flag is off; 502 when Onionoo is
  unreachable). Returns the snapshot + source + claims, plus the
  relay's bandwidth / weights / uptime when `fingerprint` is given.
- **Tests** — new `IntelX/tests/test_ig_intelx_tor_metrics.py` (18
  tests, hermetic: injected fake fetchers, no live Onionoo call).
  Added to the IntelX tier-1 CI list (REL-068).

## Design

- The Onionoo API shape was confirmed from the public protocol spec
  (`https://metrics.torproject.org/onionoo.html`): methods `/summary`,
  `/details`, `/bandwidth`, `/weights`, `/clients`, `/uptime`; every
  response carries `version` + `relays_published` /
  `bridges_published` + `relays` / `bridges` arrays; summary relay
  fields are the short keys `n` / `f` / `a` / `r`; bandwidth and
  uptime histories are keyed by period (`3_days` / `1_week` /
  `1_month` / `3_months` / `1_year` / `5_years`) and the client picks
  `1_month` first, then `1_week`, `3_days`, ... (recorded as
  `TorHistory.period`).
- The "OSINT source kit" is not a code concept (no `source_kit` in
  IntelX); the kit is the named-sources registry + connectors +
  osint_tools routes, and Tor Metrics joins it on all three seams
  (registry entry, connector, route).
- The report-type seam does not invent a new abstraction: it emits the
  plain dicts `render_report_markdown` already reads (`id`, `title`,
  `domain`, `trust_tier`, `retrieved_at`, `published_at`, `url`,
  `text` for sources; `id`, `text`, `source_id`, `status` for claims).
  A report type calls `network_snapshot(...)`, then passes
  `snapshot.to_source()` and `snapshot.to_claims()` into the report
  pipeline alongside its findings.

## Verification (first-hand, local)

- `py_compile` clean on all changed files.
- New suite: **18 passed, 0 failed** (venv
  `/tmp/muse14-int047/.venv`, from `IntelX/`). One real bug found and
  fixed first-hand: the first run had 17 passed / 1 failed — the
  `search_relays` test expected 3 entries but the summary document
  carries 3 relays + 1 bridge (4); the test expectation was wrong,
  the implementation was right (bridges belong in the census), so the
  test was corrected to expect 4 and verify the bridge entry.
- IntelX tier-1 list (all nine files incl. the new suite) re-run
  first-hand: **90 passed, 0 failed in 788.93s** (venv
  `/tmp/muse14-int047/.venv`, from `IntelX/`). (The INT-046 suite is
  not in this list yet — it rides in open PR #2008, not on main.)

## Five states

- Implemented: YES (repo-side)
- Tested: YES (18/18 hermetic; tier-1 list incl. the new suite)
- Merged: NO (work PR open)
- Deployed: NO
- Production-verified: NO

## Live leg (still owed)

One real Tor Metrics fetch cited by a real IntelX report type: enable
`ENABLE_TOR_METRICS` on IntelX-Server, call `GET
/api/v1/osint/tor-metrics?q=<relay>` against the live Onionoo API,
and pass the returned source + claims through `render_report_markdown`
(or `export_text_citations`) to show the `[S:tor-metrics:<query>]`
citation in a rendered report. Needs coordinator clearance + the
owner stop order to lift for any server-side enablement; no live
Onionoo call was attempted in this task.
