"""TASK-IG-FRG-07: build-template pack from the IG corpus.

Four corpus items describe *starting points* Forge should be able to
build from without re-deriving the shape every time:

* DZm0KTppMuD — the no-money SaaS stack: Supabase + Next.js + Vercel +
  Stripe/DodoPayments;
* DeJnEzVpp2o — a solo founder's build-to-launch tool stack, as a
  checklist spanning idea -> code -> backend -> deploy -> payments ->
  launch -> marketing;
* DfHw7hsIfvd — one-prompt agent creation: a plain-language prompt
  becomes a configured, working agent;
* DfMhyC7Ma31 — autonomous website building from a brief (a portfolio
  site, end to end).

Each becomes a :class:`BuildTemplate`: the stack, the explicit file
manifest (the FRG-004 contract shape — a build from a template must
produce exactly these files), the environment *names* it needs
(never values), the ordered build steps, and the honest constraints.
:func:`render_goal` turns a template + a project name into the Forge
goal text for the build.

Fleet rules baked into the templates, not left to chance:

* payments templates are **test-mode only** — live payment keys are
  the owner's decision, never a template default;
* the agent template routes model calls through FRIDAY's Inference
  gateway — it declares no direct provider API keys;
* every stack named here is free-tier at build time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class TemplateFile:
    path: str
    purpose: str


@dataclass(frozen=True)
class BuildTemplate:
    name: str
    title: str
    description: str
    source_shortcodes: Tuple[str, ...]
    stack: Tuple[str, ...]
    files: Tuple[TemplateFile, ...]
    env_vars: Tuple[str, ...] = ()
    steps: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()

    def manifest_paths(self) -> List[str]:
        return [f.path for f in self.files]


def _files(*pairs: Tuple[str, str]) -> Tuple[TemplateFile, ...]:
    return tuple(TemplateFile(path=p, purpose=q) for p, q in pairs)


SAAS_STACK = BuildTemplate(
    name="saas-stack",
    title="Low-cost SaaS (Supabase + Next.js + Vercel + payments)",
    description=(
        "A subscription SaaS skeleton on free tiers: Next.js app, "
        "Supabase for auth + Postgres, Stripe or DodoPayments for "
        "checkout, deployed on Vercel."
    ),
    source_shortcodes=("DZm0KTppMuD",),
    stack=("Next.js", "Supabase (Postgres + Auth)", "Vercel", "Stripe / DodoPayments"),
    files=_files(
        ("package.json", "Project manifest with Next.js + Supabase client dependencies"),
        ("app/layout.tsx", "Root layout and global styles"),
        ("app/page.tsx", "Landing page with pricing section"),
        ("app/login/page.tsx", "Sign-in page wired to Supabase Auth"),
        ("app/dashboard/page.tsx", "Signed-in dashboard (protected route)"),
        ("lib/supabase/client.ts", "Supabase client built from environment variables"),
        ("lib/payments.ts", "Checkout session creation (provider selected by env)"),
        ("app/api/checkout/route.ts", "Checkout API route — creates a test-mode session"),
        ("supabase/schema.sql", "Tables: profiles, subscriptions (with RLS policies)"),
        (".env.example", "Every environment variable the app needs, names only"),
        ("README.md", "Setup, test-mode payments, and deploy instructions"),
    ),
    env_vars=(
        "NEXT_PUBLIC_SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "PAYMENTS_PROVIDER",
        "STRIPE_SECRET_KEY",
        "DODO_API_KEY",
        "NEXT_PUBLIC_APP_URL",
    ),
    steps=(
        "Scaffold the Next.js app and install the Supabase client",
        "Apply supabase/schema.sql and enable row-level security",
        "Wire Supabase Auth (email sign-in) and the protected dashboard route",
        "Wire checkout in TEST mode and verify a full test purchase",
        "Deploy to Vercel and set the environment variables there",
    ),
    notes=(
        "Payments stay in TEST mode: live keys are the owner's decision, never a template default.",
        "Free tiers only: Supabase free project, Vercel hobby, payment-provider test mode.",
    ),
)

SOLO_FOUNDER_LAUNCH = BuildTemplate(
    name="solo-founder-launch",
    title="Solo-founder build-to-launch checklist",
    description=(
        "The build-to-launch sequence as a Forge checklist build: the "
        "deliverable is a working launch pack — landing page, waitlist, "
        "and a checklist file that tracks every stage honestly."
    ),
    source_shortcodes=("DeJnEzVpp2o",),
    stack=("Static site", "Supabase (waitlist)", "Vercel / any static host"),
    files=_files(
        ("index.html", "Landing page: problem, product, one call to action"),
        ("style.css", "Landing page styles"),
        ("script.js", "Waitlist form wiring"),
        ("lib/waitlist.ts", "Waitlist insert into Supabase (email only, no tracking)"),
        ("docs/LAUNCH_CHECKLIST.md", "The stage-by-stage checklist with honest status per stage"),
        ("docs/PRICING.md", "Pricing draft: free tier + one paid tier, with the reasoning"),
        ("README.md", "What exists, what is stubbed, what is next"),
    ),
    env_vars=("NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    steps=(
        "Stage 1 — Idea: write the one-sentence problem + who has it (in LAUNCH_CHECKLIST.md)",
        "Stage 2 — Build: landing page + waitlist live on a free static host",
        "Stage 3 — Backend: Supabase waitlist table with RLS",
        "Stage 4 — Payments: draft pricing (docs/PRICING.md); no live checkout at this stage",
        "Stage 5 — Launch: announcement copy drafted; publishing is the owner's action",
        "Stage 6 — Measure: waitlist count is the only metric claimed, read from the table",
    ),
    notes=(
        "Each checklist stage is marked done only with evidence (a URL, a row count) — never by assertion.",
        "Marketing actions that publish externally are the owner's to trigger.",
    ),
)

ONE_PROMPT_AGENT = BuildTemplate(
    name="one-prompt-agent",
    title="One-prompt agent scaffold",
    description=(
        "A single-file Python agent generated from one plain-language "
        "prompt: a tool registry, a system prompt built from the "
        "owner's description, and model calls routed through FRIDAY's "
        "Inference gateway."
    ),
    source_shortcodes=("DfHw7hsIfvd",),
    stack=("Python 3.10", "FRIDAY Inference gateway (OpenAI-compatible)"),
    files=_files(
        ("agent.py", "The agent: prompt assembly, tool loop, honest error surfacing"),
        ("tools.py", "Tool registry — each tool is a small typed function with a docstring contract"),
        ("requirements.txt", "Runtime dependencies (httpx only)"),
        ("README.md", "The originating prompt, how to run, what the agent can and cannot do"),
    ),
    env_vars=("INFERENCE_BASE_URL", "INFERENCE_API_KEY", "AGENT_MODEL"),
    steps=(
        "Turn the owner's one prompt into the agent's system prompt (stored verbatim in README.md)",
        "Scaffold agent.py + tools.py with two starter tools (read a file, call Inference)",
        "Smoke test: one real Inference call; a failure is reported, not mocked over",
        "Register the agent's name + prompt in the README so it can be rebuilt identically",
    ),
    notes=(
        "Model access is via the Inference gateway only — the template declares no direct provider keys.",
        "The agent must fail loudly when Inference is unreachable; a canned reply is a defect.",
    ),
)

PORTFOLIO_WEBSITE = BuildTemplate(
    name="portfolio-website",
    title="Portfolio website from a brief",
    description=(
        "The corpus's 'agent builds a portfolio site end-to-end' shape: "
        "a static portfolio generated from a short brief — hero, about, "
        "projects, contact — with no build step."
    ),
    source_shortcodes=("DfMhyC7Ma31",),
    stack=("Static HTML/CSS/JS",),
    files=_files(
        ("index.html", "Single-page portfolio: hero, about, projects, contact sections"),
        ("style.css", "Portfolio styles (responsive, reduced-motion safe)"),
        ("script.js", "Project filtering + contact form validation (no backend)"),
        ("assets/projects.json", "Project entries rendered by script.js — edit data, not markup"),
        ("README.md", "The brief it was built from + how to customise"),
    ),
    env_vars=(),
    steps=(
        "Expand the brief into sections and project entries (assets/projects.json)",
        "Build index.html + style.css from the brief's tone",
        "Wire project filtering and form validation in script.js",
        "Verify: every project in the JSON renders; no external assets required at runtime",
    ),
    notes=(
        "Content comes from the brief; the build must not invent projects, employers, or metrics.",
    ),
)

TEMPLATES: Dict[str, BuildTemplate] = {
    t.name: t
    for t in (SAAS_STACK, SOLO_FOUNDER_LAUNCH, ONE_PROMPT_AGENT, PORTFOLIO_WEBSITE)
}


def list_templates() -> List[BuildTemplate]:
    return [TEMPLATES[name] for name in sorted(TEMPLATES)]


def get_template(name: str) -> BuildTemplate:
    if name not in TEMPLATES:
        raise KeyError(
            f"unknown template: {name} (available: {', '.join(sorted(TEMPLATES))})"
        )
    return TEMPLATES[name]


def render_goal(template: BuildTemplate, project_name: str) -> str:
    """The Forge build goal for a template + project name."""
    if not project_name or not project_name.strip():
        raise ValueError("project_name is required")
    lines = [
        f"Build '{project_name}' from the '{template.name}' template: {template.title}.",
        "",
        f"Template: {template.description}",
        f"Stack: {', '.join(template.stack)}",
        "",
        "The build MUST produce exactly these files:",
    ]
    for entry in template.files:
        lines.append(f"- {entry.path} — {entry.purpose}")
    if template.env_vars:
        lines.append("")
        lines.append(
            "Environment variables the project needs (names only — values "
            "come from the owner's environment, never hardcode them): "
            + ", ".join(template.env_vars)
        )
    if template.steps:
        lines.append("")
        lines.append("Build steps, in order:")
        for i, step in enumerate(template.steps, start=1):
            lines.append(f"{i}. {step}")
    if template.notes:
        lines.append("")
        lines.append("Constraints:")
        for note in template.notes:
            lines.append(f"- {note}")
    return "\n".join(lines)


def validate_templates() -> List[str]:
    """Structural checks over the pack; empty list = consistent."""
    problems: List[str] = []
    for template in TEMPLATES.values():
        if not template.files:
            problems.append(f"template {template.name} has no files")
        paths = template.manifest_paths()
        if len(paths) != len(set(paths)):
            problems.append(f"template {template.name} has duplicate file paths")
        if not template.steps:
            problems.append(f"template {template.name} has no steps")
        for var in template.env_vars:
            if var != var.upper() or " " in var:
                problems.append(
                    f"template {template.name} has a malformed env var name: {var}"
                )
    return problems
