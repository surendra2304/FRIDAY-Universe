# TASK-VYR-056: Media QA gates — checkpoint 1 (diagnosis + proof attempt) — Muse 18

- Task: TASK-VYR-056 (VyralX: unblock the media QA gates — yt-dlp download
  broken, n-challenge + SABR-only; evaluate fix options, implement, prove one
  real download + full machine-QA pass). Branch
  `muse18/task-vyr-056-media-qa-gates` (claimed 2026-11-24 ~18:09 IST, hub
  comment 7131991645; assignment in coordinator watch 7131647996).
- Checkpoint 1 filed 2026-11-24 ~22:45 IST. Grant: coordinator watch 7137288514
  (run scheduled 21:17 IST) — scoped read-only on VyralX-Server
  (13.211.162.71): VYR-051 discovery AND VYR-056 proof — exactly ONE real
  download to /tmp + full machine-QA pass, file removed afterwards, no
  renders/uploads/loop/moves/deploys. Read-only verification, inside the
  owner stop order.

## Route verified (live)

- Bridge `run_shell`, server 5 = VyralX-Server, works from my client
  (client.py `run_shell` already allowlisted for the FUT-029 pull).
  Host `ip-172-26-12-48`, workspace `/opt/friday_universe` (deployment copy,
  no `.git`). `yt-dlp 2026.10.21` (`/opt/friday_universe/venv/bin/yt-dlp`,
  venv Python 3.10). Cookies `VyralX/data/youtube_cookies.txt`, 3,146 bytes,
  Nov 24 15:48 (fresh). `deno 2.9.8`, `node v18.19.1`, `ffmpeg`/`ffprobe`
  in `/usr/bin`. Bridge transport flaked on ~half the read-backs this run
  (IncompleteRead / event stream ended) — every server-side effect was
  verified by a separate call, never assumed.

## Diagnosis (stands, first-hand)

- The code fix pre-exists and is deployed: `VyralX/app/services/ytdlp_support.py`
  line 81, `opts.setdefault("remote_components", ["ejs:github"])`, applied by
  `apply_defaults` at all 4 YoutubeDL call sites. Nothing to implement
  code-side.
- Metadata fetch works: webpage, web embedded client config, player
  `4ee1fa28-main`, player API JSON and tv samsung player API JSON all
  download — cookies are fine, network is fine. The failure is only the
  `n`-challenge solve step.

## Proof attempt — ONE real download, FAILED (new precise cause)

- Target: `OfEaVD7TtXM` ("Satisfying Pottery Spiral Designs #Shorts", 41s,
  3,615 views) — VYR-055 refresh-3 candidate 1, whose QA gates are all
  BLOCKED pending this task. Command: venv yt-dlp, cookies jar,
  `--remote-components ejs:github`, `--no-playlist`,
  `-f 'bv*[height<=1080]+ba/b[height<=1080]' --merge-output-format mp4`,
  output `/tmp/vyr056_proof_OfEaVD7TtXM`, URL
  `https://www.youtube.com/shorts/OfEaVD7TtXM`. Four variants tried:
  1. Default (deno): RC=1, no file. `[jsc:deno] Solving JS challenges using
     deno`, then `Error solving n challenge request using "deno" provider:
     Error running deno process (returncode: 1): Uncaught (in promise)
     TypeError: a.addOnDisposeCallback is not a function` (at
     `getFromPrepared`, `file:///tmp/$deno$stdin.js`). Then `n challenge
     solving failed: Some formats may be missing`, `Some web_embedded client
     https formats have been skipped as they are missing a URL. YouTube may
     have enabled the SABR-only streaming experiment`, `Only images are
     available for download`, `Requested format is not available`.
  2. `--js-runtimes node`: identical — still used deno, identical crash.
     The flag did not switch the EJS runtime.
  3. Deno hidden from PATH (`PATH=/usr/bin:/bin`): no `[jsc:...]` line at
     all — no usable runtime found; `n challenge solving failed` outright.
     Node 18.19.1 is present but the EJS path does not use it.
  4. `--remote-components ejs:npm`: identical deno crash. The failure is
     independent of the solver distribution (github vs npm).
- Conclusion: the break is in the solver-under-deno layer — deno 2.9.8 +
  the current EJS solver are incompatible on this host (the solver crashes
  inside its own `getFromPrepared` eval). The `--remote-components` code
  flag is necessary but NOT sufficient. No file was ever downloaded; no
  machine-QA pass could run; no numbers invented.
- Repair options (not attempted — any server-side version change is a
  live-host change outside the read-only proof grant; needs coordinator /
  owner direction): (a) pin deno and the EJS solver to a compatible pair
  (upgrade or downgrade one side); (b) check the yt-dlp EJS tracker for
  the `addOnDisposeCallback` crash; (c) vendor a pinned solver version.
  A repo-side pin is possible only if the solver version can be pinned
  through `remote_components` — to verify before filing.

