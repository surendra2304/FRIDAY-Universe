"""
Starter Code and Component Template Catalog for Project FORGE.
"""

# --- 1. Base Project Templates ---

HTML_WEBSITE_BASE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@600;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body class="{{body_class}}">
    <!-- Interactive 3D WebGL / Particle Canvas -->
    <div class="canvas-container">
        <canvas id="forge-3d-canvas" class="webgl-canvas"></canvas>
    </div>

    <!-- Background Glow Blobs -->
    <div class="glow-orb glow-orb-1" aria-hidden="true"></div>
    <div class="glow-orb glow-orb-2" aria-hidden="true"></div>

    <header class="site-header glass-panel">
        <nav class="navbar" aria-label="Main Navigation">
            <a href="#" class="nav-brand">
                <span class="brand-badge">3D</span>
                <span class="brand-text">{{brand_name}}</span>
            </a>
            <div class="nav-links">
                <a href="#about" class="nav-link">Overview</a>
                <a href="#showcase" class="nav-link">Showcase</a>
                <a href="#contact" class="nav-link">Connect</a>
            </div>
            <div class="nav-actions">
                <button id="theme-toggle" class="btn btn-icon" aria-label="Toggle Dark / Light Theme">
                    <span class="theme-icon">🌓</span>
                </button>
                <a href="#showcase" class="btn btn-primary btn-glow">Launch</a>
            </div>
        </nav>
    </header>

    <main id="main-content">
        <section id="hero" class="hero-section">
            <div class="container hero-container">
                <div class="hero-badge">
                    <span class="pulse-dot"></span>
                    <span>Autonomous 3D Experience</span>
                </div>
                <h1 class="hero-title gradient-text">{{hero_title}}</h1>
                <p class="hero-subtitle">{{hero_subtitle}}</p>
                <div class="hero-actions">
                    <a href="#showcase" class="btn btn-primary btn-glow">Explore Works</a>
                    <a href="#contact" class="btn btn-secondary glass-panel">Get in Touch</a>
                </div>
                <div class="hero-metrics">
                    <div class="metric-chip glass-panel">
                        <span class="metric-val">60 FPS</span>
                        <span class="metric-label">Interactive 3D</span>
                    </div>
                    <div class="metric-chip glass-panel">
                        <span class="metric-val">100%</span>
                        <span class="metric-label">Responsive</span>
                    </div>
                    <div class="metric-chip glass-panel">
                        <span class="metric-val">Ultra</span>
                        <span class="metric-label">Glassmorphic</span>
                    </div>
                </div>
            </div>
        </section>

        <section id="about" class="section">
            <div class="container">
                <div class="section-header">
                    <h2 class="section-title">Architectural Vision</h2>
                    <p class="section-subtitle">Engineered for immersion, fluid interactions, and tactile responsiveness.</p>
                </div>
                <div class="glass-card about-card">
                    <p>{{about_description}}</p>
                </div>
            </div>
        </section>

        <section id="showcase" class="section">
            <div class="container">
                <div class="section-header">
                    <h2 class="section-title">Featured Showcase</h2>
                    <p class="section-subtitle">Real-time dynamic filtering and interactive 3D perspective tilt.</p>
                    <div class="filter-bar">
                        <button class="filter-btn active" data-filter="all">All</button>
                        <button class="filter-btn" data-filter="featured">Featured</button>
                        <button class="filter-btn" data-filter="core">Core</button>
                    </div>
                </div>
                <div class="bento-grid" id="showcase-grid">
                    <article class="bento-item glass-card tilt-card" data-category="featured">
                        <div class="bento-badge">Real-Time</div>
                        <h3 class="bento-title">Autonomous Synthesis</h3>
                        <p class="bento-desc">Zero-placeholder architecture, automated layout composition, and dynamic 3D rendering.</p>
                        <div class="bento-meta">
                            <span class="tech-tag">WebGL</span>
                            <span class="tech-tag">Three.js</span>
                            <span class="tech-tag">ES6</span>
                        </div>
                    </article>
                    <article class="bento-item glass-card tilt-card" data-category="core">
                        <div class="bento-badge">Performance</div>
                        <h3 class="bento-title">Tactile Glassmorphism</h3>
                        <p class="bento-desc">Subtle backdrop blur, gradient borders, and hardware-accelerated micro-interactions.</p>
                        <div class="bento-meta">
                            <span class="tech-tag">CSS3</span>
                            <span class="tech-tag">Variables</span>
                            <span class="tech-tag">Backdrop Filter</span>
                        </div>
                    </article>
                </div>
            </div>
        </section>

        <section id="contact" class="section">
            <div class="container">
                <div class="section-header">
                    <h2 class="section-title">Initiate Contact</h2>
                    <p class="section-subtitle">Deploy your project or connect with our engineering team.</p>
                </div>
                <div class="glass-card contact-card">
                    <form id="contact-form" class="contact-form">
                        <div class="form-group">
                            <label for="name">Name</label>
                            <input type="text" id="name" name="name" required placeholder="Alex Rivera">
                        </div>
                        <div class="form-group">
                            <label for="email">Email</label>
                            <input type="email" id="email" name="email" required placeholder="alex@domain.com">
                        </div>
                        <div class="form-group">
                            <label for="message">Message</label>
                            <textarea id="message" name="message" rows="4" required placeholder="Tell us about your project vision..."></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary btn-glow">Transmit Message</button>
                    </form>
                </div>
            </div>
        </section>
    </main>

    <footer class="site-footer glass-panel">
        <div class="container footer-content">
            <p>&copy; 2026 {{brand_name}}. Engineered with Project FORGE Studio.</p>
        </div>
    </footer>

    <div id="toast" class="toast-notification" aria-live="polite"></div>
    <script src="app.js"></script>
