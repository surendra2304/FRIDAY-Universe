# Real-life pressure tests

Green unit tests are not evidence that FORGE works. Everything in this directory
drives the **real** pipeline — real orchestrator, real agents, real verification
battery, real recovery engine, real filesystem — with no mocks, and reports what
actually happened.

Run them individually. They are slow on purpose: they build real projects.

```bash
# Drive real and hostile goals through the full pipeline
python tests/pressure/campaign.py --suite real      # 18 real tasks
python tests/pressure/campaign.py --suite hostile   # 16 adversarial goals
python tests/pressure/campaign.py --suite both

# Self-healing: deliberately broken projects, healed by the real RecoveryEngine
python tests/pressure/self_healing_proof.py

# Concurrency, restart-mid-build, corrupt state, unwritable workspace
python tests/pressure/world_pressure.py

# Deterministic synthesis: every generated project compiles and its own
# test suite passes
python tests/pressure/synthesis_proof.py
```

## What each one proves

| Harness | What it exercises | Pass condition |
|---|---|---|
| `campaign.py` | `intake_and_plan` → `run_task` → verify → recover → peer review, for real user goals | Task reaches a terminal state, produces files, and the files compile |
| `campaign.py --suite hostile` | Injection, SQL, HTML, unicode, emoji, 5 000-char goals, NUL bytes, path traversal, command injection | Nothing crashes, nothing hangs, no broken code written |
| `self_healing_proof.py` | 11 genuinely broken Python files repaired by `RecoveryEngine` | Score recovers **and** the file compiles afterwards |
| `world_pressure.py` | 8 concurrent builds, `SIGKILL` mid-build then resume, corrupted persisted graph, read-only project dir | No false success, no lost state |
| `synthesis_proof.py` | Every generated project kind | Code compiles and the project's own pytest suite passes |

## Why these exist

Before this suite existed, 18 real tasks driven through the pipeline produced
**zero Python files** and the verification battery scored every one of them
**9/10**. The unit tests were green throughout. These harnesses are what made
that visible, and they are what keeps it from coming back.

If you change the agent pipeline, run these. A green `pytest tests/` means the
plumbing is intact; these mean the agent actually works.
