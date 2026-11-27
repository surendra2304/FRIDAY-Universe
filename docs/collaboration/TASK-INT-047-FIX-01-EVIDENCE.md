# TASK-INT-047-FIX-01 — Live evidence: per-relay detail failures fixed, leg re-run

## Verdict: PASS — all three per-relay detail methods return real values live; the clients metric reflects the real /clients document

The INT-047 live leg (2026-11-27 ~08:09 IST) found the merged
`TorMetricsClient` failing on every per-relay detail call against live
Onionoo 8.0 (`TorMetricsUnavailable` for `relay_bandwidth` /
`relay_weights` / `relay_uptime`) and the clients metric empty. This
fix corrects the three root causes against the live document shapes
and re-runs the leg with the same query (`moria1`, limit 5). All three
detail methods now return real values, verified against fresh raw
Onionoo documents, and the census + citation seam still work.

## What changed (implementation PR)

`IntelX/intelx/connectors/tor_metrics.py` + `IntelX/tests/test_ig_intelx_tor_metrics.py`
(2 files; no board hunk; no settings defaults changed; no secrets).

1. **Fingerprint key.** Live /bandwidth, /weights and /uptime entries
   are keyed by `fingerprint`; the client matched the short key `f`
   (which exists only in /summary), so it never matched and raised for
   every relay. The client now matches `fingerprint` (falling back to
   `f` for tolerance). These documents also carry no `n` nickname
   field, so detail results report `nickname: ""` honestly.
