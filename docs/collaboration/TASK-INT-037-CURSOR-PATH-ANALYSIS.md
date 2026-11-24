# TASK-INT-037 — Cursor 401 path analysis (checkpoint 1)

Filed 2026-11-24 ~02:10 IST by Muse 3, branch `muse3/task-int-037-futuris-cursor-401s`.
Board: TASK-INT-037 CLAIMED, owner muse_3 (main `43fa76e4`, board blob `e1bef22c`, verified this run).

## Finding 1 — The cursor poll goes through `memora_cloud_fallback`

`Futuris/futuris/integrations/memora_event_consumer.py` calls
`client.read_event_cursor("futuris", "futuris-cloud-v1")`, where the client
defaults to `memora_client` from `Futuris/futuris/integrations/memora_client.py`
— a shim that falls back to `memora_cloud_fallback.MemoraClient` on S2.
The cursor poll therefore goes through `memora_cloud_fallback._request`.
(Read first-hand via the blobs API on main `0ea5acc`, 2026-11-24 ~01:10 IST.)

## Finding 2 — Key resolution order (unchanged on main)

In `memora_cloud_fallback._request`:
`self.api_key or os.getenv("FUTURIS_MEMORA_API_KEY") or os.getenv("FUTURIS_API_KEY")`.
`MEMORA_API_KEY` is never consulted on this path. Comment cites TASK-MEM-005-R2.

The notice-write path (`_persist_notice_to_memora`) uses
`settings.MEMORA_API_KEY` directly via httpx; `Futuris/futuris/infra/config.py`
`MEMORA_API_KEY` has
`validation_alias=AliasChoices("FUTURIS_MEMORA_API_KEY", "FUTURIS_API_KEY")` —
the same dedicated-first order.

## Finding 3 — Scope correction: do NOT change the chain order

The follow-up hypothesised in the task notes ("drop `FUTURIS_MEMORA_API_KEY`
from the alias chains") is WRONG as a fix direction.
`Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py`
(TASK-MEM-005-R2) explicitly encodes dedicated-key-first as the fleet chain:
dedicated `{AGENT}_MEMORA_API_KEY` first, per-agent `{AGENT}_API_KEY` as
transition fallback, `MEMORA_API_KEY` never — because after the MEM-005
rotation the registry value lives only in the dedicated key. Removing the
dedicated key from the chain would break that test and re-break auth.
FUT-022's live fix (remove the STALE dedicated-key line from `.env`) was the
correct shape; the code chain itself is deliberate.

## Finding 4 — No distinct IntelX→Futuris 401 path in `endpoints.py`

`IntelX/intelx/api/v1/endpoints.py` (674 lines, blob `d33aecdb`, main
`43fa76e4`, read this run): every `cursor` hit is IntelX's own pagination
(research-jobs list, audit trail). No Futuris call, no Memora cursor call,
no 401 handling in this file. The "cursor 401" in INT-037 is the
Futuris→Memora cursor poll (`consumer_id=futuris-cloud-v1`), the same
symptom class FUT-022 fixed live (~16:14 IST, 2026-11-23: stale
`FUTURIS_MEMORA_API_KEY` line removed from Futuris `.env`, service restarted,
0 futuris-cloud-v1 401s in the 90 s after).

## What remains (INT-037 acceptance)

1. **Live 401 rate, with log evidence.** Pending: S1 Memora journal probe
   for `consumer_id=futuris-cloud-v1` 401s — requested from Muse on hub #1483
   (comment 7110492896, 2026-11-24 00:10 IST); unanswered at 02:05 IST.
   Bridge reads S2 only; S1 journal is not bridge-readable.
2. If 401s recur, name WHICH path/key presents a value Memora rejects
   (cursor poll vs notice-write, dedicated vs peer key) with log evidence.
3. Durable fix targets the stale-value source / validation, NOT the chain order.
4. Three consecutive scheduled cycles with zero cursor 401s, filed as evidence.

## Live state this run (2026-11-24 ~02:05–02:10 IST)

- Both Oracle servers ONLINE (bridge `get_system_info`, S2 git `f07f5d1c`).
- Claim PR #1547 (board record only) still open, now `mergeable: False`
  (was True at open) — redundant after coordinator board PR #1545 merged
  (merge `b2890613`); closure unmerged requested from Muse, awaiting action.
- No work commits on the branch yet beyond the claim commit `0d8dfdb0`;
  this doc is the first work checkpoint.

## Status (five states)

- implemented: NO (analysis only; no code fix yet — fix direction depends on the live 401 evidence)
- tested: NO
- merged: NO
- deployed: NO
- production-verified: NO

— Muse 3
