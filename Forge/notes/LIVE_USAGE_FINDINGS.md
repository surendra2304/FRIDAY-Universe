# FORGE Live-Usage Adversarial Testing Log

This log tracks bugs found by **actually operating the running FORGE server**
(real HTTP requests, real concurrency, real adversarial input), as opposed to
relying on the pre-existing pytest suite passing. Every entry below was
reproduced live first, then root-caused in the source, then fixed in code,
then re-verified both by direct reproduction and by the full test suite.
Earlier findings (1-10, from the original repo-analysis pass) are tracked in
`notes/raw-findings.md`; this file picks up the numbering for the live-usage
campaign.

## Methodology
1. Run the real server (`uvicorn app.main:app`), not a mocked/test client.
2. Throw real, varied, and adversarial traffic at it: empty/huge/weird
   payloads, true concurrency (not sequential loops), and multi-step
   workflows (submit -> poll -> verify generated output actually runs).
3. When something breaks, reproduce it minimally and deterministically before
   touching any code.
4. Fix the root cause in the source (not the symptom), add a regression test
   that fails on the old code and passes on the fix, then re-run the full
   suite to confirm no regressions.
5. Keep going. A clean pytest run is not evidence of correctness by itself.

---

## Finding 11 — Unbounded `goal` field enables request-latency DoS

**Severity:** Medium (resource exhaustion / latency DoS)

**Live reproduction:** `POST /api/tasks` with a 500 KB `goal` string
(`"A" * 500_000`) took **~7 seconds** to return a 201, purely for task
*intake* — before any synthesis or execution started. A 46 KB goal was fine
(0.66s), so the cost scales with goal length: the task-type/keyword/template
classification logic scans the raw goal text repeatedly. Only an 8 MB
whole-request-body limit existed; there was no cap on the `goal` field
itself.

**Root cause:** `TaskCreateRequest.goal` in `app/api/schemas.py` had
`min_length=3` but no `max_length`.

**Fix:** Added `max_length=20_000` to `goal` and `max_length=200` to the
`requirements` list (the synthesizer only ever consults the first ~200 chars
of the raw goal anyway, so 20k is already generous headroom, not a
functional restriction).

**Verification:**
- Same 500 KB payload now rejected in **62ms** with 422 `string_too_long`.
- Regression test: `tests/unit/test_task_intake_bounds.py`.
- Full suite: 429 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 12 — Concurrent task submissions collapse onto one task id/goal

**Severity:** Critical (data integrity / silent task loss under concurrency)

**Live reproduction:** Fired 20-30 truly concurrent `POST /api/tasks`
requests (async `httpx.gather`, then reproduced in-process directly against
`OrchestratorCore`) with distinct goals. **100% of the HTTP responses
reported the same task id and the same goal back to every caller**,
regardless of what that caller actually submitted. Inspecting the SQLite DB
directly showed the rows *were* in fact persisted with distinct ids and the
correct per-caller goals — the corruption was entirely in what the
orchestration logic (and therefore the HTTP response) pointed at.

**Root cause (two compounding bugs in `OrchestratorCore.intake_and_plan`,
`app/core/orchestrator.py`):**
1. Task-id allocation was a check-then-act race: `count_tasks()` was read,
   a candidate id built from `count + current-second timestamp`, and checked
   with `get_task()` — all unlocked. Concurrent callers within the same
   wall-clock second could all compute the identical candidate id and all
   pass the "not yet taken" check before any of them had inserted.
2. When two callers did collide, the existing retry-on-`IntegrityError` path
   correctly gave the loser a new, unique `task.id` and DB row — but every
   step *after* that insert (`record_event`, `planner.plan`,
   `lifecycle.transition`, and the object returned to the HTTP layer) kept
   referencing the original, pre-retry `task_id` **local variable**, which
   was never updated. The practical effect: whichever task happened to win
   the original id absorbed the planning/lifecycle side effects and the HTTP
   responses of every other concurrent caller, while their real, correctly
   unique DB rows were silently orphaned in `PENDING` forever (never
   planned, never transitioned, never executed). Their workspace directories
   were also provisioned under the same pre-retry id, risking on-disk file
   collisions between unrelated tasks.

**Fix (`app/core/orchestrator.py`):**
- Added a process-wide `asyncio.Lock` (`_TASK_ID_ALLOC_LOCK`) serializing id
  allocation + workspace provisioning + the initial insert. `OrchestratorCore`
  is constructed fresh per HTTP request, so this has to be module-level, not
  an instance attribute, to actually protect concurrent requests. This makes
  the collision effectively impossible in the normal single-process
  deployment.
- Kept the `IntegrityError` retry as defense-in-depth (e.g. multiple worker
  processes sharing one SQLite file), but fixed it to also: (a) re-provision
  the workspace under the corrected id instead of leaving it under the stale
  one, and (b) resync the local `task_id` to `task.id` immediately after the
  critical section, so every downstream step and the final returned task are
  always bound to whatever id was *actually* persisted.

**Verification:**
- In-process repro with 30 concurrent `intake_and_plan()` calls (fresh
  `OrchestratorCore` per call, matching real request handling): before the
  fix, 1 unique id out of 10; after the fix, 30/30 unique ids, zero
  goal/index mismatches.
- Live HTTP repro against the running server: before the fix, 20/20
  responses returned the identical id; after the fix, 25/25 concurrent
  `POST /api/tasks` returned 25 unique ids, 0 duplicates, 0 non-201
  responses, and all 25 DB rows carried their own correct goal and
  progressed out of `PENDING` (`READY`/`RUNNING`).
