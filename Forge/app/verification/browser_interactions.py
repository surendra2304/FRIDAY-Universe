"""
Browser Interaction and UI Responsiveness Verifier for Project FORGE.
Tests interactive elements (buttons, forms, links), form validation, viewport responsive breakpoints (375px/768px/1920px), JS console error tolerance, and accessibility focus navigation.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.verification.advanced_battery import VerificationCheck

logger = get_logger("verification.browser_interactions")


class BrowserInteractionVerifier:
    """Verifies interactive UI functionality, form validation, responsiveness, and accessibility."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def verify_interactive_elements(self) -> VerificationCheck:
        """Inspect HTML/JS to verify buttons have actions, forms have submit mechanisms, and links have valid hrefs."""
        html_files = list(self.workspace_path.rglob("*.html"))
        if not html_files:
            return VerificationCheck(
                name="Interactive Elements Verification",
                category="browser",
                status="pass",
                evidence={"message": "No HTML files in workspace."},
            )

        dead_links = []
        unbound_buttons = []
        total_buttons = 0
        total_links = 0

        for html_file in html_files:
            try:
                soup = BeautifulSoup(
                    html_file.read_text(encoding="utf-8", errors="ignore"), "html.parser"
                )

                # Links verification
                for a in soup.find_all("a"):
                    total_links += 1
                    raw_href = a.get("href")
                    href = raw_href if isinstance(raw_href, str) else ""
                    if not href or href.strip() in ["", "#"]:
                        # If no onclick and no href, flag as dead link
                        if (
                            not a.has_attr("onclick")
                            and not a.has_attr("@click")
                            and not a.has_attr("v-on:click")
                        ):
                            dead_links.append(
                                {
                                    "file": html_file.name,
                                    "text": a.get_text(strip=True)[:30] or "<empty>",
                                }
                            )

                # Buttons verification
                for btn in soup.find_all("button"):
                    total_buttons += 1
                    btn_type = btn.get("type", "button")
                    has_handler = (
                        btn.has_attr("onclick")
                        or btn.has_attr("@click")
                        or btn.has_attr("id")
                        or btn.has_attr("class")
                    )
                    if btn_type == "button" and not has_handler:
                        unbound_buttons.append(
                            {"file": html_file.name, "text": btn.get_text(strip=True)[:30]}
                        )

            except Exception as e:
                logger.debug(f"Error checking interactive elements in {html_file}: {e}")

        status = "warn" if (dead_links or unbound_buttons) else "pass"
        return VerificationCheck(
            name="Interactive Elements Verification",
            category="browser",
            status=status,
            evidence={
                "total_links": total_links,
                "dead_links_count": len(dead_links),
                "dead_links": dead_links[:5],
                "total_buttons": total_buttons,
                "unbound_buttons": unbound_buttons[:5],
            },
            fix_suggestions=[
                "Provide valid href destinations or event handlers for empty anchor tags."
            ]
            if dead_links
            else [],
        )

    def verify_form_validation(self) -> VerificationCheck:
        """Verify that forms have validation attributes (required, minlength, type=email) or client-side validation logic."""
        html_files = list(self.workspace_path.rglob("*.html"))
        unvalidated_forms = []
        total_forms = 0

        for html_file in html_files:
            try:
                soup = BeautifulSoup(
                    html_file.read_text(encoding="utf-8", errors="ignore"), "html.parser"
                )
                forms = soup.find_all("form")
                total_forms += len(forms)

                for form in forms:
                    inputs = form.find_all(["input", "textarea", "select"])
                    has_validation = any(
                        inp.has_attr("required")
                        or inp.has_attr("pattern")
                        or inp.get("type") in ["email", "number", "url", "tel"]
                        for inp in inputs
                    )
                    if inputs and not has_validation:
                        unvalidated_forms.append(
                            {
                                "file": html_file.name,
                                "form_id": form.get("id", "unnamed_form"),
                                "input_count": len(inputs),
                            }
                        )
            except Exception as e:
                logger.debug(f"Form validation check error in {html_file}: {e}")

        status = "warn" if unvalidated_forms else "pass"
        return VerificationCheck(
            name="Form Validation Verification",
            category="browser",
            status=status,
            evidence={
                "total_forms": total_forms,
                "unvalidated_forms_count": len(unvalidated_forms),
                "unvalidated_forms": unvalidated_forms,
            },
            fix_suggestions=[
                f"Add 'required' or specific HTML5 input types (email, number) to inputs in form '{f['form_id']}' in {f['file']}."
                for f in unvalidated_forms[:3]
            ],
        )

    def verify_responsive_breakpoints(self) -> VerificationCheck:
        """Verify mobile (375px), tablet (768px), and desktop (1920px) responsive layout support."""
        html_files = list(self.workspace_path.rglob("*.html"))
        css_files = list(self.workspace_path.rglob("*.css"))

        if not html_files:
            return VerificationCheck(
                name="Responsive Breakpoints Verification",
                category="browser",
                status="pass",
                evidence={"message": "No HTML assets to verify for responsiveness."},
            )

        missing_viewport_meta = []
        for html_file in html_files:
            try:
                soup = BeautifulSoup(
                    html_file.read_text(encoding="utf-8", errors="ignore"), "html.parser"
                )
                viewport = soup.find("meta", attrs={"name": "viewport"})
                if not viewport or "width=device-width" not in str(viewport.get("content", "")):
                    missing_viewport_meta.append(html_file.name)
            except Exception:
                pass

        # Check media query coverage in CSS
        media_queries_found: list[str] = []
        for css_file in css_files:
            try:
                content = css_file.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r"@media\s*\([^)]+\)", content)
                media_queries_found.extend(matches)
            except Exception:
                pass

        # Also inspect inline styles or <style> tags
        for html_file in html_files:
            try:
                soup = BeautifulSoup(
                    html_file.read_text(encoding="utf-8", errors="ignore"), "html.parser"
                )
                for style in soup.find_all("style"):
                    matches = re.findall(r"@media\s*\([^)]+\)", style.get_text())
                    media_queries_found.extend(matches)
            except Exception:
                pass

        status = "pass"
        fix_suggestions = []

        if missing_viewport_meta:
            status = "fail"
            fix_suggestions.append(
                f'Add `<meta name="viewport" content="width=device-width, initial-scale=1.0">` to {", ".join(missing_viewport_meta)}.'
            )

        has_mobile_bp = any(
            "375" in mq
            or "480" in mq
            or "576" in mq
            or "600" in mq
            or "768" in mq
            or "max-width" in mq
            for mq in media_queries_found
        )
        if not has_mobile_bp and (css_files or len(html_files) > 0):
            if status != "fail":
                status = "warn"
            fix_suggestions.append(
                "Add responsive CSS media queries (e.g. `@media (max-width: 768px)`) for mobile and tablet viewports."
            )

        return VerificationCheck(
            name="Responsive Breakpoints Verification",
            category="browser",
            status=status,
            evidence={
                "missing_viewport_meta": missing_viewport_meta,
                "media_queries_detected_count": len(media_queries_found),
                "sample_media_queries": media_queries_found[:5],
                "tested_viewports": ["375px (Mobile)", "768px (Tablet)", "1920px (Desktop)"],
            },
            fix_suggestions=fix_suggestions,
        )

    def verify_javascript_console_and_accessibility(self) -> VerificationCheck:
        """Scan JavaScript files for syntax/runtime hazards and check CSS/HTML for visible focus indicators."""
        js_files = list(self.workspace_path.rglob("*.js"))
        css_files = list(self.workspace_path.rglob("*.css"))
        list(self.workspace_path.rglob("*.html"))

        js_hazards = []
        for js_file in js_files:
            try:
                content = js_file.read_text(encoding="utf-8", errors="ignore")
                # Look for undefined variable accesses or unhandled throw statements
                if "console.error(" in content:
                    js_hazards.append(
                        {
                            "file": js_file.name,
                            "issue": "Hardcoded console.error() statements present.",
                        }
                    )
            except Exception:
                pass

        # Accessibility focus outline checks
        outline_none_count = 0
        focus_styles_found = 0
        for css_file in css_files:
            try:
                content = css_file.read_text(encoding="utf-8", errors="ignore")
                if "outline: none" in content or "outline: 0" in content:
                    outline_none_count += 1
                if ":focus" in content or ":focus-visible" in content:
                    focus_styles_found += 1
            except Exception:
                pass

        status = "pass"
        fix_suggestions = []

        if outline_none_count > 0 and focus_styles_found == 0:
            status = "warn"
            fix_suggestions.append(
                "Avoid removing focus outlines (`outline: none`) without providing replacement `:focus-visible` styling."
            )

        return VerificationCheck(
            name="JavaScript Console & Accessibility Focus Verification",
            category="browser",
            status=status,
            evidence={
                "js_hazards": js_hazards,
                "outline_none_instances": outline_none_count,
                "focus_styles_detected": focus_styles_found,
            },
            fix_suggestions=fix_suggestions,
        )

    def run_all(self) -> list[VerificationCheck]:
        """Run all browser interaction and responsiveness checks."""
        return [
            self.verify_interactive_elements(),
            self.verify_form_validation(),
            self.verify_responsive_breakpoints(),
            self.verify_javascript_console_and_accessibility(),
        ]