## VYR-051 discovery probe (same run, granted route)

- Metadata-only discovery WORKS on VyralX-Server: one `ytsearch5` query
  (`oddly satisfying kinetic toy short`), `--flat-playlist --skip-download`,
  RC=0, 5 results with id/title/duration. The n-challenge only breaks
  media downloads, not discovery. VYR-051's discovery leg is runnable now;
  it is the working leg while VYR-056 awaits the version-fix direction.

## Hygiene

- No server change, no file installed, no service touched. `/tmp` logs left
  on VyralX-Server only (`vyr056_dl_node.log`, `vyr056_dl_node2.log`,
  `vyr056_dl_npm.log`, `vyr051_probe.log`); the proof target file was never
  created. Cookies never read (only size/mtime listed). No secret touched.
- States: implemented NO / tested NO / merged NO / deployed N/A /
  production-verified NO (diagnosis + failed proof filed; proof leg blocked
  on the deno/EJS version fix — direction asked on the hub).

## Checkpoint 2 — pin clearance received; exact versions recorded BEFORE any change

- Clearance: coordinator watch 7138911209 (22:17 run, 2026-11-24, ruling 3) —
  Muse 18 may pin deno + EJS solver to a compatible pair on VyralX-Server.
  Tooling fix, not a workload move. Record exact versions here before
  applying; file a rollback note; re-run the VYR-056 proof after.
- Exact versions recorded 2026-11-24 ~23:35 IST, first-hand via bridge
  `run_shell` server 5 (host `ip-172-26-12-48`):
  - yt-dlp `2026.10.21` (`/opt/friday_universe/venv/bin/yt-dlp`; venv
    Python 3.10, `yt_dlp/__init__.py` under
    `venv/lib/python3.10/site-packages/`).
  - EJS solver cached: `~/.cache/yt-dlp/challenge-solver/lib.json` —
    `yt-dlp_version 2026.10.21`, solver `version 0.8.0`, `variant minified`
    (meriyah 6.1.4, astring 1.9.0 bundled).
  - `yt-dlp-ejs` package: NOT INSTALLED in the venv (pip list: yt-dlp
    2026.10.21, no yt-dlp-ejs; no ejs entry in site-packages).
  - deno `2.9.8` (stable, x86_64-unknown-linux-gnu, v8 15.0.245.2-rusty,
    typescript 6.0.3) at `/usr/local/bin/deno` (96,056,011 bytes, root-owned,
    installed Nov 24 11:07).
  - node `v18.19.1` at `/usr/bin/node` (EJS path does not use it; Node 22+
    is the documented EJS minimum).
  - yt-dlp 2026.10.21 METADATA pins (read first-hand): `yt-dlp-ejs==0.8.0`
    (extra `default`); `deno>=2.9.8` (extra `deno`).
  - `VyralX/requirements.lock` pins `yt-dlp==2026.10.26` — installed
    2026.10.21 is BEHIND the lock pin.
  - EJS upstream (yt-dlp/ejs README, read 2026-11-24): runtime requirement
    deno `>=2.3`, dev requirement deno `>=2.6`; Node `>=22`.
- Refined diagnosis: the cached solver is ALREADY the exact pinned
  version (EJS 0.8.0 for yt-dlp 2026.10.21), and the `ejs:npm` remote
  variant crashed identically — so the crash is not a stale/mismatched
  solver version. Deno 2.9.8 meets every documented requirement
  (EJS >=2.3; yt-dlp METADATA >=2.9.8). The `a.addOnDisposeCallback is not
  a function` crash inside the solver's `getFromPrepared` eval therefore
  points at (i) the EJS 0.8.0 bundle vs deno 2.9.8, or (ii) a YouTube
  player-JS change the 0.8.0 solver does not handle — NOT at a wrong
  version on either side by the documented pins. Downgrading deno below
  2.9.8 would violate yt-dlp 2026.10.21's own `deno>=2.9.8` pin; do NOT
  do that without a new ruling.
- Rollback note (no server change made yet — this checkpoint is the
  pre-change record): for pin step A (`pip install yt-dlp-ejs==0.8.0` into
  `/opt/friday_universe/venv`), rollback is
  `/opt/friday_universe/venv/bin/pip uninstall -y yt-dlp-ejs` (cache
  `~/.cache/yt-dlp/challenge-solver/lib.json` untouched — it predates any
  change). For ANY deno replacement: back up `/usr/local/bin/deno` to
  `/tmp/deno-2.9.8.bak` first; rollback is restoring that file. For a
  yt-dlp upgrade: BLOCKED — 2026.10.26 requires Python 3.11+, venv is
  3.10; do not attempt without a coordinator ruling on the Python upgrade.
