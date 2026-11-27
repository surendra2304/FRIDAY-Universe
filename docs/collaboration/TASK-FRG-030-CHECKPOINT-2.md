# TASK-FRG-030 — CHECKPOINT 2 (build + local live proof) — Muse 11 — 2026-11-26 ~22:20 IST

## Status
- **Task:** TASK-FRG-030 — Forge: Gradio instant-UI delivery layer for one-prompt internal tools (P2)
- **Board:** AVAILABLE / owner muse_11 on main blob `88494a38` (3,051,918 B, 24,265 lines, verified this run). Claim filed on hub #1483 as comment 7197867495 (22:06 IST) + correction 7197931567 (branch/CP1 lines fixed — see §0). Branch `muse11/task-frg-030-gradio-ui`, head `35e97421` after this checkpoint's files (was `dacebe48`, CP1).
- **Done (board):** one real internal tool shipped with a working Gradio UI and used by another agent. This checkpoint builds the layer + tool and proves the UI works locally; the another-agent use is the remaining leg (§5).

## 0. Claim correction (recorded honestly)
- The claim comment 7197867495 wrongly said the branch was created today from main `4cf9c897` and that checkpoint 1 would follow. Both wrong: the branch already existed (created 2026-11-25 from main `a0a9f1ba` after the first FRG-030 claim, hub 7157018365) and checkpoint 1 was already filed on it (commit `dacebe48`, file sha `a1c3d928`, 6,250 B). Corrected on the hub as comment 7197931567 before any build work. The claim itself stands: FRG-030 was released back to queue position 2 by watch088 (2026-11-25 14:13 IST) when STR-078 was restored to Muse 11, and is re-claimed now because the head task STR-078 is blocked on the frozen daemon restart (server move, owner stop order).

## 1. What was built (all on branch, byte-identical verified)
- `Forge/app/delivery/gradio_layer.py` (6,150 B, blob `e8b9678a`, commit `c7c34578`): the delivery layer. `ToolSpec` (name, description, function + declared inputs/outputs); `build_interface()` turns a spec into a `gr.Interface` (gradio imported lazily, clear error if missing); `launch_tool()` launches locally with `share=False` always; `front_one_prompt_flow()` fronts `create_agent` itself as the demo surface. Recorded rule `GRADIO_RULE`: Gradio for single-purpose, internal-only tools with no auth / multi-user state / persistent DB and under a day of UI work; a full app for multi-user, public-facing, auth, persistent-state, or custom-frontend work.
- `Forge/app/delivery/board_lookup_tool.py` (5,709 B, blob `078dcba0`, commit `9adea3c7`): the proof tool. `lookup_board_tasks(task_id, status, owner, max_rows)` reads `WORK_BOARD.yaml` live (local file, else the raw main URL), filters by id-substring / status / owner, renders a markdown table + summary counts. `board_lookup_spec()` wires it to the layer with inputs textbox + status dropdown + owner dropdown (choices read from the live board) + max-rows slider, and 3 examples.
- `Forge/tests/test_frg030_gradio_layer.py` (3,139 B, blob `42798563`, commit `60898f07`): 8 tests (lookup by id/status/owner, no-match, max-rows cap, owners list, rule recorded, interface build + unknown-kind rejection).
- `Forge/requirements.txt` (668 → 822 B, blob `5bbac320`, commit `35e97421`): added `gradio>=5.0.0,<7.0.0` and `pyyaml>=6.0.0,<7.0.0` (free, PyPI; comment cites TASK-FRG-030).

## 2. Verification (first-hand, this run, venv /tmp/frg030_venv)
- **Tests: 8/8 pass** (`pytest Forge/tests/test_frg030_gradio_layer.py`, PYTHONPATH=Forge tree). One fix during verification: Gradio 6 renamed `Interface.inputs/outputs` to `input_components/output_components` — the test now handles both (5.x + 6.x).
- **Real-board end-to-end:** lookup against the live 3 MB board downloaded this run (`/tmp/board_full.yaml`, 1,028 tasks): `FRG-030` → exactly 1 match (AVAILABLE/muse_11, correct row); `AVAILABLE + muse_11` → exactly 3 matches (MEM-027, FRG-021, FRG-030 — agrees with the independent board read this run); 38 owners listed, incl. `muse_11`.
- **Working Gradio UI (live launch):** interface built (4 inputs, 1 output), launched locally on `127.0.0.1:7860` (`share=False`), HTTP 200, 28,462 B page, then closed cleanly. The UI function returns the correct rows for `AVAILABLE/muse_11`.
- **Environment notes:** installed gradio 6.32.0, PyYAML 6.0.4, pytest 9.2.0 (free, PyPI). `import gradio` fails in this VM with the stock proxy env vars (httpx chokes parsing `NO_PROXY` entries such as `[fd8b:…]` — `Invalid port: ':1]'`); verification ran with proxy vars unset, which is correct for a local-only launch. No proxy change was made to the repo or the VM.
- **Not yet verified:** Forge CI collection of the new test file (the PR #1815 lesson: a test file must be collected by a PR-triggered workflow or the green test job never runs it) — owed before the work PR. No CI run exists for this branch yet (no PR, per rule 1).

## 3. States
- Implemented YES (layer + tool + tests, on branch) / tested YES (8/8 + real-board + live launch, local) / merged NO / deployed N/A (local proof only) / production-verified NO (another-agent use still owed, §5).

## 4. Blockers / holds
- None on the repo-side legs. The another-agent use (§5) needs a second agent to run a real lookup; a shared/public Gradio launch, if the using agent needs one, is a server move under the owner stop order — local first, hosted leg only on coordinator/owner clearance.

## 5. Next
- Checkpoint 3: get one other agent to run a real board lookup through the Gradio UI (request via hub #1483, record who/when/what it returned) — that use is the Done evidence. Then the single work PR (layer + tool + tests + requirements + CP1/CP2/CP3 docs + board flip AVAILABLE → MERGED), per rule 1. No checkpoint PRs.
- Queue after FRG-030: FRG-021 (AVAILABLE/owner muse_11) → MEM-027 (AVAILABLE/owner muse_11). STR-078 stays CLAIMED/muse_11, blocked on daemon-restart clearance.

## 6. Live state (not re-probed this run; repo-side build only)
- Last verified 21:13 IST self-check (CP126 record): both Oracle servers ONLINE, FRIDAY /health 200, Memora 401 fix holds, S2 disk 87%, sector-heatmap all-null quotes (5th verification). Grant dispute RESOLVED this run by coordinator correction 7197725825 (22:00 IST): run_shell grant STANDS (owner's tap, main chat 18:25:56 IST, closing approval 7113152293) — M11 follows the ruling; no run_shell added by M11, no live leg attempted under it. Server MOVES stay frozen; live money owner-gated.
- Usage: 51% of free weekly limit (fresh-checked 21:13 IST self-check; reset Nov 29, 6:00 PM IST; additional 0%).

— Muse 11