- Regression test: `tests/unit/test_orchestrator_concurrency.py`.
- Full suite: 429 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 13 — `/api/v1/tasks/{id}/cancel` silently skips webhook/WebSocket notification

**Severity:** High (silent loss of integration notifications; API inconsistency)

**Live reproduction:** Submitted a task with a `webhook_url`, then cancelled
it via `POST /api/v1/tasks/{id}/cancel`. The server logs showed the state
transition happened, but **no webhook dispatch attempt and no WebSocket
broadcast ever fired** — confirmed by comparing against the exact same
cancel call made via `POST /api/tasks/{id}/cancel` (no `/v1`), which *did*
show webhook dispatch attempts (and retries) in the log, plus the
`TaskActionResponse.message` differed (`"Task cancelled successfully"` with
no reason vs. `"Task cancelled successfully: <reason>"`), proving two
genuinely different code paths were handling what looked like the same
endpoint.

**Root cause:** `app/api/routes.py` (`api_router`) and `app/api/tasks.py`
(`tasks_router`) both independently implemented a handler for the logical
path `/tasks/{task_id}/cancel`. `app/main.py` mounts both routers at
overlapping prefixes (`api_router` bare and under `/api` and `/api/v1`;
`tasks_router` under `/api` and `/api/v1`), and FastAPI silently resolves
such overlaps by registration order — there is no error or warning at
startup (beyond a generic "duplicate operation ID" OpenAPI-schema warning
that main.py already explicitly suppresses). The inline comment in
`main.py` above the `/api` mounts correctly described wanting the "richer"
`tasks_router` handler to win, and it does for the plain `/api` prefix — but
under `/api/v1`, `api_router` (the thinner handler: state transition only,
no progress-tracker close-out, no WebSocket broadcast, no webhook dispatch)
was registered *first* and won instead, the opposite of the stated intent.

**Fix:** Extracted the full-featured cancellation logic out of
`app/api/tasks.py::cancel_task` into a standalone, importable
`execute_task_cancellation()` function. Both `tasks_router`'s and
`api_router`'s `/tasks/{task_id}/cancel` handlers now call this single
shared implementation, so every mount point (`/tasks`, `/api/tasks`,
`/api/v1/tasks`) is guaranteed to behave identically regardless of
FastAPI's registration-order route resolution — removing the entire class
of bug rather than just reordering the two routers.

**Verification:**
- Live repro: cancelling via `/api/v1/tasks/{id}/cancel` after the fix now
  shows webhook dispatch attempts in the server log (3 retries against an
  intentionally-unreachable receiver) and the rich, reason-embedding
  response message, matching the non-v1 path exactly.
- Regression test: `tests/unit/test_cancel_route_consistency.py` (asserts
  both mount points produce identical, rich responses).
- Full suite: 430 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 14 — Generated Web APIs mix singular and plural resource paths

**Severity:** Medium-High (breaks the universal REST client assumption)

**Live reproduction:** Generated a "REST API for managing books" project,
ran it with `uvicorn`, and drove it as a real client would: `POST /books`
created `id=1`; `GET /books/1` (the plural path any standard REST client
would assume, matching the collection route that was just used) returned
**404**; only `GET /book/1` (singular) returned 200.

**Root cause:** `_api_main` in `app/agents/synthesis.py` mounted collection
routes (`list`, `create`) on `/{plural}` but every item-level route (`get`,
`update`, `delete`, `search`) on `/{singular}/{id}` — an internally
inconsistent base path for the same resource.

**Fix:** All item-level routes now also use `/{plural}/{id}`, matching the
collection routes. Updated the paired `_api_tests` generator to match so
generated projects' own test suites exercise the corrected paths too.

**Verification:**
- Live repro: `GET /items/{id}` now 200s on a freshly generated+run API,
  `PUT`/`DELETE` on the same plural path also verified.
- Regression test: `tests/unit/test_api_generator_routes.py::test_generated_api_uses_consistent_plural_paths`
  (generates a real project, imports and runs it as a real FastAPI app via
  `importlib`, and drives it with `TestClient`).

---

## Finding 15 — Generated "search" endpoint is 100% unreachable dead code

**Severity:** Critical (advertised feature silently never works)

**Live reproduction:** Generated an API whose goal explicitly asked for
search ("allow searching products"). The route existed in the source and
the OpenAPI schema. A real request to `GET /item/search?q=...` returned
**422** with `{"type": "int_parsing", "loc": ["path", "item_id"], "input":
"search"}` — i.e. it was captured by the *wrong* route.

**Root cause:** `/{plural}/search` (a literal path) was registered *after*
`/{plural}/{id}` (a parameterized path with an `int` converter) on the same
prefix. FastAPI/Starlette matches routes in registration order and does not
backtrack to a later route when an earlier one matches the URL shape but
fails parameter validation, so every request to the search endpoint was
swallowed by the id route and failed int-conversion before the search
handler ever ran.

**Fix:** Reordered route registration in `_api_main` so the literal
`/{plural}/search` route is registered *before* the parameterized
`/{plural}/{id}` route — the standard FastAPI fix for literal-vs-parameterized
path conflicts. Also added a `test_search_route_is_reachable` test directly
into the generated project's own `_api_tests` output, so every future
generated project self-verifies this isn't silently broken again.

**Verification:**
- Live repro: regenerated the same API after the fix; `GET /items/search`
  now returns 200 with matching results instead of 422.
- Regression test: `tests/unit/test_api_generator_routes.py::test_generated_api_search_route_is_reachable`.
- The generated project's own test suite (`test_main.py`) now includes and
  passes `test_search_route_is_reachable` for any goal implying search.

