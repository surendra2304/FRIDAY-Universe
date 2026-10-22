"""
Language and Framework Classifier and AI-Universe Prompt Router for Project FORGE.
"""

from enum import Enum


class TargetLanguage(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    FULLSTACK = "fullstack"


class TargetFramework(str, Enum):
    FASTAPI = "fastapi"
    FLASK = "flask"
    EXPRESS = "express"
    REACT = "react"
    NEXTJS = "nextjs"
    VUE = "vue"
    CLI = "cli"
    SCRIPT = "script"
    STATIC_WEB = "static_web"
    WEB_3D = "web_3d"


class LanguageDetector:
    """Classifies software requirements and goals into target language and framework."""

    @classmethod
    def detect(
        cls, goal: str, requirements: list[str] | None = None
    ) -> tuple[TargetLanguage, TargetFramework]:
        combined_text = f"{goal} {' '.join(requirements or [])}".lower()

        # Check for full-stack composite indicators
        is_fullstack = (
            ("frontend" in combined_text and "backend" in combined_text)
            or ("react" in combined_text and "fastapi" in combined_text)
            or ("next.js" in combined_text and "express" in combined_text)
            or ("full stack" in combined_text or "fullstack" in combined_text)
        )
        if is_fullstack:
            return TargetLanguage.FULLSTACK, TargetFramework.REACT

        # 3D, Lovable, Bolt, Durable website detection
        if any(
            k in combined_text
            for k in [
                "3d",
                "three.js",
                "threejs",
                "lovable",
                "bolt.new",
                "bolt",
                "durable",
                "futuristic",
                "web studio",
            ]
        ):
            return TargetLanguage.JAVASCRIPT, TargetFramework.WEB_3D

        # Framework detection
        if "next.js" in combined_text or "nextjs" in combined_text or "next js" in combined_text:
            return TargetLanguage.TYPESCRIPT, TargetFramework.NEXTJS

        if "react" in combined_text:
            if "typescript" in combined_text or "ts" in combined_text:
                return TargetLanguage.TYPESCRIPT, TargetFramework.REACT
            return TargetLanguage.JAVASCRIPT, TargetFramework.REACT

        if "vue" in combined_text or "vue.js" in combined_text or "vuejs" in combined_text:
            return TargetLanguage.JAVASCRIPT, TargetFramework.VUE

        if (
            "express" in combined_text
            or "express.js" in combined_text
            or "node.js" in combined_text
            or "nodejs" in combined_text
        ):
            if "typescript" in combined_text:
                return TargetLanguage.TYPESCRIPT, TargetFramework.EXPRESS
            return TargetLanguage.JAVASCRIPT, TargetFramework.EXPRESS

        if "typescript" in combined_text or ".ts" in combined_text:
            return TargetLanguage.TYPESCRIPT, TargetFramework.EXPRESS

        if "flask" in combined_text:
            return TargetLanguage.PYTHON, TargetFramework.FLASK

        if "fastapi" in combined_text or "api" in combined_text or "rest" in combined_text:
            return TargetLanguage.PYTHON, TargetFramework.FASTAPI

        if "cli" in combined_text or "command line" in combined_text or "argparse" in combined_text:
            return TargetLanguage.PYTHON, TargetFramework.CLI

        if (
            "html" in combined_text
            or "landing page" in combined_text
            or "portfolio" in combined_text
            or "website" in combined_text
        ):
            return TargetLanguage.PYTHON, TargetFramework.STATIC_WEB

        # Default fallback
        return TargetLanguage.PYTHON, TargetFramework.SCRIPT


class LanguagePromptRouter:
    """Generates language-specific prompts for AI-Universe reasoning personas."""

    @classmethod
    def format_persona_prompt(
        cls,
        language: TargetLanguage,
        framework: TargetFramework,
        filename: str,
        purpose: str,
    ) -> str:
        """Construct specialized prompt with framework idioms and mandatory security-first instructions."""
        if framework == TargetFramework.WEB_3D:
            return (
                f"Write complete, production-grade, highly aesthetic code for `{filename}` "
                f"following Lovable, Bolt.new, and Durable 3D website design standards.\n"
                f"Purpose: {purpose}\n\n"
                f"AESTHETIC & 3D REQUIREMENTS:\n"
                f"1. 3D Experience: Include interactive 3D WebGL (Three.js) canvas or smooth 60 FPS 2D particle canvas with mouse parallax interaction.\n"
                f"2. Visual Design: Modern glassmorphism (backdrop-filter blur, translucent cards, subtle gradients, glow blobs, CSS variables).\n"
                f"3. Bento Grid: Modular responsive layout with rich hover micro-interactions, badge chips, and 3D perspective tilt.\n"
                f"4. Zero Placeholders: Absolutely NO 'Lorem ipsum', 'Project Alpha', 'foo', or blank images. Synthesize rich domain-specific copy and metrics.\n"
                f"5. Dynamic Interactivity: Category filtering, modal preview, theme toggle (dark/light), and animated toasts.\n"
                f"6. Mobile Responsiveness: Fluid media queries, responsive navigation, accessible ARIA attributes.\n"
                f"Return ONLY the raw, complete, working code for `{filename}`."
            )

        lang_name = language.value.capitalize()
        framework_name = framework.value.capitalize()

        return (
            f"Write complete, production-grade {lang_name} code for `{filename}` "
            f"following modern {framework_name} best practices and design patterns.\n"
            f"Purpose: {purpose}\n"
            f"Language: {lang_name}\n"
            f"Framework: {framework_name}\n\n"
            f"MANDATORY SECURITY REQUIREMENTS:\n"
            f"1. Input Validation: Validate and sanitize all user-facing inputs and parameters (e.g. Pydantic schemas, regex, type constraints).\n"
            f"2. Injection Defense: Strictly use parameterized queries or ORM bindings for any database access (NEVER string concatenation or f-strings in SQL).\n"
            f"3. Error Handling: Catch exceptions cleanly without leaking internal stack traces or database schema details to end users.\n"
            f"4. Secure Defaults: Enforce least privilege, secure CORS configuration, and no hardcoded plaintext passwords, keys, or tokens.\n"
            f"5. Authentication & Authorization: Include security dependencies / guards on all state-changing or protected routes.\n"
            f"6. CSRF & Secure Headers: Apply CSRF protections on state-changing endpoints and set secure HTTP headers (X-Content-Type-Options, X-Frame-Options, CSP basics) where applicable.\n"
            f"Ensure strict syntax adherence, robust error handling, type definitions, and modular structure."
        )
