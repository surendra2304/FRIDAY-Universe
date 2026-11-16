# PR review supplement — Open Code Review (TASK-IG2-FRG-03)

Forge's PR-review tooling gains an optional first pass from Alibaba's
[open-code-review](https://github.com/alibaba/open-code-review)
(Apache-2.0), integrated in `forge_upgrade/ocr_review.py`.

## Standing rules

- **Supplement, never a gate.** OCR's recall is deliberately low, and
  its headline precision/F1 benchmark (AACR-Bench) is the vendor's own
  and not independently replicated. Its findings are attached to the
  existing review; the merge verdict comes from the existing
  independent review exactly as before. `supplement_review()` returns
  the gate verdict unchanged by construction.
- **Delegation Mode by default.** The host coding agent (the crew
  session running the review) supplies the model; OCR supplies
  deterministic file selection and its built-in ruleset (NPE,
  thread-safety, XSS, SQL injection, …). No separate API key, no added
  cost. A direct-provider run is possible but not the default.
- **On-demand CLI, no service.** Nothing resident is installed on the
  fleet servers; the pass runs where the review runs.

## Install (review machine / CI)

```bash
npm install -g @alibaba-group/open-code-review   # provides the `ocr` CLI, needs Git >= 2.41
```

## Use

```python
from forge_upgrade.ocr_review import run_ocr_review, supplement_review

ocr = run_ocr_review(changed_files, base="main")   # delegation mode
combined = supplement_review(existing_verdict, ocr)
combined.gate_verdict      # == existing_verdict, always
combined.ocr_findings      # extra line-level findings, may be empty
```

If `ocr` is not installed the pass reports `unavailable` and the
existing review proceeds untouched — absence of the tool must never
block or fabricate a review.

Source reel: https://www.instagram.com/reel/DeihJQuCpdp/
