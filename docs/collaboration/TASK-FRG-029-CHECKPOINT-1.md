# TASK-FRG-029 — CHECKPOINT 1 (scoping + upstream re-verification) — Muse 12 — 2026-11-26 ~19:55 IST

## Claim of record
- Hub comment 7193377341 (~18:53 IST). Queue at claim: FRG-029 → INT-054.
- **Stall found by the 19:53 IST hourly self-check and repaired in this run:** ~1 h after the claim the branch `muse12/task-frg-029-forge-repos-wave3` was still at main tip (4ab2643c), zero commits, no checkpoint (claim post only). Same mechanism as the FRG-025 / STR-078 / API-007 stalls: the work-request cycle stays cancelled while a task is held, so no work run fires — the self-check is the repair leg. This checkpoint filed on the claim branch this run.

## Board verified first-hand this run (main `4ab2643c`, WORK_BOARD.yaml)
- TASK-FRG-029: AVAILABLE / owner muse_12 / branch null / pr null. P2. No competing hub claim.
- Acceptance (verbatim shape): REPO-IMPLEMENT (owner order 2026-11-24: implement ALL 102 scouted repos): net-merge (reference-only), Plexo (reference-only) — owner-utility repos: prove with live evidence on the owner's own machines whether each works or not; no paper disposition accepted. For reference-only entries: a paper judgement is NOT a result — prove with live evidence whether it works in the agent or not (live trial or guardrail proof of absence from every production path), and file that evidence per repo. Real build task for another agent executed end-to-end through Forge and its output actually used by that agent in production, per item.

## Registry re-verified first-hand this run (main `4ab2643c`)
- Registry data file `IntelX/intelx/registries/scouted_repos.json` — blob `a18c2403451881ba89209b439b0126765d160c1f`, unchanged since INT-044 checkpoint 1 (same blob on mains be3f303e, a0a9f1ba, 98b1ce8d). Count 102.
- Both entries read from the registry file on this main:
  - `net-merge` — repo `net-merge/net-merge`, fit reference-only, agents NONE (owner utility), card `net-merge.md`, license MIT, language Go. "A free tool to use all your internet connections at once on Windows, macOS, Linux and Android. It creates a virtual TUN adapter and load-balances new connections across Wi-Fi, Ethernet, mobile data and phone tethers — no account, no server, no VPN. Key limit (README): a single connection stays on a single link, so one single-stream download does not get faster; gains come from apps that open many connections."
  - `Plexo` — repo `anmolkapil/plexo`, fit reference-only, agents NONE (owner utility), card `plexo.md`, license MIT, language TypeScript (Electron/React). "A free, open-source desktop download manager (Windows/macOS/Linux, Electron) that speeds up a single download: splits one file into chunks via HTTP range requests and downloads chunks in parallel across every selected connection, balancing load, racing slow tail chunks, then reassembling and verifying. Also torrents, magnet/.torrent, Usenet NZBs, browser-extension capture, pause/resume, scheduling. Caveat: each network needs its own upstream — Wi-Fi + Ethernet on the same router adds nothing. Pre-release (v1.0.0-rc), installers not yet code-signed."
- Spec cards `net-merge.md` / `plexo.md` named in the registry are NOT present as files in the repo (searched repo-wide this run) — the registry entry is the card of record; noted, not treated as a gap in the disposition.

## Upstream re-verification — live GitHub API reads, this run (~19:55 IST)
| Repo | License | Default branch | Last push | Latest release | Stars / forks | Archived | Open issues |
|---|---|---|---|---|---|---|---|
| net-merge/net-merge | MIT | main | 2026-11-09 | v0.3.7, 2026-11-09 | 3782 / 214 | No | 12 |
| anmolkapil/plexo | MIT | main | 2026-11-25 | v1.0.0-rc.15, 2026-10-11 (still rc series — no 1.0 final) | 5927 / 443 | No | 50 |
- Both upstreams are live and actively maintained (Plexo pushed yesterday). Both MIT, matching the registry. Plexo's registry caveat ("usable by the owner as-is once it hits 1.0") still holds: latest release is still an rc (rc.15).

## Repo-side disposition re-verified on main `4ab2643c`
- Method: depth-50 clone of the claim branch (= main tip, `git rev-parse HEAD` verified 4ab2643c) + case-insensitive grep over code files, excluding the registry file, its loader/generator/test, all `*.md`, and WORK_BOARD.yaml. Same method as INT-044 checkpoint 3.
- **net-merge: zero code hits outside registry/docs/board.** No implementation, no adoption. Reference held in the registry + board only. Disposition CONFIRMED.
- **Plexo: pattern-mined only, no upstream code vendored.** `Forge/forge_upgrade/parallel_download.py` lines 3–6: "Pattern adopted from Plexo (anmolkapil/plexo, MIT) — only the chunking pattern transfers to a cloud fleet; Plexo's multi-connection bonding [does not apply to] single-uplink VMs, and none of Plexo's code is used." Test `Forge/tests/test_ig2_frg04_parallel_download.py` cites the same pattern (TASK-IG2-FRG-04, MERGED PR #687). Disposition CONFIRMED — pattern-mining is what the reference-only rationale invites.
- This matches INT-044 checkpoint 3 (main 98b1ce8d) exactly; re-verified on the current main rather than carried.

## Live legs — HELD, ruling owed from Muse
No live step taken in this run; no fleet move; no Forge dispatch attempted.
- The owner stop order still holds live probe/deploy legs fleet-wide; no lift seen in WATCH164 / WATCH165 / WATCH166 as read this run.
- **New since checkpoint 49:** WATCH165 reversed WATCH163 Ruling 0 — the owner `run_shell` grant is confirmed genuine (hub 7193378286; owner tapped approve 18:25 IST, approval 7113152293 CLOSED). Direction in WATCH165 was given to Muse 18 (API-007 live leg) and TP6. **Not yet ruled for Muse 12 / FRG-029:** whether the confirmed grant covers these live legs — (a) a real download trial of net-merge and of Plexo on the owner's own machines, (b) one real build task per item executed end-to-end through Forge with its output actually used by another agent in production — and on which host. Ruling requested on the hub with this checkpoint.
- S2 state carried from WATCH165/166: disk 87% (49G, 42G used, 6.7G free), 1 GB RAM ceiling; VyralX restart loop; the five sleeper units were masked (WATCH166 correction: actor unidentified from hub records, fix confirmed correct per runbook §6). Cleanup still needs owner word per WATCH158 hold. None of this is FRG-029's to fix; recorded so the live-leg host choice is made with eyes open.

## Next legs
1. Muse's ruling on the live legs (grant coverage + host) — requested on the hub with this checkpoint.
2. Live trials per item once ruled: net-merge multi-connection trial + Plexo single-download trial on the owner's own machines, each with a failure case; one real Forge build task per item with output used in production.
3. Evidence + board flip to IN_REVIEW / MERGED ride in the work PR when DONE or genuinely BLOCKED (owner rule 1).

## Five states
Implemented NO (scoping + re-verification only) / tested NO / merged NO / deployed NO / production-verified NO.

## Queue / schedules / usage
- Queue: FRG-029 (head) → INT-054.
- Work-request task stays cancelled while FRG-029 is claimed (guard). Hourly self-check + weekly reset armed (verified this run).
- Usage: 34% (carried in WATCH166, posted 19:52 IST — not a fresh read this run). Free usage remains — no wrap-up.
- Verifier duty: 36 open PRs at last count (before this PR); no work PR for VYR-077 seen in the open list. Re-counted after this PR opens.
