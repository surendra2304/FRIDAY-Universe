"""
ForgeWebStudio Design System: Modern Visual Architecture & Design Tokens.
Inspired by Lovable, Bolt.new, and modern 3D web design principles.
Provides production-grade CSS design systems, glassmorphism tokens, bento grids, and responsive layouts.
"""


# CDN References for World-Class Web Apps
TAILWIND_CDN = '<script src="https://cdn.tailwindcss.com"></script>'
LUCIDE_ICONS_CDN = '<script src="https://unpkg.com/lucide@latest"></script>'
GOOGLE_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;800&family=Inter:wght@300;400;500;600;700;800&family=Montserrat:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,400&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Share+Tech+Mono&family=Space+Grotesk:wght@500;700&family=Syne:wght@600;700;800&display=swap" rel="stylesheet">'
)
THREE_JS_CDN = '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>'


def generate_modern_css_theme(
    theme_name: str = "futuristic_dark",
    primary_color: str = "#6366f1",
    accent_glow: str = "#a855f7",
    font_heading: str | None = None,
    font_body: str | None = None,
    archetype: str | None = None,
) -> str:
    """Generate a complete, self-contained modern CSS design system tailored to design archetype."""
    eff_archetype = (archetype or theme_name or "modern_glass").lower()

    # Dynamic typography per archetype
    if "luxury" in eff_archetype:
        heading_font = font_heading or "'Cinzel', 'Playfair Display', serif"
        body_font = font_body or "'Montserrat', 'Inter', sans-serif"
        bg_base = "#0a0c10"
        bg_surface = "#121520"
        border_subtle = "rgba(212, 175, 55, 0.18)"
        border_glow = "rgba(212, 175, 55, 0.45)"
    elif "cyberpunk" in eff_archetype:
        heading_font = font_heading or "'Space Grotesk', sans-serif"
        body_font = font_body or "'Share Tech Mono', monospace"
        bg_base = "#060810"
        bg_surface = "#0d1120"
        border_subtle = "rgba(0, 240, 255, 0.18)"
        border_glow = "rgba(0, 240, 255, 0.5)"
    elif "mission_control" in eff_archetype or "dashboard" in eff_archetype:
        heading_font = font_heading or "'Space Grotesk', sans-serif"
        body_font = font_body or "'Inter', sans-serif"
        bg_base = "#060a14"
        bg_surface = "#0e1424"
        border_subtle = "rgba(6, 182, 212, 0.16)"
        border_glow = "rgba(6, 182, 212, 0.45)"
    elif "brutalist" in eff_archetype:
        heading_font = font_heading or "'Syne', sans-serif"
        body_font = font_body or "'Space Grotesk', sans-serif"
        bg_base = "#0f0f11"
        bg_surface = "#1a1a1f"
        border_subtle = "rgba(255, 230, 0, 0.3)"
        border_glow = "rgba(255, 230, 0, 0.6)"
    elif "apple" in eff_archetype or "saas" in eff_archetype:
        heading_font = font_heading or "'Plus Jakarta Sans', sans-serif"
        body_font = font_body or "'Inter', sans-serif"
        bg_base = "#08090e"
        bg_surface = "#0f121d"
        border_subtle = "rgba(255, 255, 255, 0.08)"
        border_glow = "rgba(99, 102, 241, 0.4)"
    else:
        heading_font = font_heading or "'Outfit', sans-serif"
        body_font = font_body or "'Inter', sans-serif"
        bg_base = "#090d16"
        bg_surface = "#0f172a"
        border_subtle = "rgba(255, 255, 255, 0.08)"
        border_glow = "rgba(99, 102, 241, 0.4)"

    return f"""/* ==========================================================================
   FORGE WebStudio 3.0 — Bespoke Design System [{eff_archetype.upper()}]
   ========================================================================== */

:root {{
    --font-primary: {body_font};
    --font-heading: {heading_font};
    --font-body: {body_font};
    --font-mono: 'Share Tech Mono', monospace;

    /* Dynamic Theme Colors */
    --primary: {primary_color};
    --primary-hover: {primary_color};
    --primary-light: rgba(99, 102, 241, 0.15);
    --accent: {accent_glow};
    --accent-glow: rgba(168, 85, 247, 0.4);

    /* Dark Surface Foundations (Default) */
    --bg-base: {bg_base};
    --bg-surface: {bg_surface};
    --bg-surface-elevated: #1e293b;
    --border-subtle: {border_subtle};
    --border-highlight: rgba(255, 255, 255, 0.18);
    --border-glow: {border_glow};

    /* Glassmorphism Tokens */
    --glass-bg: rgba(15, 23, 42, 0.65);
    --glass-border: rgba(255, 255, 255, 0.1);
    --glass-blur: blur(16px);
    --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);

    /* Text Hierarchy */
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;

    /* Status Indicators */
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;

    /* Animations & Transitions */
    --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-smooth: 300ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-bounce: 500ms cubic-bezier(0.34, 1.56, 0.64, 1);
}}

/* Light Mode Overrides */
[data-theme="light"] {{
    --bg-base: #f8fafc;
    --bg-surface: #ffffff;
    --bg-surface-elevated: #f1f5f9;
    --border-subtle: rgba(0, 0, 0, 0.08);
    --border-highlight: rgba(0, 0, 0, 0.15);
    --border-glow: rgba(99, 102, 241, 0.3);

    --glass-bg: rgba(255, 255, 255, 0.75);
    --glass-border: rgba(0, 0, 0, 0.08);
    --glass-shadow: 0 8px 24px 0 rgba(148, 163, 184, 0.2);

    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
}}

/* Global Reset & Box-Sizing */
*, *::before, *::after {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

html {{
    scroll-behavior: smooth;
    font-size: 16px;
}}

body {{
    font-family: var(--font-body);
    background-color: var(--bg-base);
    color: var(--text-primary);
    line-height: 1.6;
    overflow-x: hidden;
    position: relative;
    min-height: 100vh;
    transition: background-color var(--transition-smooth), color var(--transition-smooth);
}}

/* Background Ambient Glow */
.ambient-glow-layer {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
}}

.ambient-orb {{
    position: absolute;
    border-radius: 50%;
    filter: blur(120px);
    opacity: 0.25;
    animation: floatOrb 20s ease-in-out infinite alternate;
}}

.orb-1 {{
    top: -10%;
    left: -10%;
    width: 50vw;
    height: 50vw;
    background: radial-gradient(circle, var(--primary) 0%, transparent 70%);
}}

.orb-2 {{
    bottom: -15%;
    right: -10%;
    width: 60vw;
    height: 60vw;
    background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
    animation-delay: -7s;
}}

@keyframes floatOrb {{
    0% {{ transform: translate(0, 0) scale(1); }}
    100% {{ transform: translate(60px, 40px) scale(1.1); }}
}}

/* Typography */
h1, h2, h3, h4, h5, h6 {{
    font-family: var(--font-heading);
    font-weight: 700;
    line-height: 1.2;
    color: var(--text-primary);
}}

.gradient-text {{
    background: linear-gradient(135deg, var(--text-primary) 0%, var(--primary) 50%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: inline-block;
}}

/* Glassmorphism Containers */
.glass-panel {{
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    box-shadow: var(--glass-shadow);
    border-radius: 1rem;
}}

.glass-card {{
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: 1rem;
    padding: 1.5rem;
    transition: transform var(--transition-smooth), border-color var(--transition-smooth), box-shadow var(--transition-smooth);
    position: relative;
    overflow: hidden;
}}

.glass-card:hover {{
    transform: translateY(-4px);
    border-color: var(--border-glow);
    box-shadow: 0 12px 30px -10px var(--accent-glow);
}}

.tilt-card {{
    transform-style: preserve-3d;
    will-change: transform;
}}

/* Bento Grid Architecture */
.bento-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.5rem;
}}

@media (min-width: 1024px) {{
    .bento-grid-3 {{
        grid-template-columns: repeat(3, 1fr);
    }}
    .bento-col-span-2 {{
        grid-column: span 2;
    }}
}}

/* Modern Buttons */
.btn-modern {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    font-family: var(--font-primary);
    font-weight: 600;
    font-size: 0.95rem;
    border-radius: 0.75rem;
    border: none;
    cursor: pointer;
    text-decoration: none;
    transition: all var(--transition-smooth);
}}

.btn-primary {{
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%);
    color: #ffffff;
    box-shadow: 0 4px 20px -2px var(--accent-glow);
}}

.btn-primary:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 25px 0 var(--accent-glow);
}}

.btn-glass {{
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    color: var(--text-primary);
}}

.btn-glass:hover {{
    background: var(--bg-surface-elevated);
    border-color: var(--border-highlight);
    transform: translateY(-2px);
}}

/* Interactive Canvas / 3D Container */
.canvas-container {{
    position: relative;
    width: 100%;
    overflow: hidden;
}}

.hero-canvas {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: auto;
    z-index: 1;
}}

.hero-content {{
    position: relative;
    z-index: 2;
    pointer-events: none;
}}

.hero-content * {{
    pointer-events: auto;
}}

/* Badges and Tags */
.pill-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-radius: 9999px;
    background: var(--primary-light);
    color: var(--primary);
    border: 1px solid rgba(99, 102, 241, 0.3);
}}

/* Toast Notifications */
.toast-container {{
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    pointer-events: none;
}}

.toast {{
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    border-radius: 0.75rem;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-highlight);
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    color: var(--text-primary);
    font-size: 0.9rem;
    transform: translateY(20px);
    opacity: 0;
    transition: all var(--transition-bounce);
}}

.toast.show {{
    transform: translateY(0);
    opacity: 1;
}}

/* Interactive 3D HUD Controls Bar */
.hud-controls-bar {{
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--border-subtle);
    padding: 0.4rem 0.8rem;
    border-radius: 9999px;
    box-shadow: var(--glass-shadow);
    z-index: 10;
    transition: border-color var(--transition-smooth);
}}

.hud-controls-bar:hover {{
    border-color: var(--border-glow);
}}

.btn-hud {{
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.35rem 0.75rem;
    border-radius: 9999px;
    transition: all var(--transition-fast);
}}

.btn-hud:hover, .btn-hud.active {{
    background: var(--primary-light);
    color: var(--primary);
}}

/* Telemetry Metrics Strip */
.telemetry-strip {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1.5rem;
    text-align: center;
    padding: 1.5rem;
}}

.telemetry-item .stat-number {{
    font-size: 2.25rem;
    font-weight: 800;
    font-family: var(--font-heading);
    line-height: 1.1;
}}

.telemetry-item .stat-label {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    display: block;
    margin-top: 0.35rem;
}}

/* Cyber Command Terminal */
.terminal-container {{
    background: var(--bg-surface);
    border: 1px solid var(--border-glow);
    border-radius: 1rem;
    overflow: hidden;
    box-shadow: 0 16px 40px -10px var(--accent-glow);
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}}

.terminal-header {{
    background: rgba(0, 0, 0, 0.4);
    padding: 0.75rem 1.25rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border-subtle);
}}

.terminal-dots {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}

.terminal-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
}}

.terminal-output {{
    padding: 1.25rem;
    min-height: 160px;
    max-height: 240px;
    overflow-y: auto;
    font-size: 0.85rem;
    line-height: 1.6;
    color: #a5f3fc;
    background: rgba(5, 10, 20, 0.9);
}}

.terminal-input-row {{
    display: flex;
    align-items: center;
    padding: 0.6rem 1.25rem;
    background: rgba(0, 0, 0, 0.5);
    border-top: 1px solid var(--border-subtle);
    gap: 0.5rem;
}}

.terminal-prompt {{
    color: var(--primary);
    font-weight: bold;
    font-size: 0.85rem;
}}

.terminal-input {{
    flex: 1;
    background: transparent;
    border: none;
    color: #ffffff;
    font-family: inherit;
    font-size: 0.85rem;
    outline: none;
}}

.terminal-chips {{
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem 1.25rem;
    background: rgba(0, 0, 0, 0.6);
    flex-wrap: wrap;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}}

.terminal-chip {{
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-family: inherit;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all var(--transition-fast);
}}

.terminal-chip:hover {{
    background: var(--primary-light);
    border-color: var(--primary);
    color: var(--primary);
}}

/* ==========================================================================
   Domain-Specific Component Architectures (E-Commerce, SaaS, Dashboard)
   ========================================================================== */

/* Cart Drawer (E-Commerce) */
.cart-drawer-backdrop {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(6px);
    z-index: 1000;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
}}
.cart-drawer-backdrop.open {{
    opacity: 1;
    pointer-events: auto;
}}
.cart-drawer {{
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(440px, 100vw);
    background: var(--bg-surface);
    border-left: 1px solid var(--border-highlight);
    z-index: 1001;
    transform: translateX(100%);
    transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    display: flex;
    flex-direction: column;
    box-shadow: -10px 0 35px rgba(0, 0, 0, 0.5);
}}
.cart-drawer.open {{
    transform: translateX(0);
}}
.cart-drawer-header {{
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.cart-drawer-body {{
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
}}
.cart-drawer-footer {{
    padding: 1.25rem 1.5rem;
    border-top: 1px solid var(--border-subtle);
    background: rgba(0, 0, 0, 0.2);
}}
.cart-badge {{
    background: var(--primary);
    color: #ffffff;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    margin-left: 0.35rem;
}}

/* Pricing Toggle & Cards (SaaS) */
.pricing-toggle-bar {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    margin-bottom: 2.5rem;
}}
.toggle-switch-track {{
    width: 52px;
    height: 28px;
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 9999px;
    position: relative;
    cursor: pointer;
    transition: all var(--transition-fast);
}}
.toggle-switch-thumb {{
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--primary);
    position: absolute;
    top: 3px;
    left: 4px;
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}
.toggle-switch-track.annual .toggle-switch-thumb {{
    transform: translateX(24px);
}}
.pricing-card {{
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    padding: 2.25rem;
    border-radius: 1.25rem;
    position: relative;
    transition: all var(--transition-smooth);
}}
.pricing-card.featured {{
    border-color: var(--primary);
    box-shadow: 0 0 35px -5px var(--accent-glow);
}}

/* Telemetry Table & Gauges (Dashboard) */
.telemetry-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}}
.telemetry-table th {{
    text-align: left;
    padding: 0.85rem 1rem;
    color: var(--text-muted);
    font-weight: 600;
    border-bottom: 1px solid var(--border-subtle);
    background: rgba(0, 0, 0, 0.2);
}}
.telemetry-table td {{
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-secondary);
}}
.telemetry-table tr:hover td {{
    background: rgba(255, 255, 255, 0.02);
    color: var(--text-primary);
}}
.status-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.2rem 0.65rem;
    border-radius: 9999px;
}}
.status-pill.nominal {{
    background: rgba(16, 185, 129, 0.15);
    color: var(--success);
    border: 1px solid rgba(16, 185, 129, 0.3);
}}
.status-pill.warning {{
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning);
    border: 1px solid rgba(245, 158, 11, 0.3);
}}
.status-pill.incident {{
    background: rgba(239, 68, 68, 0.15);
    color: var(--danger);
    border: 1px solid rgba(239, 68, 68, 0.3);
}}

/* ==========================================================================
   Lovable & Bolt-Caliber Split Hero & 3D Holographic Viewport Architecture
   ========================================================================== */

/* Modern Subtle Dot Grid Background */
body {{
    background-image: radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px);
    background-size: 28px 28px;
    background-position: center top;
}}

/* 2-Column Split Hero Section */
.hero-split-section {{
    position: relative;
    padding: 3rem 1.5rem 4.5rem 1.5rem;
    overflow: hidden;
    min-height: 84vh;
    display: flex;
    align-items: center;
}}

.hero-split-container {{
    max-width: 1280px;
    margin: 0 auto;
    width: 100%;
    display: grid;
    grid-template-columns: 1.12fr 0.88fr;
    gap: 3.5rem;
    align-items: center;
    position: relative;
    z-index: 10;
}}

@media (max-width: 980px) {{
    .hero-split-container {{
        grid-template-columns: 1fr;
        gap: 2.5rem;
        text-align: center;
    }}
}}

.hero-copy-col {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
}}

@media (max-width: 980px) {{
    .hero-copy-col {{
        align-items: center;
        text-align: center;
    }}
}}

.hero-title {{
    font-size: clamp(2.3rem, 4.5vw, 4.0rem);
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.035em;
    margin-bottom: 1.25rem;
    color: var(--text-primary);
}}

.hero-title .gradient-text {{
    background: linear-gradient(135deg, #ffffff 25%, var(--primary) 70%, var(--secondary) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}

.hero-subheadline {{
    font-size: clamp(1.05rem, 1.8vw, 1.2rem);
    line-height: 1.65;
    color: var(--text-secondary);
    margin-bottom: 2.25rem;
    max-width: 580px;
}}

.hero-cta-group {{
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 2.5rem;
}}

@media (max-width: 980px) {{
    .hero-cta-group {{
        justify-content: center;
    }}
}}

/* Trust / Social Proof Band */
.hero-trust-band {{
    display: flex;
    align-items: center;
    gap: 1rem;
    padding-top: 1.25rem;
    border-top: 1px solid var(--border-subtle);
}}

.avatar-stack {{
    display: flex;
    align-items: center;
}}

.avatar-stack .avatar-circle {{
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 2px solid var(--bg-base);
    margin-left: -8px;
    background: var(--bg-surface-elevated);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-primary);
}}

.avatar-stack .avatar-circle:first-child {{
    margin-left: 0;
}}

.trust-rating {{
    display: flex;
    flex-direction: column;
    font-size: 0.8rem;
    line-height: 1.3;
}}

.trust-stars {{
    color: #fbbf24;
    font-size: 0.85rem;
    letter-spacing: 2px;
}}

.trust-text {{
    color: var(--text-muted);
    font-weight: 500;
}}

/* Dedicated 3D Holographic Stage Viewport Card */
.hero-stage-col {{
    position: relative;
    width: 100%;
}}

.viewport-card {{
    position: relative;
    background: radial-gradient(circle at 50% 15%, rgba(99, 102, 241, 0.12), rgba(15, 23, 42, 0.75));
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid var(--border-highlight);
    border-radius: 1.5rem;
    box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.7), inset 0 1px 1px 0 rgba(255, 255, 255, 0.15);
    overflow: hidden;
    transition: transform var(--transition-smooth), box-shadow var(--transition-smooth);
}}

.viewport-card:hover {{
    box-shadow: 0 30px 70px -10px var(--accent-glow), inset 0 1px 1px 0 rgba(255, 255, 255, 0.25);
}}

.viewport-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 1.25rem;
    border-bottom: 1px solid var(--border-subtle);
    background: rgba(0, 0, 0, 0.25);
}}

.window-dots {{
    display: flex;
    gap: 6px;
}}

.window-dots .dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
}}

.window-dots .dot.red {{ background: #ef4444; }}
.window-dots .dot.yellow {{ background: #f59e0b; }}
.window-dots .dot.green {{ background: #10b981; }}

.viewport-title-badge {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}

.viewport-title-badge .status-dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
}}

.viewport-actions {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}

.view-pill {{
    padding: 0.25rem 0.65rem;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: var(--glass-bg);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}}

.view-pill:hover, .view-pill.active {{
    background: var(--primary);
    color: #ffffff;
    border-color: var(--primary);
}}

/* Dedicated 3D Canvas Viewport Box */
.canvas-wrapper {{
    position: relative;
    width: 100%;
    height: 440px;
    background: transparent;
    overflow: hidden;
}}

.canvas-wrapper canvas {{
    width: 100% !important;
    height: 100% !important;
    display: block;
    cursor: grab;
}}

.canvas-wrapper canvas:active {{
    cursor: grabbing;
}}

/* Corner Floating Viewport Chips */
.viewport-chip {{
    position: absolute;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.35rem 0.75rem;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--border-highlight);
    color: var(--text-primary);
    pointer-events: none;
    z-index: 5;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}}

.viewport-chip.chip-top-right {{
    top: 1rem;
    right: 1rem;
}}

.viewport-chip.chip-bottom-left {{
    bottom: 1rem;
    left: 1rem;
}}

.viewport-chip.chip-bottom-right {{
    bottom: 1rem;
    right: 1rem;
    color: var(--primary);
}}

/* 3D Viewport Footer & Live Color Customizer */
.viewport-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.25rem;
    border-top: 1px solid var(--border-subtle);
    background: rgba(0, 0, 0, 0.2);
}}

.model-color-picker {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}

.color-dot {{
    width: 18px;
    height: 18px;
    border-radius: 50%;
    cursor: pointer;
    border: 2px solid transparent;
    transition: transform 0.2s ease, border-color 0.2s ease;
}}

.color-dot:hover {{
    transform: scale(1.2);
}}

.color-dot.active {{
    border-color: #ffffff;
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.6);
    transform: scale(1.15);
}}

.model-stats {{
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
}}

/* Infinite Marquee Tech Ticker */
.marquee-container {{
    overflow: hidden;
    white-space: nowrap;
    position: relative;
    padding: 2rem 0;
    border-top: 1px solid var(--border-subtle);
    border-bottom: 1px solid var(--border-subtle);
    background: rgba(0, 0, 0, 0.15);
    margin: 2rem 0 4rem 0;
    mask-image: linear-gradient(to right, transparent, black 15%, black 85%, transparent);
    -webkit-mask-image: linear-gradient(to right, transparent, black 15%, black 85%, transparent);
}}

.marquee-content {{
    display: inline-flex;
    gap: 3.5rem;
    animation: marquee 30s linear infinite;
}}

@keyframes marquee {{
    from {{ transform: translateX(0); }}
    to {{ transform: translateX(-50%); }}
}}

.marquee-item {{
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-muted);
    opacity: 0.75;
    transition: opacity 0.2s ease, color 0.2s ease;
}}

.marquee-item:hover {{
    opacity: 1;
    color: var(--text-primary);
}}
"""
