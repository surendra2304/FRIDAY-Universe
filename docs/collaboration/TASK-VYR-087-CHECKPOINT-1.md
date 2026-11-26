# TASK-VYR-087: Checkpoint 1 — scoping (transition from FRD-058) — Muse TP6

- Task: TASK-VYR-087 (P1, VyralX: supervised cycle 6 candidate pool —
  most-popular discovery + machine QA gates). Claimed 2026-11-26 ~14:20 IST,
  hub comment 7187045309. Branch `musetp6/task-vyr-087-candidate-pool` @
  main `84982689`. Board AVAILABLE → CLAIMED flip rides in the work PR
  (standing orders).
- Transition: FRD-058 repo leg MERGED — work PR #1962, merge `703965cc`,
  merged_at 2026-11-26T08:04:03Z by surendra2304; CI 10/10 green on head
  `746e1b49` first-hand; board IN_REVIEW on main `84982689` via coordinator
  board PR #1974 (WATCH150, hub 7186930415). FRD-058 branch already deleted
  (404 verified this run — coordinator-side cleanup). Live leg (one real
  article read on production FRIDAY at two rates) stays GATED, clearance
  owed; nothing further owed from TP6 on FRD-058 until clearance.
- Acceptance (board, main `84982689`, blob `557a64cc`, 3,023,567 bytes,
  24,014 lines): (1) pool of fresh candidates from most-popular-video
  discovery, each passing the machine QA gates (caption-track count, BGM
  presence, watermark, loudness); (2) pool filed as
  `docs/collaboration/TASK-VYR-087-POOL.json` + candidate-pool doc;
  (3) loop stays OFF, uploader paused, renders held unlisted.
- Precedent chain (read first-hand this run): VYR-053 (cycle 4) / VYR-054
  (cycle 5, PR #1655) / VYR-055 (refresh, Muse 5, 2026-11-24) / VYR-057.
  VYR-055 method: flat-playlist ytsearch discovery on S2, 7 fresh
  candidates from 60 results, duration 15–60s PASS; gates recorded
  PENDING/BLOCKED, not passed, not failed; pool filed as
  `TASK-VYR-055-POOL.json` + doc; script
  `VyralX/scripts/find_viral_candidates_flat.py` + offline tests + CI
  tier-1 line. VYR-055 merged on that shape.
- S2 state verified first-hand this run (bridge, read-only):
  `get_system_info` — Oracle Server 2 (10.0.0.120), workspace
  `/opt/friday_universe`, git branch `muse10/task-sen-036-live-proof-run-2`
  @ `a7e21456`, both Oracle servers ONLINE. `read_text` Server 2
  `/opt/friday_universe/VyralX/scripts/find_viral_candidates_flat.py` —
  READABLE, first 25 lines: the VYR-055 flat discovery script is present
  on S2; its docstring states flat search works (rc 0) and media gates
  stay BLOCKED until the download path is repaired. The S2 tree is
  present — the 2026-11-25 partial-state finding stands; the pool doc's
  "whole tree deleted" line does not match what is readable.
- Blocker 1 — machine QA gates cannot run: VYR-056 leg CLOSED as
  unachievable (coordinator ruling 4, watch 7140957093): yt-dlp download
  broken (n-challenge deno 2.9.8 crash + SABR-only, no formats); pin step
  A failed identically; no newer deno/EJS exists (latest deno 2.9.8,
  latest EJS 0.8.0, checked first-hand by Muse 18). No repair direction
  has landed in WATCH145–150 (carried items only: S2 disk cleanup
  decision, #1852 fix, M18 API-007 blocked, MEM-034 bridge grant
  decision). VYR-087 acceptance bullet 1 ("each passing the machine QA
  gates") is unmeetable until the download path is repaired. VYR-055
  precedent filed the pool with gates PENDING/BLOCKED and merged.
- Blocker 2 — discovery needs a grant + a run route TP6 does not hold:
  the flat script must run on S2 (venv yt-dlp + cookie jar + exclusion
  sets live there). TP6's bridge helper in this account allows only
  `get_system_info` and `read_text` — no `run_shell`. Running discovery
  is a live-host action under the owner stop order (2026-11-24 ~16:42
  IST); it needs a coordinator grant (read-only scope: flat-playlist
  discovery only, `--skip-download`, loop OFF, no renders/uploads/moves)
  and a run_shell-capable route, as granted to Muse 18 for VYR-056.
- Decisions owed to Muse: (1) grant for a read-only S2 discovery run
  (flat script, loop OFF) and who runs it; (2) ruling: is gates
  PENDING/BLOCKED acceptable for the VYR-087 pool (VYR-055 precedent), or
  does VYR-087 wait for the download-path repair (upstream yt-dlp report
  / Node 22+ path / fresh session / PO-token — all still owed from
  VYR-056)? (3) If the pool is to be filed with gates pending, confirm
  the VYR-055 shape (pool JSON + doc + script reuse, no new code) is the
  expected deliverable.
- No repo code executed (execution-risk flag stands); no S2 change made
  (read-only probes only). No candidates invented — none filed until
  discovery runs.
- States: implemented NO / tested NO / merged NO / deployed N/A /
  production-verified NO (scoping only; discovery + gates blocked pending
  Muse's rulings above).

— Muse TP6
