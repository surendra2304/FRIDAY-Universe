# Browser tasks in the owner's own browser (TASK-IG-LAP-04)

Corpus item Dc3pMkakrid (browser-use). The repo card's verdict binds:
the browser-use **library** is *adapt* — MIT-licensed, but it requires
Python 3.11+ and the fleet runs 3.10, so the pattern is implemented
here and the library is not vendored. (The owner may still install it
laptop-side later; this loop's decider is the seam where a different
planner could plug in.)

**Release pin (TASK-LAP-003, 2026-11-26):** browser-use **1.0.8**
(2026-11-22) — the library version for any laptop-side install. Do not
follow past 1.x without a fresh check: the v1.0 rewrite shipped Nov
2026 and the README warns to pin the version exactly. The pin is
recorded here, not in code, because the library is not vendored.

## What already existed vs what this adds

FRIDAY already drives a browser **on the server** (`real_browser_agent`,
BrowserAutomationTool) — useful for public pages, useless for anything
behind the owner's logins. This task adds the missing half: the same
observe → decide → act loop driving the browser **on the owner's
laptop**, through the LAP-001 laptop bridge, using only commands that
already exist there (`screenshot_data`, `open_url`, `click`,
`type_text`). No new bridge commands; the owner's existing laptop
client build serves it unchanged.

| Piece | Where |
|---|---|
| Planner loop | `FRIDAY/src/friday/remote/laptop_browser_agent.py` |
| Tool (`laptop_browser_task`, SENSITIVE) | `FRIDAY/src/friday/tools/builtin/laptop_browser_control.py` |
| Tests | `FRIDAY/tests/test_laptop_browser_agent.py` |

Observation = the laptop screenshot OCR'd on the FRIDAY host, with the
OCR words grouped into text lines that carry click centres — the
browser equivalent of the phone planner's UI hierarchy.

## Safety posture (code-level, same as the phone planner)

* Credential-seeking instructions are refused before the first action.
* Typing stops when the visible page looks like a sign-in form
  (password-labelled element + sign-in context). OCR is a weaker
  signal than a structural hierarchy, so this gate is a stated
  heuristic — conservative by design.
* Banking/payment-looking pages stop the task before acting.
* Only allowlisted actions execute; two unusable decisions end the
  task; an exhausted step budget reports **not done**, never partial
  success.

## Honest limits

* OCR grounding is coarser than a DOM: dense or canvas-rendered pages
  may yield few clickable lines, and the planner will (correctly) fail
  rather than guess. For public pages, the server-side DOM browser
  agent remains the better tool — this one exists for the owner's
  logged-in session.
* The loop acts in the owner's real browser: it can click real buttons
  (send, buy, delete) if instructed to. The gates above reduce, not
  eliminate, that risk; consequential instructions should be phrased
  precisely, and the step transcript in every result shows exactly
  what was clicked/typed.

## Verification status

Implemented + unit-tested with an injected executor, scripted decider
and scripted OCR (9 tests). The owner's laptop is **not yet
connected**, so no device verification is claimed; first live proof is
the owner connecting the laptop client and asking FRIDAY to look
something up in his own browser.
