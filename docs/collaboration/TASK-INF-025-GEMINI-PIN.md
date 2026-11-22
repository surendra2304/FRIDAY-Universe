# TASK-INF-025 — Live text-path Gemini pin verification

- **Task:** Inference/FRIDAY — verify the live text-path Gemini pin is
  gemini-3.5-flash-lite (the 2.5 legacy id is access-limited from 2026-12-01);
  fix the pin if wrong, probe completion, file evidence.
- **Provenance:** coordinator queues post 7084110569 (Muse 9 queue position 2);
  queue VAL-010 → INF-025 → INF-026 per coordinator watch 7085314708.
  Claimed by skipping from VAL-010 under the blocked-head rule after the
  FRIDAY chat 401 gate re-probe (03:41 IST) stayed closed — claim comment
  7086670912, 2026-11-23 ~03:46 IST. Branch
  `muse9/task-inf-025-gemini-pin`, base main `719b175e` (board blob
  `cd37c776`, verified against the true main blob before editing).
- **Verdict: pin correct — no fix needed.** Every live text-path location
  already pins gemini-3.5-flash-lite, and a live completion on that id
  serves under its own name. The one remaining 2.5 id in a live fallback
  is an OpenRouter listing, not the Gemini text path (§5) — flagged, not
  silently changed.

## 1. Code pins — main 719b175e and deployed Server 1 checkout 3f9cec0c (identical on every pin below)

- FRIDAY voice key-probe stage-1 text pin:
  `FRIDAY/src/friday/voice/livekit_worker.py:901`
  `_PROBE_TEXT_MODEL = "gemini-3.5-flash-lite"` — used at :995
  (`client.models.generate_content(model=_PROBE_TEXT_MODEL, contents="ping")`).
  Set by TASK-VOI-021; the legacy gemini-2.5-flash-lite pin it replaced is gone.
- FRIDAY fast-escalation pin:
  `FRIDAY/src/friday/llm/escalation.py:356`
  `FAST_ESCALATION_MODEL = "gemini-3.5-flash-lite"` (used at :510).
- Inference catalogue: `Inference/app/api/v1_core_routes.py:901`
  `{"id": "gemini-3.5-flash-lite", "owned_by": "google", "provider": "gemini"}`.
  Class `economy` (:998); it leads the `simple` task ranking (:1031) and is
  ranked in every other suitability list. No 2.5 id anywhere in the catalogue
  (gemini-2.5-flash removed as Google-404 by TASK-REL-030, :883 comment).
- Inference Gemini adapter: `Inference/app/providers/gemini.py:50`
  `SUPPORTED_MODELS` includes `"gemini-3.5-flash-lite"`. The legacy
  gemini-2.5-flash-lite entry was REMOVED by TASK-INF-017 (:38 comment).
  `DEFAULT_MODEL = "gemini-flash-latest"` (:28) — the `-latest` alias, not a
  2.5 id; it is the adapter default when no model is named, not the
  text-path pin, so it is left alone.
- Routing safety net: a request naming a non-catalogue id is never forwarded
  verbatim — REL-043 best-suitable selection substitutes from the verified
  catalogue, with the provenance block disclosing the substitution
  (`selected_as`, downgrade flag). For a simple request the substitute is
  gemini-3.5-flash-lite (leads the `simple` ranking).

## 2. Live env pins — Server 1, 2026-11-23 ~03:48 IST (names + model values only; no key values read)

- `/opt/friday_universe/FRIDAY/.env`: `FRIDAY_LLM_MODEL=gemini-3.6-flash`,
  `FRIDAY_GEMINI_MODEL=gemini-3.6-flash`, `FRIDAY_VISION_MODEL=gemini-3.6-flash`,
  `FRIDAY_VOICE_LIVE_MODEL=gemini-3.8-live`. These are the primary
  reasoning/vision/voice models, NOT the text-path (fast/economy) pin —
  deliberately NOT changed: the task pins the fast text path to
  flash-lite, not FRIDAY's primary model to the economy tier.
- `/opt/friday_universe/Inference/.env`: no `MODEL`/`ALIAS` vars at all —
  no `LITELLM_MODEL_ALIASES_JSON` override exists live, so no alias can
  re-point the pin at a 2.5 id.

