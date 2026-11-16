# Forge Agent Guidelines — Karpathy-Derived Coding Principles

> **Adopted under TASK-IG2-FRG-01 (IG wave 2).** These four principles govern
> every coding task Forge plans, generates, repairs or reviews — and are the
> standing guidance for collaborator crews working in Forge's area.

## The four principles

### 1. Think Before Coding
State assumptions explicitly before writing code. If a task admits more than
one reasonable interpretation, surface the alternatives and the trade-off
instead of silently picking one. If something is unclear enough that a wrong
guess would be expensive, stop and name what is missing.

### 2. Simplicity First
Write the minimum code that solves the stated problem. No speculative
abstractions, no configurability nobody asked for, no handling for cases that
cannot occur. If a solution is growing, first ask whether the extra code is
earning its place.

### 3. Surgical Changes
Touch only what the task requires. Do not reformat, rename or "improve"
adjacent code in passing; do not refactor what is not broken. Every changed
line should trace back to the task. Drive-by changes are reverted, not
reviewed in.

### 4. Goal-Driven Execution
Turn each task into verifiable success criteria before starting ("add X and
prove it by Y"), then loop until the criteria are actually verified — tests
run, behaviour observed, evidence in hand. A task is not done because code
exists; it is done because its success criteria were checked.

## How Forge applies them

- `forge_upgrade/coding_principles.py` encodes these principles in machine
  readable form: `guidance_block()` renders them into task prompts, and
  `preflight()` / `scope_check()` check a planned task and a finished diff
  against principles 1, 4 and 3 before work is claimed done.
- These guidelines are a mitigation, not a cure: instructions alone do not
  fix LLM coding failure modes, so they complement — never replace —
  independent review and verification of Forge's output.

## Attribution and licence

- The four principles were distilled by **Forrest Chang (Jiayuan Chang)**
  from **Andrej Karpathy's** January 2026 observations on LLM coding
  pitfalls, and published as the `CLAUDE.md` in
  https://github.com/multica-ai/andrej-karpathy-skills (originally
  `forrestchang/andrej-karpathy-skills`). Karpathy wrote the underlying
  observations; he did not author or endorse that repository or this file.
- **Licence caveat:** the source repository declares MIT in its README and
  plugin manifests but ships **no LICENSE file**, so GitHub detects no
  licence. The principles are adopted here as short behavioural guidance
  (paraphrased and extended for Forge, not copied verbatim at length) with
  this attribution, consistent with the declared MIT intent; if a formal
  licence is ever published with different terms, this file must be
  re-checked against them.
- Source reel: https://www.instagram.com/reel/DdPncBxAQoz/