</body>
</html>
"""

CSS_BASE = """:root {
    --bg-primary: #0a0e17;
    --bg-secondary: #111827;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --accent-primary: #6366f1;
    --accent-glow: rgba(99, 102, 241, 0.4);
    --border-color: rgba(255, 255, 255, 0.1);
    --card-bg: rgba(17, 24, 39, 0.65);
    --glass-blur: 16px;
    --shadow-soft: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    --shadow-glow: 0 0 25px rgba(99, 102, 241, 0.35);
    --radius-sm: 8px;
    --radius-md: 14px;
    --radius-lg: 22px;
}

[data-theme="light"], body.light-mode {
    --bg-primary: #f8fafc;
    --bg-secondary: #ffffff;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --accent-primary: #4f46e5;
    --accent-glow: rgba(79, 70, 229, 0.25);
    --border-color: rgba(0, 0, 0, 0.08);
    --card-bg: rgba(255, 255, 255, 0.75);
    --glass-blur: 16px;
    --shadow-soft: 0 10px 25px -5px rgba(0, 0, 0, 0.08);
    --shadow-glow: 0 0 20px rgba(79, 70, 229, 0.2);
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html {
    scroll-behavior: smooth;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    overflow-x: hidden;
    position: relative;
    min-height: 100vh;
    transition: background-color 0.3s ease, color 0.3s ease;
}

/* 3D Canvas Background */
.canvas-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 0;
    pointer-events: none;
}

.webgl-canvas {
    width: 100%;
    height: 100%;
    display: block;
}

/* Ambient Glow Blobs */
.glow-orb {
    position: fixed;
    border-radius: 50%;
    filter: blur(120px);
    z-index: 0;
    pointer-events: none;
    opacity: 0.45;
}

.glow-orb-1 {
    top: 5%;
    left: 15%;
    width: 380px;
    height: 380px;
    background: radial-gradient(circle, var(--accent-primary) 0%, transparent 70%);
}

.glow-orb-2 {
    bottom: 10%;
    right: 10%;
    width: 450px;
    height: 450px;
    background: radial-gradient(circle, #ec4899 0%, transparent 70%);
}

/* Glassmorphism Classes */
.glass-panel {
    background: var(--card-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--border-color);
}

.glass-card {
    background: var(--card-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-soft);
    padding: 1.75rem;
    transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}

.glass-card:hover {
    transform: translateY(-4px);
    border-color: rgba(99, 102, 241, 0.4);
    box-shadow: var(--shadow-glow);
}

.container {
    max-width: 1180px;
    margin: 0 auto;
    padding: 0 1.5rem;
    position: relative;
    z-index: 1;
}

/* Site Header */
.site-header {
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 1px solid var(--border-color);
}

.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1180px;
    margin: 0 auto;
    padding: 1rem 1.5rem;
}

.nav-brand {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    text-decoration: none;
    color: var(--text-primary);
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 1.3rem;
}

