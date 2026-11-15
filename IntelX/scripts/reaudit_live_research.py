#!/usr/bin/env python3
"""Re-audit hook for stored live research (TASK-INT-009, INT-005 §6 item 5).

READ-ONLY: this script issues SELECT statements only and never commits.
It loads stored ``live_research_runs`` and re-checks every stored finding
against its cited source AS RETRIEVED NOW — the check whose absence the
TASK-INT-005 fact-check audit exposed when a stored Bruker claim carried
``quotes_verified=true`` for a quote that does not exist on the live cited
page (the synthesis gate had verified it against the fetched snapshot,
not the live page).

Per finding (``intelx.api.grounded_live_research.reaudit_finding``):

* boilerplate (page title / breadcrumb / skip-link) -> NON_CLAIM,
  excluded from the accuracy denominator and labelled as such;
* quote absent from the live page -> UNSUPPORTED (Bruker class);
* quote present but the statement outruns the page (numbers / entities /
  content coverage, via ``statement_support``) -> PARTIAL;
* both legs pass -> VERIFIED, on the quote + coverage legs ONLY —
  independent corroboration and contradiction are not mechanically
  assessed here and are never implied by this report;
* source not retrievable at audit time -> UNVERIFIABLE, never a pass.

The AFTER partition is the stored corpus as the shipped verification
pass would treat it today: grounded = VERIFIED claims, downgraded =
UNSUPPORTED / PARTIAL claims, excluded = NON_CLAIM boilerplate.

Usage:
    python3 scripts/reaudit_live_research.py [--json-out PATH]
        [--limit N] [--db-url URL] [--no-fetch]

With no arguments it uses the configured INTELX database (Oracle in
production). For a local test database set INTELX_ENV=test and pass
``--db-url sqlite+aiosqlite:////path/to.db``. ``--no-fetch`` skips live
retrieval entirely (every non-boilerplate finding is UNVERIFIABLE);
it exists for offline smoke tests, not for accuracy claims.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intelx.api.grounded_live_research import reaudit_finding
from intelx.api.live_research_task import DocumentText
from intelx.db.engine import dispose_engine, get_async_engine
from intelx.db.models import LiveResearchRun

STANDARD_MIN_VERIFIED_SHARE = 0.90


async def _fetch_live_text(client: httpx.AsyncClient, url: str) -> str | None:
    """Retrieve a cited page and extract text with the same rules the
    brief collector used at storage time. Any failure -> None (the
    finding becomes UNVERIFIABLE, never a pass)."""
    try:
        response = await client.get(url)
        if response.status_code != 200:
            return None
        content_type = str(response.headers.get("content-type", "")).lower()
        if not any(t in content_type for t in ("text/html", "text/plain", "text/markdown")):
            return None
        text = response.text
        if "text/html" in content_type:
            parser = DocumentText()
            parser.feed(text)
            text = "".join(parser.parts)
        return text
    except Exception:
        return None


async def run_reaudit(db_url: str | None, limit: int, fetch_live: bool) -> dict[str, Any]:
    engine = get_async_engine(db_url)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        rows = list(
            (
                await session.execute(
                    select(LiveResearchRun)
                    .order_by(LiveResearchRun.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    text_by_url: dict[str, str | None] = {}
    totals = {"findings": 0, "claims": 0, "non_claims": 0, "verified": 0,
              "partial": 0, "unsupported": 0, "unverifiable": 0,
              "single_source_claims": 0}
    run_reports: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=20.0, follow_redirects=True,
        headers={"User-Agent": "intelx-reaudit/1.0 (TASK-INT-009)"},
    ) as client:
        for row in rows:
            payload = row.payload_json or {}
            findings = payload.get("findings") or []
            finding_reports = []
            for finding in findings:
                if not isinstance(finding, dict):
                    continue
                citations = finding.get("citations") or []
                url = ""
                if citations and isinstance(citations[0], dict):
                    url = str(citations[0].get("source_url") or "")
                if fetch_live and url:
                    if url not in text_by_url:
                        text_by_url[url] = await _fetch_live_text(client, url)
                    live_text = text_by_url[url]
                else:
                    live_text = None
                result = reaudit_finding(finding, live_text)
                totals["findings"] += 1
                if result["classification"] == "NON_CLAIM":
                    totals["non_claims"] += 1
                else:
                    totals["claims"] += 1
                    totals[result["verdict"].lower()] += 1
                    if result["single_source"]:
                        totals["single_source_claims"] += 1
                finding_reports.append({
                    "statement": str(finding.get("statement") or "")[:160],
                    "source_url": url,
                    **result,
                })
            run_reports.append({
                "run_id": row.id, "task_id": row.task_id, "status": row.status,
                "stored_quotes_verified": payload.get("quotes_verified"),
                "findings": finding_reports,
            })

    claims = totals["claims"]
    verified_share = (totals["verified"] / claims) if claims else None
    summary = {
        "runs_audited": len(rows),
        "fetch_live": fetch_live,
        "totals": totals,
        "verified_share_of_claims": verified_share,
        "standard": {
            "min_verified_share": STANDARD_MIN_VERIFIED_SHARE,
            "met": bool(verified_share is not None and verified_share >= STANDARD_MIN_VERIFIED_SHARE),
            "scope_note": (
                "Mechanical legs only (verbatim quote on the live page + "
                "statement coverage). Independent corroboration and "
                "contradiction are not assessed by this hook."
            ),
        },
        "after_partition": {
            "grounded": totals["verified"],
            "downgraded": totals["unsupported"] + totals["partial"],
            "excluded_boilerplate": totals["non_claims"],
            "unverifiable": totals["unverifiable"],
        },
        "runs": run_reports,
    }
    await dispose_engine()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", default=None, help="Explicit DB URL (test suite only)")
    parser.add_argument("--json-out", default=None, help="Also write the JSON summary here")
    parser.add_argument("--limit", type=int, default=50, help="Newest N stored runs to audit")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Offline smoke mode: no live retrieval (all claims UNVERIFIABLE)")
    args = parser.parse_args()
    summary = asyncio.run(run_reaudit(args.db_url, args.limit, fetch_live=not args.no_fetch))
    totals = summary["totals"]
    print(f"runs audited: {summary['runs_audited']} (fetch_live={summary['fetch_live']})")
    print(f"findings: {totals['findings']} | claims: {totals['claims']} "
          f"| non-claim boilerplate: {totals['non_claims']}")
    print(f"VERIFIED {totals['verified']} | PARTIAL {totals['partial']} "
          f"| UNSUPPORTED {totals['unsupported']} | UNVERIFIABLE {totals['unverifiable']}")
    share = summary["verified_share_of_claims"]
    print(f"verified share of claims: {share if share is None else round(share, 4)} "
          f"(standard >= {STANDARD_MIN_VERIFIED_SHARE}: {'MET' if summary['standard']['met'] else 'NOT MET'})")
    print(f"after partition: {summary['after_partition']}")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
        print(f"JSON summary written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
