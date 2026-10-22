# Phase 6 — Multi-agent collaboration, self-healing, self-brain

**Date:** 2026-10-06
**Branch:** `arena/01a10cc0-forge`
**Commits:** `75c032a` → `b6a17b5` → `f989b4e` → `c07ad5a` (on top of `aededdf`, the self-brain fix)

---

## The directive this phase answered

> "passing tests doesn't mean that the agent is working flawlessly. You must have
> to test it in real world and at extreme pressures and all multi agent
> interaction and helping each other and self healing and self brain and what not
> implement everything."

Everything below was proven by **executing code against real workspaces**, not by
pytest and not by reading source. Where something could not be made to work in
this environment, it is labelled **CONFIGURED-BUT-UNVERIFIED** with the reason.

---

## 1. Self-brain — FIXED and proven

**Before:** `forge_upgrade/memora_client.py` was dead code. A direct probe
(`/tmp/memora_probe.py`) showed 6 of 8 public methods raising `AttributeError`,
`record_interaction()` returning `None`, and `recall_memories()` returning `[]`.
The agents had a memory subsystem that remembered nothing.

**After** (committed `aededdf`): the client was rewritten against the canonical
schema shared with `app/integrations`, with keyword-overlap + importance + recency
retrieval, exception-safe public methods, async wrappers via `asyncio.to_thread`,
and a portable `MEMORA_DB_PATH` defaulting to `<repo>/data/memora.db`.

**Proof (real executions):**

| Probe | Result |
|---|---|
| `/tmp/memora_verify.py` | 8/8 methods OK; `context contains lesson: True` |
| `/tmp/agent_mem_test.py` | `contains MEMORA block: True`; `contains the lesson: True`; prompt shows `[MEMORA SELF-UPGRADE CONTEXT] / Relevant prior experience: - CLI apps must handle KeyboardInterrupt and expose --help` |
| `/tmp/mem_perf.py` | recall 2.25 ms/call, write 1.36 ms/call at 2 000 memories |

Full suite 0 failures, 6/6 golden benchmarks, ruff clean at that commit.

---

## 2. Self-healing — BUILT and proven under real defects

### What was broken

`RecoveryEngine.attempt_recovery` had exactly one repair route and ended the
attempt as soon as that route returned *anything*. Two failures, both proven
before the fix:

- The synthesis heuristic returned a patch that **did not compile**; the engine
  wrote it anyway and then reported `Re-verification failed after applying patch`
  — the file stayed broken.
- Every other failure class hit `Unable to synthesize automated patch for unknown`
  and gave up. The Debugger agent — a full specialist with tools and a persona —
  was **never consulted by the recovery path at all**.

### What was built (`app/recovery/`)

| Piece | Role |
|---|---|
| `syntax_repair.py` (new) | `_repair_python_source` — compile-validated repair of missing colons, unbalanced brackets, unterminated strings |
| `_patch_is_sound` | rejects any candidate `.py` patch that does not `compile()` **before it is written** |
| `_deterministic_syntax_repair` | provider-independent repair route; works with every AI endpoint unreachable |
| `_escalate_repair_to_agent` | hands real failure evidence to the Debugger agent |
| `_resolve_target_file` | normalizes the classifier's path (backslashes, `project/` prefixes, first `*.py` fallback) |
| `_audit` | all `store.record_event` calls go through it; a failed audit write logs a warning and **never aborts a repair** |
| `_record_repair_lesson` / `_remember_repair` | every attempt and outcome recorded to Memora under `self_healing` |

`attempt_recovery` is now a **ladder** — `synthesis` → `deterministic` → `agent` —
where a route only wins if its patch is applied **and** re-verification passes.
The soundness gate is what makes the ladder work: a route handing back
unparseable code no longer ends the attempt.

### Proof (real execution, `/tmp/pressure/heal_proof2.py`)

Six → eight deliberately broken temp-workspace projects:

```
PASS  missing_colon_def      8/10 -> 10/10  compiles=True
PASS  missing_colon_if       8/10 -> 10/10  compiles=True
PASS  missing_colon_for      8/10 -> 10/10  compiles=True
PASS  unclosed_bracket       8/10 -> 10/10  compiles=True
PASS  unterminated_string    8/10 -> 10/10  compiles=True
PASS  multiline_list_deficit 8/10 -> 10/10  compiles=True  route=deterministic
FAIL  unclosed_paren         8/10 ->  8/10  NOT repaired
FAIL  multiline_dict_deficit 8/10 ->  8/10  NOT repaired
```

