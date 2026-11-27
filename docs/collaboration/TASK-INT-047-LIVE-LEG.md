# TASK-INT-047 — Live leg: one real Tor Metrics fetch through the merged code

## Verdict: PARTIAL — the census + citation path works live; the per-relay detail methods and the clients metric FAIL against live Onionoo 8.0

The live leg was run and it found real bugs. The merged `TorMetricsClient`
works end to end for the relay census and the report citation seam, but
`relay_bandwidth` / `relay_weights` / `relay_uptime` raise
`TorMetricsUnavailable` for every relay against the live API, and
`network_clients` / the snapshot's country counts come back empty. The
cause in each case is a mismatch between the document shapes the
implementation assumes and the shapes Onionoo 8.0 actually serves (see
"Live findings" below). The 18 hermetic tests still pass — they encode
the assumed shapes via injected fake fetchers, so they could not catch
this. No fix is made in this PR; the fix belongs to a follow-up task.

## What ran

- Base: `origin/main` at `5fd32fdf` (merge of PR #2049), which contains the
  INT-047 merge `63538e60` (work PR #2039, merged 2026-11-27 07:39:45 IST
  by surendra2304). Verified: `git merge-base --is-ancestor 63538e60 HEAD`.
- Worktree: `~/workspace/friday-int047-liveleg`, branch
  `muse14/task-int-047-live-leg` (the existing `muse14/task-int-047`
  branch, head `0c19cc45`, was not touched).
- Script: `/tmp/muse14-int047-liveleg/live_leg.py`, run from `IntelX/` with
  a fresh venv replicating the CI tier-1 step
  (`python3 -m venv`, `pip install -r requirements.txt pytest
  pytest-asyncio aiosqlite`), at **2026-11-27 08:09:45 IST**
  (fetched_at `2026-11-27T02:39:44.715556+00:00`).
- Client: the real merged `TorMetricsClient`
  (`IntelX/intelx/connectors/tor_metrics.py`), query `moria1`, limit 5,
  then `relay_bandwidth` / `relay_weights` / `relay_uptime` for the one
  returned relay, then `to_source()` / `to_claims()` through the real
  `intelx.core.report` pipeline (`filter_and_ground_findings`,
  `render_report_markdown`, `export_text_citations`).
- Transport note (honest): the client's DEFAULT fetcher
  (`HttpFetchConnector`) could not run in this sandbox — its SSRF guard
  resolves `onionoo.torproject.org` to `198.18.51.45` (sandbox DNS
  returns a CGNAT `198.18.0.0/15` address) and raises `SSRFBlocked`
  before any request. The live API itself is reachable from the sandbox
  (plain `curl`: HTTP 200, ~1 s). The client was therefore run with a
  real `httpx` transport doing genuine live HTTPS GETs to
  `onionoo.torproject.org` (same `(status, final_url, body)` shape).
  Every `TorMetricsClient` code path — document fetch, version check,
  relay/history parsing, snapshot assembly, `to_source()`/`to_claims()`
  — is the merged code exercised against live data. No fake fetcher, no
  cached data, no fabricated numbers. (A second sandbox quirk: the
  shell's `no_proxy` contains bracketed IPv6 literals such as `[::1]`
  which `httpx` cannot parse as URL patterns; the run set
  `NO_PROXY=no_proxy=localhost,127.0.0.1,::1`.)
- In production DNS the SSRF guard would resolve Onionoo to a real
  public IP, so this guard interaction is a sandbox artifact, not a
  production finding. It is recorded here so the next run is not
  surprised by it.

## Live evidence (verbatim, from the run)

Snapshot (`network_snapshot("moria1", limit=5)`, 2.2 s):

- Onionoo protocol version: `8.0`
- `relays_published`: `2026-11-27 01:00:00`
- `bridges_published`: `2026-11-27 00:43:47`
- Relays returned: 1; running relays: 1; running bridges: 0
- Relay: `moria1`, fingerprint
  `1A25C6358DB91342AA51720A5038B72742732498`, running `true`,
  addresses `["128.31.0.39"]`
- Total average clients: `None`; countries returned: 0 (see finding 3)

Per-relay detail calls for fingerprint
`1A25C6358DB91342AA51720A5038B72742732498` — ALL FAILED:

- `relay_bandwidth` (0.37 s): `TorMetricsUnavailable: Onionoo has no
  bandwidth document for relay '1A25C6358DB91342AA51720A5038B72742732498'`
- `relay_weights` (0.45 s): `TorMetricsUnavailable: Onionoo has no
  weights document for relay '1A25C6358DB91342AA51720A5038B72742732498'`
- `relay_uptime` (0.44 s): `TorMetricsUnavailable: Onionoo has no
  uptime document for relay '1A25C6358DB91342AA51720A5038B72742732498'`

Citation seam — WORKS. `to_source()` id `tor-metrics:moria1`, 2 claims
(`tor-metrics:moria1-census`, `tor-metrics:moria1-relay-1A25C635`).
`filter_and_ground_findings`: grounded 1, unverified 0. Rendered report
markdown (real `render_report_markdown`) carries the citation:

```markdown
# Research Report: Tor Metrics live-leg check for relay query 'moria1'

## Direct Answer (confidence: Moderate)
As of the Onionoo consensus published 2026-11-27 01:00:00, 1 relays and 0 bridges matching 'moria1' were running.

## Key Findings
- As of the Onionoo consensus published 2026-11-27 01:00:00, 1 relays and 0 bridges matching 'moria1' were running. [Confidence: High] [C:tor-metrics:moria1-c] [S:tor-metr]

## Evidence Map
| Finding | Claim ID | Source ID | Verdict / Status |
|---|---|---|---|
| As of the Onionoo consensus published 2026-11... | [C:tor-metrics:moria1-c] | [S:tor-metr] | ACTIVE |

## Sources
- **[S:tor-metr]** Tor Metrics network snapshot for 'moria1' — `onionoo.torproject.org` (Tier: STANDARD, Published: 2026-11-27T01:00:00+00:00, Retrieved: 2026-11-27T02:39:44.715556+00:00; retrieval time does not establish currentness, Injection Risk: False)
```

`export_text_citations` likewise lists
`[S:tor-metr] [Tor Metrics network snapshot for 'moria1'](https://onionoo.torproject.org/summary?search=moria1&limit=5&running=true)`.
Note: `[S:tor-metr]` is the renderer's normal short form —
`format_citation_id` returns the shortest >=8-character unique prefix
of the source id `tor-metrics:moria1`; the full id is in the source
record, not truncated data. The earlier "blank finding" in a first
render attempt was the run script's own bug (it passed the finding text
under key `text`; the renderer reads `statement`/`conclusion`), fixed
in the script and re-run — not a product issue.

