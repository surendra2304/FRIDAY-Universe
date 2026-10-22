"""
Regression tests for the silently-dropped-input and fabricated-output defects
found in the 2026-10 audit.

Bug #11  ForgeWebStudio.synthesize_website accepted `requirements` but never
         forwarded them to DomainSynthesizer.analyze_goal, so an explicit
         requirement such as "must be an e-commerce store" could not influence
         the generated architecture at all. `forge build --req` was silently
         dropped for web-studio goals.

Bug #29  LLMResponseParser.extract_files returned as soon as the XML pass found
         anything, so every "### File:" markdown block in a mixed response was
         silently discarded.

Bug #29b The documented "**File:** `path`" header form never matched the header
         regex at all: the closing emphasis after the colon was not consumed.

Bug #14  SecurityReviewerRole.execute_step probed `"response" in locals()` to
         decide whether the model had been consulted.

Bug #16  GitTool.create_pr returned a hardcoded
         https://github.com/mock-repo/pulls/<task_id> URL with status "created"
         without contacting GitHub.
"""

import pytest

from app.agents.parser import LLMResponseParser
from app.execution.git_tool import GitTool
from app.templates.web_studio.domain_synthesizer import DomainSynthesizer
from app.templates.web_studio.generator import ForgeWebStudio

# ---------------------------------------------------------------------------
# Bug #11 -- requirements must reach the classifier
# ---------------------------------------------------------------------------


def test_requirements_influence_the_chosen_domain():
    """A requirement naming a domain must steer the architecture."""
    plain = DomainSynthesizer.analyze_goal("Build a modern site for my startup")
    with_reqs = DomainSynthesizer.analyze_goal(
        "Build a modern site for my startup",
        requirements=["must be an ecommerce store with a shopping cart"],
    )
    assert plain.domain_type != "ecommerce"
    assert with_reqs.domain_type == "ecommerce"


def test_requirements_are_recorded_in_the_generated_readme():
    files = ForgeWebStudio.synthesize_website(
        "Build a modern site for my startup",
        requirements=["must support dark mode", "must include a contact form"],
    )
    readme = files["README.md"]
    assert "Requested Requirements" in readme
    assert "must support dark mode" in readme
    assert "must include a contact form" in readme


def test_synthesize_website_without_requirements_still_works():
    files = ForgeWebStudio.synthesize_website("Build a portfolio site")
    assert {"index.html", "style.css", "app.js", "README.md"} <= set(files)
    assert "Requested Requirements" not in files["README.md"]


# ---------------------------------------------------------------------------
# Bug #29 -- a mixed response must yield every file
# ---------------------------------------------------------------------------


MIXED_RESPONSE = """Here is the implementation.

<file path="src/api.py">
def api():
    return 1
</file>

### File: src/app.py
```python
def app():
    return 2
```

**File:** `src/util.py`
```python
def util():
    return 3
```
"""


def test_mixed_xml_and_markdown_response_yields_all_files():
    files = LLMResponseParser.extract_files(MIXED_RESPONSE)
    paths = {f.relative_path for f in files}
    assert paths == {"src/api.py", "src/app.py", "src/util.py"}, (
        f"markdown blocks were dropped: {sorted(paths)}"
    )
    contents = {f.relative_path: f.content for f in files}
    assert "return 2" in contents["src/app.py"]
    assert "return 3" in contents["src/util.py"]


def test_xml_only_response_still_parses():
    files = LLMResponseParser.extract_files('<file path="a.py">x = 1</file>')
    assert [f.relative_path for f in files] == ["a.py"]


def test_markdown_only_response_still_parses():
    files = LLMResponseParser.extract_files("### File: b.py\n```python\ny = 2\n```")
    assert [f.relative_path for f in files] == ["b.py"]


def test_info_string_response_still_parses():
    files = LLMResponseParser.extract_files("```python:src/c.py\nz = 3\n```")
    assert [f.relative_path for f in files] == ["src/c.py"]


def test_generic_fallback_still_parses():
    files = LLMResponseParser.extract_files("```python\nw = 4\n```", default_filename="main.py")
    assert [f.relative_path for f in files] == ["main.py"]


@pytest.mark.parametrize(
    "header",
    [
        "### File: src/x.py",
        "**File:** `src/x.py`",
        "**File:**`src/x.py`",
        "__File:__ `src/x.py`",
        "File: src/x.py",
        "Target File: src/x.py",
        "#### File: src/x.py",
    ],
)
def test_every_documented_header_form_is_recognized(header: str):
    text = f"{header}\n```python\nvalue = 1\n```"
    files = LLMResponseParser.extract_files(text)
    assert [f.relative_path for f in files] == ["src/x.py"], f"{header!r} was not recognized"


def test_no_duplicate_paths_when_patterns_overlap():
    """The same file expressed in two forms must be emitted once."""
    text = (
        "### File: src/dup.py\n```python\na = 1\n```\n\n"
        "```python:src/dup.py\na = 1\n```\n"
    )
    files = LLMResponseParser.extract_files(text)
    assert [f.relative_path for f in files] == ["src/dup.py"]


# ---------------------------------------------------------------------------
# Bug #14 -- no locals() sentinel
# ---------------------------------------------------------------------------


def test_security_reviewer_no_longer_probes_locals():
    import inspect

    from app.agents import roles

    source = inspect.getsource(roles.SecurityReviewerRole.execute_step)
    assert '"response" in locals()' not in source, (
        "SecurityReviewerRole still probes locals() to decide whether the model ran"
    )
    assert "response = None" in source, "response must be initialised explicitly"


# ---------------------------------------------------------------------------
# Bug #16 -- no fabricated PR URL
# ---------------------------------------------------------------------------


def test_create_pr_does_not_fabricate_a_mock_url(tmp_path, monkeypatch):
    import asyncio

    from app.core.config import Settings
    from app.core.workspace import WorkspaceManager

    s = Settings()
    s.workspaces_dir = tmp_path / "workspaces"
    s.ensure_directories()
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: s)

    tool = GitTool(wm=WorkspaceManager(settings=s))
    result = asyncio.run(
        tool.create_pr(
            "task_no_mock",
            title="t",
            body="b",
            head_branch="feature",
            base_branch="main",
            role="release_engineer",
            authorized=True,
        )
    )
    assert "mock-repo" not in result["pr_url"]
    assert result["status"] != "created"
    assert result["head"] == "feature"
