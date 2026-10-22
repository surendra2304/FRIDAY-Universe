"""
ForgeWebStudio: Modern 3D and Futuristic Web Application Synthesis Engine.
"""

from app.templates.web_studio.design_system import (
    GOOGLE_FONTS_LINK,
    LUCIDE_ICONS_CDN,
    TAILWIND_CDN,
    THREE_JS_CDN,
    generate_modern_css_theme,
)
from app.templates.web_studio.domain_synthesizer import DomainBlueprint, DomainSynthesizer
from app.templates.web_studio.generator import ForgeWebStudio
from app.templates.web_studio.three_d_engine import (
    Web3DEngine,
    generate_3d_tilt_script,
    generate_three_d_scene_script,
)

__all__ = [
    "ForgeWebStudio",
    "DomainSynthesizer",
    "DomainBlueprint",
    "Web3DEngine",
    "generate_modern_css_theme",
    "generate_three_d_scene_script",
    "generate_3d_tilt_script",
    "TAILWIND_CDN",
    "LUCIDE_ICONS_CDN",
    "THREE_JS_CDN",
    "GOOGLE_FONTS_LINK",
]