Hermetic suite re-run on this base (same venv, from `IntelX/`):
**18 passed in 174.05 s** (`tests/test_ig_intelx_tor_metrics.py`).

## Live findings (root causes, verified against raw Onionoo documents)

Probed with plain `curl` against the same live endpoints, same relay,
same morning (documents version `8.0`, `relays_published`
`2026-11-27 01:00:00`):

1. **`/bandwidth`, `/weights`, `/uptime` entries are keyed by
   `fingerprint`, not `f`.** Live entry keys: bandwidth
   `fingerprint, overload_ratelimits, read_history, write_history`;
   weights `consensus_weight, consensus_weight_fraction,
   exit_probability, fingerprint, guard_probability,
   middle_probability`; uptime `fingerprint, flags, uptime`. The short
   key `f` exists only in `/summary`. The client matches on
   `r.get("f", "") == fingerprint` (`tor_metrics.py`:
   `relay_bandwidth` / `relay_weights` / `relay_uptime`), so it never
   matches and raises `TorMetricsUnavailable` for every relay. These
   documents also carry no `n` nickname field, so the client's
   `nickname=str(entry.get("n", ""))` would be empty even after the
   key fix.
2. **`consensus_weight` and `consensus_weight_fraction` are
   period-keyed history maps, not plain numbers.** Live
   `consensus_weight.1_month`: 186 values, factor
   `0.02002002002002002`, last value `999`. The client does
   `int(weight) if isinstance(weight, (int, float)) else None`, so even
   with the fingerprint key fixed, weights would come back `None` /
   `None`. They need the same `_parse_history` treatment as bandwidth
   / uptime.
3. **`/clients` carries no per-country data in the live document.**
   Live `/clients`: `relays: []`, `bridges: 3481` entries; bridge
   entries have only `fingerprint` and `average_clients`, no `country`
   field at all; `average_clients` is a period-keyed history map
   (first bridge, `1_month`: 31 values, factor `0.3305765765765766`,
   last value `243`), not a plain number. The client reads `relays`
   only, expects `country` and a numeric `average_clients`, so
   `network_clients()` returns `[]` and the snapshot reports
   `total_average_clients: None`, `countries: 0`. The "users by
   country" censorship metric as implemented does not exist in the
   live `/clients` document; the endpoint is per-bridge average
   clients. (Minor: live history maps also carry a `6_months` period,
   which `_HISTORY_PERIODS` does not list — harmless, `1_month` is
   picked first.)
4. **Ground truth the client should have returned for moria1**
   (from the raw live documents, same fingerprint): bandwidth
   `write_history.1_month` first `2026-10-26 12:00:00`, last
   `2026-11-25 12:00:00`, interval `86400`, factor
   `25813.976216216215`, 31 values, last value `317` (read last `214`);
   weights `consensus_weight.1_month` last value `999`;
   uptime `1_month` first `2026-10-27 02:00:00`, last
   `2026-11-26 22:00:00`, factor `0.001001001001001001`, 186 values,
   last value `999`.

## Five states

- Implemented: YES (repo-side, PR #2039 merged)
- Tested: YES hermetic (18/18 on this base) — BUT the hermetic tests
  encode the wrong live document shapes, so they pass while the live
  leg fails. Live coverage is the gap.
- Merged: YES (PR #2039, merge `63538e60`, 2026-11-27 07:39:45 IST)
- Deployed: NO — the production leg (`ENABLE_TOR_METRICS=True` +
  service restart on FRIDAY-Server) remains gated by the owner stop
  order of 2026-11-24. This leg proves the merged code against the
  live public API only; it is NOT a production deployment.
- Production-verified: NO

## What remains

- Fix `TorMetricsClient` for live Onionoo 8.0 shapes (follow-up task):
  match `fingerprint` (not `f`) in `/bandwidth` / `/weights` /
  `/uptime`; parse `consensus_weight` /
  `consensus_weight_fraction` as histories; rework or drop the
  per-country clients metric to match the live `/clients` document
  (per-bridge `average_clients` histories, no country field).
  Re-run this live leg after the fix and re-file the evidence.
- Production leg still gated by the owner stop order of 2026-11-24
  (enable `ENABLE_TOR_METRICS` on IntelX-Server + restart + live
  `GET /api/v1/osint/tor-metrics` check). Needs coordinator clearance
  + stop-order lift; no server was touched in this leg.

— Muse 14
