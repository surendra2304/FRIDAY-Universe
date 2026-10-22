"""
Unit tests for ForgeWebStudio 3D Website and Web App Engine.
Validates Lovable/Bolt/Durable standards, 3D WebGL graphics, zero placeholders,
and aesthetic verification.
"""

from pathlib import Path

import pytest

from app.agents.language_builders import Web3DBuilder
from app.templates.web_studio.domain_synthesizer import DomainSynthesizer
from app.templates.web_studio.generator import ForgeWebStudio
from app.templates.web_studio.three_d_engine import Web3DEngine
from app.verification.quality_analyzer import CodeQualityAnalyzer


def test_domain_synthesizer_classification():
    portfolio_bp = DomainSynthesizer.analyze_goal("Build a personal 3D creative developer portfolio")
    assert portfolio_bp.domain_type == "portfolio"
    assert portfolio_bp.showcase_items
    assert len(portfolio_bp.showcase_items) >= 2

    saas_bp = DomainSynthesizer.analyze_goal("Create a modern AI SaaS analytics platform")
    assert saas_bp.domain_type == "saas"
    assert saas_bp.showcase_items

    ecom_bp = DomainSynthesizer.analyze_goal("Build a luxury minimalist e-commerce fashion store")
    assert ecom_bp.domain_type == "ecommerce"

    dash_bp = DomainSynthesizer.analyze_goal("Build a real-time IoT sensor telemetry dashboard")
    assert dash_bp.domain_type == "dashboard"

    creative_bp = DomainSynthesizer.analyze_goal("Futuristic 3D generative particle visualizer app")
    assert creative_bp.domain_type == "creative"


def test_web_studio_complete_synthesis():
    goal = "Futuristic Cyberpunk 3D Portfolio for Senior Creative Technologist"
    files = ForgeWebStudio.synthesize_website(goal, ["Three.js interactive scene", "Dark mode"])

    assert "index.html" in files
    assert "style.css" in files
    assert "app.js" in files
    assert "README.md" in files

    html = files["index.html"]
    css = files["style.css"]
    js = files["app.js"]

    # 1. HTML Assertions
    assert "<!DOCTYPE html>" in html
    assert "<canvas" in html
    assert 'id="webstudio-3d-canvas"' in html or 'id="forge-3d-canvas"' in html
    assert 'class="bento-grid"' in html
    assert 'id="theme-toggle"' in html
    assert "three.min.js" in html
    assert "fonts.googleapis.com" in html

    # 2. CSS Assertions
    assert ":root" in css
    assert "backdrop-filter" in css
    assert "--glass-blur" in css or "blur(" in css
    assert "--bg-primary" in css or "--bg-base" in css
    assert "--accent-primary" in css or "--primary" in css
    assert ".bento-grid" in css
    assert ".tilt-card" in css

    # 3. JS Assertions
    assert "THREE.Scene" in js or "initThreeJSScene" in js
    assert "addEventListener" in js
    assert "perspectiveTilt" in js or "tilt-card" in js or "rotateX" in js

    # 4. Zero Placeholders Guarantee
    for forbidden in ["lorem ipsum", "project alpha", "project beta", "john doe", "untitled project"]:
        assert forbidden not in html.lower(), f"Forbidden placeholder found in HTML: {forbidden}"
        assert forbidden not in js.lower(), f"Forbidden placeholder found in JS: {forbidden}"


def test_three_d_engine_generation():
    engine_js = Web3DEngine.generate_engine_js()
    assert "THREE.PerspectiveCamera" in engine_js
    assert "renderer.render" in engine_js
    assert "initHighSpeedParticleCanvas" in engine_js or "Particle" in engine_js
    assert "requestAnimationFrame" in engine_js

    tilt_js = Web3DEngine.generate_card_tilt_js()
    assert "tilt-card" in tilt_js
    assert "perspective" in tilt_js or "transform" in tilt_js


