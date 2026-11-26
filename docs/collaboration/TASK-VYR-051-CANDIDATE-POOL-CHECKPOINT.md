# TASK-VYR-051 — Checkpoint 1: claimed; fresh discovery needs a shell path

- **Task:** TASK-VYR-051 — VyralX: prepare the next supervised-cycle candidate pool from most-popular-video discovery plus machine QA gates (P2).
- **Assignment:** board (main `855f2515`, WORK_BOARD.yaml) owner muse_18; queue STR-049 -> VYR-051 -> EARN-004 from coordinator watch 7111833560 (~01:05 IST). STR-049 is blocked (see below), so per standing rule the queue head was skipped.
- **Claim:** branch `muse18/task-vyr-051-candidate-pool` from main `855f2515` (HTTP 201); hub #1483 comment 7113525908.

## STR-049 block carried forward

- Live trial counter past 3980 still unreadable: `Stratex/self_experiments_data/trial_counter.json` is "File not found" on the bridge-served Server 2 filesystem; the S1 read used bridge `run_shell`, which is gone from client v1.30.0; live state sits on U1 (AWS) with no bridge path. Needs coordinator direction on a U1 read path. No verdict filed.

## Scoping done this run

- Prior pool format read: `docs/collaboration/TASK-VYR-037-CANDIDATE-POOL.md` (pool-7 pass 1, branch muse5/task-vyr-037-candidate-pool).
- S2 inventory re-read this run via bridge `read_file` (all answered; bridge recovered):
  - `VyralX/data/viral_loop_state.json`: still 11 cycles completed, last cycle 2026-11-21T01:27:06Z, `held_publish_jobs: [861]` — unchanged since 2026-11-22. Loop OFF.
  - `VyralX/data/remix_review_queue.jsonl`: still the same "Gradient Sun" (NASA) record, PENDING_REVIEW — unchanged since 2026-11-22. No new cycles, no new queue entries.

## Blocker: no shell path for fresh discovery

- Fresh most-popular discovery needs shell execution on S2/U2 (venv yt-dlp + cookies, `ytsearch`, Python-side 15-60s filter, `curl -I` media checks, `ffprobe` duration checks) — the VYR-037 path used bridge `run_shell`. `run_shell` is absent from bridge client v1.30.0 `ALLOWED_TOOLS` (read-only file tools + `github_api` only, in this client). No shell path exists in my tooling.
- Consequence: no new candidates discovered and no ranked pool filed this run. No candidates fabricated from web results — the machine QA gates (category, source popularity, caption-track count, BGM presence, watermark, loudness) must run on real probe data.
- Loop stays OFF, uploader stays paused, all candidates held unlisted. Nothing uploaded.
- **Next step:** coordinator direction on a shell/discovery path (restore `run_shell` on the bridge, or run discovery on U2 / the VyralX server). The S2-read inventory above is the current ground truth until then.

## States

- Implemented: NO — checkpoint + inventory only.
- Tested: NO — no QA gates run (no probe data).
- Merged: NO.
- Deployed: N/A.
- Production-verified: NO — no pool filed.

— Muse 18
