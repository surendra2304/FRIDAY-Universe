# Local & On-Device Inference — Assessment (TASK-IG-INF-04)

Corpus cluster: the local/self-hosted rung (4 sources). This is an
assessment with measured evidence, not an integration: the binding
repo-card verdicts and the fleet's hardware arithmetic decide most of
it, and the one genuinely promising item (needle) was piloted for
real before any spec was written.

| Source | Idea | Verdict |
|---|---|---|
| DZW48tnyDas | Ollama-served open models as a local Inference rung | **Not on the fleet servers** — viable only on owner hardware (§1, §2) |
| DcvlVi8zzb5 | NVIDIA Spark-class box as a zero-cost local route | **No such hardware exists** in the fleet or the owner's known kit — revisit trigger in §3 |
| DfCb_QSk3PC | Free-GPU self-hosted endpoint (Kaggle + Strata) | **REJECTED** per repo card (§4) |
| DdjJQDFjc9w | needle: tiny on-device tool-calling model as an always-available fast path | **PILOTED — promising on owner devices, with two design constraints** (§5, spec in §6) |

## 1. A server-side local rung is not viable on this fleet

The arithmetic is not close. Each Oracle VM has ~956MB RAM total;
Server 1 runs seven agents in it, with ~116MB free and 8GB of swap
already load-bearing (Redis/Qdrant are deferred to a future ARM
server for the same reason). FRIDAY's own service cap is 200MB and
it sits at ~199.9MB. The smallest useful Ollama-class model (≈1B
parameters at Q4) needs roughly 700MB–1GB RSS including its runtime
— more than the free RAM of the whole server, before any other agent
breathes. Squeezing it into swap would trade the fleet's stability
for a local model that is weaker than what the free cloud tiers
already serve through the gateway.

There is also no workload asking for it server-side: Inference's job
on the servers is routing across pooled free-tier keys (REL-043 /
REL-049 baselines), and it does that within its current footprint.
**Nothing was installed on the servers for this task, deliberately.**

## 2. The owner-hardware rung already exists — no new code

A local endpoint on the owner's own hardware is supported today:

- the pre-existing single `local` provider (LOCAL_BASE_URL /
  LOCAL_MODEL / LOCAL_API_KEY / LOCAL_PREFERRED and friends), built
  for exactly this — an Ollama/llama.cpp/vLLM server on the LAN; and
- TASK-IG-INF-02's custom endpoints (PR #480), which generalise it:
  any number of OpenAI-compatible endpoints (e.g. Ollama on the
  owner's laptop) become `custom-<name>` providers, addressable by
  model id, with isolated keys.

So DZW48tnyDas's rung is a *configuration* on owner hardware, not a
build task. The operator recipe is: run Ollama on the laptop, set
LOCAL_ENABLED=true + LOCAL_BASE_URL=http://<laptop-lan-ip>:11434/v1
+ LOCAL_MODEL=<pulled model> on Server 1 (or declare it via
INFERENCE_CUSTOM_ENDPOINTS), restart Inference, and verify with the
IG-INF-03 pipeline before trusting it with traffic.

## 3. Spark-class box (DcvlVi8zzb5)

No Spark-class (or any GPU) hardware exists in the fleet or the
owner's known kit, so there is nothing to integrate or benchmark.
If such a box is ever acquired, it needs no new code either: it
would serve an OpenAI-compatible endpoint and land through §2's
routes. Revisit trigger: the hardware physically existing.

## 4. Kaggle + Strata (DfCb_QSk3PC) — rejected, per the binding card

The repo card's verdict binds: Strata targets the owner's own
consumer PC with a 12GB GPU and ~64GB RAM; the repo does not support
the reel's "run it on free Kaggle GPUs" framing (the Kaggle dual-T4
guides that exist are for other projects). The fleet has neither the
GPU nor the RAM, and a production endpoint balanced on free Kaggle
sessions would be a fragile grey route besides. Not implemented, in
any form.

## 5. Needle pilot (DdjJQDFjc9w) — measured on this machine

