# Inference Discovery Feed (TASK-INF-041)

The automated discovery feed files new model/tool releases as candidate
records into Inference's candidate-evaluation pipeline. It closes the
gap Inference baseline A2 records as PARTIAL: the evaluation half
exists (`benchmarks/evaluate_candidate.py`, TASK-IG-INF-03); the
automated discovery half was absent.

## What the feed does — and does not do

- **It files.** Each run scans the sources below and writes one JSON
  record per new release into `benchmarks/discovery/`, with source,
  date, claim and provenance.
- **It does not adopt.** A filed record is `status: filed`,
  `evaluation: pending`. Nothing enters the catalogue, the model
  catalogue, or any route until it passes the normal evaluation gate
  (IG-INF-03: serve-check + fixed INF-005 bench). A record becomes a
  candidate spec only when a worker writes
  `benchmarks/candidates/<name>.json` for it and runs the gate.
- **It does not verify free tiers.** The record states what the source
  lists; a free-tier claim is verified by the evaluation, never by
  the feed. (See `LITELLM_AB_EVAL.md` for why a listing is not proof.)

## Sources (v1)

All public, no key, no auth, no account. Free sources only.

| Source | What it lists | How "new" is decided |
|---|---|---|
| OpenRouter catalogue (`https://openrouter.ai/api/v1/models`) | Models with $0 prompt **and** $0 completion pricing — the gateway's own discovery source | `created` timestamp inside the 14-day window |
| Hugging Face models API, curated org watchlist (`deepseek-ai`, `google`, `meta-llama`, `microsoft`, `mistralai`, `NousResearch`, `nvidia`, `Qwen`, `reflection`) | New text models from labs that publish open models | `createdAt` inside the 14-day window |

Two source quirks, both handled in the code and both worth knowing:

- The HF API rejects `sort=created` (400). The feed sorts by
  `lastModified` (top 100 per org — the list is a moving window) and
  filters on `createdAt` client-side.
- The HF public API rate-limits anonymous bursts (429). The feed
  pauses 5 s between source fetches; a 429 still fails that source
  loudly (the run exits 2) rather than silently skipping it. A missed
  org is retried by the next day's run while its items are still
  in-window, so a single failed run loses nothing.

## Filing rule

An item is filed only when **all** of these hold:

1. Its release/creation date is inside the window (default 14 days).
   Historical catalogue entries are not news; the six seed records
   cover the backlog the task names.
2. Its id is not in `state.json` (`seen`) and no record file for it
   already exists on disk — the file is the durable memory if state
   ever goes stale.
3. Its model id is not already a candidate spec in
   `benchmarks/candidates/`.

A second run files nothing new (idempotent). `state.json` is pruned
to 30 days each run, so it stays bounded.

## What is deliberately not filed

Derivative artefacts are skipped and listed in the run output, so the
omission is auditable: speculative-decoding draft models (`-draft`),
export-format repacks (`-onnx`, `-webgpu`), quantised repacks
(`-gguf`, `-awq`, `-gptq`, `-int4`, `-fp4`, `-fp8`, `-bnb`, `-mlx`).
The base model, when it is itself new, is filed separately. The full
marker list is `HF_DERIVATIVE_MARKERS` in `scripts/discovery_feed.py`.

## Record schema (`inference.discovery-record/v1`)

| Field | Meaning |
|---|---|
| `id` | `<source>-<slug>`, e.g. `openrouter-inclusionai-ling-3-2-flash-free` |
| `name`, `kind` | Display name; `model` or `tool` |
| `source`, `source_url` | Where the listing came from |
| `date` | Release/creation date (`YYYY-MM-DD`, month precision, or `null` when the source states none) |
| `discovered_at` | Date the feed filed it |
| `claim` | What the source claims, in the source's own terms |
| `provenance` | How this record came to exist (seed vs automatic, source item) |
| `verification` | What has actually been checked (seeds: live check 2026-11-25; auto: `pending — source listing only`) |
| `route` | Provider / base URL / model id / key env, when known; `{}` for tools and weight-only releases |
| `status` / `evaluation` | `filed` / `pending — IG-INF-03 gate; not admitted, not routed` |

## Seed records (the six named releases)