The two non-repairs are **honest**, not hidden. `unclosed_paren` has a mid-file
deficit (`return sum([a, b, c` followed by more code): appending `])` at EOF does
not compile, the soundness gate rejects it, and **no broken code is written**.
`multiline_dict_deficit` needs a brace inserted mid-file, which a line-oriented
repairer cannot do correctly. Both are reported as "cannot fix".

`multiline_list_deficit` is the proof that the **deterministic route wins where
synthesis cannot** — the synthesis heuristic is gated on `failure_class ==
"syntax_error"` and a valid `failing_line`, which this case does not have.

---

## 3. Multi-agent collaboration — BUILT and proven

### What was broken

The agents never interacted. Each DAG node went to one specialist in a parallel
wave, results landed in a shared context, and that was the whole story. No review
step, no hand-off, no path for one agent to act on another's findings. The only
thing named "consensus" was an HTTP call to an external AI Universe service
(which is unreachable here — TLS `CERTIFICATE_VERIFY_FAILED`).

### What was built (`app/agents/coordinator.py`, new)

- **Reviewers** are the specialist checkers — `build_engineer`, `code_reviewer`,
  `security_reviewer`, `test_engineer` — the same code the verification battery
  uses, so a finding is a fact with an exit code and a file, **not an opinion**.
- **Fixers** are the engineering agents — Debugger, then Developer. They receive
  the findings as a brief, read the workspace, and write the repair through the
  normal permission-checked file tools.
- The deterministic repairer is the final fallback, so the loop converges with
  every model endpoint unreachable.
- The loop is **review → delegate repair → re-review**, bounded by `max_rounds`,
  tracking findings **resolved versus introduced** so a "fix" that breaks
  something else is reported rather than hidden.
- Wired into `OrchestratorCore._verify_and_repair`, so **every real build now runs
  a peer review pass** after the verification battery.

### Proof (real execution, `/tmp/pressure/multiagent_proof.py`)

Workspace seeded with a syntax error, a hardcoded secret and an unused import:

```
3 findings from 3 different specialists
  [high    ] build_engineer     Build & Syntax Check      (missing ':' after def)
  [medium  ] code_reviewer      Ruff / Static Code Linter
  [critical] security_reviewer  Static Security & Secret Scanner (hardcoded key)

outcome: rounds=2 findings 3->2 resolved=1 introduced=0
        agents=build_engineer,code_reviewer,debugger,security_reviewer
```

`app.py` went from `def load(path)` (SyntaxError) to `def load(path):` and compiles.
The two remaining findings are reported honestly: the offline fixer cannot author
a correct fix for an unused import or a hardcoded secret, and the coordinator says
so instead of pretending.

---

## 4. Extreme-pressure results

Pressure testing found **six real defects that unit tests did not**. All are fixed.

### 4a. Repairer fuzzing — 4 000 random/adversarial sources

```
fuzz: 4000 inputs in 0.1s -- 322 repaired, 0 non-compiling returned, 3678 left alone
concurrent healing: 8/8 reached 10/10 in 2.0s
ALL PASS
```

The invariant that matters — **never return a candidate that does not compile** —
holds across all 4 000 inputs. 3 678 were correctly left alone.

Defects found here:
- **NUL bytes crashed the repair path.** `_deterministic_syntax_repair` probed the
  file with a bare `compile()`, which raises `ValueError` (not `SyntaxError`) on a
  NUL byte. Binary content took the whole healing attempt down with an unhandled
  exception instead of reporting "cannot repair".
- **The missing-colon repair appended `:` without balancing the line's brackets**,
  so `def f(` became `def f(:` — a second syntax error. The candidate failed the
  compile gate and the repair silently never happened. Brackets are now closed
  before the colon is added, giving `def f():`.
- **`_extract_target_file` reduced every path to its basename**, so a finding on
  `src/util.py` sent the fixer looking for `util.py` at the project root. The
  repair was skipped and the finding survived the whole loop.

### 4b. Coordinator adversarial workspaces — 11 scenarios

```
OK  empty_workspace    0.0s  before= 0 after= 0 rounds=0
OK  single_broken     12.5s  before= 2 after= 0 rounds=1 repairs=1 agents=3
OK  all_binary         0.0s  before= 0 after= 0 rounds=0
OK  nul_bytes         12.5s  before= 2 after= 2 rounds=1 repairs=0 agents=2
OK  huge_file          3.6s  before= 0 after= 0 rounds=0
OK  many_files         0.1s  before= 0 after= 0 rounds=0
OK  deep_paths        12.5s  before= 2 after= 0 rounds=1 repairs=1 agents=3
OK  unicode_names     24.9s  before= 2 after= 0 rounds=2 repairs=2 agents=3
OK  mixed_valid_broken 12.4s before= 2 after= 0 rounds=1 repairs=1 agents=3
OK  empty_files        0.0s  before= 0 after= 0 rounds=0
OK  only_comments      0.0s  before= 0 after= 0 rounds=0
ALL PASS
```