.brand-badge {
    background: linear-gradient(135deg, var(--accent-primary), #ec4899);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 800;
    padding: 0.15rem 0.45rem;
    border-radius: 6px;
    letter-spacing: 0.05em;
}

.nav-links {
    display: flex;
    gap: 2rem;
}

.nav-link {
    color: var(--text-secondary);
    text-decoration: none;
    font-weight: 500;
    font-size: 0.95rem;
    transition: color 0.2s ease;
}

.nav-link:hover {
    color: var(--text-primary);
}

.nav-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.65rem 1.4rem;
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.95rem;
    cursor: pointer;
    text-decoration: none;
    border: none;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-primary {
    background: linear-gradient(135deg, var(--accent-primary) 0%, #8b5cf6 100%);
    color: #ffffff;
}

.btn-glow {
    box-shadow: 0 0 15px var(--accent-glow);
}

.btn-glow:hover {
    box-shadow: 0 0 25px var(--accent-glow);
    transform: translateY(-2px);
}

.btn-secondary {
    color: var(--text-primary);
    border: 1px solid var(--border-color);
}

.btn-icon {
    width: 40px;
    height: 40px;
    padding: 0;
    border-radius: 50%;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
}

/* Hero Section */
.hero-section {
    padding: 7rem 0 5rem;
    position: relative;
    z-index: 1;
    text-align: center;
}

.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.9rem;
    border-radius: 9999px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #a5b4fc;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
}

.pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10b981;
    box-shadow: 0 0 8px #10b981;
}

.hero-title {
    font-family: 'Outfit', sans-serif;
    font-size: 3.5rem;
    font-weight: 800;
    line-height: 1.15;
    margin-bottom: 1.25rem;
    letter-spacing: -0.03em;
}

