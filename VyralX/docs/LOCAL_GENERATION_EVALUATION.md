# Local generation in VyralX — WanGP evaluation (TASK-IG3-VYR-06)

Status: **evaluated; NOT fleet-runnable; not adopted.** The
generated-footage admission gate is unchanged by this document:
**the gate stays CLOSED** (see §4). Companion records:
`docs/GENERATED_FOOTAGE.md` (intake spec + the untaken admission
decision), repo card `deepbeepmeep-wan2gp.md` (fit: reject).

IG sources: package entry V-08 (Wan2GP local stack); wave-2
cluster 134 (local Wan2GP text-to-video; sources Dd7M_sLjunh,
DeRrQa-E2AV). Cross-references: V-01 (Open-Generative-AI
studio), V-06 (named free hosted routes).

## 1. What was evaluated

**WanGP** (deepbeepmeep/WanGP — the repo named in the source
reels as `deepbeepmeep/Wan2GP` has been renamed) is a local,
one-stop generative "super app": video models (Wan 2.1/2.2 and
derivatives, MiniMax H3, LTX-2/2.3/2.5, Hunyuan Video,
LongCat, Kandinsky), image models (Flux 1/2, Qwen Image,
Krea 2, Z-Image), plus TTS/audio and 3D models, behind a
Gradio interface with LoRA support, quantised checkpoint
formats (int8, fp8, gguf, NV FP4), a generation queue,
headless batch mode, an API and an MCP interface. It is very
actively maintained (~11,900 stars, 9 releases, v19.292 on
2026-11-12, per the repo card's 2026-11-16 check).

The question this evaluation answers is narrow: **can the
fleet run it, and if not, what is the honest path by which
its output could ever reach VyralX?**

## 2. Licence

GitHub classifies the repo licence as **Other (NOASSERTION)**.
A `LICENSE.txt` is present; the README states WanGP is free
to use locally and will never ask for a licence fee. The
**underlying models carry their own licences** — a model
bundled or downloadable through WanGP is not thereby cleared
for any particular use. Consequence for VyralX: even on
suitable hardware, every generated clip would still need its
model's terms evaluated at intake (the `generated_footage`
terms evaluation exists for exactly this), and "the tool is
free" must never be recorded as "the output is cleared".

## 3. Hardware verdict — NOT fleet-runnable

WanGP bills itself as built for "the GPU Poor", but GPU-poor
still means **a GPU**:

| Requirement (repo card, README) | Fleet reality |
|---|---|
| As little as **4GB VRAM** for select models; **8GB VRAM** to get started with interactive worlds | **No GPU at all** — two Oracle VMs, ~956MB RAM each |
| Install paths target GTX 10XX / RTX 20XX–50XX with PyTorch/CUDA | No CUDA device exists on either server |
| Current path: Python 3.11 / PyTorch 2.10 / CUDA 13 | Fleet runs Python 3.10 |
| Multi-GB model weights per model | Exceed a VM's total RAM; VyralX's per-service cap is ~180MB |

**Verdict: NOT fleet-runnable.** This is a measurement, not a
preference: there is no configuration of the current fleet on
which WanGP starts, let alone generates. The owner's FREE-only
rule also rules out the rented/hosted-GPU workaround as a
default — hosted GPU generation is a paid service, and
adopting it is a spend decision this evaluation does not take.

This matches the card's recorded fit (**reject**) and the
earlier LTX-2 rejection (TASK-IG-VYR-07): same hardware facts,
same outcome.

## 4. The gate is not part of this evaluation

Nothing here changes the generated-footage position:

* the admission gate in `app/services/generated_footage.py`
  stays **CLOSED** — generated clips are not admitted as
  production inputs;
* the **A3 REMIX_POLICY `ai_generated_terms` admission is a
  policy decision, not yet taken** — it is the owner's, and
  this document does not take it, pre-empt it, or argue it;
* a clip generated locally by the owner would receive **no
  exception**: it enters, if at all, through the same
  provenance intake as any other generated media (§5).

## 5. The owner-hardware path (the only path)

If the owner later runs WanGP on **his own GPU hardware**,
its low-VRAM optimisation, quantised checkpoints and
all-in-one model coverage would make it a strong generation
candidate — strong enough to subsume the LTX-2 route rejected
earlier. The path for its output is the one that already
exists:

1. Generate on the owner's machine (his hardware, his call).
2. Submit each clip through the **provenance intake**
   (`generated_footage.intake_generated_clip`): generator,
   model, prompt, timestamp and locator are all required —
   incomplete provenance is refused outright.
3. The clip's model terms are evaluated at intake (§2); the
   intake records, it does not admit.
4. Admission of the `ai_generated_terms` class remains gated
   on the owner's A3 decision (§4). Until that decision is
   taken, intaken clips sit in the registry and are used for
   nothing.

No step in this path requires fleet changes, so there is
nothing to build today: the evaluation, the intake, and the
gate are all already in place. What is missing is hardware
and a policy decision — both the owner's.

## 6. Cross-references (evaluated, not adopted)

* **V-01 — Open-Generative-AI studio** (Anil-matcha/
  Open-Generative-AI): a hosted studio route, carded
  reference-only. It is not local generation and offers the
  fleet nothing the stocked catalogues + intake do not
  already cover. **Not adopted.**
* **V-06 — named free hosted routes** (Sora 2, MiniMax,
  NanoBanana, Wan 2.6, SadTalker, Gamma AI): hosted services,
  not local generation. The names are recorded as reference
  data in `channel_strategy.json` (`free_route_alternatives`,
  TASK-IG3-VYR-01) with their recorded status; recording a
  name is not adopting a route, and none is a production
  input. **Not adopted.**

## 7. Bottom line

WanGP is a real, free, actively maintained local generation
stack that this fleet cannot run — no GPU, ~956MB RAM,
Python 3.10 against a 4GB-VRAM / CUDA / Python 3.11 floor.
It is recorded here so the question never has to be
re-asked from scratch: **revisit only if the owner gets GPU
hardware of his own**, and even then its output enters only
through the provenance intake, behind a gate that stays
CLOSED until the owner decides otherwise.
