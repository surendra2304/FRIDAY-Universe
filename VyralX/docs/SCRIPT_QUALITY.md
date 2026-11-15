# VyralX Script Quality System (TASK-VYR-007)

The rubric, hook library and pre-production scorer that VyralX's own
scriptwriter uses for the three owner-confirmed lanes:

1. **Space & science** — NASA/NOAA/ESA public-domain footage
2. **History & did-you-know** — Wikimedia / Internet Archive public domain
3. **Tech & AI explainers** — own screen recordings and review clips

## Why this exists

The old autopilot produced template-identical slideshow scripts with
weak openings and no payoff — the exact pattern YouTube's
inauthentic-content policy demonetises, and the pattern viewers swiped
away from. This system attacks that at the script stage, before any
rendering or upload: the scriptwriter is *told* what good looks like
(a brief), and every generated script is *graded* against the same
rubric before production.

## Files

| File | Role |
|---|---|
| `app/services/script_quality_data.json` | The library: lanes, 10 hook formulas, 3 format structures, escalation/payoff patterns, banned terms, rubric weights and thresholds. Retune the system by editing this file only. |
| `app/services/script_quality.py` | The engine: rotation, brief builder, scorer. Deterministic, standard-library only. |
| `app/services/content.py` | The scriptwriter. Optional `lane` / `script_format` / `recent_scripts` parameters (default off — historical behaviour unchanged). |
| `tests/test_script_quality.py` + `tests/script_quality_samples.py` | 25 tests and the 8 sample scripts below. |
| `scripts/run_script_quality_samples.py` | Re-runs the sample scoring and prints the results table. |

## How the scriptwriter uses it

1. **Rotation** (`choose_rotation`): from the lane's recent production
   history, the least-recently-used format and hook formula are
   assigned. Consecutive videos in a lane never share a
   format + formula pairing, and formats cycle before repeating.
2. **Brief** (`build_script_brief`): a plain-text rubric brief is
   injected into the Inference prompt — lane promise, format structure
   and rules, the assigned hook formula with a lane example, the
   3-second hook budget, escalation and payoff requirements, the
   35–60 second length window, and the banned framings.
3. **Grade** (`score_script` / `score_content_pack`): the returned
   pack is graded and stamped `pack["script_quality"]` (with
   `pack["script_brief"]` recording what it was assigned). The grade
   is advisory — `requires_editor_review` still governs production —
   but a REJECT verdict is the signal to regenerate, not to render.

## The hook library (first 3 seconds)

Every hook must land inside 3 seconds of speech: **5–8 words ideal,
10 soft cap, 12 hard cap** (at the measured 2.6 words/second narration
pace). No greetings, no channel intros, no "in this video".

| Formula | Template | Formats |
|---|---|---|
| Number shock | This {subject} is {number} times {comparison} than you think. | all |
| Question gap | Why does {subject} {unexpected behaviour}? | one-fact, story |
| Myth negation | {Subject} is not what you think it is. | one-fact, story |
| Countdown promise | Five {things} — and number one {twist}. | top-5 |
| Story cold open | {Year}. {Place}. {Person} {did something irreversible}. | story |
| Scale anchor | If {familiar thing} were {scale}, {subject} would {effect}. | one-fact, top-5 |
| Second-person stakes | You {everyday experience} — but {hidden mechanism}. | one-fact, story |
| Reveal delay | {Observers} found {object}. Then they looked closer. | one-fact, story |
| Contrast pair | {A} does {X}. {B} does the exact opposite. | one-fact, top-5 |
| Timebox promise | In the next {seconds} seconds: {promise}. | all |

Each formula ships with a worked example per lane in the data file.

## Formats (rotating, never template-identical)

- **One fact** (4–7 beats): hook → context → mechanism → scale → payoff.
  One central claim; the mechanism beat is mandatory.
- **Top 5** (7–11 beats): countdown 5 → 1, each entry outranking the
  last; number 1 is the item teased in the hook.
- **Story** (6–9 beats): cold open at the climax → rewind → two rising
  complications → climax callback → verdict payoff line.

## The rubric (100 points)

| Dimension | Weight | What is measured |
|---|---|---|
| Hook | 25 | Word budget vs the 3-second window, assigned-formula cues present, no throat-clearing opener, a concrete anchor (number / name / lane keyword). |
| Escalation | 20 | Beat count, turn markers (but / then / until…), stakes (numbers & comparisons) rising into the final third, no adjacent-beat repetition. |
| Payoff | 15 | Final beat matches a payoff pattern (callback, scale landing, implication, loop close, verdict line); the hook's promise returns in the final third. |
| Format fit | 15 | Beat count inside the format's range, estimated duration inside 35–60 s, format rules (full countdown, story anchor + turns, one-fact focus). |
| Lane fit | 10 | Lane signal vocabulary present; stronger signals for a *different* lane deduct. |
| Originality | 15 | Word 4-gram overlap and beat-shape fingerprint similarity against recent scripts; rotation pairing not repeated back-to-back. |

Verdicts: **PASS ≥ 75**, **REVISE 55–74**, **REJECT < 55** — or any
hard gate:

- `banned_content` — financial-advice terms, deception framing
  ("they don't want you to know", "before it gets deleted"), or a
  lane-specific ban (e.g. NASA-conspiracy framing in space & science).
- `hook_too_long` — hook over 12 words cannot fit the first 3 seconds.
- `duration_too_long` — estimated speech over 75 s (also protects the
  under-60-seconds rule for claimable-source Shorts).
- `template_repeat` — 4-gram overlap ≥ 0.5 with a recent script.
- `empty_script`.

## Scorer results on the sample scripts

Measured with `scripts/run_script_quality_samples.py` on this branch
(the flawed repeat is scored against the good history story's result
as its history, exactly as production would):

| Sample | Lane / format | Score | Grade | Verdict | Gates |
|---|---|---|---|---|---|
| good_space_one_fact | space_science / one_fact | 77.2 | B | PASS | — |
| good_space_top5 | space_science / top5 | 84.0 | A | PASS | — |
| good_history_story | history_facts / story | 80.2 | A | PASS | — |
| good_tech_one_fact | tech_ai / one_fact | 88.0 | A | PASS | — |
| flawed_tech_top5 | tech_ai / top5 | 48.6 | D | REJECT | — (score) |
| flawed_history_repeat | history_facts / story | 68.2 | C | REJECT | template_repeat (4-gram 0.73) |
| flawed_space_banned | space_science / one_fact | 52.2 | D | REJECT | banned_content |
| flawed_hook_too_long | history_facts / one_fact | 69.0 | C | REJECT | hook_too_long (21 words) |

The flawed Top-5 is the old autopilot's signature failure — greeting
hook, three unmarked entries, subscribe-begging ending: hook 2/25,
payoff 2/15, countdown flagged incomplete. The repeat sample is a
*good* script in isolation (68.2) and is still rejected, because
publishing near-duplicates is precisely the inauthentic-content risk.

## Honest limits

- The scorer is a deterministic heuristic grader, not a model of
  human taste: it enforces structure, budgets and originality, and
  its notes say *why* points were lost. It does not fact-check —
  `fact_check_notes` and editor review still do that.
- Duration is estimated from word count at 2.6 words/second; the
  render pipeline's measured per-beat timings (VYR-003) remain the
  authority on final sync.
- With no recent-script history supplied, originality is graded on
  rotation only (9/15) — pass the lane's recent results in to get the
  full anti-template check.