.gradient-text {
    background: linear-gradient(135deg, #ffffff 20%, #94a3b8 60%, var(--accent-primary) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-subtitle {
    font-size: 1.25rem;
    color: var(--text-secondary);
    max-width: 680px;
    margin: 0 auto 2.5rem;
}

.hero-actions {
    display: flex;
    justify-content: center;
    gap: 1.25rem;
    margin-bottom: 3.5rem;
}

.hero-metrics {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    flex-wrap: wrap;
}

.metric-chip {
    padding: 0.75rem 1.5rem;
    border-radius: var(--radius-md);
    text-align: center;
    min-width: 140px;
}

.metric-val {
    display: block;
    font-family: 'Outfit', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
}

.metric-label {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

/* Sections */
.section {
    padding: 5rem 0;
    position: relative;
    z-index: 1;
}

.section-header {
    text-align: center;
    margin-bottom: 3rem;
}

.section-title {
    font-family: 'Outfit', sans-serif;
    font-size: 2.25rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
}

.section-subtitle {
    font-size: 1.05rem;
    color: var(--text-secondary);
}

/* Filter Bar */
.filter-bar {
    display: flex;
    justify-content: center;
    gap: 0.75rem;
    margin-top: 1.5rem;
}

.filter-btn {
    padding: 0.4rem 1rem;
    border-radius: 9999px;
    border: 1px solid var(--border-color);
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.filter-btn.active, .filter-btn:hover {
    background: var(--accent-primary);
    color: #ffffff;
    border-color: var(--accent-primary);
}

/* Bento Grid */
.bento-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.75rem;
}

.bento-item {
    position: relative;
    overflow: hidden;
}

.bento-badge {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--accent-primary);
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
}

.bento-title {
    font-size: 1.35rem;
    margin-bottom: 0.5rem;
}

.bento-desc {
    color: var(--text-secondary);
    font-size: 0.95rem;
    margin-bottom: 1.25rem;
}

.bento-meta {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.tech-tag {
    font-size: 0.75rem;
    padding: 0.2rem 0.6rem;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-secondary);
}

/* Forms */
.contact-card {
    max-width: 600px;
    margin: 0 auto;
}

.form-group {
    margin-bottom: 1.25rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.4rem;
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.form-group input, .form-group textarea {
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background: rgba(0, 0, 0, 0.2);
    color: var(--text-primary);
    font-family: inherit;
    font-size: 0.95rem;
    outline: none;
    transition: border-color 0.2s ease;
}

.form-group input:focus, .form-group textarea:focus {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px var(--accent-glow);
}

/* Site Footer */
.site-footer {
    border-top: 1px solid var(--border-color);
    padding: 2.5rem 0;
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.9rem;
    position: relative;
    z-index: 1;
}

/* Toast */
.toast-notification {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    padding: 0.85rem 1.4rem;
    background: var(--card-bg);
    backdrop-filter: blur(16px);
    border: 1px solid var(--accent-primary);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    box-shadow: var(--shadow-glow);
    z-index: 1000;
    transform: translateY(120%);
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-notification.show {
    transform: translateY(0);
}

/* Responsive */
@media (max-width: 768px) {
    .hero-title {
        font-size: 2.5rem;
    }
    .nav-links {
        display: none;
    }
}
"""

JS_BASE = """document.addEventListener("DOMContentLoaded", () => {
    // 1. Theme Toggle
    const themeToggleBtn = document.getElementById("theme-toggle");
    const savedTheme = localStorage.getItem("forge_theme") || "dark";
    if (savedTheme === "light") {
        document.body.classList.add("light-mode");
        document.documentElement.setAttribute("data-theme", "light");
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", () => {
            const isLight = document.body.classList.toggle("light-mode");
            document.documentElement.setAttribute("data-theme", isLight ? "light" : "dark");
            localStorage.setItem("forge_theme", isLight ? "light" : "dark");
        });
    }

    // 2. 3D WebGL Three.js Scene with Canvas 2D Fallback
    const canvas = document.getElementById("forge-3d-canvas");
    if (canvas && typeof THREE !== "undefined") {
        try {
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            const renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

            const geometry = new THREE.IcosahedronGeometry(2.4, 2);
            const material = new THREE.MeshBasicMaterial({
                color: 0x6366f1,
                wireframe: true,
                transparent: true,
                opacity: 0.4
            });
            const mesh = new THREE.Mesh(geometry, material);
            scene.add(mesh);
            camera.position.z = 4.8;

            let mouseX = 0, mouseY = 0;
            window.addEventListener("mousemove", (e) => {
                mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
                mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
            });

            const animate = () => {
                requestAnimationFrame(animate);
                mesh.rotation.x += 0.003;
                mesh.rotation.y += 0.005;
                mesh.position.x += (mouseX * 0.5 - mesh.position.x) * 0.05;
                mesh.position.y += (-mouseY * 0.5 - mesh.position.y) * 0.05;
                renderer.render(scene, camera);
            };
            animate();

            window.addEventListener("resize", () => {
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            });
        } catch (e) {
            console.warn("Three.js init failed, falling back to 2D particles:", e);
            init2DParticles(canvas);
        }
    } else if (canvas) {
        init2DParticles(canvas);
    }

    function init2DParticles(cvs) {
        const ctx = cvs.getContext("2d");
        if (!ctx) return;
        let w = cvs.width = window.innerWidth;
        let h = cvs.height = window.innerHeight;
        const particles = Array.from({ length: 45 }, () => ({
            x: Math.random() * w,
            y: Math.random() * h,
            vx: (Math.random() - 0.5) * 0.8,
            vy: (Math.random() - 0.5) * 0.8,
            radius: Math.random() * 2 + 1
        }));
        const render = () => {
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = "rgba(99, 102, 241, 0.5)";
            particles.forEach(p => {
                p.x += p.vx; p.y += p.vy;
                if (p.x < 0 || p.x > w) p.vx *= -1;
                if (p.y < 0 || p.y > h) p.vy *= -1;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fill();
            });
            requestAnimationFrame(render);
        };
        render();
        window.addEventListener("resize", () => {
            w = cvs.width = window.innerWidth;
            h = cvs.height = window.innerHeight;
        });
    }

    // 3. Dynamic Filter Handler
    const filterButtons = document.querySelectorAll(".filter-btn");
    const cards = document.querySelectorAll(".bento-item");
    filterButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            filterButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const filter = btn.getAttribute("data-filter");
            cards.forEach(card => {
                if (filter === "all" || card.getAttribute("data-category") === filter) {
                    card.style.display = "block";
                } else {
                    card.style.display = "none";
                }
            });
        });
    });

    // 4. Contact Form Handler with Toast
    const form = document.getElementById("contact-form");
    const toast = document.getElementById("toast");
    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            if (toast) {
                toast.textContent = "Message transmitted successfully!";
                toast.classList.add("show");
                setTimeout(() => toast.classList.remove("show"), 3500);
            }
            form.reset();
        });
    }
});
"""

# --- 2. CLI Project Template ---

PYTHON_CLI_BASE = '''"""
{{cli_name}}: {{cli_description}}
Generated by Project FORGE.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_FILE = Path("data.json")