- Pin plan (in order): (A) install `yt-dlp-ejs==0.8.0` locally so yt-dlp
  uses the pinned package instead of the remote-component cache, then
  re-run the proof (same target `OfEaVD7TtXM`, same command); (B) if (A)
  fails identically, check whether a newer deno than 2.9.8 exists and
  whether the EJS tracker records this crash, and report back for
  direction — do not guess a deno downgrade; (C) yt-dlp 2026.10.26 +
  Python 3.11 is a separate decision for the coordinator.
- States: implemented NO / tested NO / merged NO / deployed N/A /
  production-verified NO (pin clearance received; versions recorded;
  pin step A next).

## Checkpoint 3 — pin step A applied; proof STILL FAILS identically; no newer deno/EJS exists

- Pin step A applied 2026-11-24 ~23:45 IST under watch 7138911209 ruling 3:
  `/opt/friday_universe/venv/bin/pip install 'yt-dlp-ejs==0.8.0'` —
  "Successfully installed yt-dlp-ejs-0.8.0" (pip show confirms 0.8.0).
  This was the missing piece: the venv had no yt-dlp-ejs package at all.
- Proof re-run, same target `OfEaVD7TtXM`, same command, WITHOUT the
  `--remote-components` flag (so the local pinned package is used):
  RC=1, no file. Identical crash: `[jsc:deno] Solving JS challenges using
  deno`, then `Error solving n challenge request using "deno" provider:
  Error running deno process (returncode: 1): Uncaught (in promise)
  TypeError: a.addOnDisposeCallback is not a function` (at `getFromPrepared`,
  `file:///opt/friday_universe/$deno$stdin.js`), player `b485e332-main`
  (rotated from `4ee1fa28-main` at checkpoint 1 — same crash on the new
  player). `n challenge solving failed`, SABR-only skip, only images
  available, requested format not available. Log on VyralX-Server:
  `/tmp/vyr056_dl_pinA.log`; proof file never created.
- Decisive, checked first-hand this run via the GitHub releases API:
  latest deno IS v2.9.8 (published 2026-10-21) and latest EJS IS 0.8.0
  (published 2026-03-17). No newer release of either exists. The installed
  pair (yt-dlp 2026.10.21 + EJS 0.8.0 + deno 2.9.8) is exactly the pair all
  upstream pins describe — and it still crashes. No version pin within the
  available releases fixes this. The break is a YouTube player-JS change
  the 0.8.0 solver cannot handle, or a deno 2.9.8 regression — an upstream
  matter, not a version choice. yt-dlp itself asks for an upstream report
  ("Please report this issue on https://github.com/yt-dlp/yt-dlp/issues").
- Install KEPT in place: it is the version yt-dlp pins, and it removes the
  missing-package gap. Rollback remains `pip uninstall -y yt-dlp-ejs`
  (cache untouched). No other server change: deno untouched (2.9.8),
  no Python upgrade (2026.10.26 needs 3.11+, venv is 3.10 — blocked on a
  ruling, not attempted), Node untouched (18.19.1; EJS needs Node 22+ —
  an upgrade path, not attempted).
- Direction owed from the coordinator: report upstream to yt-dlp, or rule
  on the Node 22+ runtime path, or wait for a new EJS/yt-dlp release.
  Proof leg stays blocked; discovery leg unaffected.
- States: implemented NO / tested NO / merged NO / deployed N/A /
  production-verified NO (pin step A failed identically; blocked on
  upstream — direction owed).

— Muse 18

## Checkpoint 4 — leg CLOSED by coordinator ruling 4 (2026-11-25 ~00:14 IST)

- Coordinator watch 7140957093 (run scheduled 2026-11-24 23:37 IST), RULING 4:
  "VYR-056 pin (M18): leg CLOSED as unachievable. No newer deno/EJS exists
  (step A failed identically for M18 and in the earlier attempt). M18 files
  the failed-step evidence, then moves on; no further pin attempts. M18 holds
  VYR-051."
- This PR files that evidence: checkpoints 1–3 above (diagnosis, failed proof,
  failed pin step A with the decisive no-newer-release check) rebased onto
  current main `abe9b9f4`, plus this closure note. No code change, no server
  change, no board hunk — the VYR-056 board record rides in the consolidated
  board PR.
- No further pin attempts. Upstream report / Node 22+ path is for the
  coordinator to rule on, not for M18 to pursue — the leg is closed.
- States: implemented NO / tested NO / merged NO (this PR open) / deployed
  N/A / production-verified NO (leg closed as unachievable, per ruling 4).

— Muse 18
