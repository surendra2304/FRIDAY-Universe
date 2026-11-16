#!/usr/bin/env python3
"""Generate IntelX/intelx/registries/scouted_repos.json from the spec cards.

The registry is generated, never hand-edited (TASK-IG-INT-06; wave-2
incorporation X-06/X-08). Source of truth: the verified spec cards in
~/workspace/ig-references/repos/ plus the card tables in its INDEX.md
(INDEX order is the registry order).

Usage:
    python3 scripts/generate_scouted_repos.py [--cards-dir PATH] [--out PATH]

Parsing rules (each one pinned by the wave-1 audit — the generator
reproduces the 32 hand-audited wave-1 entries exactly):

  * Fields come from the card's bullet lines (Repo / What it does /
    License / Primary language / FRIDAY agent / Source video(s) / Fit).
    Hosted-service cards (e.g. bytez) carry a Service line instead of
    Repo; their registry identity is the GitHub docs/SDK repo named in
    the card, exactly as INDEX.md records it.
  * friday_agents: the card's FRIDAY-agent line with parenthetical
    annotations stripped first (they can contain '/' and ';'), split
    on '/' and ';', 'also ' prefixes dropped; a token is kept iff it
    is a canonical agent name or a single word (the wave-1 registry
    keeps 'Voice'); multi-word descriptors ('FRIDAY tooling',
    'science majority') are not agent names and are dropped. The
    verbatim line is preserved in friday_agent_raw. The
    'NONE (owner utility)' marker is kept whole.
  * fit / fit_rationale come from the card's Fit line; the header's
    fit_counts are computed from the cards, never copied from prose
    summaries (INDEX.md's wave-1 roll-up sentence transposes its own
    table — see the scouted_repos module docstring).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FIELD_RE = {
    "repo": re.compile(r"^- \*\*Repo:\*\*\s*(\S+)", re.M),
    "what": re.compile(r"^- \*\*What it does:\*\*\s*(.+)$", re.M),
    "license": re.compile(r"^- \*\*License:\*\*\s*(.+)$", re.M),
    "language": re.compile(r"^- \*\*Primary language:\*\*\s*(.+)$", re.M),
    "agent": re.compile(r"^- \*\*FRIDAY agent:\*\*\s*(.+)$", re.M),
    "sources": re.compile(r"^- \*\*Source video\(s\):\*\*\s*(.+)$", re.M),
    "fit": re.compile(r"^- \*\*Fit:\*\*\s*\*\*([a-z-]+)\*\*\s*—\s*(.+)$", re.M),
}
CODE_RE = re.compile(r"(?:^|[\s,])([A-Za-z0-9_-]{11})(?=\s*\()")
INDEX_ROW_RE = re.compile(
    r"^\| \[([^\]]+\.md)\]\([^)]+\) \| ([^|]+) \| ([^|]+) \| ([a-z-]+) \|", re.M
)

CANONICAL_AGENTS = {
    "FRIDAY", "Inference", "Memora", "Stratex", "Futuris", "IntelX",
    "Forge", "Sentinel", "Cortex", "VyralX",
    "Laptop-Phone-control", "Website-UI",
}

GENERATED_FROM = (
    "~/workspace/ig-references/repos/ spec cards + INDEX.md "
    "(102 verified cards: wave 1 verified 2026-11-15; waves 2 + 2b verified "
    "2026-11-16) via IntelX/scripts/generate_scouted_repos.py"
)


def split_agents(raw: str) -> list[str]:
    """Derive the canonical agent list from a card's FRIDAY-agent line."""
    if raw.strip().upper().startswith("NONE"):
        return [raw.strip()]
    cleaned = re.sub(r"\([^)]*\)", "", raw)
    agents: list[str] = []
    for chunk in re.split(r"[;/]", cleaned):
        part = re.sub(r"^also\s+", "", chunk.strip()).strip()
        if not part:
            continue
        if (part in CANONICAL_AGENTS or " " not in part) and part not in agents:
            agents.append(part)
    return agents


def parse_card(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    name = re.search(r"^# (.+)$", text, re.M).group(1).strip()
    got: dict = {}
    for key, rx in FIELD_RE.items():
        m = rx.search(text)
        if not m:
            if key == "repo":
                gh = re.search(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text)
                if gh:
                    got[key] = gh.group(0)
                    continue
            raise ValueError(f"{path.name}: missing field {key}")
        got[key] = m.group(1).strip() if key != "fit" else m
    repo_url = got["repo"].rstrip("/")
    fit_m = got["fit"]
    return {
        "card": path.name,
        "name": name,
        "repo": repo_url.removeprefix("https://github.com/"),
        "repo_url": repo_url,
        "what_it_does": got["what"],
        "license": got["license"],
        "language": got["language"],
        "friday_agents": split_agents(got["agent"]),
        "source_videos": CODE_RE.findall(got["sources"]),
        "fit": fit_m.group(1),
        "fit_rationale": fit_m.group(2).strip(),
        "friday_agent_raw": got["agent"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cards-dir",
        default=str(Path.home() / "workspace/ig-references/repos"),
        help="Directory holding the spec cards + INDEX.md",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "intelx/registries/scouted_repos.json"),
        help="Registry JSON to write",
    )
    args = parser.parse_args()

    cards_dir = Path(args.cards_dir)
    index = (cards_dir / "INDEX.md").read_text(encoding="utf-8")
    card_names = [m.group(1) for m in INDEX_ROW_RE.finditer(index)]
    entries = [parse_card(cards_dir / name) for name in card_names]

    fit_counts: dict[str, int] = {}
    for entry in entries:
        fit_counts[entry["fit"]] = fit_counts.get(entry["fit"], 0) + 1

    payload = {
        "schema": "intelx.scouted_repos/v1",
        "generated_from": GENERATED_FROM,
        "count": len(entries),
        "fit_counts": fit_counts,
        "entries": entries,
    }
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(entries)} entries, fit_counts={fit_counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