---

## Finding 16 — The literal word "CRUD" does not imply an `update` endpoint

**Severity:** Critical (the single most common way a real user phrases this
request silently produces an incomplete API/CLI)

**Live reproduction:** `parse_goal("Build a REST API for managing books
with CRUD endpoints using FastAPI")` → `commands == ['add', 'list',
'delete']`. **No `update`.** The generated API shipped with no `PUT` route
at all — a caller trying to edit an existing book got `405 Method Not
Allowed` — despite the goal explicitly spelling out all four CRUD
operations in those exact words.

**Root cause:** `COMMAND_SIGNALS` in `app/agents/synthesis.py` maps
individual words ("update", "edit", "modify", "change", ...) to the
`update` command, but the acronym "CRUD" itself never appears in any
signal list, so a goal that only says "CRUD" (rather than spelling out
"update"/"edit") matched `add` (from "managing"/"Create" framing), `list`,
and `delete`, but nothing implied `update`.

**Fix:** `_detect_commands` now special-cases the whole word "crud": when
present, it ensures `add`, `list`, `update`, and `delete` are all included
regardless of what else matched. This is a shared helper used by both the
CLI and the Web API generators, so the fix applies to both: verified
`parse_goal("Build a CLI tool for managing todos with CRUD operations")`
now also includes `update`.

**Verification:**
- `parse_goal(...)` for the exact live-reproduced goal now returns
  `['add', 'list', 'update', 'delete']`.
- Live repro: regenerated the same "books CRUD API" project; `PUT
  /books/{id}` now returns 200 and actually updates the record.
- Regression tests: `tests/unit/test_api_generator_routes.py::test_crud_keyword_implies_update`
  and `::test_generated_crud_api_actually_has_a_working_update_route`.
- Full suite: 434 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 17 — Generated portfolio website's contact form does nothing

**Severity:** High (a named, explicitly-advertised feature is non-functional
for 100% of generated sites that include it)