def test_web_3d_builder_scaffolding(tmp_path: Path):
    builder = Web3DBuilder()
    manifest = builder.file_manifest("Build a 3D AI startup website")
    assert "index.html" in manifest.files_to_generate
    assert "style.css" in manifest.files_to_generate
    assert "app.js" in manifest.files_to_generate

    created = builder.scaffold_project("Build a 3D AI startup website", tmp_path)
    assert len(created) == 4
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "style.css").exists()
    assert (tmp_path / "app.js").exists()
    assert (tmp_path / "README.md").exists()

    # Verify quality analyzer passes on generated files
    analyzer = CodeQualityAnalyzer(tmp_path)
    aesthetic_check = analyzer.analyze_web_aesthetic_and_interactivity()
    assert aesthetic_check is not None
    assert aesthetic_check.status == "pass"
    assert aesthetic_check.evidence["canvas_detected"] is True
    assert aesthetic_check.evidence["glassmorphic_tokens"] is True
    assert len(aesthetic_check.evidence["failures"]) == 0


def test_quality_analyzer_detects_placeholders(tmp_path: Path):
    bad_html = "<html><body><h1>Project Alpha</h1><p>Lorem ipsum dolor sit amet</p></body></html>"
    (tmp_path / "index.html").write_text(bad_html, encoding="utf-8")
    (tmp_path / "style.css").write_text("body { color: red; }", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('hi');", encoding="utf-8")

    analyzer = CodeQualityAnalyzer(tmp_path)
    check = analyzer.analyze_web_aesthetic_and_interactivity()
    assert check is not None
    assert check.status == "fail"
    assert any("placeholder" in f.lower() for f in check.evidence["failures"])


@pytest.mark.asyncio
async def test_aesthetic_and_interactive_checker(tmp_path: Path):
    from app.core.config import Settings
    from app.core.workspace import WorkspaceManager
    from app.execution.engine import ExecutionEngine
    from app.verification.checkers import AestheticAndInteractiveChecker

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    task_id = "test_aesthetic_task"

    # Synthesize complete 3D website in workspace
    files = ForgeWebStudio.synthesize_website("Futuristic 3D Portfolio")
    for p, content in files.items():
        wm.write_project_file(task_id, p, content)

    checker = AestheticAndInteractiveChecker()
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is True
    assert evidence.exit_code == 0
    assert "Aesthetic verification passed" in evidence.stdout
    assert len(evidence.issues) == 0


def test_web_studio_hud_telemetry_terminal():
    goal = "Build a futuristic 3D cyberpunk developer portfolio with Three.js"
    files = ForgeWebStudio.synthesize_website(goal)

    html = files["index.html"]
    css = files["style.css"]
    js = files["app.js"]

    # 1. 3D HUD Controls
    assert 'id="hud-wireframe-toggle"' in html
    assert 'id="hud-speed-toggle"' in html
    assert 'id="hud-reset-view"' in html
    assert ".hud-controls-bar" in css
    assert "hud-wireframe-toggle" in js
    assert "hud-speed-toggle" in js
    assert "hud-reset-view" in js

    # 2. Telemetry Strip
    assert "telemetry-strip" in html
    assert "FPS Native 3D WebGL" in html
    assert "stat-number" in html
    assert ".telemetry-strip" in css
    assert "animateCounters" in js

    # 3. Cyber Terminal
    assert 'id="terminal"' in html
    assert 'id="terminal-output"' in html
    assert 'id="terminal-input"' in html
    assert "terminal-chip" in html
    assert ".terminal-container" in css
    assert "runTerminalCommand" in js
    assert "skills" in js
    assert "projects" in js
    assert "stats" in js


@pytest.mark.asyncio
async def test_developer_role_synchronizes_3d_web_app(tmp_path: Path):
    from uuid import uuid4

    from app.agents.roles import DeveloperRole
    from app.core.config import Settings
    from app.core.workspace import WorkspaceManager
    from app.execution.engine import ExecutionEngine

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()
    context = {
        "goal": "Build a futuristic 3D cyberpunk developer portfolio with Three.js",
        "file_manifest": ["index.html", "style.css", "app.js"],
    }

    result = await developer.execute_step(
        task_id=task_id,
        node_title="Implement 3D Web Application",
        context=context,
        engine=engine,
    )

    assert result["status"] == "success"
    assert "index.html" in result["files_written"]
    assert "style.css" in result["files_written"]
    assert "app.js" in result["files_written"]
    assert result["fallback_stub"] is False

    # Verify files on disk match
    html = engine.fs.read_file(task_id, "index.html", role="developer")
    assert "<canvas" in html.lower()
    assert "<html" in html.lower()

    css = engine.fs.read_file(task_id, "style.css", role="developer")
    assert ":root" in css or "body" in css

    js = engine.fs.read_file(task_id, "app.js", role="developer")
    assert len(js.strip()) > 50


def test_ecommerce_domain_synthesis():
    """Verify E-Commerce domain produces distinct cart drawer, product grid, and checkout."""
    files = ForgeWebStudio.synthesize_website(
        "Build a luxury 3D e-commerce store for futuristic hardware and tech accessories"
    )
    html = files["index.html"]
    js = files["app.js"]

    assert 'id="cart-drawer"' in html
    assert 'id="cart-btn"' in html
    assert 'id="checkout-modal"' in html
    assert "add-to-cart-btn" in html
    assert "addToCart" in js
    assert "cart" in js


def test_saas_domain_synthesis():
    """Verify SaaS domain produces distinct ROI calculator, billing toggle, and tier pricing."""
    files = ForgeWebStudio.synthesize_website(
        "Create a modern futuristic 3D AI SaaS analytics platform with interactive pricing"
    )
    html = files["index.html"]
    js = files["app.js"]

    assert 'id="roi-calculator"' in html
    assert 'id="team-size-slider"' in html
    assert 'id="billing-toggle"' in html
    assert "tier-price" in html
    assert "teamSlider" in js or "team-size-slider" in js
    assert "billingToggle" in js or "billing-toggle" in js


def test_dashboard_domain_synthesis():
    """Verify Dashboard domain produces distinct telemetry table, throughput gauges, and alert drawer."""
    files = ForgeWebStudio.synthesize_website(
        "Build a real-time IoT mission control operations dashboard with telemetry"
    )
    html = files["index.html"]
    js = files["app.js"]

    assert 'id="telemetry-table"' in html
    assert 'id="kpi-throughput"' in html
    assert 'id="kpi-latency"' in html
    assert 'id="simulate-spike-btn"' in html
    assert 'id="alerts-drawer"' in html
    assert "kpiThroughput" in js or "telemetry-table" in js


def test_portfolio_domain_synthesis():
    """Verify Portfolio domain produces distinct 3D HUD controls, cyber terminal, and showcase cards."""
    files = ForgeWebStudio.synthesize_website(
        "Build a futuristic 3D cyberpunk developer portfolio with Three.js"
    )
    html = files["index.html"]
    js = files["app.js"]

    assert 'id="hud-wireframe-toggle"' in html
    assert 'id="hud-speed-toggle"' in html
    assert 'id="hud-reset-view"' in html
    assert 'id="terminal"' in html
    assert "runTerminalCommand" in js


def test_dashboard_quick_diagnostics_button_has_a_click_handler():
    """Finding 17b (live-reproduced, same bug family as the portfolio
    contact form): the dashboard template's "Run Quick Diagnostics" button
    (`id="quick-diagnostics-btn"`) had zero corresponding JavaScript -- a
    plain dead button with no visible response to a click, unlike every
    other interactive control in the same template (theme toggle, spike
    simulation, alerts bell). Verified by actually running the generated
    app.js against a real DOM (jsdom): before the fix the button's label
    never changed on click; after the fix it flips to "Running
    Diagnostics…" and the button disables for the duration.
    """
    files = ForgeWebStudio.synthesize_website(
        "Build a real-time IoT sensor telemetry dashboard with alerts"
    )
    html = files["index.html"]
    js = files["app.js"]

    assert 'id="quick-diagnostics-btn"' in html
    assert "getElementById('quick-diagnostics-btn')" in js, (
        "quick-diagnostics-btn exists in the HTML but nothing in app.js looks "
        "it up -- clicking it does nothing"
    )
    assert "diagBtn.addEventListener('click'" in js


def test_ecommerce_checkout_reads_the_customer_info_it_collects():
    """Finding 26 (live-reproduced): the ecommerce template's checkout form
    collected a customer's name/email/address (with native `required`
    validation on each <input>) but its submit handler never read any of
    those three fields -- it only generated a random order id and showed a
    generic "Order Successfully Dispatched!" message. A real user's
    submitted contact/shipping info was silently discarded, never
    validated beyond the browser's own HTML5 constraint, never reflected
    back, never used. Found via a generator-wide id-wiring sweep extended to
    cover <input>/<select> (not just <form>/<button>), which flagged
    cust-name/cust-email/cust-address as having zero JS references anywhere
    in app.js.
    """
    files = ForgeWebStudio.synthesize_website(
        "Build a luxury minimalist e-commerce fashion store with a shopping cart and checkout"
    )
    html = files["index.html"]
    js = files["app.js"]

    for field_id in ("cust-name", "cust-email", "cust-address"):
        assert f'id="{field_id}"' in html
        assert f"getElementById('{field_id}')" in js, (
            f"checkout field {field_id} is collected from the user but never read by any JS"
        )
    # The confirmation view must actually reflect what was submitted.
    assert "order-confirmation-recipient" in html
    assert "order-confirmation-recipient" in js


def test_every_website_template_wires_up_its_interactive_elements():
    """Systematic, generator-wide guard for the "styled element with no
    handler" bug family: every <form id="...">, <button id="...">,
    <input id="...">, and <select id="..."> emitted by any of the four
    domain templates must have a matching getElementById() (or equivalent
    selector) lookup somewhere in that same template's generated app.js.
    This is intentionally broad (not tied to one specific id) so a *new*
    dead element introduced by a future template change is caught
    automatically instead of needing its own one-off regression test.

    Extended (originally forms/buttons only) after Finding 26: a sweep with
    <input>/<select> included caught the ecommerce checkout form's
    cust-name/cust-email/cust-address inputs, which were collected with
    native `required` validation but never read by any JS anywhere -- see
    `test_ecommerce_checkout_reads_the_customer_info_it_collects` below for
    the live end-to-end (jsdom) verification of that specific fix.
    """
    import re

    goals = {
        "portfolio": "Build a personal 3D creative developer portfolio with a contact form",
        "ecommerce": "Build a luxury minimalist e-commerce fashion store with a shopping cart and checkout",
        "saas": "Create a modern AI SaaS analytics platform with pricing plans and a signup form",
        "dashboard": "Build a real-time IoT sensor telemetry dashboard with alerts",
    }

    for domain, goal in goals.items():
        files = ForgeWebStudio.synthesize_website(goal, [])
        html = files["index.html"]
        js = files["app.js"]

        interactive_ids = (
            set(re.findall(r'<form[^>]*\sid="([a-zA-Z0-9_-]+)"', html))
            | set(re.findall(r'<button[^>]*\sid="([a-zA-Z0-9_-]+)"', html))
            | set(re.findall(r'<input[^>]*\sid="([a-zA-Z0-9_-]+)"', html))
            | set(re.findall(r'<select[^>]*\sid="([a-zA-Z0-9_-]+)"', html))
        )

        def _is_wired_up(el_id: str) -> bool:
            # Most elements are looked up directly...
            if f"getElementById('{el_id}')" in js or f'getElementById("{el_id}")' in js:
                return True
            # ...but some are wired up as part of a shared CSS-selector list,
            # e.g. `document.querySelectorAll('#a, #b, .some-class')`.
            return f"#{el_id}" in js

        missing = [el_id for el_id in interactive_ids if not _is_wired_up(el_id)]
        assert not missing, (
            f"{domain} template has interactive element(s) with no JS handler: "
            f"{missing} -- these will be dead/no-op when a real user clicks them"
        )


def test_portfolio_contact_form_has_a_submit_handler():
    """Finding 17 (live-reproduced): the portfolio template's contact form
    (`id="contact-form"`) had zero corresponding JavaScript anywhere in the
    generated app.js. The <form> has no `action`, so a real user submitting
    it got the browser's un-intercepted default behavior -- a full page
    reload with the form fields silently discarded and no confirmation.
    Verified by actually running the generated site's app.js against a real
    DOM (jsdom) and firing a submit event: before the fix, nothing happened
    to intercept it; after the fix, the submit is prevented and the form is
    replaced with an on-page confirmation. This test asserts the static
    precondition for that behavior -- that the generator actually emits a
    handler wired to the exact id the HTML uses -- so a future refactor that
    silently drops the handler (or renames one side without the other) fails
    immediately instead of only being caught by someone manually running the
    output in a browser.
    """
    files = ForgeWebStudio.synthesize_website(
        "Build a personal 3D creative developer portfolio with a contact form"
    )
    html = files["index.html"]
    js = files["app.js"]

    assert 'id="contact-form"' in html, "portfolio template should render a contact form"
    assert "getElementById('contact-form')" in js, (
        "contact-form exists in the HTML but nothing in app.js looks it up -- "
        "submitting it will fall through to the browser's default (page-reload) "
        "behavior instead of being handled client-side"
    )
    assert "contactForm.addEventListener('submit'" in js
    assert "preventDefault" in js.split("getElementById('contact-form')")[1][:500]