2. **Weight histories.** Live `consensus_weight` /
   `consensus_weight_fraction` are period-keyed history maps, not
   plain numbers. They are now parsed via `_parse_history` and the
   scalars are the latest values scaled by the history factor
   (`value * factor`, per the Onionoo spec: "Factor by which
   subsequent data values need to be multiplied to obtain original
   values"). The full histories are kept on the result
   (`consensus_weight_history` /
   `consensus_weight_fraction_history`) so the evidence is not
   discarded. Plain-number weights still pass through.
3. **Clients metric rework.** Live /clients carries NO country field
   and `relays` is empty: it is per-BRIDGE average clients only
   (entries: `fingerprint` + `average_clients`, a period-keyed history
   map). `network_clients()` now returns per-bridge rows
   (`TorBridgeClients`); the snapshot's `total_average_clients` is the
   sum of per-bridge average clients (users connecting via bridges)
   and `countries` is empty. The source text and claims now say
   "connecting via bridges" and state honestly that no per-country
   breakdown is published. Also: `_HISTORY_PERIODS` gains `6_months`
   (the live API serves it).

## Root causes re-verified against fresh live documents

Probed with plain `curl` against the same live endpoints, same relay,
2026-11-27 ~20:20 IST (documents version `8.0`, `relays_published`
`2026-11-27 13:00:00` at probe time) — all three causes from the
original leg confirmed, not assumed:

- /bandwidth entry keys: `fingerprint, overload_ratelimits,
  read_history, write_history`. /weights entry keys:
  `consensus_weight, consensus_weight_fraction, exit_probability,
  fingerprint, guard_probability, middle_probability`. /uptime entry
  keys: `fingerprint, flags, uptime`. No `f`, no `n` in any of them.
- `consensus_weight.1_month`: 186 values, factor
  `0.02002002002002002`, last value `999`. `consensus_weight_fraction.1_month`:
  186 values, factor `1.1552552552552552e-10`, last value `887`.
- /clients: `relays: []`, `bridges: 3479`; bridge entries have only
  `fingerprint` and `average_clients`; no `country` field in any of
  the first 5 bridges. First bridge `average_clients.1_month`: 31
  values, factor `0.3305765765765766`, last value `243`.
- The factor semantics were confirmed from the Onionoo spec itself
  (https://metrics.torproject.org/onionoo.html, fetched 2026-11-27):
  history `factor` is the "Factor by which subsequent data values
  need to be multiplied to obtain original values."

## Live leg re-run (same query as the original leg)

- Base: branch `muse14/task-int-047-fix-01` (fixed code), run
  2026-11-27 ~20:47 IST (fetched_at `2026-11-27T15:17:34Z`).
  Script: `/tmp/muse14-int047-fix01/live_leg.py` (kept in the
  worktree run, not committed). Client: the fixed `TorMetricsClient`,
  query `moria1`, limit 5, then `relay_bandwidth` / `relay_weights` /
  `relay_uptime` for the one returned relay, then `to_source()` /
  `to_claims()` through the real `intelx.core.report` pipeline.
- Transport note (honest, same as the original leg): the client's
  DEFAULT fetcher (`HttpFetchConnector`) could not run in this
  sandbox — its SSRF guard resolves `onionoo.torproject.org` to
  `198.18.51.45` (sandbox DNS returns a CGNAT `198.18.0.0/15`
  address) and raises `SSRFBlocked`. The live API is reachable
  (plain `curl`: HTTP 200, ~1 s). The client was run with a real
  `httpx` transport doing genuine live HTTPS GETs (same `(status,
  final_url, body)` shape). In production DNS the guard resolves
  Onionoo to a real public IP — a sandbox artifact, not a production
  finding.

### Snapshot (live, `relays_published` 2026-11-27 14:00:00)

- Onionoo protocol version: `8.0`
- Relays returned: 1; running relays: 1; running bridges: 0
- Relay: `moria1`, fingerprint
  `1A25C6358DB91342AA51720A5038B72742732498`, running `true`,
  addresses `["128.31.0.39"]`
- Total average clients (via bridges): `161626`; bridge rows: `3478`;
  countries: `0`

### Per-relay detail calls — ALL RETURN REAL VALUES (were all TorMetricsUnavailable)

- `relay_bandwidth` (0.64 s): **OK**. `write_history.1_month`:
  31 values, first `2026-10-27 12:00:00`, last `2026-11-26
  12:00:00`, interval `86400`, factor `25813.976216216215`, last
  raw `314` → scaled `8,105,589` bytes/s. `read_history.1_month`:
  31 values, last raw `201` → scaled `201,621` bytes/s. Cross-checked
  against the raw /bandwidth document fetched by curl: exact match
  (last raw 314 / 201, same factors).
- `relay_weights` (0.58 s): **OK**. `consensus_weight` = `20`
  (999 × 0.02002002002002002); `consensus_weight_fraction` =
  `1.0247114114114114e-07` (887 × 1.1552552552552552e-10).
  Histories kept: `consensus_weight_history.1_month` 186 values,
  last raw `999`; `consensus_weight_fraction_history.1_month` 186
  values, last raw `887`. Cross-checked against the raw /weights
  document: exact match.
- `relay_uptime` (0.81 s): **OK**. `uptime.1_month`: 186 values,
  first `2026-10-27 14:00:00`, last `2026-11-27 10:00:00`, factor
  `0.001001001001001001`, last raw `999`. Cross-checked against the
  raw /uptime document: exact match.

### Clients metric — reflects the real /clients document

- `network_clients()` (direct call): `3478` rows; first three:
  `0009FD59…` → `80` (243 × 0.3305765765765766), `004B3E68…` →
  `3`, `005F44D1…` → `None` (no parseable history — honest).
- Direct total `161626` == snapshot `total_average_clients`
  `161626` (matches).
- No country rows (the live document has no country field).

### Citation seam — still works

- `to_source()` id `tor-metrics:moria1`; 3 claims
  (`tor-metrics:moria1-census`, `tor-metrics:moria1-relay-1A25C635`,
  `tor-metrics:moria1-clients-total` — "Estimated Tor users
  connecting via bridges averaged 161626").
- `filter_and_ground_findings`: grounded 1, unverified 0. Rendered
  report markdown carries `[S:tor-metr]`; `export_text_citations`
  lists `[S:tor-metr] [Tor Metrics network snapshot for
  'moria1'](https://onionoo.torproject.org/summary?search=moria1&limit=5&running=true)`.

## Tests

- File suite `tests/test_ig_intelx_tor_metrics.py`: **23 passed in
  247.43 s** (18 original tests updated to the real Onionoo 8.0
  shapes + 5 new: fingerprint-key match for bandwidth/uptime,
  short-`f` fallback, plain-number weight passthrough, bridge
  clients, empty bridges, `6_months` period preference).
  Baseline before the fix on the same base: 18 passed in 175.96 s
  (the old tests encoded the wrong shapes).
- Full IntelX tier-1 suite (12 files): **141 passed in 1315.83 s
  (0:21:55), 0 failed** (fresh venv
  `~/workspace/venvs/muse14-int047-fix01`).

## Five states

- Implemented: YES (fix in the implementation PR)
- Tested: YES hermetic (23/23) + live leg re-run PASS (all three
  detail methods return real values, verified against raw documents)
- Merged: NO (implementation PR open)
- Deployed: NO — the production leg (`ENABLE_TOR_METRICS=True` +
  service restart on IntelX-Server) remains gated by the owner stop
  order of 2026-11-24. This leg proves the fixed code against the
  live public API only; it is NOT a production deployment.
- Production-verified: NO

## What remains

- Production leg still gated by the owner stop order of 2026-11-24
  (enable `ENABLE_TOR_METRICS` on IntelX-Server + restart + live
  `GET /api/v1/osint/tor-metrics` check). Needs coordinator clearance
  + stop-order lift; no server was touched in this leg.
- The detail methods report `nickname: ""` because /bandwidth,
  /weights and /uptime carry no nickname field — the fingerprint
  identifies the relay; a caller that needs the nickname should take
  it from the /summary census.

— Muse 14