**Live reproduction:** Generated a portfolio website ("...with a gallery,
about page, and contact form"), ran it, and inspected the real output
instead of trusting that a nicely-styled `<form>` meant the feature worked.
`grep -n "contact-form" app.js` → **zero matches** anywhere in the 869-line
generated JS file. The `<form id="contact-form">` has no `action`
attribute, so clicking "Transmit Message" triggers the browser's default,
un-intercepted submit behavior: a full page reload with the typed fields
silently discarded and no confirmation of anything. Confirmed the generator
itself (not just this one generated sample) is at fault: `contact-form`
appears exactly once in the entire 2399-line
`app/templates/web_studio/generator.py` (the HTML template), with no
corresponding handler anywhere else in the file -- every portfolio site this
generator produces ships with the same dead form.

**Root cause:** The portfolio template's JS builder (`_generate_portfolio_js`)
wires up handlers for the 3D HUD controls, theme toggle, showcase filters,
details modal, and a fake CLI terminal -- but never for the contact form,
despite the form existing in the paired HTML template.

**Fix:** Added a submit handler for `#contact-form` to
`_generate_portfolio_js`: it prevents the default navigation, runs the same
HTML5 validity check the browser would have (and surfaces the native
validation UI via `reportValidity()` if it fails), and replaces the form
with an on-page confirmation message. This is the correct behavior for a
static, backend-less generated site (there is nothing real to submit the
data *to*), and matches the interaction quality of the terminal feature
that already existed.

**Verification:**
- Static: regenerated the site and confirmed `getElementById('contact-form')`
  and a `submit` listener now exist in `app.js`; `node --check app.js` still
  passes (valid syntax).
- **Behavioral, not just static**: installed `jsdom` (from the allowed
  `registry.npmjs.org` host) and actually executed the generated `app.js`
  against a real DOM built from the generated `index.html`, filled in the
  form fields, and dispatched a real `submit` Event. Confirmed: the submit's
  default action was prevented (`defaultPrevented === true`), the form
  element was removed from the DOM, and a confirmation message containing
  "Thanks!" was inserted in its place -- i.e. the fix was verified by
  actually running the generated artifact end-to-end, not by reading the
  source.
- Regression test: `tests/unit/test_web_studio.py::test_portfolio_contact_form_has_a_submit_handler`
  (static assertion that the generator emits a handler bound to the exact id
  the HTML uses, so a future refactor that silently drops or renames one
  side fails immediately).
- Full suite: 435 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 17b — Dashboard template's "Run Quick Diagnostics" button is dead

**Severity:** Medium (dead UI element, no data loss but breaks the implied
affordance of a styled, labeled button)

**Live reproduction:** After fixing Finding 17, systematically swept all
four WEBSITE domain templates (portfolio, ecommerce, saas, dashboard) for
the same bug class: every `<form id="...">`/`<button id="...">` in the
generated HTML cross-checked against the generated `app.js` for a matching
`getElementById(...)` *or* a shared `querySelectorAll('#id, ...')`
reference (to avoid false positives from legitimately shared-selector
wiring, which both ecommerce and saas use for their CTA buttons). Found one
more real dead element: the dashboard template's "Run Quick Diagnostics"
button (`id="quick-diagnostics-btn"`) — zero references anywhere in
`app.js`, unlike every other dashboard control (theme toggle, traffic-spike
simulation, alerts bell), which all have working handlers.

**Fix:** Added a click handler to `_generate_dashboard_js` mirroring the
existing traffic-spike button's disable/restore interaction pattern: on
click, the button disables and its label changes to "Running Diagnostics…",
then after a short delay shows "All Systems Nominal ✓", then restores the
original label and re-enables.

**Verification:**
- Live, behavioral (not just static): ran the regenerated dashboard's
  `app.js` against a real DOM via `jsdom`, dispatched a real `click` Event
  on the button, and confirmed the label actually changed to "Running
  Diagnostics…" and the button became disabled during the click — the same
  run-it-for-real standard used for Finding 17.
- Regression tests:
  `tests/unit/test_web_studio.py::test_dashboard_quick_diagnostics_button_has_a_click_handler`
  (specific) and
  `tests/unit/test_web_studio.py::test_every_website_template_wires_up_its_interactive_elements`
  (general, generator-wide guard across all four templates so a *new* dead
  element introduced by any future template change is caught automatically
  rather than needing its own one-off test).
- Full suite: 437 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 18 — Generated rename script silently destroys data on a case collision

**Severity:** Critical (silent, irreversible data loss, reported as success)

**Live reproduction:** Generated the Script-kind project for "renames all
files in a directory to lowercase". Created a directory with `A.txt`,
`README.MD`, and `readme.md` (a real, common scenario: a repo with both an
uppercase and lowercase README from different tooling conventions) and ran
`python path.py rename . --apply`. The directory went from 3 files to 2:
`readme.md`'s original content ("content-lower-readme") was gone, silently
replaced by `README.MD`'s content, with **exit code 0** and output claiming
success. The CLI's own message also read "1 file(s) **would be** renamed"
even though `--apply` had actually renamed a file -- dry-run language on a
real, destructive run, which would make it even harder for a user to
realize their rename had just destroyed something.

**Root cause:** `rename_lower` in `_script_main`
(`app/agents/synthesis.py`) called `path.rename(target)` unconditionally
whenever the lowercased name differed from the original, with no check for
whether `target` already existed. `Path.rename()` silently overwrites an
existing destination file on POSIX.

**Fix:** `rename_lower` now tracks both the directory's pre-existing
filenames and the targets already claimed within the current pass, skips
(rather than applies) any rename whose target collides with either, and
reports each skip to stderr (`skip: X -> Y (target already exists)`)
instead of destroying data silently. Also fixed the CLI's success message
to say "renamed" vs. "would be renamed" based on whether `--apply` was
actually passed.

**Verification:**
- Live repro: regenerated the script, recreated the exact `A.txt` /
  `README.MD` / `readme.md` scenario, ran `rename --apply` again — both
  readme files now survive with their original, distinct content; `A.txt`
  still correctly renames to `a.txt` (no collision); the skip is reported
  on stderr; the message now correctly says "renamed".
- Regression test:
  `tests/unit/test_script_generator_data_safety.py::test_rename_lower_never_silently_destroys_a_colliding_file`
  and `::test_rename_cli_message_reflects_whether_apply_was_used` (both
  import and execute the actual generated script module, not a
  reimplementation of its logic).

---

## Finding 19 — Generated backup script silently loses files to a flattening collision

**Severity:** Critical (same class as Finding 18: silent data loss, reported as success)

**Live reproduction:** The same generated script also ships a `backup`
subcommand. Created `sub1/data.txt` and `sub2/data.txt` (two different
files that happen to share a basename in different subdirectories — a very
ordinary directory layout) and ran `python path.py backup . ../out`. Output
claimed `"copied 2 file(s)"`, but the backup folder only ever contained a
single flat `data.txt` — one of the two files' content was gone from the
backup entirely, overwritten by the other mid-copy.

**Root cause:** `backup_today` walks the source tree recursively
(`source.rglob("*")`) but copied every match to a flat destination
`target / path.name` (basename only, discarding the relative directory
path), so any two files sharing a basename in different subdirectories
collided on the same destination.

**Fix:** Destinations are now computed as `target / path.relative_to(source)`,
preserving the original directory structure under the backup folder (with
`dest.parent.mkdir(parents=True, exist_ok=True)` to create any needed
subdirectories), so same-named files from different source directories can
no longer collide.

**Verification:**
- Live repro: regenerated the script, recreated the `sub1/data.txt` +
  `sub2/data.txt` scenario, ran `backup` again — both files now land at
  `out/sub1/data.txt` and `out/sub2/data.txt` with their original, distinct
  content, and the reported count still correctly says 2.
- Regression test:
  `tests/unit/test_script_generator_data_safety.py::test_backup_today_does_not_flatten_colliding_basenames`.
- Full suite: 440 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 20 — Generated json2csv command corrupts output on mismatched rows and crashes ugly on bad input

**Severity:** High (silent output corruption reported as a clean error; unhandled crash with internal traceback on malformed input)

**Live reproduction (part 1 — inconsistent keys):** Same generated script,
`json2csv` subcommand. Ran it against
`[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25, "city": "NYC"}]`
(a very ordinary shape for real-world JSON exports, where not every record
has every field). The command printed `error: dict contains fields not in
fieldnames: 'city'` and exited 1 — but by then it had **already written**
a truncated CSV file to disk: header + Alice's row only, Bob's row silently
missing, with no indication in the file itself that it was incomplete.

**Live reproduction (part 2 — non-dict items):** Ran `json2csv` against
`["just", "a", "list", "of", "strings"]` (also a very plausible shape —
e.g. someone exporting a flat JSON array thinking it would "just work").
The command crashed with an unhandled `AttributeError: 'str' object has no
attribute 'keys'` and a raw internal Python traceback, not the clean
`error: ...` / exit-1 behavior the CLI uses for every other failure mode.

**Root cause:** `json_to_csv` computed `fieldnames` only from `rows[0]`'s
keys and called `rows[0].keys()` without checking `rows[0]` (or any row)
was actually a dict. It also wrote directly to the target file via
`csv.DictWriter(fh, ...)` as it iterated, so a `writerows()` failure
partway through left whatever had already been flushed sitting on disk at
the target path.

**Fix:** `json_to_csv` now (1) validates every row is a dict up front,
raising a clear `ValueError(f"row {index} is not a JSON object: ...")` that
the existing `except (OSError, ValueError)` handler in `main()` already
turns into a clean `error: ...` / exit-1 message; (2) builds `fieldnames`
as the union of every row's keys in first-seen order, so rows with extra or
missing fields no longer crash `DictWriter`; (3) writes the whole CSV into
an in-memory `io.StringIO()` buffer first and only calls
`target.write_text(...)` once, as a single atomic operation, so a failure
can never leave a truncated file behind.

**Verification:**
- Live repro: regenerated the script and re-ran all four scenarios —
  inconsistent keys now produces a complete, correct CSV (`name,age,city`
  header, both rows present, Bob's missing `city` left blank per normal CSV
  conventions) with exit 0; non-dict items now produce a clean
  `error: row 0 is not a JSON object: 'just'` / exit 1; the pre-existing
  empty-array and happy-path behaviors are unchanged (verified by direct
  re-run).
- Regression tests:
  `tests/unit/test_script_generator_data_safety.py::test_json_to_csv_handles_rows_with_inconsistent_keys`
  and `::test_json_to_csv_rejects_non_dict_rows_with_a_clean_error`.
- Full suite: 442 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 21 — Generated "contact" library is 100% non-functional (crashes every call)

**Severity:** Critical (every single generated project for this entity is unusable out of the box)

**Live reproduction:** Generated the Library-kind project for "Build a
Python library for managing a contact list with search". The resulting
`contact.py` has exactly one exported function, `search()`, which calls
`json.dumps(c, default=str)` internally. The generated module's docstring
read:
```
"""
contact: Build a Python library for managing a contact list with search

import json
Generated by Project FORGE deterministic synthesis.
"""
```
-- i.e. `import json` had been spliced in as a line of **plain text inside
the module docstring**, not as a real top-level import statement. Calling
`contact.search(...)` therefore raised `NameError: name 'json' is not
defined` on every invocation, and the project's own bundled
`test_contact.py` failed immediately with the same error the moment it was
run (`pytest test_contact.py` → 1 failed). Any real user generating a
contact-management library would receive a project that cannot do the one
thing it exists to do.

**Root cause:** `_lib_main` (`app/agents/synthesis.py`) built the contact
entity's `search()` function body referencing `json.dumps(...)`, then tried
to patch the import in after the fact with
`if "import json" not in "\n".join(L): L.insert(3, "import json")`. Index 3
in the accumulated output lines `L` is always
`"Generated by Project FORGE deterministic synthesis."` (the last line of
the fixed docstring header that every library emits), not the import
section — so the "import" landed inside the triple-quoted docstring instead
of becoming executable code.

**Fix:** Computed `needs_json = spec.entity == "contact"` up front, before
building any output lines, and emit `import json` as a real top-level
import directly in the header (alongside `from typing import Any`) when
needed, instead of mutating the line buffer after the fact by a hardcoded
index. Removed the old broken `L.insert(3, ...)` patch entirely.

**Verification:**
- Live repro: regenerated the "contact" library — the docstring is now
  clean, `import json` appears as a real top-level import, the generated
  `test_contact.py` passes, and `contact.search([{...}], "ann")` returns the
  correct filtered list instead of raising.
- Coverage-gap fix: the existing `CASES` list in
  `tests/unit/test_deterministic_synthesis.py` had only ever exercised the
  "string" and "number" library entities — none of the other eleven
  entity-specific branches in `_lib_main` (note/todo/book/contact/expense/
  event/file/user/password/url/recipe/habit) were ever generated *and
  executed* by any test, which is exactly how this bug went unnoticed. Added
  `test_every_library_entity_actually_runs`, a new parametrized sweep over
  all 17 recognised library entities/domains that generates each library and
  runs its own bundled test suite with a real interpreter (same "no mocks"
  standard as the rest of the file). All 17 pass post-fix; this would have
  caught Finding 21 immediately had it existed before.
- Full suite: 459 passed / 1 skipped / 0 failed (post-fix, after a fresh
  `.venv` rebuild this session since the prior session's virtualenv was not
  persisted).

---

## Finding 22 — `days_between` raised a raw, confusing error on a malformed date

**Severity:** Low-medium (crash with a confusing message, not data loss)

**Live reproduction:** Ran a systematic adversarial probe across all 17
library entities/domains, calling every exported function with edge-case
inputs (empty lists, `None` fields, unicode, malformed shapes). Every
function handled its edge cases gracefully except one:
`days_between("not-a-date", "2024-01-01")` raised
`ValueError: invalid literal for int() with base 10: 'not'` — a message
that names neither the argument nor the expected format, surfacing a
Python-internals implementation detail (`int()` parsing) instead of a
clear, actionable error.

**Root cause:** `parse()` inside `days_between` (`_DOMAIN_BODIES["date"]` in
`app/agents/synthesis.py`) called `int(x) for x in str(v).split("-")`
directly with no validation that the split actually produced 3 numeric
parts.

**Fix:** `parse()` now validates the split has exactly 3 all-digit parts
before converting, raising `ValueError(f"expected a YYYY-MM-DD date, got
{v!r}")` when it doesn't.

**Verification:**
- Live repro: regenerated the date library, confirmed
  `days_between("not-a-date", "2024-01-01")` now raises the clear message,
  the happy path (`days_between("2024-01-01", "2024-01-11") == 10`) is
  unaffected, and the generated `test_date.py` still passes.
- Regression test:
  `tests/unit/test_deterministic_synthesis.py::test_days_between_raises_a_clear_error_on_a_malformed_date`.
- The broader adversarial sweep (empty lists, `None` fields, unicode,
  malformed dict shapes across all 17 library entities) found no other
  bugs — every other function already degrades gracefully (e.g. `total([{"amount":
  None}])` → `0.0`, `active_users([{"active": None}])` → `[]`,
  `longest_streak([])` → `0`).
- Full suite: 460 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 23 — Scraper/automation scripts misrouted to the website generator

**Severity:** Critical (completely wrong deliverable: zero Python code, zero requested logic)

**Live reproduction:** Submitted the goal "Write a script that scrapes a
website and saves the data to a file" (a very ordinary, realistic request)
to `synthesize_project`. The output was `['README.md', 'app.js',
'index.html', 'style.css']` — a static HTML/CSS/JS landing page, with no
Python file at all and nothing resembling a scraper. Same misroute hits any
script-ish goal that happens to mention "website" (e.g. "monitor a website
for changes", "test a website's links").

**Root cause:** `_detect_kind` (`app/agents/synthesis.py`) checked
`ProjectKind.WEBSITE` second, immediately after `ProjectKind.API`, against
a broad keyword set that includes the bare substring `"website"`. Because
"website" appeared as the *object* of the goal's verb ("scrapes a
**website**") rather than describing the deliverable, it matched before the
SCRIPT-kind keyword `"scrape"` later in the same goal ever got a chance to
be checked — WEBSITE's check came first and returned immediately.

**Fix:** Reordered `_detect_kind`'s priority so the most generic, most
false-positive-prone keyword set (WEBSITE: "website", "webpage", "page",
"html") is checked **last**, after CLI, LIBRARY, and SCRIPT have each had a
chance to claim the goal on their own, more specific/intentional keywords.
API keeps top priority since its keywords ("fastapi", "rest api",
"endpoint") never collide with the others.

**Verification:**
- Live repro: regenerated the scraper goal — now correctly produces a real
  Python script project (`file.py` + `test_file.py`, generated tests pass)
  instead of a static website.
- Regression swept 12 goals across all 5 kinds (API/CLI/LIBRARY/SCRIPT/
  WEBSITE, including the three ambiguous "mentions website but wants a
  script" cases and two real website goals) — all classify correctly
  post-fix, confirming the reorder introduces no new misclassifications.
- Regression test:
  `tests/unit/test_deterministic_synthesis.py::test_script_goals_mentioning_website_are_not_misrouted_to_the_website_generator`
  (5 parametrized cases).
- Full suite: 465 passed / 1 skipped / 0 failed (post-fix) — the pre-existing
  `CASES` parametrized classification/compile/generated-tests-pass tests all
  still pass unchanged, confirming zero regressions from the reorder.

---

## Finding 24 — Generated REST API accepts unbounded string payloads (DoS vector)

**Severity:** Medium (resource exhaustion, not data loss/crash)

**Live reproduction:** Ran a 14-point adversarial probe against a real,
running generated FastAPI app (via `TestClient`, no mocks): malformed JSON
bodies, missing/wrong-typed fields, negative/absurdly-large/non-numeric
ids, path traversal attempts, unsupported HTTP methods, duplicate unique
fields, negative limit/offset, search with no query, double-delete,
updating a nonexistent id, and 50 rapid sequential creates. Every case
handled correctly **except**: POSTing a book with a 2MB `title` field
returned `201 Created` and stored the full 2MB string, uncapped, in the
in-memory `_DB` — trivially repeatable to exhaust server memory.

**Root cause:** Generated string fields on both the response model and the
`...Create` model had no `max_length` constraint — only `min_length=1` on
the Create model's required string fields.

**Fix:** Added `max_length=10_000` to every generated string field (both
`Optional[str]` fields on the response model and required `str` fields on
the Create model) — large enough for any realistic text field, small enough
to make a resource-exhaustion attempt fail fast with a clean 422.

**Verification:**
- Live repro: regenerated the books API, re-ran the adversarial probe — the
  2MB payload now returns 422 (`"String should have at most 10000
  characters"`), a normal-sized payload still returns 201, and all 13 other
  adversarial cases from the sweep continued to pass with zero regressions.
- Regression tests:
  `tests/unit/test_api_generator_routes.py::test_generated_api_rejects_pathological_string_payloads`
  and `::test_generated_api_survives_an_adversarial_probe_without_crashing`
  (the latter locks in all 13 non-size-related adversarial cases as a
  standing regression guard against future API-generator changes).
- Full suite: 467 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 25 — Generated CLI loses data and crashes under concurrent invocations

**Severity:** Critical (silent data loss + crashes under an entirely realistic usage pattern)

**Live reproduction:** Generated the CLI-kind project for a note-taking app
and launched 20 `python main.py add "Note N"` invocations concurrently
(`&` in a shell loop — exactly how a real user might batch-populate a CLI
tool, or how two terminal tabs/a background job could collide by accident).
Result: several invocations crashed with
`FileNotFoundError: [Errno 2] No such file or directory:
'note_data.json.tmp' -> 'note_data.json'`, duplicate ids were assigned
(`Added note #8` printed three times, `#9` twice), and when the dust
settled **only 12 of the 20 records actually existed on disk** — 8 were
silently lost even though every invocation printed a success message and
exited 0.

**Root cause (two independent bugs in the same code path):**
1. `Store.save()` always wrote to the exact same literal tmp filename
   (`<db>.tmp`) before atomically replacing the real file. Two concurrent
   writers share that identical tmp path, so one process's `tmp.replace()`
   could consume or race another's in-flight `tmp.write_text()`, crashing
   with `FileNotFoundError`.
2. `add`/`delete`/`update`/`clear` each called `self.load()` then (after
   mutating in memory) `self.save(...)` with **no locking** around the
   pair. Two concurrent processes each load the same on-disk list, each
   compute their own next id and append their own record, and each save
   their own full in-memory copy — the last writer's save silently
   discards every other concurrent writer's change (a classic
   read-modify-write "lost update" race).

**Fix:**
1. `save()`'s tmp filename now includes `os.getpid()`, so concurrent
   writers never share a tmp path.
2. Added `Store._locked()`, a `@contextlib.contextmanager` that acquires a
   blocking, exclusive, cross-process advisory lock (`fcntl.flock` on
   POSIX, with a documented best-effort no-op fallback on non-POSIX
   platforms where `fcntl` doesn't exist) on a sibling `.lock` file.
   `add`/`delete`/`update`/`clear` now wrap their **entire**
   load-modify-save cycle in `with self._locked():`, serializing concurrent
   writers so no update is ever lost.
3. (Minor, found while re-linting the fix) Commands with no further
   argparse configuration (e.g. `list`, `clear`) were still assigned to an
   unused `p_{cmd}` variable, tripping ruff's F841 on every generated CLI
   that had such a command. Fixed to only bind the variable when a command
   actually needs further configuration.

**Verification:**
- Live repro: regenerated the CLI, re-ran the exact 20-way concurrent `add`
  stress test — **zero crashes, all 20 records present, zero duplicate
  ids** (sequential 1-20). Pushed further to 50 concurrent adds (50/50
  survived, zero duplicates) and a mixed concurrent add+update+delete
  stress (no crashes, final state fully consistent with the operations
  performed).
- `ruff check` on the regenerated `main.py`: clean (previously had one
  F841).
- Regression tests (real subprocesses, real temp files, no mocks):
  `tests/unit/test_cli_generator_concurrency.py::test_concurrent_add_invocations_never_lose_or_crash`
  and `::test_concurrent_mixed_add_update_delete_do_not_crash`.
- Full suite: 469 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 26 — Ecommerce checkout form discards the customer info it collects

**Severity:** Medium (misleading UX, no data loss of app state, but a user's submitted PII is silently thrown away)

**Live reproduction:** Extended the existing generator-wide "dead
interactive element" sweep (previously `<form>`/`<button>` only) to also
cover `<input>`/`<select>` ids, across all four website templates. This
flagged the ecommerce template's checkout form: `cust-name`, `cust-email`,
and `cust-address` inputs (each with native `required` validation) had
**zero** references anywhere in `app.js`. Reading the submit handler
confirmed it: it generates a random order id, shows a generic "Order
Successfully Dispatched!" message, and clears the cart — but never once
reads `.value` on any of the three fields the customer just filled in and
submitted. A real user's name, email, and shipping address are collected,
validated for non-emptiness by the browser, and then thrown away.

**Root cause:** The checkout form's submit handler in
`_generate_ecommerce_js` (`app/templates/web_studio/generator.py`) was
written to only synthesize a fake order id and flip between the form/success
views — no code path ever called `document.getElementById('cust-name')` (or
the other two fields).

**Fix:** Added an `order-confirmation-recipient` element to the success
view, and the submit handler now reads `cust-name`/`cust-email`/
`cust-address`, trims them, and renders a real confirmation sentence
("Confirmation for `<name>` will be sent to `<email>` -- shipping to
`<address>`."). The form is also reset after a successful submit.

**Verification:**
- Live repro: regenerated the ecommerce site, verified via real jsdom DOM
  execution (not a static string check) — filled all three inputs,
  dispatched a real `submit` event on `checkout-form`, and confirmed
  `order-confirmation-recipient`'s rendered text contains the exact name,
  email, and address that were typed in.
- (Test-harness note, not a product bug: an early verification attempt
  manually re-dispatched a synthetic `DOMContentLoaded` *in addition to*
  jsdom's own native one, double-registering every listener and making the
  handler run twice per submit -- once with the real values, once with
  stale/empty ones from the second registration's own element references
  overwriting the first. Removing the manual redispatch and relying solely
  on jsdom's native event fixed the test; documented here so a future
  session doesn't mistake this jsdom double-fire quirk for a real bug
  again.)
- `node --check app.js`: clean.
- Regression tests:
  `tests/unit/test_web_studio.py::test_ecommerce_checkout_reads_the_customer_info_it_collects`
  and the generator-wide sweep
  `test_every_website_template_wires_up_its_interactive_elements`, now
  extended to check `<input>`/`<select>` ids (previously `<form>`/`<button>`
  only) across all four templates — this closes the exact coverage gap that
  let Finding 26 hide, the same way the Finding 17/17b sweep closed the
  form/button gap.
- Full suite: 470 passed / 1 skipped / 0 failed (post-fix).

---

## Finding 27 — Pause/cancel racing an in-flight DAG wave gets silently discarded (critical)

**Severity:** Critical. A user's explicit `cancel()` could be silently undone
and the task kept running and burning budget after they believed it was
dead; `pause()` suffered the same fate.

**Live reproduction:** `OrchestratorCore.step_task()` dispatches a wave of
ready DAG nodes concurrently via `asyncio.gather`. Each node's
`agent.execute_step()` can take a real LLM call, file I/O, or any other
`await` — plenty of wall-clock time for a user to call `POST
/tasks/{id}/pause` or `/cancel` from another request while the wave is
in flight. Those endpoints persist `BLOCKED`/`CANCELLED` immediately via
`TaskStateMachine`. But once the wave finished, every downstream write in
`step_task()` — the "more work remains" branch, the failure branch, and the
DAG-complete branch — unconditionally derived its next write from either a
**stale, pre-wave-start** `task.state` local variable, or a brand new
state of its own, and persisted that over whatever had since landed in the
DB. Built a deterministic repro (no wall-clock race needed): an injected
fake agent calls `lifecycle.pause()` / `lifecycle.cancel()` from *inside*
`execute_step()` (standing in for "a concurrent user action landed while
this await was in flight"), then returns normally.
- Pausing mid-wave: `pause()` correctly set `BLOCKED` in the DB, but
  `step_task()`'s own return value — and the persisted row — flipped right
  back to `RUNNING` the instant the wave completed. The user's pause was
  discarded with no error of any kind.
- Cancelling mid-wave: same thing, but worse — a `CANCELLED` task was
  resurrected to `RUNNING`, and `run_task()`'s own loop (which only stops on
  a terminal/`BLOCKED` state) kept calling `step_task()` and executing
  further waves of a task the user explicitly told it to stop.
- Edge case found along the way: if the *same* node that triggered the
  concurrent cancel then itself raised an exception (plausible — e.g. an
  LLM call failing right after the cancel was recorded), the failure branch
  tried to transition `CANCELLED -> FAILED`, which isn't a legal transition
  in `TaskStateMachine.TRANSITION_MATRIX` and crashed with an unhandled
  `InvalidStateTransitionError` instead of a clean "already cancelled, no-op."

**Root cause:** `step_task()`'s post-wave bookkeeping trusted its own local
`task` variable (captured before the wave ran) rather than re-checking the
live, currently-persisted state before deciding what to write next.

**Fix:** In `app/core/orchestrator.py`, right after the wave's results are
folded in and the graph is saved, `step_task()` now re-reads the task's
live state. If it has moved to `BLOCKED` or `CANCELLED` since the wave
started, `step_task()` returns that state as-is and skips every subsequent
write (the failure branch, the DAG-complete branch, and the progress-update
branch) instead of overwriting it.

**Verification:**
- Live repro scripts proved the bug for both pause and cancel, and the
  cancel-then-fail crash, before the fix; all three were clean after.
- Added three permanent regression tests to
  `tests/unit/test_orchestrator_concurrency.py`:
  `test_pause_mid_wave_is_not_silently_undone_by_step_task`,
  `test_cancel_mid_wave_is_not_silently_undone_by_step_task` (also checks
  `run_task()` doesn't keep driving a cancelled task), and
  `test_cancel_mid_wave_survives_a_subsequent_node_failure`. Confirmed all
  three fail against the pre-fix code (one with the raw
  `InvalidStateTransitionError` crash) and pass after.
- Test-hygiene note (caught by this work, not a product bug): the first
  draft of these tests monkeypatched `orch.registry.create_agent` directly.
  `OrchestratorCore.registry` defaults to the *module-level singleton*
  `app.agents.registry.agent_registry`, not a per-instance copy, so that
  mutation permanently broke real agent creation for every other test in
  the rest of the session (observed live as unrelated orchestrator tests
  elsewhere in the suite failing with "Task ... not found"). Fixed by
  constructing a dedicated `registry=` object per test and passing it into
  `OrchestratorCore(...)` instead of mutating the shared singleton —
  documented here so a future session doesn't reach for the same shortcut.
- Full suite: 473 passed / 1 skipped / 0 failed (up from 470 — 3 new tests,
  zero regressions).

---

## Next up (live-usage campaign continuing)
- Idempotent/double-submit handling. (Cancel-route consistency itself
  already covered by Finding 13; true execution-time pause/resume races
  against a long-running task remain untested.)
- Repeated/idempotent submissions of the same goal.
- Webhook delivery under receiver failure (timeouts, 5xx, DNS failure) --
  partially observed as a side effect of Finding 13's verification (3 retries
  against an unreachable receiver, logged as a WARNING, no crash) but not
  yet deliberately stress-tested on its own.
- Unicode/injection-style goal content (already partially covered by the
  NUL-byte sanitize fix documented inline in `orchestrator.py`; broaden to
  RTL overrides, zero-width chars, script injection strings).
- The generator-wide "dead interactive element" sweep
  (`test_every_website_template_wires_up_its_interactive_elements`) now
  covers forms/buttons across all four website templates going forward;
  consider extending it to `<a>`/`<select>`/`<input type="range">` elements
  too.
- Audit the Library generator (`_lib_main`) with adversarial inputs (empty
  lists, non-dict items, duplicate ids, huge inputs) for the same
  silent-failure bug family just found three times in the Script generator
  (Findings 18/19/20) -- the earlier "no bugs found" pass on the Library
  generator only exercised the happy path on a 2-item list.
- Multi-file website/web-API generation at larger scale: submit several
  different project kinds back-to-back through the live orchestrator (not
  just direct generator calls) and confirm delivery packaging + the
  verification pipeline catch issues like Findings 14-19 automatically, or
  confirm they currently do not (a process gap worth noting either way).