Filed by hand for TASK-INF-041 from inference package I-04 to I-09
(item Deo925ayzJ9, a six-release countdown). Each seed's `verification`
field records the live check run on 2026-11-25.

| Seed | Date | Verification (2026-11-25) |
|---|---|---|
| SANA-WM (NVIDIA Sana world model) | 2026-05 | Repo `NVlabs/Sana` public, Apache-2.0, pushed 2026-11-25. VyralX reject for generation use (H100-class GPU); catalogue record only |
| PentAGI | — | Repo `vxcontrol/pentagi` public, MIT, pushed 2026-11-13. Tool, not a model; reference-only (Sentinel defensive role pattern, TASK-SEN-033) |
| Reflection AI Beam | 2026-10-05 | Announced 2026-10-05, open weights 2026-10-16 (`reflection/Beam-1.0-501B-A23B`, Apache 2.0). Beta API `$0.70/$2.10` per 1M — paid, no free tier stated |
| Gemini 4 Argon | 2026-10-13 | First-party DeepMind model card + Google blog. Paid-only (`$2/$10` per 1M intro); API model id to re-confirm before evaluation |
| Locally Uncensored | — | Repo `PurpleDoubleD/locally-uncensored` public, AGPL-3.0, pushed 2026-11-24. Desktop tool; reference-only |
| DeepSeek V4.1-Flash | 2026-09-10 | DeepSeek API docs + HF `deepseek-ai/DeepSeek-V4.1-Flash` (MIT weights); update V4.1-Flash-1017 2026-10-17. Paid API, no free tier claimed |

## Schedule

`.github/workflows/inference-discovery-feed.yml` — daily 06:00 UTC
(11:30 IST) plus manual `workflow_dispatch`. Each run executes
`scripts/discovery_feed.py` from `Inference/`; when new records are
filed it commits them (with the updated `state.json`) to a
`discovery-feed/YYYY-MM-DD` branch and opens a PR for review. Nothing
lands on main without a PR and a merge — the feed files, it does not
adopt, and it does not self-merge. A run with a failed source exits 2
and the workflow fails loudly; a run with no new releases exits 0
and opens nothing.

## Proof run (2026-11-25, live, this machine)

Three runs against the live sources, same entry point the workflow
calls:

1. **Run 1** — scanned 326, filed 2: `openrouter-inclusionai-ling-3-2-flash-free`
   (InclusionAI Ling 3.2 Flash, created 2026-11-13) and
   `huggingface-microsoft-aion-1-0-instruct-2-3b` (Microsoft Aion 1.0
   Instruct 2.3B, created 2026-11-18, 5,476 downloads). 3 HF orgs
   429'd (burst pacing not yet in place).
2. **Run 2** — scanned 377, filed 0 (idempotent), 2 orgs 429'd.
   Pacing raised 2 s → 5 s between source fetches.
3. **Run 3** — scanned 455, filed 0, exit 0, all 9 orgs + OpenRouter
   clean. The two auto-filed records above are the first
   automatically-filed new candidates.

Also observed in run 3: 87 derivative artefacts skipped (FP8/GPTQ/
GGUF repacks, draft models, ONNX exports), including
`reflection/Beam-1.0-501B-A23B-FP8` — the quantised repack of the
seeded Beam release, correctly not filed as a new model.

## Running it by hand

```sh
cd Inference
python3 scripts/discovery_feed.py            # scan + file
python3 scripts/discovery_feed.py --dry-run  # report only, write nothing
python3 scripts/discovery_feed.py --bootstrap  # seed state, file nothing
python3 -m pytest tests/test_discovery_feed.py -q   # 15 tests, no network
```

## Limits (known, accepted)

- HF is sampled, not censused: top 100 by `lastModified` per org. A
  release created in-window but pushed out of the top 100 by 100
  newer modifications would be missed until a later run — the window
  is 14 days, so it has 13 more daily chances.
- The feed sees listings, not releases: a model listed without a
  creation date is never filed (no date, no window decision).
- The feed cannot see sources behind auth (private leaderboards,
  waitlist-only announcements). Adding a source is a deliberate
  change to `scripts/discovery_feed.py`, not a config tweak.
