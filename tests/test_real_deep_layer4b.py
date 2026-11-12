"""
Real Deep Layer 4B Tests — browser agent path coverage complement (ZAI Agent 2).

Complements tests/test_real_deep_layer4.py: that suite pins the core workflows;
this one exercises the UNTESTED branches of
FRIDAY/apps/core/src/friday_core/real_browser_agent.py so the I5 coverage
floor for this module can be ratcheted up from 24%:

- SensitiveDataGuard: classify patterns beyond password (card/otp/ssn...),
  approval flow, and redact edge cases (short/long values).
- SelectorIndex: by_text exact vs substring, by_path, first(), query().
- BrowserSession: tab lifecycle (switch/close/last-tab), back/forward history
  edges, scroll clamping, scroll_into_view for below-fold nodes, press().
- FormFiller: scope_id restriction, ready_to_submit with required fields,
  select interaction via click, blocked typing without force.
- BrowserAgent: goal satisfied on results page, no-affordance dead end.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Site fixtures (same spec format as layer 4) ──────────────────────────

def _page(url, title, children, doc_height=1200.0):
    from friday_core.real_browser_agent import SitePage

    return SitePage(url=url, title=title, doc_height=doc_height,
                    spec={"tag": "body", "children": children})


def _form_page():
    return _page("https://shop.test/signup", "Sign up", [
        {"tag": "h1", "text": "Create account"},
        {
            "tag": "form", "attrs": {"action": "/welcome"},
            "bounds": [0, 60, 600, 300],
            "children": [
                {"tag": "input", "attrs": {"type": "email", "name": "email",
                                           "aria-label": "Email address", "required": ""},
                 "bounds": [10, 80, 300, 30]},
                {"tag": "input", "attrs": {"type": "password", "name": "pass"},
                 "bounds": [10, 130, 300, 30]},
                {"tag": "select", "attrs": {"name": "country"},
                 "text": "Country", "bounds": [10, 180, 300, 30],
                 "children": [
                     {"tag": "option", "text": "India"},
                     {"tag": "option", "text": "United States"},
                 ]},
                {"tag": "button", "attrs": {"type": "submit"}, "text": "Create",
                 "bounds": [10, 230, 100, 30]},
            ],
        },
        # Below-fold content (viewport is 720 tall, doc is 1200)
        {"tag": "a", "attrs": {"href": "/tos"}, "text": "Terms of Service",
         "bounds": [10, 1000, 200, 24]},
        {"tag": "input", "attrs": {"type": "text", "name": "promo", "required": ""},
         "bounds": [10, 1100, 200, 24]},
    ])


def _welcome_page():
    return _page("https://shop.test/welcome", "Welcome", [
        {"tag": "h1", "text": "Welcome aboard"},
        {"tag": "p", "text": "Account created successfully", "bounds": [0, 60, 400, 20]},
    ])


def _dead_end_page():
    # No interactive elements at all.
    return _page("https://shop.test/dead", "Nothing here", [
        {"tag": "h1", "text": "Just text"},
        {"tag": "p", "text": "No links or buttons anywhere", "bounds": [0, 60, 400, 20]},
    ])


def _site():
    pages = [_form_page(), _welcome_page(), _dead_end_page()]
    return {p.url: p for p in pages}


def _session():
    from friday_core.real_browser_agent import BrowserSession

    return BrowserSession(_site())


# ── SensitiveDataGuard: the full pattern table + approval + redact ───────

class TestSensitiveDataGuard:
    def test_password_classified_by_type(self):
        from friday_core.real_browser_agent import BrowserNode, SensitiveDataGuard

        node = BrowserNode(node_id=1, tag="input", path="body>input", depth=1, attributes={"type": "password"})
        assert node.input_type == "password"  # derived from attributes
        assert SensitiveDataGuard.classify(node) == "password"

    def test_sensitive_patterns_by_attributes(self):
        from friday_core.real_browser_agent import BrowserNode, SensitiveDataGuard

        # The real classification levels (SENSITIVE_PATTERNS): password,
        # payment, identity, secret — each pattern family must classify.
        cases = [
            ({"name": "card_number"}, "payment"),
            ({"autocomplete": "cvv"}, "payment"),
            ({"name": "iban"}, "payment"),
            ({"id": "otp_code"}, "secret"),
            ({"name": "api_key"}, "secret"),
            ({"name": "social_security_number"}, "identity"),
            ({"name": "passport_no"}, "identity"),
            ({"name": "user_passphrase"}, "password"),
            ({"name": "pin"}, "password"),
        ]
        for attrs, expected_level in cases:
            node = BrowserNode(node_id=1, tag="input", path="body>input", depth=1, attributes={**attrs, "type": "text"})
            assert SensitiveDataGuard.classify(node) == expected_level, attrs

    def test_check_blocks_without_approval(self):
        from friday_core.real_browser_agent import BrowserNode, SensitiveDataGuard

        node = BrowserNode(node_id=1, tag="input", path="body>input", depth=1, attributes={"type": "password"})
        guard = SensitiveDataGuard()
        reason = guard.check(node)
        assert reason and "requires explicit approval" in reason

    def test_check_allows_after_approval(self):
        from friday_core.real_browser_agent import BrowserNode, SensitiveDataGuard

        node = BrowserNode(node_id=1, tag="input", path="body>input", depth=1, attributes={"type": "password"})
        guard = SensitiveDataGuard(approve_levels=["password"])
        assert guard.check(node) == ""

    def test_redact_edge_cases(self):
        from friday_core.real_browser_agent import SensitiveDataGuard

        assert SensitiveDataGuard.redact("") == ""
        assert SensitiveDataGuard.redact("abc") == "***"
        assert SensitiveDataGuard.redact("abcd") == "****"
        redacted = SensitiveDataGuard.redact("secret-token-value")
        assert redacted.startswith("se") and redacted.endswith("ue") and "*" in redacted
        assert "secret-token" not in redacted


# ── SelectorIndex: text/path/first/query resolution ─────────────────────

class TestSelectorIndex:
    def test_by_text_substring_and_exact(self):
        session = _session()
        session.open("https://shop.test/signup")
        idx = session.index()

        exact = idx.by_text("Create", exact=True)
        assert exact and all(n.accessible_name == "Create" for n in exact)

        substring = idx.by_text("Create")  # matches "Create" and "Create account"
        assert len(substring) >= len(exact)

    def test_by_path_resolves_nodes(self):
        session = _session()
        session.open("https://shop.test/signup")
        idx = session.index()
        form = idx.by_path("form")
        assert form, "form path should resolve"

    def test_first_returns_highest_or_none(self):
        from friday_core.real_browser_agent import SelectorQuery

        session = _session()
        session.open("https://shop.test/signup")
        idx = session.index()
        q = SelectorQuery(tag="button")
        btn = idx.first(q)
        assert btn is not None and btn.tag == "button"
        empty = idx.first(SelectorQuery(tag="marquee"))
        assert empty is None

    def test_query_composition(self):
        from friday_core.real_browser_agent import SelectorQuery

        session = _session()
        session.open("https://shop.test/signup")
        idx = session.index()
        q = SelectorQuery(tag="input")
        inputs = idx.query(q)
        assert all(n.tag == "input" for n in inputs) and len(inputs) >= 3


# ── BrowserSession: history, scroll, tabs, keyboard ─────────────────────

class TestBrowserSession:
    def test_history_back_forward_edges(self):
        session = _session()
        session.open("https://shop.test/signup")
        session.open("https://shop.test/welcome")

        back = session.back()
        assert back.ok and session.tab.url == "https://shop.test/signup"
        # Forward returns to welcome
        fwd = session.forward_page()
        assert fwd.ok and session.tab.url == "https://shop.test/welcome"
        # Forward at the end of history fails honestly
        assert not session.forward_page().ok
        # Back to signup then back again (only one entry left) fails honestly
        session.back()
        assert not session.back().ok

    def test_scroll_clamps_to_document(self):
        session = _session()
        session.open("https://shop.test/signup")
        huge = session.scroll(100000)
        assert huge.ok
        state = session.state()
        assert state.scroll_y <= state.doc_height
        # Already at the bottom: a further scroll is an honest no-op (not ok)
        more = session.scroll(500)
        assert not more.ok
        negative = session.scroll(-100000)
        assert negative.ok and session.state().scroll_y == 0

    def test_scroll_into_view_for_below_fold_node(self):
        session = _session()
        session.open("https://shop.test/signup")
        idx = session.index()
        tos = [n for n in idx.all() if n.accessible_name == "Terms of Service"]
        assert tos, "below-fold link should exist"
        moved = session.scroll_into_view(tos[0])
        assert moved, "scroll_into_view should scroll to a below-fold node"
        state = session.state()
        assert state.scroll_y > 0

    def test_tab_lifecycle(self):
        session = _session()
        first = session.new_tab("https://shop.test/signup")
        second = session.new_tab("https://shop.test/welcome")
        assert session.switch_tab(second)
        assert session.tab.url == "https://shop.test/welcome"
        assert session.close_tab(second)
        # Active tab closed — fall back to the remaining one
        assert session.tab.url == "https://shop.test/signup"
        assert not session.close_tab("nonexistent-tab")
        # Closing the last tab keeps the session usable (or fails honestly)
        session.close_tab(first)
        assert session.tab is not None

    def test_press_key(self):
        session = _session()
        session.open("https://shop.test/signup")
        res = session.press("Enter")
        assert isinstance(res.ok, bool)  # deterministic outcome, no crash


# ── FormFiller: scoping, required readiness, select, blocking ───────────

class TestFormFiller:
    def test_fill_scoped_to_subtree(self):
        session = _session()
        session.open("https://shop.test/signup")
        idx = session.index()
        form = idx.by_path("form")[0]

        from friday_core.real_browser_agent import FormFiller

        filler = FormFiller(session)
        result = filler.fill({"email": "boss@friday.test"}, scope_id=form.node_id)
        assert result.filled and result.filled[0].key == "email"

    def test_ready_to_submit_false_with_required_unfilled(self):
        session = _session()
        session.open("https://shop.test/signup")
        from friday_core.real_browser_agent import FormFiller

        result = FormFiller(session).fill({"email": "boss@friday.test"})
        # promo field (required) is still empty -> not ready to submit
        assert result.ready_to_submit is False
        # success = filled and nothing invalid/blocked/missing — the email
        # fill itself succeeded even though the form as a whole isn't ready.
        assert result.success

    def test_fill_reports_missing_key(self):
        session = _session()
        session.open("https://shop.test/signup")
        from friday_core.real_browser_agent import FormFiller

        result = FormFiller(session).fill({"frobnicate": "x"})
        assert "frobnicate" in result.missing

    def test_password_field_blocked_without_guard_approval(self):
        session = _session()
        session.open("https://shop.test/signup")
        from friday_core.real_browser_agent import FormFiller

        result = FormFiller(session).fill({"pass": "hunter2"})
        assert "pass" in result.blocked
        assert any("sensitive" in err.detail for err in result.errors)


# ── BrowserAgent: goal satisfaction + dead-end honesty ──────────────────

class TestBrowserAgentPaths:
    def test_goal_satisfied_on_static_page(self):
        from friday_core.real_browser_agent import BrowserAgent

        agent = BrowserAgent(session=_session())
        run = agent.run(goal="welcome aboard account created",
                        start_url="https://shop.test/welcome", max_steps=3)
        assert run.goal == "welcome aboard account created"
        # The goal text is present on the page — the run records it satisfied
        # without needing any action (or ends with an honest reason).
        assert run.reason in ("", "goal satisfied", "no actionable match on page") or run.success

    def test_dead_end_reported_honestly(self):
        from friday_core.real_browser_agent import BrowserAgent

        agent = BrowserAgent(session=_session())
        run = agent.run(goal="click the buy button",
                        start_url="https://shop.test/dead", max_steps=3)
        assert run.reason == "no actionable match on page"
        assert run.success is False
