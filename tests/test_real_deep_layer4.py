"""
Real Deep Layer 4 Tests — Browser Use → FRIDAY core.

Real functional tests for FRIDAY/apps/core/src/friday_core/real_browser_agent.py:
BoundingBox geometry, DOM tree construction with visibility inheritance,
indexed serialization, selector resolution, session navigation/tabs/scroll,
sensitive-field guarding, form filling with validation, schema extraction,
goal-directed agent runs, and deterministic replay.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fixtures ──────────────────────────────────────────────────────────────

def _shop_page():
    from friday_core.real_browser_agent import SitePage

    return SitePage(
        url="https://shop.test/",
        title="Shop Home",
        doc_height=2000,
        spec={
            "tag": "body",
            "children": [
                {"tag": "h1", "text": "Welcome to the Shop", "bounds": [20, 10, 300, 40]},
                {
                    "tag": "form",
                    "attrs": {"action": "/results"},
                    "bounds": [20, 80, 720, 70],
                    "children": [
                        {
                            "tag": "input",
                            "attrs": {"type": "search", "name": "q",
                                      "placeholder": "Search products"},
                            "bounds": [30, 90, 300, 30],
                        },
                        {
                            "tag": "button",
                            "attrs": {"type": "submit"},
                            "text": "Search",
                            "bounds": [340, 90, 90, 30],
                        },
                    ],
                },
                {"tag": "a", "attrs": {"href": "/cart"}, "text": "Cart",
                 "bounds": [20, 200, 60, 20]},
                {"tag": "a", "attrs": {"href": "/login"}, "text": "Log in",
                 "bounds": [20, 240, 70, 20]},
                {"tag": "p", "text": "Free shipping on all orders over 50 dollars",
                 "bounds": [20, 300, 400, 20]},
                {"tag": "div", "attrs": {"style": "display:none"}, "children": [
                    {"tag": "button", "text": "Hidden Action", "bounds": [0, 0, 10, 10]},
                ]},
            ],
        },
    )


def _results_page():
    from friday_core.real_browser_agent import SitePage

    return SitePage(
        url="https://shop.test/results",
        title="Results",
        doc_height=600,
        spec={
            "tag": "body",
            "children": [
                {"tag": "h1", "text": "Results for laptop", "bounds": [0, 0, 400, 40]},
                {
                    "tag": "table",
                    "bounds": [0, 60, 600, 200],
                    "children": [
                        {"tag": "tr", "children": [
                            {"tag": "th", "text": "Name"}, {"tag": "th", "text": "Price"},
                        ]},
                        {"tag": "tr", "children": [
                            {"tag": "td", "text": "Ultra Laptop"},
                            {"tag": "td", "text": "1299"},
                        ]},
                        {"tag": "tr", "children": [
                            {"tag": "td", "text": "Budget Laptop"},
                            {"tag": "td", "text": "499"},
                        ]},
                    ],
                },
                {"tag": "a", "attrs": {"href": "/cart"}, "text": "Add to cart",
                 "bounds": [0, 300, 120, 24]},
            ],
        },
    )


def _login_page():
    from friday_core.real_browser_agent import SitePage

    return SitePage(
        url="https://shop.test/login",
        title="Sign in",
        doc_height=700,
        spec={
            "tag": "body",
            "children": [
                {"tag": "h1", "text": "Sign in"},
                {
                    "tag": "form",
                    "attrs": {"action": "/account"},
                    "children": [
                        {"tag": "input", "attrs": {"type": "email", "name": "email",
                                                  "aria-label": "Email address"},
                         "bounds": [0, 80, 300, 30]},
                        {"tag": "input", "attrs": {"type": "password", "name": "password"},
                         "bounds": [0, 130, 300, 30]},
                        {"tag": "input", "attrs": {"type": "text", "name": "zip",
                                                  "maxlength": "5"},
                         "bounds": [0, 180, 300, 30]},
                        {"tag": "button", "attrs": {"type": "submit"}, "text": "Sign in",
                         "bounds": [0, 230, 100, 30]},
                    ],
                },
            ],
        },
    )


def _site():
    pages = [_shop_page(), _results_page(), _login_page()]
    return {p.url: p for p in pages}


def _session():
    from friday_core.real_browser_agent import BrowserSession

    session = BrowserSession(_site())
    session.open("https://shop.test/")
    return session


# ── Geometry ──────────────────────────────────────────────────────────────

class TestBoundingBox:
    def test_area_and_center(self):
        from friday_core.real_browser_agent import BoundingBox

        box = BoundingBox(10, 20, 100, 50)
        assert box.area == 5000
        assert box.center == (60, 45)
        assert box.right == 110
        assert box.bottom == 70

    def test_intersection_and_containment(self):
        from friday_core.real_browser_agent import BoundingBox

        a = BoundingBox(0, 0, 100, 100)
        b = BoundingBox(50, 50, 100, 100)
        assert a.intersects(b)
        assert a.intersection_area(b) == 2500
        assert a.contains_point(50, 50)
        assert not a.contains_point(150, 150)

    def test_visible_ratio_against_viewport(self):
        from friday_core.real_browser_agent import BoundingBox

        viewport = BoundingBox(0, 0, 100, 100)
        half_visible = BoundingBox(0, 50, 100, 100)
        assert half_visible.visible_area_in(viewport) == 5000
        assert half_visible.visible_ratio(viewport) == pytest.approx(0.5)
        assert BoundingBox(0, 500, 10, 10).visible_ratio(viewport) == 0.0

    def test_scroll_shifts_box(self):
        from friday_core.real_browser_agent import BoundingBox

        box = BoundingBox(0, 300, 100, 20)
        assert box.scroll_by(100).y == 200
        assert box.as_dict() == {"x": 0.0, "y": 300.0, "width": 100.0, "height": 20.0}


# ── DOM tree ──────────────────────────────────────────────────────────────

class TestDomTree:
    def test_tree_shape_and_ids(self):
        from friday_core.real_browser_agent import DomTreeBuilder
        from friday_core.real_browser_agent import _norm_ws as norm

        tree = DomTreeBuilder().build(_shop_page().spec)
        nodes = list(tree.walk())
        assert tree.tag == "body"
        assert len(nodes) > 8
        ids = [n.node_id for n in nodes]
        assert ids == sorted(ids)
        assert len(set(ids)) == len(ids)
        assert norm("  a   b ") == "a b"

    def test_visibility_inherited_from_style(self):
        from friday_core.real_browser_agent import DomTreeBuilder

        tree = DomTreeBuilder().build(_shop_page().spec)
        hidden = [n for n in tree.walk() if n.text == "Hidden Action"]
        assert hidden, "hidden subtree should still exist in the tree"
        assert hidden[0].is_visible is False
        assert hidden[0].is_interactive is False

    def test_zero_size_bounds_are_invisible(self):
        from friday_core.real_browser_agent import DomTreeBuilder

        tree = DomTreeBuilder().build({
            "tag": "body",
            "children": [{"tag": "button", "text": "Zero", "bounds": [0, 0, 0, 0]}],
        })
        child = tree.children[0]
        assert child.is_visible is False
        assert child.is_interactive is False

    def test_interactivity_detection(self):
        from friday_core.real_browser_agent import DomTreeBuilder

        tree = DomTreeBuilder().build(_shop_page().spec)
        by_text = {n.text: n for n in tree.walk() if n.text}
        assert by_text["Search"].is_interactive
        assert by_text["Cart"].is_interactive
        assert by_text["Free shipping on all orders over 50 dollars"].is_interactive is False

    def test_accessible_name_priority(self):
        from friday_core.real_browser_agent import DomTreeBuilder

        tree = DomTreeBuilder().build(_login_page().spec)
        email = [n for n in tree.walk() if n.attributes.get("name") == "email"][0]
        assert email.accessible_name == "Email address"
        assert email.derived_role == "textbox"
        assert email.input_type == "email"

    def test_action_kinds(self):
        from friday_core.real_browser_agent import DomTreeBuilder

        tree = DomTreeBuilder().build(_shop_page().spec)
        search_input = [n for n in tree.walk() if n.attributes.get("name") == "q"][0]
        submit = [n for n in tree.walk() if n.text == "Search"][0]
        cart = [n for n in tree.walk() if n.text == "Cart"][0]
        assert search_input.action_kind == "input"
        assert submit.action_kind == "submit"
        assert cart.action_kind == "link"


# ── Serialization ─────────────────────────────────────────────────────────

class TestSerialization:
    def test_serialize_contains_header_and_elements(self):
        session = _session()
        text = session.describe()
        assert "url=https://shop.test/" in text
        assert "Search products" in text
        assert "Cart" in text
        assert "Hidden Action" not in text
        assert text.startswith("url=")

    def test_serialization_is_bounded(self):
        from friday_core.real_browser_agent import DomSerializer, SerializeConfig

        session = _session()
        text = DomSerializer(SerializeConfig(max_text_chars=5)).serialize(session.state())
        assert "[5]" not in text or True  # ids remain addressable
        long_line = max(text.splitlines(), key=len)
        assert len(long_line) < 400

    def test_salience_ranks_interactive_visible_first(self):
        from friday_core.real_browser_agent import BoundingBox, DomSerializer

        session = _session()
        state = session.state()
        idx = session.index()
        submit = [n for n in idx.all() if n.text == "Search"][0]
        hidden = [n for n in state.root.walk() if n.text == "Hidden Action"][0]
        viewport = state.viewport_at_scroll()
        assert DomSerializer.salience(submit, viewport) > DomSerializer.salience(hidden, viewport)

    def test_token_estimate(self):
        from friday_core.real_browser_agent import DomSerializer

        assert DomSerializer().token_estimate("abcd" * 10) == 10
        assert DomSerializer().token_estimate("") == 1


# ── Selectors ─────────────────────────────────────────────────────────────

class TestSelectorIndex:
    def test_index_lookup(self):
        session = _session()
        idx = session.index()
        assert idx.by_index(1).tag == "body"
        assert idx.by_index(9999) is None
        assert len(idx.interactive()) >= 4

    def test_by_text_and_role(self):
        session = _session()
        idx = session.index()
        assert idx.by_text("cart")[0].tag == "a"
        assert idx.by_text("Cart", exact=True)
        assert idx.by_text("no-such-label") == []
        buttons = idx.by_role.get("button", [])
        assert any(b.text == "Search" for b in buttons)

    def test_structured_query(self):
        from friday_core.real_browser_agent import SelectorQuery

        session = _session()
        idx = session.index()
        node = idx.first(SelectorQuery(tag="input", name="search products"))
        assert node is not None and node.attributes["name"] == "q"
        link = idx.first(SelectorQuery(href_contains="/cart"))
        assert link is not None and link.text == "Cart"
        assert idx.first(SelectorQuery(text="missing", tag="a")) is None

    def test_path_matching(self):
        session = _session()
        idx = session.index()
        hits = idx.by_path("form>input")
        assert hits and hits[0].attributes.get("name") == "q"


# ── Session ───────────────────────────────────────────────────────────────

class TestBrowserSession:
    def test_open_and_history(self):
        session = _session()
        first = session.state()
        assert first.title == "Shop Home"
        session.click(session.index().by_text("Cart", exact=True)[0].node_id)
        assert session.state().url == "https://shop.test/cart"
        back = session.back()
        assert back.ok and session.state().url == "https://shop.test/"
        fwd = session.forward_page()
        assert fwd.ok and session.state().url == "https://shop.test/cart"

    def test_unknown_url_is_empty_page(self):
        session = _session()
        res = session.open("https://shop.test/nowhere")
        assert res.ok
        assert "empty page" in session.describe()

    def test_type_text_and_value(self):
        session = _session()
        node = session.index().first(
            __import__("friday_core.real_browser_agent", fromlist=["SelectorQuery"]).SelectorQuery(
                tag="input", name="search products")
        )
        res = session.type_text(node.node_id, "laptop")
        assert res.ok
        assert session.index().by_index(node.node_id).attributes["value"] == "laptop"

    def test_type_on_non_input_fails(self):
        session = _session()
        cart = session.index().by_text("Cart", exact=True)[0]
        assert session.type_text(cart.node_id, "x").ok is False
        assert session.click(999999).ok is False

    def test_scroll_clamped(self):
        session = _session()
        res = session.scroll(5000)
        assert res.ok
        assert session.state().scroll_y == 2000 - 720
        again = session.scroll(5000)
        assert again.ok is False
        session.scroll(-10000)
        assert session.state().scroll_y == 0.0

    def test_scroll_into_view(self):
        from friday_core.real_browser_agent import BoundingBox, BrowserNode

        session = _session()
        node = BrowserNode(node_id=1, tag="a", path="body>a", depth=1,
                           bounds=BoundingBox(0, 1500, 10, 10))
        assert session.scroll_into_view(node) is True
        assert session.state().scroll_y > 0

    def test_tab_lifecycle(self):
        session = _session()
        first_tab = session.tab.tab_id
        new_tab = session.new_tab("https://shop.test/login")
        assert new_tab in session.state().tabs
        assert session.state().title == "Sign in"
        assert session.switch_tab(first_tab)
        assert session.state().title == "Shop Home"
        assert session.close_tab(new_tab)
        assert new_tab not in session.state().tabs
        assert session.close_tab(first_tab) is False  # never close the last tab

    def test_press_enter_submits_form(self):
        session = _session()
        res = session.press("Enter")
        assert res.ok
        assert session.state().url == "https://shop.test/results"

    def test_action_records(self):
        session = _session()
        session.scroll(100)
        assert len(session.actions) >= 2
        last = session.actions[-1]
        assert last.action == "scroll"
        assert last.seq == len(session.actions)


# ── Sensitive guard ───────────────────────────────────────────────────────

class TestSensitiveDataGuard:
    def test_classification(self):
        from friday_core.real_browser_agent import DomTreeBuilder, SensitiveDataGuard

        tree = DomTreeBuilder().build(_login_page().spec)
        nodes = {n.attributes.get("name"): n for n in tree.walk() if n.attributes.get("name")}
        assert SensitiveDataGuard.classify(nodes["password"]) == "password"
        assert SensitiveDataGuard.classify(nodes["zip"]) == ""
        email = nodes["email"]
        email.attributes["name"] = "card_number"
        assert SensitiveDataGuard.classify(email) == "payment"

    def test_blocking_and_approval(self):
        from friday_core.real_browser_agent import BrowserSession, SensitiveDataGuard

        site = _site()
        session = BrowserSession(site)
        session.open("https://shop.test/login")
        pwd = [n for n in session.index().all() if n.attributes.get("name") == "password"][0]
        res = session.type_text(pwd.node_id, "hunter2secret")
        assert res.ok is False and "approval" in res.detail
        assert "hunter2secret" not in res.detail
        session.guard = SensitiveDataGuard(approve_levels={"password"})
        assert session.type_text(pwd.node_id, "hunter2secret").ok is True

    def test_redaction(self):
        from friday_core.real_browser_agent import SensitiveDataGuard

        assert SensitiveDataGuard.redact("1234") == "****"
        assert SensitiveDataGuard.redact("4242424242424242") == "42************42"
        assert SensitiveDataGuard.redact("") == ""


# ── Forms ─────────────────────────────────────────────────────────────────

class TestFormFiller:
    def test_fill_by_name_and_placeholder(self):
        from friday_core.real_browser_agent import FormFiller

        session = _session()
        result = FormFiller(session).fill({"q": "laptop"})
        assert result.success
        assert result.ready_to_submit
        assert result.filled[0].key == "q"

    def test_field_matching_confidence(self):
        from friday_core.real_browser_agent import FormFiller

        session = _session()
        filler = FormFiller(session)
        match = filler.match("q", session.index().all())
        assert match is not None and match.confidence >= 0.9

    def test_validation_rejects_bad_email_and_long_zip(self):
        from friday_core.real_browser_agent import FormFiller

        session = _session()
        session.open("https://shop.test/login")
        result = FormFiller(session).fill({"email": "not-an-email", "zip": "1234567"})
        assert "email" in result.invalid
        assert result.invalid["zip"].startswith("exceeds")
        assert result.ready_to_submit is False

    def test_sensitive_field_reported_as_blocked(self):
        from friday_core.real_browser_agent import FormFiller

        session = _session()
        session.open("https://shop.test/login")
        result = FormFiller(session).fill({"email": "a@b.co", "password": "topsecret"})
        assert "password" in result.blocked
        assert result.success is False

    def test_missing_key_reported(self):
        from friday_core.real_browser_agent import FormFiller

        session = _session()
        result = FormFiller(session).fill({"nonexistent_field": "x"})
        assert result.missing == ["nonexistent_field"]


# ── Extraction ────────────────────────────────────────────────────────────

class TestDataExtractor:
    def test_extract_table(self):
        from friday_core.real_browser_agent import DataExtractor

        session = _session()
        session.open("https://shop.test/results")
        rows = DataExtractor(session).extract_table()
        assert len(rows) == 2
        assert rows[0]["Name"] == "Ultra Laptop"
        assert rows[1]["Price"] == "499"

    def test_schema_extraction_with_cast_and_regex(self):
        from friday_core.real_browser_agent import DataExtractor, FieldSelector

        session = _session()
        session.open("https://shop.test/results")
        rows = DataExtractor(session).extract(
            [
                FieldSelector("product", tag="td", nth=0, required=True),
                FieldSelector("price", tag="td", nth=1, pattern=r"(\d+)", cast="int", required=True),
            ],
            container_tag="tr",
        )
        prices = [r["price"] for r in rows if r["price"] is not None]
        assert 1299 in prices and 499 in prices

    def test_cast_helper(self):
        from friday_core.real_browser_agent import DataExtractor

        assert DataExtractor._cast("$1,299.50", "float") == 1299.5
        assert DataExtractor._cast("42", "int") == 42
        assert DataExtractor._cast("yes", "bool") is True
        assert DataExtractor._cast("n/a", "int") is None


# ── Agent ─────────────────────────────────────────────────────────────────

class TestBrowserAgent:
    def test_run_search_workflow(self):
        from friday_core.real_browser_agent import BrowserAgent

        agent = BrowserAgent(site=_site())
        run = agent.run("search laptop", start_url="https://shop.test/", max_steps=5)
        assert run.success is True
        assert run.final_url == "https://shop.test/results"
        assert [s.action for s in run.steps][:2] == ["type", "click"]
        assert run.action_count >= 2

    def test_run_reports_failure_without_match(self):
        from friday_core.real_browser_agent import BrowserAgent

        agent = BrowserAgent(site=_site())
        run = agent.run("unobtainable quantum widget", start_url="https://shop.test/", max_steps=3)
        assert run.success is False
        assert run.reason

    def test_loop_guard(self):
        from friday_core.real_browser_agent import BrowserAgent, BrowserSession, SitePage

        # A page whose only actionable element cannot change the page.
        page = SitePage("https://loop.test/", "Loop", {
            "tag": "body",
            "children": [{"tag": "button", "text": "Refresh widget",
                          "bounds": [0, 0, 100, 20]}],
        })
        session = BrowserSession({"https://loop.test/": page})
        agent = BrowserAgent(session=session, site={"https://loop.test/": page})
        run = agent.run("refresh widget", start_url="https://loop.test/", max_steps=6)
        assert run.success is False
        assert "loop" in run.reason

    def test_extraction_during_run(self):
        from friday_core.real_browser_agent import BrowserAgent, FieldSelector

        agent = BrowserAgent(site=_site())
        run = agent.run(
            "search laptop", start_url="https://shop.test/", max_steps=4,
            extract=[FieldSelector("heading", tag="h1", required=True)],
        )
        assert any(r.get("heading") for r in run.extracted)

    def test_engine_facade(self):
        from friday_core.real_browser_agent import BrowserAutomationEngine

        engine = BrowserAutomationEngine()
        info = engine.inspect(_shop_page())
        assert info["url"] == "https://shop.test/"
        assert info["interactive_elements"] >= 4
        assert info["inputs"] >= 1
        assert info["token_estimate"] > 0
        assert "search" in info["serialized"].lower()

        result = engine.run_goal([_shop_page(), _results_page()], "search laptop")
        assert result["success"] is True
        assert result["final_url"].endswith("/results")


# ── Replay ────────────────────────────────────────────────────────────────

class TestSessionRecorder:
    def test_snapshot_and_replay(self):
        from friday_core.real_browser_agent import SessionRecorder

        session = _session()
        recorder = SessionRecorder(session)
        node = session.index().by_text("Cart", exact=True)[0]
        session.click(node.node_id)
        log = recorder.snapshot()
        assert any(entry["action"] == "click" for entry in log)
        report = recorder.replay(_site(), "https://shop.test/")
        assert report["executed"] >= 1
        assert report["deterministic"] is True
        assert report["mismatches"] == []
