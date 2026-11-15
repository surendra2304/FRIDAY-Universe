# Owner-briefing format — before / after (TASK-INT-006)

Same research topic throughout: **solid-state batteries**. The live-brief pair is rendered by `collect_live_brief` with stub search/fetch/synthesis returning a production-shaped envelope (source-attributed draft, 2 findings, 2 domains, quotes verified). The stored-export pair is rendered by `export_text_citations` on the production-shaped fixture used in `tests/test_owner_briefing.py`. The BEFORE code is the pre-change delivery layer reconstructed by reversing this task's edits; the AFTER code is this branch.

## Live brief — BEFORE

```text
Source-attributed model draft — quotations checked, claims not independently verified.

Battery Journal: Finding from Battery Journal: the source reports measured progress on the question.
https://journal-a.org/battery-paper
Supporting source quotation: Solid state batteries have moved from laboratory cells toward pilot production lines this year.

Battery News: Finding from Battery News: the source reports measured progress on the question.
https://news-b.com/battery-story
Supporting source quotation: Independent testing shows solid state batteries retaining strong cycle life in recent trials.
```

## Live brief — AFTER

```text
Finding from Battery Journal: the source reports measured progress on the question.

Confidence: Moderate — Source-attributed draft: every quotation was verified verbatim against its source (2 source(s), 2 domains). Claims are attributed, not independently fact-checked — that is why this caps at Moderate.

Battery Journal: Finding from Battery Journal: the source reports measured progress on the question.
https://journal-a.org/battery-paper
Supporting source quotation: Solid state batteries have moved from laboratory cells toward pilot production lines this year.

Battery News: Finding from Battery News: the source reports measured progress on the question.
https://news-b.com/battery-story
Supporting source quotation: Independent testing shows solid state batteries retaining strong cycle life in recent trials.

What would change this conclusion:
- The cited sources agree as retrieved. A contradicting report from an independent outlet — or a correction from any cited source — would reopen the headline.
```

## Stored export — BEFORE

```text
### Key Findings with Citations

1. Sodium battery energy density reached 160 Wh/kg in 2025. ([C:claim-7890]) *(Confidence: 0.95)*
2. Solid state packs entered pilot production this year. ([C:claim-7891]) *(Confidence: 0.9)*

### Sources & Evidence References
- [Battery Research Journal](https://example.com/paper)
- [Cell Weekly](https://cellweekly.net/pilot)
```

## Stored export — AFTER

```text
Sodium battery energy density reached 160 Wh/kg in 2025.

Confidence: Moderate — 2 of 2 finding(s) are backed by verified claims across 2 domains. Citations are machine-checked for integrity; the underlying facts are not independently verified — that is why this caps at Moderate. Mean claim confidence 0.93.

### Key Findings with Citations

1. Sodium battery energy density reached 160 Wh/kg in 2025. ([C:claim-7890]) *(Confidence: 0.95)*
2. Solid state packs entered pilot production this year. ([C:claim-7891]) *(Confidence: 0.9)*

### What Would Change This Conclusion
- The cited sources agree as retrieved. A contradicting report from an independent outlet — or a correction from any cited source — would reopen the headline.

### Sources & Evidence References
- [Battery Research Journal](https://example.com/paper)
- [Cell Weekly](https://cellweekly.net/pilot)
```
