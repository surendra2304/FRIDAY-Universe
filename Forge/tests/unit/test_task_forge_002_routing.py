"""TASK-FORGE-002 (GAP 3) regressions: web-studio routing needs an explicit web deliverable.

Before the fix, WEB_STUDIO_KEYWORDS contained generic product substrings ("shop",
"pricing", "telemetry", "dashboard", ...), so a REST API for a book shop was planned
as a static website and a CLI telemetry tool was synthesized into a 3D site. The
routing now requires an explicit web-deliverable noun plus a web-domain keyword,
and the backend-exclusive veto (word-boundary matched) covers api/rest/cli/script/
command-line so "javascript" cannot veto a genuine web goal.
"""

from app.agents.roles import is_web_3d_goal, is_web_studio_goal


def test_rest_api_for_book_shop_is_not_web_studio():
    """Concrete audit misroute: generic 'shop'/'pricing' words must not win."""
    goal = "Build a REST API for a book shop with pricing rules"
    assert not is_web_studio_goal(goal)
    assert not is_web_3d_goal(goal)


def test_cli_telemetry_tool_is_not_web_studio_or_3d():
    """Concrete audit misroute: 'telemetry' alone must not build a 3D site."""
    goal = "Build a CLI tool that logs telemetry from my sensors"
    assert not is_web_studio_goal(goal)
    assert not is_web_3d_goal(goal)


def test_genuine_landing_page_request_still_routes_to_web_studio():
    goal = "Create a responsive interactive landing page in HTML5, CSS3, and modern JavaScript"
    assert is_web_studio_goal(goal)


def test_website_mention_is_an_explicit_deliverable():
    goal = "Build a portfolio website with project galleries"
    assert is_web_studio_goal(goal)


def test_javascript_word_does_not_trigger_the_script_veto():
    """'javascript' contains 'script'; word-boundary matching must keep it a web goal."""
    goal = "Build a website with JavaScript animations"
    assert is_web_studio_goal(goal)


def test_generic_dashboard_telemetry_words_need_a_web_deliverable():
    assert not is_web_studio_goal("Build a dashboard that tracks my gym telemetry")
    assert is_web_studio_goal("Build a telemetry web dashboard for my sensors")


def test_web_3d_routing_survives_for_immersive_requests():
    assert is_web_3d_goal("Build a futuristic 3D cyberpunk developer portfolio with Three.js")


def test_script_goal_cannot_route_to_web_3d():
    assert not is_web_3d_goal("Write a script that renders 3D data offline")
    assert not is_web_3d_goal("Build a command-line tool with a 3D ASCII preview")
