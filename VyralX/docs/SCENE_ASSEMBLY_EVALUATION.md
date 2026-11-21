# Scene-by-scene assembly in VyralX — evaluation (TASK-IG3-VYR-10)

Status: **evaluated; the composition layer already exists
in-fleet; per-scene clip generation stays OFF-FLEET by
design; not adopted as a generation route.** The
generated-footage admission gate is unchanged by this
document: **the gate stays CLOSED** (see §4). Companion
records: `docs/LOCAL_GENERATION_EVALUATION.md` (the WanGP
evaluation, TASK-IG3-VYR-06 — same hardware facts),
`docs/GENERATED_FOOTAGE.md` (intake spec + the untaken
admission decision).

IG source: wave-2 cluster 120 (scene-by-scene cartoon
assembly; source De1VfkaOM_2, @trywithmark, full browser
watch 2026-11-16). Cross-references: cluster 117 (Google
Vids as a production route — SKIP, §3), cluster 112/113
(script-to-video lanes), cluster 131 (the production-rules
folder, TASK-IG3-VYR-09 — word-timed visuals).

## 1. What the source video shows

A three-step workflow for a full-length cartoon video:

1. Prompt ChatGPT for a complete story: narration script
   plus a visual prompt per scene (the example: a cozy
   jungle hotel run by animals).
2. Paste the script into Google Vids, select a voice,
   generate the narration; then paste each scene prompt
   individually into its AI video option to generate an
   8-second clip per scene.
3. Add every clip to the timeline **in story order** and
   **match them to the narration**.

The cluster's ask, restated precisely: the *assembly* —
scene-by-scene composition of generated clips on a
narration-matched timeline. The generation in step 2 is
Google Vids, a hosted third-party product.

## 2. What already exists in VyralX (the composition layer)

The assembly half of the workflow is built, as tested
libraries with production-path wiring landing across the
IG3 clusters:

| Video step | VyralX counterpart |
|---|---|
| Story → scene-by-scene breakdown | Retired with the Path C lane (TASK-VYR-033, 2026-11-21): `previs.build_storyboard` / `previs.contact_sheet_plan` were removed with the lane catalogues they matched beats against; beat-level storyboarding against stocked clips is no longer offered. The assembly step below still covers script → planned footage. |
| Script → per-segment assembly plan | `short_video_assembly.build_assembly_plan` / `build_batch` — segments the script and plans footage per segment |
| Clips on a timeline, in story order | `film_pipeline.build_film` — a validated film manifest (shots with start/duration/end computed in order, lanes restricted to the channel's three, Shorts <60s cap); `film_pipeline.render_film_html` — the single-file film artifact |
| Human fixes before render | `film_pipeline.apply_studio_edit` — trim / move / restyle / retype, each logged, film stays `pending_review` |
| Narration timing | `style_recipe.clean_transcript` (timed words, dead-air/false-start cuts); the rules folder's word-timing rule (`production_rules`, TASK-IG3-VYR-09) checks that visuals land on their words |
| Run discipline + quality gates | `pipeline_orchestration.create_run` / `advance_run` (state machine with a storyboard approval gate) and `pipeline_orchestration.evaluate_quality_gate` (duration cap, captions present, provenance present, finance-advice screen) |
| Post-assembly verification | `take_verification` (TASK-IG3-VYR-05) — blank-frame gate + take scoring over the assembled recording's evidence |

Retirement note (TASK-VYR-033, 2026-11-21): the Path C lane —
the lane catalogues, their loaders, `content_factory` and
`previs` — was retired after verifying no live path used
it. The composition layer above is what remains; the
bottom line (§6) is unchanged.

This is why the lane baseline graded cluster 120 PARTIAL
with "the composition layer exists" rather than ABSENT:
the missing piece was never the assembly.

## 3. What stays off-fleet, and why

**Per-scene AI clip generation does not run on this
fleet.** Two independent reasons, either sufficient:

1. **The source's route is a hosted product, not a
   feature.** Google Vids generation is cluster 117,
   graded SKIP: third-party hosted product adoption; no
   FRIDAY-native feature to build. Recording the pattern
   (this document) is the adoption the lane makes of it.
2. **Generation is GPU/hosted-class work.** The hardware
   facts are measured in the WanGP evaluation and are not
   repeated here: no GPU on either server, ~956MB RAM per
   VM, a ~180MB per-service cap, Python 3.10. The fleet's
   own render rule states the same boundary from the
   composition side: `film_pipeline.render_gate` REFUSES
   in-service rendering (`renders_in_service: False`) and
   names the allowed hosts — the owner's machine, or
   post-ARM. VyralX orchestrates and composes; it does not
   generate or render inside the service.

The owner's FREE-only rule closes the remaining door:
rented hosted generation is a paid service, and adopting
it is a spend decision this evaluation does not take.

## 4. The gate is not part of this evaluation

A generated scene clip is generated footage, and nothing
here changes that position:

* the admission gate in `app/services/generated_footage.py`
  stays **CLOSED** — generated clips are not admitted as
  production inputs, scene clips included;
* the **A3 REMIX_POLICY `ai_generated_terms` admission is
  a policy decision, not yet taken** — it is the owner's,
  and this document does not take it, pre-empt it, or
  argue it;
* a scene clip generated off-fleet would receive **no
  exception**: it enters, if at all, through the same
  provenance intake as any other generated media (§5).

## 5. The honest path (the only path)

If the owner wants a scene-by-scene cartoon assembled:

1. Story, narration script and per-scene prompts are
   produced in-fleet (the assembly layer, §2) —
   this part needs nothing new.
2. Scene clips are generated **off-fleet**, on the owner's
   hardware or a route the owner chooses and pays for (his
   call, his spend decision — §3).
3. Each clip is submitted through the **provenance
   intake** (`generated_footage.intake_generated_clip`):
   generator, model, prompt, timestamp and locator are
   all required — incomplete provenance is refused
   outright.
4. Admission of the `ai_generated_terms` class remains
   gated on the owner's A3 decision (§4). Until it is
   taken, intaken clips sit in the registry and are used
   for nothing.
5. Admitted clips — if that day comes — assemble through
   the existing composition layer and are verified by the
   existing gates (§2). No step requires building a
   generation capability today.

## 6. Bottom line

Cluster 120's assembly ask is already answered by the
composition layer on main; its generation step belongs to
a hosted product the lane deliberately does not adopt
(cluster 117) and to hardware the fleet does not have.
The evaluation is recorded so the question never has to
be re-asked from scratch: **revisit only if the owner
supplies generated scene clips through the provenance
intake, behind a gate that stays CLOSED until he decides
otherwise.**