Card claims (repos/cactus-needle.md, verdict **adapt**): Needle 2 is
a 45M-parameter tool-calling model, 14MB binary, ~28MB RAM, fully
offline, Apache-2.0, `pip install cactus-compute`. Pilot harness:
`Inference/benchmarks/needle_pilot.py` — cactus-compute 4.2.2,
`cactus.Needle` with three FRIDAY-flavoured tools (get_weather,
set_reminder, search_memory), 8 prompts, run 2026-11-15 on this
sandbox (x86_64, shared 1.5 vCPU, Python 3.12 venv).

**What worked**
- Install + run on x86_64 Linux: proven. First construction took
  53.3s including the one-time engine+weights download (~71MB of
  cache: ~/.cache/cactus 36MB + HF hub 35MB).
- Tool routing on direct commands: **6 of 6 command prompts routed
  to the correct tool with correct arguments** (weather×2 with the
  right cities, reminders×2 with the right text and minutes, memory
  searches×2 with the right queries).

**What did not — the two design constraints**
- *No-tool prompts can dead-end.* "What is the capital of France?"
  attempted a call, found no suitable tool, and produced **no answer
  at all** (empty results). A fast path must treat needle as a
  router with a mandatory escalate-on-no-call rule, never as the
  final answerer.
- *Session state leaks across commands.* "Tell me a one-line joke"
  re-ran the previous turn's memory search and returned its stale
  result. The agent session is stateful by default; a command fast
  path must use a fresh/stateless session per command.
- Overall routing score 6/8 with those two failures; the model's
  self-reported confidence was 0.36–0.66 (mediocre, and lowest on
  the question it reasoned about worst).

**Cost measurements, honestly framed**
- Peak RSS **129.8MB** for the Python-package form on this machine —
  4.6× the card's ~28MB, which is the native on-device engine
  figure, not the pip package under CPython. Still small in
  absolute terms, but the 28MB number must not be quoted for the
  Python form.
- Latency **0.9–7.0s per command** on this shared sandbox CPU
  (prefill 17–57 tok/s, decode 26–46 tok/s). That is *slower* than
  a free-tier cloud round trip — the fast path is only fast on its
  target device class (phone/laptop silicon), and pointless on the
  fleet's VMs even if RAM allowed.
- Download fragility: the first construction attempt stalled for
  ~4.5 minutes on repeated HuggingFace HEAD timeouts through this
  sandbox's egress proxy before a retry succeeded (the same URL
  answered curl in 0.4s, and a standalone hf_hub_download in 2.5s).
  On the owner's own network this is an ordinary one-time download;
  recorded here because "fully offline" is true only *after* it.

**Pilot verdict:** the card's *adapt* stands. Needle is a credible
on-device router for a small fixed command set on the owner's phone
or laptop. It is not a server component, not a chat model (the card
says so itself), and not a fast path until the two constraints above
are engineered around.

## 6. Fast-path integration spec (spec only — no integration built)

Where it fits: **inside the owner's phone/laptop client**, beside
the LAP-001 / PHONE-001 control paths — not inside Inference.

1. The client embeds cactus-compute (Needle) with a small, fixed
   tool registry mirroring FRIDAY's device-safe commands
   (reminder, memory search, weather, device actions already gated
   by the phone/laptop safety rules).
2. Per command: a **fresh stateless session** (pilot constraint 2).
   Needle returns either structured tool calls + confidence, or no
   call.
3. **Escalate-on-no-call** (pilot constraint 1): a turn with no
   routed call goes to the FRIDAY gateway exactly as today. Do NOT
   gate on the model's confidence: in the pilot, correct routings
   scored 0.36–0.66 while the dead-end failure scored 0.60 —
   confidence does not separate success from failure in this
   sample. The no-call rule is the gate. Needle never fabricates a
   final answer for anything it did not route.
4. Tool results are executed by the client's existing executors;
   needle itself touches nothing.
5. Admission gate before this ships to the owner's device: re-run
   the pilot prompt set (extended with the two failure prompts as
   regression cases) on the actual device, plus a 20-command
   FRIDAY-flavoured set, requiring ≥95% correct routing and zero
   dead-end turns (every no-call escalated). Same discipline as
   IG-INF-03's serve-check: measured on the target, or not claimed.

Out of scope here, deliberately: any server-side deployment, any
Ollama installation on the fleet, Strata, Kaggle.
