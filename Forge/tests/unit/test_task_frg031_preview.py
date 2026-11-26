"""TASK-FRG-031: live preview of generated web output, served by the real app.

Forge verified generated static output with checkers but never served a
generated site for the owner to look at before delivery
(Forge/docs/IG_EVALUATION_NOTES.md section 5). The preview routes in
app/api/tasks.py serve the task workspace's project/ directory
read-only. These tests boot the assembled app (create_app(), the
TASK-API-001 mounted-app pattern) against a real on-disk workspace
holding a small generated web build, and prove: the entry page and its
assets serve live with the right content types, the verification-report
header tracks the build's verification state, and nothing outside
project/ is reachable.
"""

from fastapi.testclient import TestClient

from app.api import tasks as tasks_module
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.main import create_app

TASK_ID = "task_frg031_preview"
INDEX_HTML = (
    "<!doctype html><html><head>"
    '<link rel="stylesheet" href="style.css">'
    "</head><body><h1>FRG-031 preview build</h1>"
    '<script src="app.js"></script></body></html>'
)


def _client_with_web_build(tmp_path, monkeypatch, *, verified: bool):
    """Boot create_app() over a temp workspace holding a web build."""
    settings = Settings()
    settings.base_dir = tmp_path
    wm = WorkspaceManager(settings=settings)
    paths = wm.create_workspace(TASK_ID)
    (paths.project / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (paths.project / "style.css").write_text("h1 { color: teal; }", encoding="utf-8")
    (paths.project / "app.js").write_text("console.log('frg031');", encoding="utf-8")
    if verified:
        (paths.artifacts / "verification_report.json").write_text(
            '{"passed": true}', encoding="utf-8"
        )
    monkeypatch.setattr(tasks_module, "workspace_manager", wm)
    return TestClient(create_app())


def test_preview_serves_entry_page_live(tmp_path, monkeypatch):
    """GET /preview returns the build's index.html as HTML, uncached."""
    client = _client_with_web_build(tmp_path, monkeypatch, verified=True)

    response = client.get(f"/api/tasks/{TASK_ID}/preview")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "FRG-031 preview build" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-forge-verification-report"] == "present"


def test_preview_serves_assets_with_content_types(tmp_path, monkeypatch):
    """Sibling assets of the generated site serve from the same tree."""
    client = _client_with_web_build(tmp_path, monkeypatch, verified=True)

    css = client.get(f"/api/tasks/{TASK_ID}/preview/style.css")
    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert "teal" in css.text

    js = client.get(f"/api/tasks/{TASK_ID}/preview/app.js")
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]
    assert "frg031" in js.text


def test_preview_marks_unverified_output(tmp_path, monkeypatch):
    """Without a verification report the header says so, loudly."""
    client = _client_with_web_build(tmp_path, monkeypatch, verified=False)

    response = client.get(f"/api/tasks/{TASK_ID}/preview")
    assert response.status_code == 200
    assert response.headers["x-forge-verification-report"] == "absent"


def test_preview_404s_without_web_output(tmp_path, monkeypatch):
    """A task with no workspace, or no index page, previews as 404."""
    settings = Settings()
    settings.base_dir = tmp_path
    wm = WorkspaceManager(settings=settings)
    monkeypatch.setattr(tasks_module, "workspace_manager", wm)
    client = TestClient(create_app())

    missing = client.get("/api/tasks/task_no_such_build/preview")
    assert missing.status_code == 404

    wm.create_workspace(TASK_ID)  # workspace exists, but no web output yet
    empty = client.get(f"/api/tasks/{TASK_ID}/preview")
    assert empty.status_code == 404


def test_preview_cannot_escape_project_dir(tmp_path, monkeypatch):
    """Traversal and artifact paths are not reachable through preview."""
    client = _client_with_web_build(tmp_path, monkeypatch, verified=True)

    traversal = client.get(
        f"/api/tasks/{TASK_ID}/preview/%2e%2e%2fartifacts%2fverification_report.json"
    )
    assert traversal.status_code == 404
    assert "passed" not in traversal.text

    absent = client.get(f"/api/tasks/{TASK_ID}/preview/nope.png")
    assert absent.status_code == 404
