# Generated footage in VyralX — intake spec and gate decision (TASK-IG-VYR-07)

Status: **intake implemented; admission is a policy decision, not yet taken.**
Companion code: `app/services/generated_footage.py`. Gate: TASK-VYR-004
(`app/services/remix_flow.py`, `docs/REMIX_POLICY.md`).

## Why this document exists

The Instagram reference corpus (2026-11-15 triage) contains a cluster of
items promoting free AI generation tools as production inputs for
faceless channels (DdnNrgtE7HN, Dee1ZxUybxd, De4XEoLjg_f, DeI_T6dB-uk,
DXlFWL5EkaN). VyralX's licence gate has one rule that binds everything:
**no provenance, not a candidate.** AI-generated media is exactly where
provenance goes missing, so generated footage gets a dedicated intake
instead of being dropped into the stock catalogues.

## What is implemented

`generated_footage.intake_generated_clip(metadata)`:

1. **Refuses incomplete provenance outright** — generator, model,
   prompt, generation timestamp and media locator are all required;
   missing fields raise, naming every gap. Nothing partial is recorded.
2. **Evaluates terms, never assumes them** — a clip is marked
   terms-granting only when the caller asserts the generator's terms
   grant commercial + derivative rights in outputs AND supplies the
   terms URL as evidence. Assertion without URL ⇒ terms unknown.
3. **Records complete intakes** in the append-only VYR-004 provenance
   registry with generator, model and the terms verdict in the
   decision reason — the evidence exists permanently, whatever the
   admission decision later is.

## What is deliberately NOT done — and the decision that unblocks it

Intake does **not** make a clip a remix candidate. The gate admits
licence classes `cc0 / public_domain / cc_by / cc_by_sa / owner`;
generated footage classifies as `ai_generated_terms` (terms-granting)
or `unknown`, and `require_candidate` refuses both today.

**The decision, for the coordinator/owner:** amend `REMIX_POLICY.md`
to define when AI-generated outputs may be used (suggested minimum:
terms grant commercial + derivative rights, evidenced by URL; prompt
and model recorded; output carries the provenance watermark from
TASK-IG-VYR-08), then add `"ai_generated_terms"` to
`ALLOWED_LICENSE_CLASSES`. One line of code — but it is a policy line,
and it does not belong inside an intake PR.

## Corpus generation sources, evaluated against the gate

| Source (IG id) | What it is | Verdict |
|---|---|---|
| LTX-2.5 (DeyMp0wu1Gx) | Open-weights video model (Lightricks) | **REJECT — hardware.** Repo card verdict: needs GPU compute far beyond the ~1 GB RAM fleet; no CPU path. Skipped; revisit only if a hosted free tier with admissible terms appears. |
| Unnamed free AI video tools (Dee1ZxUybxd, DdnNrgtE7HN) | Comment/DM-gated tool names | **Cannot evaluate** — unnamed tools have no terms to evaluate. Any clip sourced this way still needs full intake metadata; without it, refused. |
| AI media generation tools (De4XEoLjg_f, DeI_T6dB-uk, DXlFWL5EkaN) | Tool roundups / single tools | **Spec only.** No generator is integrated: integrating one means an account, a key, and terms review per tool. Note also that AI video generation is currently unavailable on the channel owner's accounts (provider-side 403), so there is nothing to wire today. |
| HyperFrames (DbI_v6gMDW1 cluster tooling) | HTML→video composition | Not a generator — a renderer; covered by the motion-graphics work (TASK-IG-VYR-09), with its off-fleet render constraint. |

## Rule going forward

Any future generated clip — from any tool, however it arrives — enters
through `intake_generated_clip` or it does not enter at all. "The tool
was free" is not a licence, and "AI made it" is not provenance.