class StorageManager:
    """Manages JSON file persistence."""
    def __init__(self, filepath: Path = DEFAULT_DB_FILE):
        self.filepath = filepath

    def load(self) -> List[Dict[str, Any]]:
        if not self.filepath.exists():
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save(self, items: List[Dict[str, Any]]) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)


def handle_add(args: argparse.Namespace, storage: StorageManager) -> int:
    items = storage.load()
    new_item = {
        "id": len(items) + 1,
        "title": args.title,
        "completed": False,
    }
    items.append(new_item)
    storage.save(items)
    print(f"Added item #{new_item['id']}: {new_item['title']}")
    return 0


def handle_list(args: argparse.Namespace, storage: StorageManager) -> int:
    items = storage.load()
    if not items:
        print("No items found.")
        return 0

    print(f"--- {args.filter.capitalize() if hasattr(args, 'filter') and args.filter else 'All'} Items ({len(items)}) ---")
    for item in items:
        status = "[X]" if item.get("completed") else "[ ]"
        print(f"#{item['id']} {status} {item['title']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="{{cli_name}}",
        description="{{cli_description}}",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    add_parser = subparsers.add_parser("add", help="Add a new item")
    add_parser.add_argument("title", help="Title or description of the item")

    list_parser = subparsers.add_parser("list", help="List all items")
    list_parser.add_argument("--filter", choices=["all", "pending", "done"], default="all", help="Filter items")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    storage = StorageManager()

    if args.command == "add":
        return handle_add(args, storage)
    elif args.command == "list":
        return handle_list(args, storage)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
'''

PYTHON_CLI_TEST_BASE = '''"""
Unit tests for {{cli_name}}.
"""

import os
from pathlib import Path
import pytest
from main import StorageManager, build_parser, main


@pytest.fixture
def temp_storage(tmp_path: Path):
    db_file = tmp_path / "test_data.json"
    storage = StorageManager(filepath=db_file)
    return storage


def test_storage_add_and_load(temp_storage: StorageManager):
    items = temp_storage.load()
    assert len(items) == 0

    temp_storage.save([{"id": 1, "title": "Buy groceries", "completed": False}])
    loaded = temp_storage.load()
    assert len(loaded) == 1
    assert loaded[0]["title"] == "Buy groceries"


def test_cli_help(capsys):
    ret = main(["--help"])
    assert ret == 0


def test_cli_add_and_list(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "data.json"
    monkeypatch.setattr("main.DEFAULT_DB_FILE", test_file)

    ret_add = main(["add", "Write documentation"])
    assert ret_add == 0

    ret_list = main(["list"])
    assert ret_list == 0
'''

# --- 3. FastAPI Service Template ---

FASTAPI_APP_BASE = '''"""
{{api_name}}: {{api_description}}
Generated by Project FORGE.
"""

from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(
    title="{{api_title}}",
    description="{{api_description}}",
    version="1.0.0",
)


class Item(BaseModel):
    id: Optional[int] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    completed: bool = False


# In-memory storage
ITEMS_DB: Dict[int, Item] = {}
ID_COUNTER: int = 1


@app.get("/health", summary="Health Check")
def health():
    return {
        "status": "healthy",
        "service": "{{api_name}}",
        "version": "1.0.0",
    }


@app.get("/items", response_model=List[Item], summary="List all items")
def list_items():
    return list(ITEMS_DB.values())


@app.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED, summary="Create a new item")
def create_item(item: Item):
    global ID_COUNTER
    item.id = ID_COUNTER
    ITEMS_DB[ID_COUNTER] = item
    ID_COUNTER += 1
    return item


@app.get("/items/{item_id}", response_model=Item, summary="Get item by ID")
def get_item(item_id: int):
    if item_id not in ITEMS_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return ITEMS_DB[item_id]


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete item")
def delete_item(item_id: int):
    if item_id not in ITEMS_DB:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    del ITEMS_DB[item_id]
    return None
'''

FASTAPI_TEST_BASE = '''"""
Integration tests for {{api_title}}.
"""

from fastapi.testclient import TestClient
from main import app, ITEMS_DB

client = TestClient(app)


def setup_function():
    ITEMS_DB.clear()


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"


def test_create_and_get_item():
    res = client.post("/items", json={"title": "Test Task", "description": "Verify endpoint"})
    assert res.status_code == 201
    created = res.json()
    assert created["id"] is not None
    assert created["title"] == "Test Task"

    get_res = client.get(f"/items/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Test Task"


def test_get_nonexistent_item():
    res = client.get("/items/9999")
    assert res.status_code == 404
'''
