# TASK-FRD-057 — Build + Verify Record

- **Task:** TASK-FRD-057 — FRIDAY: book-page translation reading mode (P3)
- **Worker:** Muse TP9 (implementation) — re-filed by Muse 15 per coordinator WATCH129 (PR #1849 superseded)
- **Branch:** `muse15/task-frd-057-book-translation`, base main `4c0acbfa`; TP9 head re-filed: `db022b52`

## Re-file changes (Muse 15, vs TP9 head `db022b52`)

- `.github/workflows/friday-universe-ci.yml` re-anchored onto main `4c0acbfa`: `tests/test_ig_frd_061_lead_verification.py` has since joined the tier-1 invocation; the FRD-057 test is appended after it (TP9's patch predates that file).
- Module docstring TTS paragraph corrected to the `/api/voice/speak` edge-tts path (the build-verify record already carried this correction; the docstring did not).
- Board flip (CLAIMED → IN_REVIEW) follows as a second commit once coordinator board PR #1924 merges — it carries the FRD-057 re-slot to Muse 15.
- **Date:** 2026-11-25

## What the task asked for

Source F-15 (item DaFKBDwJlLZ): a study method for Telugu readers —
screenshot 10–20 book pages daily and have the AI translate them into
Telugu. Build: owner photographs/screenshots book pages → FRIDAY OCRs
the page, translates it to Telugu through the Inference route, returns
the translation page by page, with optional spoken read-out through
the voice lane. Done = live proof on production FRIDAY: one real book
page translated end to end, page image in, Telugu text out.

## What was built

### 1. Reading workflow — `FRIDAY/src/friday/workflows/book_translation.py`

- `ocr_page_image(image_path)`: local Tesseract OCR via pytesseract
  (the same pattern as `tools/builtin/screen_ocr.py` — `image_to_data`,
  confidence floor 40, lines rebuilt by top coordinate). Free, no cloud
  call. A photo with no readable text, a missing file, or a missing
  Tesseract install returns an honest error — nothing is invented.
- `translate_to_telugu(text)`: sends the OCR text to the LLM provider
  stack (`create_llm_provider` — the REL-044 escalating stack, so a
  full-page translation is served by Inference) with a translate-only
  prompt (Telugu output only, paragraph breaks preserved). Returns the
  Telugu text + serving provider, or an honest error.
- `translate_page(image_path, book, page_no)`: OCR → translate → save.
  Pages are saved as `FRIDAY/.data/book_translation/<book>/page-<n>.md`
  (Telugu + OCR source + metadata) and progress is tracked in
  `state.json` (pages done, last page). Page numbers auto-increment per
  book, so the owner just keeps sending photos. Either step failing
  returns the reason honestly; a translation failure also returns the
  OCR text that was read.
- `book_progress(book)`: pages done / last page (honest empty).
- No send/apply path anywhere in the module.

### 2. Telegram photo entry — `FRIDAY/src/friday/proactive/telegram_gateway.py`

The gateway previously dropped photos silently (`if not text: return`).
Now, after the owner gate (so a non-owner photo is refused, never
processed): a photo update downloads the largest size Telegram kept
(`getFile` + file download), saves it to the book-translation inbox,
runs `translate_page` (caption = book name, or "unspecified"), and
replies with the Telugu translation (`send_message` chunks long texts
itself). Every failure — no file id, download failure, OCR failure,
translation failure — is replied honestly. The handler never raises
into the poller.

### 3. Tool — `FRIDAY/src/friday/tools/builtin/book_translation_tools.py`

`translate_book_page` (SENSITIVE): chat-side equivalent for a local
image path — OCR, translate, save, return the Telugu translation.
Registered in `friday/tools/builtin/__init__.py`.

### 4. Tests — `FRIDAY/tests/test_ig_frd_057_book_translation.py`

Hermetic (fake OCR runner + fake LLM, no engine/network/key): OCR line
reconstruction, honest empty/missing-file OCR, translation prompt +
return, translation failure, page save + state tracking + auto-increment
(page 1 then page 2), OCR failure calls no translation, translation
failure saves nothing, empty progress, tool success/error, gateway photo
translates + replies (getFile with the largest file id), non-owner photo
refused, translation failure replied honestly. Collected in the FRIDAY
tier-1 CI invocation (REL-068).

## Design decisions (recorded, not assumed)

- **Entry channel is Telegram.** The owner already photographs things
  on his phone and texts FRIDAY on Telegram (@fridayuniverse_bot);
  that is the only phone-side surface FRIDAY has. No new app, no new
  bot.
- **OCR is local Tesseract, not a cloud vision call.** Free, no quota,
  and the pattern already exists in FRIDAY (screen_ocr). A Gemini
  vision fallback was considered and not built: it would draw on
  FRIDAY's own Gemini pool for every page, and the honest-failure +
  install path is the cleaner contract.
- **Spoken read-out is NOT wired in this task.** The acceptance calls
  it optional. CORRECTION (2026-11-25): a Telugu TTS path DOES exist on
  the server — `POST /api/voice/speak` synthesises English or Telugu
  via edge-tts (Microsoft neural voices) and returns audio/mpeg. An
  earlier draft of this record wrongly claimed no Telugu TTS path
  existed (NativeTTS is Windows SAPI, English-only, and no `speak_text`
  exists in FRIDAY/src — both true, but the API speak endpoint is the
  server-side path). Wiring a "read aloud" button for a saved page is
  a follow-up: POST the page's Telugu text to /api/voice/speak and play
  the returned audio.

## Live checks done 2026-11-25

- Tesseract is NOT installed in this worker VM (checked: `which
  tesseract` empty; a rendered 5-line book page could not be OCR'd
  here). This VM is not the production server, so it proves nothing
  about FRIDAY-Server — but it sets the deploy prerequisite below.
- No live end-to-end proof exists yet (no deploy, no real page photo).
  The workflow, tool and gateway paths are verified by the hermetic
  tests above plus the reused proven patterns (screen_ocr pytesseract,
  web_research provider call, gateway send path).

## Deploy prerequisite (for Muse)

FRIDAY-Server needs the `tesseract-ocr` package installed for the OCR
step; without it the workflow reports "Local OCR unavailable" on every
page (honest, but the feature does nothing). One-line apt install on
the server, then the first real page photo is the production proof.

## Five states

- implemented: YES (workflow + tool + Telegram photo entry + tests)
- tested: PARTIAL (unit tests in CI; live proof pending — see below)
- merged: NO (work PR pending)
- deployed: NO
- production-verified: NO

## What is NOT done — the remaining step

The task's Done is one real book page translated end to end on
production FRIDAY (page image in, Telugu text out). That needs merge +
deploy (+ tesseract on the server) + one real page photo from the
owner through Telegram. That run is the production verification this
record does not yet claim.
