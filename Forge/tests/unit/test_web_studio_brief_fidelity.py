"""
Brief-fidelity regression tests for ForgeWebStudio (diagnosis §8).

The 2026-11-17 Forge evaluation (B2-C07) measured brief fidelity ~= 0 in the
Web Studio lane: two real briefs produced generic templates that ignored the
brief -- no brand, no requested sections, no requested behaviour. The root
cause (forge-webstudio-diag/DIAGNOSIS.md): requirements were dropped at the
DomainSynthesizer -> builder handoff, substring keyword matching misfired
("ai" inside "email"), brand extraction could not parse CamelCase or
"Name - description" lead-ins, the SaaS skeleton had no form, and the
"creative" archetype fell through to the portfolio renderer.

These tests pin the brief -> page connection with the evaluation's two
briefs verbatim as fixtures, plus a cross-archetype brand-token matrix.
Deterministic, no model, no network.
"""

from app.templates.web_studio.domain_synthesizer import DomainSynthesizer
from app.templates.web_studio.generator import ForgeWebStudio

# ---------------------------------------------------------------------------
# Fixtures -- the evaluation's two briefs, verbatim (goal + requirements
# exactly as passed to ForgeWebStudio.synthesize_website in the evaluation).
# ---------------------------------------------------------------------------

BRIEF_A_GOAL = (
    "BeanRoute - a neighbourhood coffee subscription service landing page. "
    "Hero with headline and email signup form, features section, 3 pricing "
    "tiers, testimonials, FAQ, footer. Responsive, modern design."
)
BRIEF_A_REQUIREMENTS = [
    "hero with email signup form",
    "features section",
    "3 pricing tiers",
    "testimonials",
    "FAQ",
    "footer",
    "responsive",
]

BRIEF_B_GOAL = (
    "TaskBoard Mini - a personal task board app. A form to add a task "
    "(title, priority, due date), a list view of all tasks with filter by "
    "status, mark-complete and delete actions, tasks persisted in browser "
    "localStorage. Single page."
)
BRIEF_B_REQUIREMENTS = [
    "add task form with title priority due date",
    "list view of tasks",
    "filter by status",
    "mark complete",
    "delete",
    "localStorage persistence",
]


# ---------------------------------------------------------------------------
# Brief A -- BeanRoute coffee subscription landing page (SaaS lane)
# ---------------------------------------------------------------------------


def test_brief_a_brand_and_subject_reach_the_page():
    files = ForgeWebStudio.synthesize_website(
        BRIEF_A_GOAL, requirements=BRIEF_A_REQUIREMENTS
    )
    html = files["index.html"]
    assert "BeanRoute" in html
    assert "coffee" in html.lower()


def test_brief_a_signup_form_is_rendered():
    files = ForgeWebStudio.synthesize_website(
        BRIEF_A_GOAL, requirements=BRIEF_A_REQUIREMENTS
    )
    html = files["index.html"]
    assert "<form" in html
    assert 'type="email"' in html


def test_brief_a_off_brief_persona_is_gone():
    """The measured defect: brand "Hero" + the AI-copilot persona, produced
    by the substring "ai" inside "email" and a fallback brand guess."""
    files = ForgeWebStudio.synthesize_website(
        BRIEF_A_GOAL, requirements=BRIEF_A_REQUIREMENTS
    )
    html = files["index.html"]
    assert "AI Copilot That Writes" not in html
    assert "Hero AI" not in html


def test_brief_a_blueprint_carries_the_brief_model():
    bp = DomainSynthesizer.analyze_goal(
        BRIEF_A_GOAL, requirements=BRIEF_A_REQUIREMENTS
    )
    assert bp.app_title.startswith("BeanRoute")
    sections = getattr(bp, "requested_sections", [])
    assert "signup_form" in sections
    assert "testimonials" in sections


# ---------------------------------------------------------------------------
# Brief B -- TaskBoard Mini form + list app (creative fallthrough lane)
# ---------------------------------------------------------------------------


def test_brief_b_list_app_fields_reach_the_page():
    files = ForgeWebStudio.synthesize_website(
        BRIEF_B_GOAL, requirements=BRIEF_B_REQUIREMENTS
    )
    html = files["index.html"]
    assert "TaskBoard" in html
    assert "priority" in html.lower()
    assert "due" in html.lower()


def test_brief_b_localstorage_crud_is_brief_keyed():
    bp = DomainSynthesizer.analyze_goal(
        BRIEF_B_GOAL, requirements=BRIEF_B_REQUIREMENTS
    )
    entity = getattr(bp, "app_entity", None)
    assert entity, "app-shaped brief produced no entity model"
    field_names = [f["name"] for f in entity["fields"]]
    assert "priority" in field_names
    assert any("due" in name for name in field_names)
    storage_key = entity["storage_key"]
    assert storage_key != "forge_theme"
    assert "task" in storage_key

    files = ForgeWebStudio.synthesize_website(
        BRIEF_B_GOAL, requirements=BRIEF_B_REQUIREMENTS
    )
    js = files["app.js"]
    assert "localStorage" in js
    assert storage_key in js
    assert "delete" in js.lower()


def test_brief_b_creative_no_longer_renders_as_portfolio():
    files = ForgeWebStudio.synthesize_website(
        BRIEF_B_GOAL, requirements=BRIEF_B_REQUIREMENTS
    )
    html = files["index.html"]
    assert "Featured Engineering Systems" not in html
    assert "Core Competencies" not in html


# ---------------------------------------------------------------------------
# Cross-archetype brand matrix -- brand extraction must work generally,
# not just for the two fixtures (CamelCase lead-in brands).
# ---------------------------------------------------------------------------

BRAND_MATRIX = [
    (
        "LoomAndCo - a furniture store. Browse the collection, add items "
        "to the cart, and check out securely.",
        ["product grid", "shopping cart", "checkout"],
        "ecommerce",
        "LoomAndCo",
    ),
    (
        "PulseGrid - a real-time operations dashboard. Live charts, "
        "alerts, and team activity feeds.",
        ["live charts", "alerts"],
        "dashboard",
        "PulseGrid",
    ),
    (
        "MayaChen - a creative developer portfolio. Selected work, "
        "skills, and contact.",
        ["selected work", "skills", "contact"],
        "portfolio",
        "MayaChen",
    ),
]


def test_cross_archetype_brand_tokens():
    for goal, reqs, expected_domain, brand in BRAND_MATRIX:
        bp = DomainSynthesizer.analyze_goal(goal, requirements=reqs)
        assert bp.domain_type == expected_domain, (goal, bp.domain_type)
        files = ForgeWebStudio.synthesize_website(goal, requirements=reqs)
        assert brand in files["index.html"], (goal, brand)


# ---------------------------------------------------------------------------
# Guard -- a brief that requests nothing brief-specific must not gain
# brief sections or an entity model (existing briefs render unchanged).
# ---------------------------------------------------------------------------


def test_plain_brief_gains_no_brief_sections():
    bp = DomainSynthesizer.analyze_goal("Build a portfolio site")
    assert getattr(bp, "app_entity", None) is None
    assert "signup_form" not in getattr(bp, "requested_sections", [])
    files = ForgeWebStudio.synthesize_website("Build a portfolio site")
    assert 'id="signup-form"' not in files["index.html"]
    assert "localStorage" not in files["app.js"] or "forge_theme" in files["app.js"]