## 3. Live completion probe — gemini-3.5-flash-lite, Server 1, ~03:50 IST

- `POST http://127.0.0.1:8001/v1/chat/completions` from Server 1, key read
  server-side from the Inference env (never printed, never copied) and
  sent as `X-INFERENCE-API-KEY`; body
  `{"model": "gemini-3.5-flash-lite", "messages": [{"role": "user",
  "content": "Reply with exactly this word: PIN-OK"}], "max_tokens": 20,
  "temperature": 0, "stream": false}`.
- Result: **HTTP 200 in 2.36 s; `response_model` gemini-3.5-flash-lite**
  (served under its own name, no substitution); `finish_reason STOP`;
  content `'PIN-OK'` exactly; usage 78 prompt / 3 completion / 81 total
  tokens. The live text path generates on the pinned id.
- Note: the public `/inference/v1/models` endpoint returns 401 without a
  key (also on localhost) — the probe therefore ran server-side with the
  fleet's own key in place, the same pattern as the voice worker's key
  probe. One short completion on the Flash-Lite free tier (500 RPD).

## 4. Legacy-id probe — gemini-2.5-flash-lite, Server 1, ~03:51 IST

- Same call shape as §3 but `model: "gemini-2.5-flash-lite"`.
- Result: **HTTP 200 in 10.02 s; content `'PIN-OK'`; `finish_reason STOP`**.
  The legacy id is NOT forwarded to Google and does NOT 404: the
  provenance block discloses the substitution —
  `requested_model gemini-2.5-flash-lite`, `selected_as best_suitable_for_chat`,
  `selected_model gemini-3.8-flash`, `served_by_model gemini-3.6-flash`,
  `response_model gemini-3.6-flash`. So a caller still naming the legacy
  id gets an honest, disclosed substitution from the verified catalogue,
  and the 2026-12-01 Google-direct access-limit can never bite through
  the gateway path.
- Honesty note: `selected_model` (3.8-flash) differs from `served_by_model`
  (3.6-flash) — the selected flagship did not serve, and the gateway's
  ladder served the next rung. `fallback_reason` is null in the provenance,
  so the cause of the 3.8 miss is UNVERIFIED this run (the known 3.8
  free-tier demand limit, cf. TASK-INT-021's 503 evidence, is the likely
  cause, but this run did not prove it — no 3.8 probe was run). The
  substitution itself, and its disclosure, are verified.

## 5. Remaining 2.5 ids — flagged, not changed

- `Inference/app/providers/openrouter.py:30`
  `FALLBACK_FREE_MODELS["research"] = "google/gemini-2.5-flash"` — the
  OpenRouter listing of that name, deliberately retained per the REL-030
  comment ("retired at Google direct, but the OpenRouter listing of that
  name is live"). It is a fallback for OpenRouter `research` capability,
  not the Gemini text path, and the task's access-limit concerns the
  Google-direct legacy id. Changing a deliberately-retained fallback
  without coordinator direction would be scope creep; flagged here for
  Muse to rule on.
- `Inference/app/providers/gemini.py:51` `"gemini-2.5-pro"` stays in
  `SUPPORTED_MODELS` — the Pro family, a different model from the
  access-limited flash-lite legacy id; not a text-path pin.
- `gemini.py:132` `_THINKING_FAMILIES = ("gemini-3", "gemini-2.5")` — a
  substring family tag for thinking-budget handling, not a model pin.

## 6. What was NOT changed, and why

- No code change: every text-path pin is already gemini-3.5-flash-lite on
  both main and the deployed Server 1 checkout (3f9cec0c).
- No env change: `FRIDAY_LLM_MODEL` stays gemini-3.6-flash (primary
  reasoning model — out of this task's scope).
- No deploy/restart: none needed; `FRIDAY.service` and
  `Inference.service` are active/running on Server 1 (PIDs 2503092 /
  2503138, started 01:32 IST), and the running Inference answers
  `/health` 200 with providers including gemini. Live-fleet deploys need
  Muse's clearance in any case; none was sought because none is needed.

— Muse 9
