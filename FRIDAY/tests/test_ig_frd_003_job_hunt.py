"""TASK-IG-FRD-003 — job-hunt workflow tests (hermetic: fake fetcher)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from friday.workflows.job_hunt import (
    build_prep_plan,
    draft_outreach,
    extract_listings,
    extract_listings_from_greenhouse_json,
    greenhouse_api_url,
    load_profile,
    rank_listings,
    run_scan,
    save_draft,
    score_listing,
)

PROFILE = {
    "name": "Surendra",
    "skills": ["python", "fastapi", "docker"],
    "target_titles": ["software engineer", "backend engineer"],
    "locations": ["remote", "hyderabad"],
    "remote_ok": True,
    "exclude_keywords": ["unpaid"],
    "summary": "Backend engineer building AI systems.",
    "career_pages": ["https://example.com/careers"],
}

PAGE = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"JobPosting",
 "title":"Senior Software Engineer",
 "description":"We need python and fastapi experience. Docker a plus.",
 "datePosted":"2026-11-10",
 "url":"https://example.com/jobs/1",
 "hiringOrganization":{"@type":"Organization","name":"Acme"},
 "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Remote","addressCountry":"IN"}},
 "jobLocationType":"TELECOMMUTE"}
</script>
<script type="application/ld+json">
{"@type":"JobPosting","title":"Unpaid Intern","description":"python role, unpaid internship",
 "datePosted":"2026-11-14","url":"https://example.com/jobs/2",
 "hiringOrganization":{"name":"Beta"},"jobLocation":{"address":{"addressLocality":"Mumbai"}}}
</script>
</head><body>careers</body></html>
"""

EMPTY_PAGE = "<html><body>No structured postings here.</body></html>"

# Shape of the live Greenhouse Job Board API single-job response, from the
# checkpoint-1 probe (GitLab 8623389002, crawled 2026-11-28): content is
# double-entity-encoded HTML.
GREENHOUSE_JOB = {
    "id": 8623389002,
    "title": "Site Reliability Engineer, Infrastructure Platforms — AMER (Intermediate to Senior Staff)",
    "company_name": "GitLab",
    "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/8623389002",
    "location": {"name": "Remote, Canada; Remote, US"},
    "content": "&amp;lt;p&amp;gt;We need python and fastapi experience. Docker a plus.&amp;lt;/p&amp;gt;",
    "first_published": "2026-07-10T22:45:49-04:00",
    "updated_at": "2026-11-06T15:25:07-05:00",
}


def test_greenhouse_api_url():
    assert (
        greenhouse_api_url("gitlab", "8623389002")
        == "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs/8623389002"
    )


def test_greenhouse_json_maps_to_listing():
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc).timestamp()
    listings = extract_listings_from_greenhouse_json(
        GREENHOUSE_JOB, "https://job-boards.greenhouse.io/gitlab/jobs/8623389002", now_epoch=now
    )
    assert len(listings) == 1
    first = listings[0]
    assert first["id"] == "gh-8623389002"
    assert first["title"].startswith("Site Reliability Engineer")
    assert first["company"] == "GitLab"
    assert first["url"] == "https://job-boards.greenhouse.io/gitlab/jobs/8623389002"
    assert first["location"] == "Remote, Canada; Remote, US"
    assert first["description"] == "We need python and fastapi experience. Docker a plus."
    assert first["posted_days_ago"] == 9


def test_greenhouse_double_encoded_content_decodes():
    job = dict(GREENHOUSE_JOB, content="&amp;lt;div&amp;gt;Hello &amp;amp; goodbye&amp;lt;/div&amp;gt;")
    (listing,) = extract_listings_from_greenhouse_json(job, "https://job-boards.greenhouse.io/gitlab/jobs/8623389002")
    assert listing["description"] == "Hello & goodbye"
    assert "<" not in listing["description"]


def test_greenhouse_non_job_payload_is_honest_empty():
    url = "https://job-boards.greenhouse.io/gitlab/jobs/1"
    assert extract_listings_from_greenhouse_json({}, url) == []
    assert extract_listings_from_greenhouse_json({"error": "not found"}, url) == []
    assert extract_listings_from_greenhouse_json(None, url) == []


def test_run_scan_greenhouse_url_uses_api(tmp_path):
    fetched: list[str] = []

    def fetcher(url: str) -> str:
        fetched.append(url)
        if "boards-api.greenhouse.io" in url:
            if "9999999999" in url:
                return json.dumps({"error": "not found"})
            return json.dumps(GREENHOUSE_JOB)
        if "down" in url:
            raise ConnectionError("boom")
        return PAGE

    state = tmp_path / "scan.json"
    scan = run_scan(
        PROFILE,
        [
            "https://job-boards.greenhouse.io/gitlab/jobs/8623389002",
            "https://job-boards.greenhouse.io/gitlab/jobs/9999999999",
            "https://example.com/careers",
        ],
        fetcher=fetcher,
        state_path=str(state),
    )
    # The API endpoint was fetched, never the HTML job page.
    assert "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs/8623389002" in fetched
    assert "https://job-boards.greenhouse.io/gitlab/jobs/8623389002" not in fetched
    statuses = {s["url"]: s["status"] for s in scan["sources"]}
    assert statuses["https://job-boards.greenhouse.io/gitlab/jobs/8623389002"] == "ok"
    assert statuses["https://job-boards.greenhouse.io/gitlab/jobs/9999999999"] == "no_postings_found"
    assert statuses["https://example.com/careers"] == "ok"
    gh = [l for l in scan["shortlist"] if l["company"] == "GitLab"]
    assert len(gh) == 1
    assert gh[0]["title"].startswith("Site Reliability Engineer")
    assert json.loads(state.read_text())["total_listings"] == 3  # 1 Greenhouse + 2 LD-JSON