No crash, no hang, and **no claim of a fix that did not happen** (the harness
asserts that a "resolved" finding actually disappeared from re-review).
12 concurrent review loops all complete.

---

## 5. A real end-to-end build, and the false confidence it exposed

Driving the full pipeline through `OrchestratorCore.run_task` against an isolated
workspace with every AI endpoint unreachable:

```
state: TaskState.FAILED  progress: 100%  (32s)
events: 17   node.completed: 7
files produced (6): .pytest_cache/*, docs/ARCHITECTURE_SPEC.md, docs/FILE_MANIFEST.json
python files: 0

verification_report.json: 9/10 passed
  PASS  Build & Syntax Check          PASS  Pytest Test Suite Runner
  PASS  Static Code Linter            PASS  Runtime CLI / Service Smoke Check
  PASS  Static Security Scanner       PASS  Performance Sanity Verification
  PASS  Security & Vulnerability      PASS  Code Quality & Complexity
  PASS  Web Accessibility (a11y)      FAIL  Keyword & Feature Presence Verifier
```

Two findings, both worth writing down:

**5.1 — A verification blind spot (OPEN, needs its own fix).**
The battery scores **9/10 on a workspace containing zero Python files**. "Build &
Syntax Check" passes because there is nothing to break; "Pytest Test Suite Runner"
passes because there are no tests to fail; "Runtime CLI / Service Smoke Check"
passes because there is nothing to run. Only the feature-presence verifier notices
that nothing was built. A 9/10 score on an empty project is false confidence in
the verification layer.

The orchestrator itself behaves correctly — it refuses to call this a success and
transitions to `FAILED` with `"Fell back to stub generation"` — so **no fabricated
result is reported**. But the verification layer's own score is misleading and
should not be trusted as a quality signal on its own.

**5.2 — Verification and recovery used the wrong workspace (FIXED, `c07ad5a`).**
`_verify_and_repair` built `VerificationEngine()` and `RecoveryEngine()` with no
arguments, so both fell back to the module-level singletons rather than the
orchestrator's own workspace manager. Any orchestrator built with an injected
`WorkspaceManager` verified and repaired the wrong directory. Proven live: the
task reached `FAILED` with **zero verification evidence recorded against it**.
Both are now constructed with the orchestrator's own engine and workspace manager.

---

## 6. Verification status

All commands executed in this phase, on the final state of the branch:

| Check | Result | Evidence |
|---|---|---|
| Full non-golden suite | **0 failures** (440 tests) | `/tmp/fs23.txt` |
| Golden benchmarks | **6/6 passed** | `/tmp/g24.txt` |
| ruff | **All checks passed!** | `/tmp/pressure/final_ruff.txt` |
| Self-healing proof | 6/8 self-healed, 2 honest non-repairs | `/tmp/pressure/final_heal.txt` |
| Self-healing pressure | 4 000 fuzz inputs, 0 bad candidates, 8/8 concurrent | `/tmp/pressure/final_hp.txt` |
| Multi-agent proof | 3 reviewers → fixer → 3→2 findings | `/tmp/pressure/final_ma.txt` |
| Multi-agent pressure | 11 adversarial workspaces, 12 concurrent loops | `/tmp/pressure/final_map.txt` |

---

## 7. Honest limitations

1. **The offline provider cannot author code.** With every AI endpoint
   unreachable (TLS `CERTIFICATE_VERIFY_FAILED` to AI Universe, OpenAI, Anthropic
   and GitHub), the fixer agents produce nothing and the deterministic repairer is
   the only route that closes defects. Every claim above was proven *with that
   constraint in force* — none of it depends on a provider being reachable.
2. **Two syntax classes are not repairable** (`unclosed_paren`,
   `multiline_dict_deficit`). They need a bracket inserted mid-file, which a
   line-oriented repairer cannot do safely. They are reported as "cannot fix".
3. **The unused-import and hardcoded-secret findings are not fixed** by the
   offline fixer. They are reported, not hidden.
4. **The verification blind spot in §5.1 is OPEN.** Fixing it means changing
   checker semantics (an empty workspace should not score 9/10), which is a
   behaviour change beyond surgical scope and deserves its own phase.
5. Nothing has been pushed. All work is local on `arena/01a10cc0-forge`, per the
   repository's own rule that modifications stay local unless explicitly
   instructed otherwise.
