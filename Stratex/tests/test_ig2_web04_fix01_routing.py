"""TASK-IG2-WEB-04-FIX-01 — tests for the Stratex dashboard routing fix.

The dashboard is served under /stratex/ in production (Caddy strips the
prefix) and at / standalone, so its asset and API references must be
relative to the mount, not root-relative: root /static/* 404s and root
/api/* serves the FRIDAY SPA (TASK-WEB-006 live verification 2026-11-25,
0 of 4 verified).

These tests pin the fix without the fleet: they serve the REAL
Stratex/static files and the REAL sector-heatmap blueprint from a test
Flask app that mirrors dashboard.py's serving config (Flask
static_folder='static', index route, blueprint registration), behind a
WSGI middleware that strips a /stratex prefix exactly like Caddy
handle_path /stratex* does, and assert every URL the dashboard
references answers 200 under BOTH mounts. dashboard.py itself is not
imported here (heavy trading deps); the route existence of the eight
app.js API endpoints is pinned against dashboard.py source instead.
Network-free: the heatmap payload is stubbed; Stooq is never touched.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from flask import Flask, send_from_directory

import api.sector_heatmap as heatmap_mod
from api.sector_heatmap import sector_heatmap_bp

STRATEX_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = STRATEX_ROOT / "static"
REPO_ROOT = STRATEX_ROOT.parent

# (JS file, API path the dashboard fetches, dashboard.py route that serves it)
APP_JS_ENDPOINTS = [
    ("app.js", "/api/status", "@app.route('/api/status')"),
    ("app.js", "/api/engine-health", "@app.route('/api/engine-health')"),
    ("app.js", "/api/paper/forward-status", "@app.route('/api/paper/forward-status')"),
    ("app.js", "/api/positions", "@app.route('/api/positions')"),
    ("app.js", "/api/telemetry/trades", "@app.route('/api/telemetry/trades')"),
    ("app.js", "/api/equity-history", "@app.route('/api/equity-history')"),
    ("app.js", "/api/markets", "@app.route('/api/markets')"),
    ("app.js", "/api/telemetry/signals", "@app.route('/api/telemetry/signals')"),
    ("heatmap.js", "/api/v1/market/sector-heatmap", "sector_heatmap_bp"),
    ("quantum.js", "/api/quantum/advisory", "quantum_bp"),
]

HTML_ASSETS = [
    "static/style.css",
    "static/app.js",
    "static/heatmap.js",
    "static/command-palette.js",
    "static/layout.js",
]


class PrefixStripMiddleware:
    """Simulate Caddy `handle_path /stratex*`: strip the prefix, like the
    production ingress does before proxying to the Stratex app."""

    def __init__(self, app, prefix="/stratex"):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            environ["SCRIPT_NAME"] = self.prefix
        return self.app(environ, start_response)


STUB_PAYLOAD = {
    "as_of": "2026-11-26T00:00:00+00:00",
    "source": "stooq (free daily quotes)",
    "sectors": [
        {
            "sector": "Technology",
            "change_pct": 1.25,
            "members_available": 4,
            "members_total": 4,
            "members": [{"symbol": "XLK", "change_pct": 1.25}],
        },
        {
            "sector": "Energy",
            "change_pct": None,
            "members_available": 0,
            "members_total": 3,
            "members": [{"symbol": "XLE", "change_pct": None}],
        },
    ],
}


@pytest.fixture()
def client(monkeypatch):
    """Test Flask app mirroring dashboard.py serving, behind the strip."""
    monkeypatch.setattr(heatmap_mod, "build_heatmap", lambda: STUB_PAYLOAD)
    heatmap_mod._cache["payload"] = None
    heatmap_mod._cache["fetched_at"] = 0.0
    app = Flask(__name__, static_folder=str(STATIC_DIR))
    app.register_blueprint(sector_heatmap_bp)

    @app.route("/")
    def index():
        return send_from_directory(str(STATIC_DIR), "index.html")

    app.wsgi_app = PrefixStripMiddleware(app.wsgi_app)
    app.config["TESTING"] = True
    return app.test_client()


def _read(rel):
    return (STRATEX_ROOT / rel).read_text(encoding="utf-8")


# --- 1. No root-relative references remain in the dashboard files -----------

def test_index_html_has_no_root_relative_asset_refs():
    html = _read("static/index.html")
    refs = re.findall(r'(?:href|src)\s*=\s*"([^"]+)"', html)
    assert refs, "index.html has no href/src references at all"
    for ref in refs:
        assert not ref.startswith("/"), f"root-relative asset ref remains: {ref}"
        assert not ref.startswith("//"), f"protocol-relative asset ref: {ref}"


def test_quantum_html_has_no_root_relative_asset_refs():
    html = _read("static/quantum.html")
    refs = re.findall(r'(?:href|src)\s*=\s*"([^"]+)"', html)
    # Only same-document refs (relative paths) and the Google Fonts URL.
    for ref in refs:
        assert not ref.startswith("/"), f"root-relative asset ref remains: {ref}"


def test_js_files_have_no_root_relative_fetches():
    for name in ("app.js", "heatmap.js", "quantum.js"):
        text = _read(f"static/{name}")
        assert "dashboardMountBase" in text, f"{name}: mount-base helper missing"
        assert "API_BASE + '/api/" in text, f"{name}: no mount-aware API fetch"
        bare = re.findall(r"fetch\(\s*['\"]/api/", text)
        assert not bare, f"{name}: root-relative fetch remains: {bare}"
        bare_static = re.findall(r"['\"]/static/", text)
        assert not bare_static, f"{name}: root-relative /static/ literal remains"


# --- 2. The mount-base derivation returns the right prefix ------------------

def _extract_mount_base(js_text):
    start = js_text.find("function dashboardMountBase()")
    assert start >= 0, "dashboardMountBase not found"
    depth = 0
    for i in range(start, len(js_text)):
        if js_text[i] == "{":
            depth += 1
        elif js_text[i] == "}":
            depth -= 1
            if depth == 0:
                return js_text[start:i + 1]
    raise AssertionError("unbalanced braces in dashboardMountBase")


@pytest.mark.parametrize(
    ("pathname", "expected"),
    [
        ("/stratex/", "/stratex"),
        ("/stratex", "/stratex"),
        ("/", ""),
        ("", ""),
        ("/index.html", ""),
        ("/stratex/index.html", "/stratex"),
        ("/stratex//", "/stratex"),
    ],
)
@pytest.mark.parametrize("js_file", ["app.js", "heatmap.js", "quantum.js"])
def test_mount_base_derivation(js_file, pathname, expected):
    if shutil.which("node") is None:
        pytest.skip("node not available to execute the dashboard JS")
    fn_src = _extract_mount_base(_read(f"static/{js_file}"))
    script = (
        "var window = {location: {pathname: %s}};\n%s\n"
        "process.stdout.write(dashboardMountBase());"
        % (json.dumps(pathname), fn_src)
    )
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected, (
        f"{js_file} pathname {pathname!r}: got {result.stdout!r}, want {expected!r}"
    )


# --- 3. The dashboard serves under BOTH mounts -------------------------------

def test_index_serves_at_root_and_under_stratex(client):
    for path in ("/", "/stratex/"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert b"STRATEX" in resp.data
        assert b'static/style.css' in resp.data


def test_static_assets_serve_at_root_and_under_stratex(client):
    for asset in HTML_ASSETS + ["static/quantum.js", "static/ui-compat.js"]:
        for prefix in ("", "/stratex"):
            resp = client.get(f"{prefix}/{asset}")
            assert resp.status_code == 200, f"{prefix}/{asset}"
    resp = client.get("/static/style.css")
    assert b"{" in resp.data  # real stylesheet, not an error page


def test_sector_heatmap_serves_at_root_and_under_stratex(client):
    for path in ("/api/v1/market/sector-heatmap", "/stratex/api/v1/market/sector-heatmap"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        payload = resp.get_json()
        assert payload["source"].startswith("stooq")
        assert payload["sectors"][0]["sector"] == "Technology"
        assert payload["sectors"][0]["change_pct"] == 1.25
        # Unpriced sectors stay honestly unavailable — never invented.
        energy = next(s for s in payload["sectors"] if s["sector"] == "Energy")
        assert energy["change_pct"] is None
        assert energy["members_available"] == 0


def test_every_dashboard_referenced_url_answers_200(client):
    """Resolve every URL the dashboard pages reference, under both mounts."""
    html = _read("static/index.html")
    refs = re.findall(r'(?:href|src)\s*=\s*"([^"#]+)(?:#[^"]*)?"', html)
    for ref in refs:
        assert not ref.startswith(("http", "/")), f"unexpected ref: {ref}"
        for prefix in ("", "/stratex"):
            resp = client.get(f"{prefix}/{ref.split('?')[0]}")
            assert resp.status_code == 200, f"{prefix}/{ref}"


# --- 4. Every API path the JS fetches has a server route ----------------------

def test_app_js_endpoints_exist_in_dashboard_py():
    dashboard = _read("dashboard.py")
    for js_file, api_path, route_marker in APP_JS_ENDPOINTS:
        js = _read(f"static/{js_file}")
        assert f"API_BASE + '{api_path}" in js, f"{js_file} does not fetch {api_path}"
        if route_marker == "sector_heatmap_bp":
            assert "sector_heatmap" in dashboard, "heatmap blueprint not in dashboard.py"
        elif route_marker == "quantum_bp":
            assert "register_blueprint(quantum_bp, url_prefix='/api/quantum')" in dashboard
        else:
            assert route_marker in dashboard, f"no {route_marker} route in dashboard.py"


# --- 5. The Caddyfile maps the root paths without stripping -------------------

def test_caddyfile_maps_root_static_and_heatmap_without_stripping():
    caddy = (REPO_ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "handle /static/*" in caddy, "root /static/* handle missing"
    assert "handle /api/v1/market/sector-heatmap" in caddy, "heatmap handle missing"
    assert "handle_path /static" not in caddy, (
        "handle_path would strip /static and break Flask's static route"
    )
    static_block = caddy[caddy.index("handle /static/*"):]
    assert "127.0.0.1:18003" in static_block.split("}")[0], "static handle must proxy to Stratex"
    heatmap_block = caddy[caddy.index("handle /api/v1/market/sector-heatmap"):]
    assert "127.0.0.1:18003" in heatmap_block.split("}")[0], "heatmap handle must proxy to Stratex"
    # Both handles must sit before the final catch-all `handle` to FRIDAY.
    catch_all = caddy.rindex("    handle {\n        reverse_proxy 127.0.0.1:10000")
    assert caddy.index("handle /static/*") < catch_all
    assert caddy.index("handle /api/v1/market/sector-heatmap") < catch_all