def test_run_scan_greenhouse_api_failure_is_fetch_failed(tmp_path):
    def fetcher(url: str) -> str:
        if "boards-api.greenhouse.io" in url:
            return "<html>not json</html>"
        return PAGE

    scan = run_scan(
        PROFILE,
        ["https://job-boards.greenhouse.io/gitlab/jobs/8623389002"],
        fetcher=fetcher,
        state_path=str(tmp_path / "scan.json"),
    )
    assert scan["sources"][0]["status"] == "fetch_failed"
    assert scan["total_listings"] == 0


def test_extract_listings_from_json_ld():
    # Pin "now" to the fixture's datePosted + 1 day: the recency assertion
    # is about the formula, not the calendar — a wall-clock now would rot
    # this test every 10 days (it failed on the stale 2026-11-10 fixture).
    now = datetime(2026, 11, 11, tzinfo=timezone.utc).timestamp()
    listings = extract_listings(PAGE, "https://example.com/careers", now_epoch=now)
    assert len(listings) == 2
    first = listings[0]
    assert first["title"] == "Senior Software Engineer"
    assert first["company"] == "Acme"
    assert "remote" in first["location"].lower()
    assert first["posted_days_ago"] == 1


def test_extract_empty_page_is_honest_empty():
    assert extract_listings(EMPTY_PAGE, "https://x.example") == []


def test_exclusion_rejects():
    listing = {"title": "Unpaid Intern", "description": "python", "location": "Mumbai"}
    verdict = score_listing(PROFILE, listing)
    assert verdict["rejected"] is True
    assert "exclusion" in verdict["reasons"][0]


def test_scoring_ranks_strong_fit_first():
    good = {
        "title": "Senior Software Engineer",
        "description": "python fastapi docker",
        "location": "Remote",
        "posted_days_ago": 1,
        "company": "Acme",
        "url": "https://example.com/1",
    }
    weak = {
        "title": "Sales Manager",
        "description": "crm targets",
        "location": "Delhi",
        "posted_days_ago": 20,
        "company": "Gamma",
        "url": "https://example.com/2",
    }
    ranked = rank_listings(PROFILE, [weak, good])
    assert ranked[0]["company"] == "Acme"
    assert ranked[0]["match"]["score"] > ranked[1]["match"]["score"]
    assert set(ranked[0]["match"]["matched_skills"]) == {"python", "fastapi", "docker"}


def test_overlooked_flag_needs_age_and_score():
    old_strong = {
        "title": "Backend Engineer",
        "description": "python fastapi docker",
        "location": "Remote",
        "posted_days_ago": 6,
        "company": "Delta",
        "url": "https://example.com/3",
    }
    verdict = score_listing(PROFILE, old_strong)
    assert verdict["overlooked"] is True
    fresh = dict(old_strong, posted_days_ago=0)
    assert score_listing(PROFILE, fresh)["overlooked"] is False


def test_run_scan_records_source_failures(tmp_path):
    def fetcher(url: str) -> str:
        if "empty" in url:
            return EMPTY_PAGE
        if "down" in url:
            raise ConnectionError("boom")
        return PAGE

    state = tmp_path / "scan.json"
    scan = run_scan(
        PROFILE,
        ["https://example.com/careers", "https://empty.example", "https://down.example"],
        fetcher=fetcher,
        state_path=str(state),
    )
    statuses = {s["url"]: s["status"] for s in scan["sources"]}
    assert statuses["https://example.com/careers"] == "ok"
    assert statuses["https://empty.example"] == "no_postings_found"
    assert statuses["https://down.example"] == "fetch_failed"
    # The unpaid listing was excluded by the profile, so shortlist has 1.
    assert len(scan["shortlist"]) == 1
    assert json.loads(state.read_text())["total_listings"] == 2


def test_prep_plan_uses_missing_skills():
    listing = {
        "title": "Backend Engineer",
        "company": "Acme",
        "description": "python only",
        "location": "Remote",
        "posted_days_ago": 2,
        "url": "https://example.com/1",
    }
    listing["match"] = score_listing(PROFILE, listing)
    plan = build_prep_plan(PROFILE, listing)
    assert "30-day prep plan" in plan
    assert "fastapi" in plan  # a missing skill drives Week 1


def test_outreach_is_a_labelled_draft():
    listing = {
        "title": "Backend Engineer",
        "company": "Acme",
        "description": "python fastapi",
        "location": "Remote",
        "posted_days_ago": 2,
        "url": "https://example.com/1",
    }
    listing["match"] = score_listing(PROFILE, listing)
    draft = draft_outreach(PROFILE, listing)
    assert "DRAFT" in draft
    assert "does not send" in draft


def test_save_draft_writes_file(tmp_path):
    listing = {"company": "Acme Corp", "id": "job-1"}
    path = save_draft("prep", listing, "hello", drafts_dir=str(tmp_path))
    with open(path) as f:
        assert f.read() == "hello"
    assert "acme-corp" in path


def test_load_profile_missing_is_none(tmp_path):
    assert load_profile(str(tmp_path / "nope.json")) is None


def test_module_has_no_send_or_apply_path():
    # The human gate is structural: no function in the module may send
    # email/outreach or submit an application.
    import friday.workflows.job_hunt as jh

    names = [n for n in dir(jh) if not n.startswith("_")]
    for forbidden in ("send", "apply", "submit", "post_application"):
        assert not any(forbidden in n.lower() for n in names), names
