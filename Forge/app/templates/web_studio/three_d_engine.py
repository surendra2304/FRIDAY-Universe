"""
ForgeWebStudio 3D & Interactive Canvas Engine.
Provides client-side 3D WebGL scenes, interactive particle physics, 3D card tilt, and mouse-reactive visual shaders.
Zero external bundler required; runs natively in modern browsers.
"""


def generate_three_d_scene_script(
    canvas_id: str = "webstudio-3d-canvas",
    scene_mode: str = "portfolio",
    primary_hex: str = "#6366f1",
    accent_hex: str = "#a855f7",
    domain_type: str | None = None,
    scene_type: str | None = None,
) -> str:
    """
    Generates high-performance, responsive 3D / WebGL JavaScript code tailored to domain archetype.
    Supports Three.js interactive 3D geometry (E-Commerce Product Showcase, SaaS Neural Core,
    Dashboard Orbital Globe, Cyberpunk Torus Knot) or high-speed 60FPS 2D/3D particle constellations.
    """
    effective_domain = (domain_type or scene_mode or "portfolio").lower()
    effective_scene = (scene_type or effective_domain or "default").lower()
    if any(k in effective_domain for k in ["ecommerce", "shop", "store", "product"]):
        domain_key = "ecommerce"
    elif any(k in effective_domain for k in ["saas", "platform", "cloud"]):
        domain_key = "saas"
    elif any(k in effective_domain for k in ["dashboard", "analytics", "telemetry", "metrics"]):
        domain_key = "dashboard"
    else:
        domain_key = "portfolio"

    return f"""// ==========================================================================
// ForgeWebStudio 3.0 — 3D Scene & Particle Physics Engine [{domain_key.upper()}]
// ==========================================================================

function init3DHeroCanvas() {{
    const canvas = document.getElementById("{canvas_id}");
    if (!canvas) return;

    let attempts = 0;
    function tryMount() {{
        if (typeof THREE !== 'undefined') {{
            initThreeJSScene(canvas);
        }} else if (attempts < 10) {{
            attempts++;
            setTimeout(tryMount, 200);
        }} else {{
            initHighSpeedParticleCanvas(canvas);
        }}
    }}
    tryMount();

    function initThreeJSScene(targetCanvas) {{
        const container = targetCanvas.parentElement || document.body;
        let width = targetCanvas.clientWidth || container.clientWidth || 550;
        let height = targetCanvas.clientHeight || container.clientHeight || 440;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({{
            canvas: targetCanvas,
            alpha: true,
            antialias: true,
            powerPreference: "high-performance"
        }});
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        const group = new THREE.Group();
        scene.add(group);

        // Studio Lighting Rig
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
        scene.add(ambientLight);

        const pointLight1 = new THREE.PointLight('{primary_hex}', 3.5, 60);
        pointLight1.position.set(6, 6, 6);
        scene.add(pointLight1);

        const pointLight2 = new THREE.PointLight('{accent_hex}', 3.0, 60);
        pointLight2.position.set(-6, -4, 4);
        scene.add(pointLight2);

        // Domain-Specific 3D Geometry Setup
        const domain = "{domain_key}";
        const sceneType = "{effective_scene}";
        let mainMesh, secondaryMesh, tertiaryMesh;
        let orbitRing1, orbitRing2, satBeacon1, satBeacon2;
        let secHand, minHand, hourHand, caseMat, bezelMat, markerMat;
        let isDragging = false;
        let prevMouse = {{ x: 0, y: 0 }};
        let autoRotate = true;

        if (domain === "ecommerce") {{
            if (sceneType === "watch_dial" || sceneType.includes("watch") || domain.includes("watch")) {{
                // BESPOKE LUXURY WATCH WITH 3D DIAL & MOVING TICKING HANDS
                camera.position.z = 4.2;

                // 1. Watch Case Body (Cylinder with metallic finish)
                const caseGeo = new THREE.CylinderGeometry(1.65, 1.65, 0.38, 64);
                caseMat = new THREE.MeshStandardMaterial({{
                    color: '{primary_hex}',
                    metalness: 0.95,
                    roughness: 0.12,
                    wireframe: false
                }});
                mainMesh = new THREE.Mesh(caseGeo, caseMat);
                mainMesh.rotation.x = Math.PI / 5;
                group.add(mainMesh);

                // 2. Bezel Ring (Fluted outer bezel)
                const bezelGeo = new THREE.TorusGeometry(1.65, 0.07, 16, 64);
                bezelMat = new THREE.MeshStandardMaterial({{
                    color: '{primary_hex}',
                    metalness: 0.98,
                    roughness: 0.08
                }});
                const bezel = new THREE.Mesh(bezelGeo, bezelMat);
                bezel.rotation.x = Math.PI / 2;
                bezel.position.y = 0.19;
                mainMesh.add(bezel);

                // 3. Dial Face (Obsidian / Sunburst inner disc)
                const dialGeo = new THREE.CylinderGeometry(1.5, 1.5, 0.04, 64);
                const dialMat = new THREE.MeshStandardMaterial({{
                    color: '#080c14',
                    roughness: 0.3,
                    metalness: 0.4
                }});
                const dial = new THREE.Mesh(dialGeo, dialMat);
                dial.position.y = 0.18;
                mainMesh.add(dial);

                // 4. 12 Hour Markers (Applied batons around the dial face)
                markerMat = new THREE.MeshStandardMaterial({{
                    color: '{primary_hex}',
                    metalness: 0.95,
                    roughness: 0.1
                }});
                for (let i = 0; i < 12; i++) {{
                    const angle = (i / 12) * Math.PI * 2;
                    const isCardinal = (i % 3 === 0);
                    const mWidth = isCardinal ? 0.08 : 0.04;
                    const mHeight = isCardinal ? 0.26 : 0.16;
                    const markerGeo = new THREE.BoxGeometry(mWidth, 0.03, mHeight);
                    const marker = new THREE.Mesh(markerGeo, markerMat);
                    const radius = 1.25;
                    marker.position.set(Math.sin(angle) * radius, 0.21, Math.cos(angle) * radius);
                    marker.rotation.y = angle;
                    mainMesh.add(marker);
                }}

                // 5. Watch Hands (Hour, Minute, and Ticking Second Hand)
                const handMat = new THREE.MeshStandardMaterial({{
                    color: '#f8fafc',
                    metalness: 0.92,
                    roughness: 0.1
                }});
                const secondMat = new THREE.MeshStandardMaterial({{
                    color: '{accent_hex}',
                    metalness: 0.85,
                    roughness: 0.15
                }});

                // Center Pin
                const pinGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.08, 32);
                const pin = new THREE.Mesh(pinGeo, handMat);
                pin.position.y = 0.23;
                mainMesh.add(pin);

                // Hour Hand
                const hourGeo = new THREE.BoxGeometry(0.07, 0.02, 0.72);
                hourGeo.translate(0, 0, -0.36);
                hourHand = new THREE.Mesh(hourGeo, handMat);
                hourHand.position.y = 0.22;
                mainMesh.add(hourHand);

                // Minute Hand
                const minGeo = new THREE.BoxGeometry(0.05, 0.02, 1.12);
                minGeo.translate(0, 0, -0.56);
                minHand = new THREE.Mesh(minGeo, handMat);
                minHand.position.y = 0.23;
                mainMesh.add(minHand);

                // Second Hand
                const secGeo = new THREE.BoxGeometry(0.02, 0.015, 1.32);
                secGeo.translate(0, 0, -0.5);
                secHand = new THREE.Mesh(secGeo, secondMat);
                secHand.position.y = 0.24;
                mainMesh.add(secHand);

                // 6. Winding Crown at 3 o'clock
                const crownGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.32, 24);
                const crown = new THREE.Mesh(crownGeo, caseMat);
                crown.position.set(1.78, 0, 0);
                crown.rotation.z = Math.PI / 2;
                mainMesh.add(crown);

            }} else {{
                // Standard E-COMMERCE: Articulated Cybernetic Hardware / Spatial Core
                camera.position.z = 4.8;

                const chassisGeo = new THREE.CylinderGeometry(1.2, 1.2, 0.65, 32);
                const chassisMat = new THREE.MeshStandardMaterial({{
                    color: '{primary_hex}',
                    metalness: 0.9,
                    roughness: 0.15,
                    emissive: '{accent_hex}',
                    emissiveIntensity: 0.25,
                    wireframe: false
                }});
                mainMesh = new THREE.Mesh(chassisGeo, chassisMat);
                mainMesh.rotation.x = Math.PI / 5;
                group.add(mainMesh);

                const visorGeo = new THREE.SphereGeometry(1.05, 32, 16, 0, Math.PI * 2, 0, Math.PI * 0.5);
                const visorMat = new THREE.MeshStandardMaterial({{
                    color: '{accent_hex}',
                    roughness: 0.08,
                    metalness: 0.15,
                    transparent: true,
                    opacity: 0.85,
                    emissive: '{accent_hex}',
                    emissiveIntensity: 0.35
                }});
                secondaryMesh = new THREE.Mesh(visorGeo, visorMat);
                secondaryMesh.rotation.x = Math.PI / 2;
                group.add(secondaryMesh);

                const ring1Geo = new THREE.TorusGeometry(2.1, 0.035, 16, 100);
                const ring1Mat = new THREE.MeshBasicMaterial({{ color: '{primary_hex}', transparent: true, opacity: 0.7 }});
                orbitRing1 = new THREE.Mesh(ring1Geo, ring1Mat);
                orbitRing1.rotation.x = Math.PI / 3;
                group.add(orbitRing1);

                const ring2Geo = new THREE.TorusGeometry(2.4, 0.02, 16, 100);
                const ring2Mat = new THREE.MeshBasicMaterial({{ color: '{accent_hex}', transparent: true, opacity: 0.55 }});
                orbitRing2 = new THREE.Mesh(ring2Geo, ring2Mat);
                orbitRing2.rotation.y = Math.PI / 4;
                group.add(orbitRing2);

                const sparkGeo = new THREE.BufferGeometry();
                const sparkCount = 160;
                const sparkPos = new Float32Array(sparkCount * 3);
                for (let i = 0; i < sparkCount * 3; i += 3) {{
                    const r = 2.0 + Math.random() * 1.5;
                    const theta = Math.random() * Math.PI * 2;
                    const phi = (Math.random() - 0.5) * Math.PI;
                    sparkPos[i] = r * Math.cos(theta) * Math.cos(phi);
                    sparkPos[i + 1] = r * Math.sin(phi);
                    sparkPos[i + 2] = r * Math.sin(theta) * Math.cos(phi);
                }}
                sparkGeo.setAttribute('position', new THREE.BufferAttribute(sparkPos, 3));
                const sparkMat = new THREE.PointsMaterial({{ size: 0.035, color: '{primary_hex}', transparent: true, opacity: 0.8 }});
                tertiaryMesh = new THREE.Points(sparkGeo, sparkMat);
                group.add(tertiaryMesh);
            }}

        }} else if (domain === "saas") {{
            // SAAS: Floating Quantum AI Neural Core with Synaptic Constellation
            camera.position.z = 5.0;

            const geodesicGeo = new THREE.IcosahedronGeometry(1.65, 2);
            const geodesicMat = new THREE.MeshStandardMaterial({{
                color: '{primary_hex}',
                wireframe: true,
                transparent: true,
                opacity: 0.85,
                emissive: '{primary_hex}',
                emissiveIntensity: 0.4
            }});
            mainMesh = new THREE.Mesh(geodesicGeo, geodesicMat);
            group.add(mainMesh);

            const nucleusGeo = new THREE.SphereGeometry(0.8, 32, 32);
            const nucleusMat = new THREE.MeshStandardMaterial({{
                color: '{accent_hex}',
                emissive: '{accent_hex}',
                emissiveIntensity: 0.75,
                roughness: 0.15,
                metalness: 0.7
            }});
            secondaryMesh = new THREE.Mesh(nucleusGeo, nucleusMat);
            group.add(secondaryMesh);

            const nodeCount = 35;
            const nodeVectors = [];
            for (let i = 0; i < nodeCount; i++) {{
                nodeVectors.push(new THREE.Vector3(
                    (Math.random() - 0.5) * 3.8,
                    (Math.random() - 0.5) * 3.8,
                    (Math.random() - 0.5) * 3.8
                ));
            }}
            const linePoints = [];
            for (let i = 0; i < nodeCount; i++) {{
                for (let j = i + 1; j < nodeCount; j++) {{
                    if (nodeVectors[i].distanceTo(nodeVectors[j]) < 1.7) {{
                        linePoints.push(nodeVectors[i].x, nodeVectors[i].y, nodeVectors[i].z);
                        linePoints.push(nodeVectors[j].x, nodeVectors[j].y, nodeVectors[j].z);
                    }}
                }}
            }}
            const lineGeo = new THREE.BufferGeometry();
            lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePoints, 3));
            const lineMat = new THREE.LineBasicMaterial({{ color: '{primary_hex}', transparent: true, opacity: 0.5 }});
            tertiaryMesh = new THREE.LineSegments(lineGeo, lineMat);
            group.add(tertiaryMesh);

        }} else if (domain === "dashboard") {{
            // DASHBOARD: Planetary Holographic Globe with Orbital Telemetry Satellites
            camera.position.z = 5.2;

            const globeGeo = new THREE.SphereGeometry(1.7, 24, 24);
            const globeMat = new THREE.MeshStandardMaterial({{
                color: '{primary_hex}',
                wireframe: true,
                transparent: true,
                opacity: 0.8,
                emissive: '{primary_hex}',
                emissiveIntensity: 0.3
            }});
            mainMesh = new THREE.Mesh(globeGeo, globeMat);
            group.add(mainMesh);

            const ring1Geo = new THREE.TorusGeometry(2.5, 0.025, 16, 100);
            const ring1Mat = new THREE.MeshBasicMaterial({{ color: '{accent_hex}', transparent: true, opacity: 0.65 }});
            orbitRing1 = new THREE.Mesh(ring1Geo, ring1Mat);
            orbitRing1.rotation.x = Math.PI / 2.8;
            group.add(orbitRing1);

            const ring2Geo = new THREE.TorusGeometry(2.9, 0.02, 16, 100);
            const ring2Mat = new THREE.MeshBasicMaterial({{ color: '{primary_hex}', transparent: true, opacity: 0.45 }});
            orbitRing2 = new THREE.Mesh(ring2Geo, ring2Mat);
            orbitRing2.rotation.x = -Math.PI / 3.2;
            group.add(orbitRing2);

            const satGeo = new THREE.SphereGeometry(0.12, 16, 16);
            const satMat = new THREE.MeshBasicMaterial({{ color: '#ffffff' }});
            satBeacon1 = new THREE.Mesh(satGeo, satMat);
            group.add(satBeacon1);
            satBeacon2 = new THREE.Mesh(satGeo, satMat);
            group.add(satBeacon2);

        }} else {{
            // PORTFOLIO / CYBERPUNK: High-Tech Cybernetic Torus Knot
            camera.position.z = 5.2;

            const torusGeo = new THREE.TorusKnotGeometry(1.8, 0.42, 128, 32);
            const torusMat = new THREE.MeshStandardMaterial({{
                color: '{primary_hex}',
                wireframe: true,
                roughness: 0.15,
                metalness: 0.9,
                emissive: '{accent_hex}',
                emissiveIntensity: 0.35,
                transparent: true,
                opacity: 0.9
            }});
            mainMesh = new THREE.Mesh(torusGeo, torusMat);
            group.add(mainMesh);

            const coreGeo = new THREE.IcosahedronGeometry(1.1, 2);
            const coreMat = new THREE.MeshStandardMaterial({{
                color: '{accent_hex}',
                wireframe: false,
                roughness: 0.2,
                metalness: 0.8,
                emissive: '{primary_hex}',
                emissiveIntensity: 0.5
            }});
            secondaryMesh = new THREE.Mesh(coreGeo, coreMat);
            group.add(secondaryMesh);

            const particlesCount = 380;
            const positions = new Float32Array(particlesCount * 3);
            for (let i = 0; i < particlesCount * 3; i += 3) {{
                positions[i] = (Math.random() - 0.5) * 14;
                positions[i + 1] = (Math.random() - 0.5) * 14;
                positions[i + 2] = (Math.random() - 0.5) * 14;
            }}
            const particlesGeometry = new THREE.BufferGeometry();
            particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            const particlesMaterial = new THREE.PointsMaterial({{
                size: 0.045,
                color: '{primary_hex}',
                transparent: true,
                opacity: 0.8
            }});
            tertiaryMesh = new THREE.Points(particlesGeometry, particlesMaterial);
            group.add(tertiaryMesh);

            // Wire HUD controls if present
            const wireframeBtn = document.getElementById('hud-wireframe-toggle');
            if (wireframeBtn) {{
                wireframeBtn.addEventListener('click', () => {{
                    torusMat.wireframe = !torusMat.wireframe;
                    wireframeBtn.classList.toggle('active');
                }});
            }}
            const speedBtn = document.getElementById('hud-speed-toggle');
            if (speedBtn) {{
                let hudSpeed = 1.0;
                speedBtn.addEventListener('click', () => {{
                    hudSpeed = hudSpeed === 1.0 ? 2.5 : (hudSpeed === 2.5 ? 5.0 : 1.0);
                    const lbl = document.getElementById('hud-speed-label');
                    if (lbl) lbl.textContent = `Speed: ${{hudSpeed}}x`;
                }});
            }}
            const resetBtn = document.getElementById('hud-reset-view');
            if (resetBtn) {{
                resetBtn.addEventListener('click', () => {{
                    group.position.set(0, 0, 0);
                    group.rotation.set(0, 0, 0);
                }});
            }}
        }}

        // Live Material Color Customizer
        document.querySelectorAll('.color-dot').forEach(dot => {{
            dot.addEventListener('click', () => {{
                document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
                dot.classList.add('active');
                const hex = dot.getAttribute('data-color');
                if (hex) {{
                    if (caseMat) caseMat.color.set(hex);
                    if (bezelMat) bezelMat.color.set(hex);
                    if (markerMat) markerMat.color.set(hex);
                    if (mainMesh && mainMesh.material) {{
                        mainMesh.material.color.set(hex);
                        if (mainMesh.material.emissive) {{
                            mainMesh.material.emissive.set(hex);
                        }}
                    }}
                }}
            }});
        }});

        // View Mode Toggles in Viewport Card Header
        const wireBtn = document.getElementById('view-mode-wireframe');
        if (wireBtn) {{
            wireBtn.addEventListener('click', () => {{
                if (mainMesh && mainMesh.material) {{
                    const isWire = !mainMesh.material.wireframe;
                    mainMesh.material.wireframe = isWire;
                    wireBtn.classList.toggle('active', isWire);
                }}
            }});
        }}

        const rotBtn = document.getElementById('view-mode-rotate');
        if (rotBtn) {{
            rotBtn.addEventListener('click', () => {{
                autoRotate = !autoRotate;
                rotBtn.classList.toggle('active', autoRotate);
            }});
        }}

        // Mouse-Drag to Rotate with Smooth Damping
        targetCanvas.style.cursor = 'grab';
        targetCanvas.addEventListener('pointerdown', (e) => {{
            isDragging = true;
            prevMouse = {{ x: e.clientX, y: e.clientY }};
            targetCanvas.style.cursor = 'grabbing';
        }});
        window.addEventListener('pointermove', (e) => {{
            if (!isDragging) return;
            const dx = e.clientX - prevMouse.x;
            const dy = e.clientY - prevMouse.y;
            group.rotation.y += dx * 0.008;
            group.rotation.x += dy * 0.008;
            prevMouse = {{ x: e.clientX, y: e.clientY }};
        }});
        window.addEventListener('pointerup', () => {{
            isDragging = false;
            targetCanvas.style.cursor = 'grab';
        }});

        // Mouse Parallax
        let mouseX = 0, mouseY = 0;
        let targetX = 0, targetY = 0;
        window.addEventListener('mousemove', (e) => {{
            mouseX = (e.clientX / window.innerWidth) * 2 - 1;
            mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
        }});

        // Animation Loop
        let clock = new THREE.Clock();
        function animate() {{
            requestAnimationFrame(animate);
            const t = clock.getElapsedTime();

            if (domain === "ecommerce") {{
                if (secHand && minHand && hourHand) {{
                    const now = new Date();
                    const ms = now.getMilliseconds();
                    const s = now.getSeconds() + ms / 1000;
                    const m = now.getMinutes() + s / 60;
                    const h = (now.getHours() % 12) + m / 60;
                    secHand.rotation.y = (s / 60) * Math.PI * 2;
                    minHand.rotation.y = (m / 60) * Math.PI * 2;
                    hourHand.rotation.y = (h / 12) * Math.PI * 2;
                    if (autoRotate && !isDragging) {{
                        mainMesh.rotation.y += 0.005;
                        mainMesh.rotation.x = Math.PI / 5 + Math.sin(t * 0.5) * 0.08;
                    }}
                }} else {{
                    if (autoRotate && !isDragging) {{
                        mainMesh.rotation.y += 0.007;
                        mainMesh.rotation.x = Math.sin(t * 0.6) * 0.12;
                        if (secondaryMesh) secondaryMesh.rotation.y += 0.007;
                    }}
                    if (orbitRing1) orbitRing1.rotation.z += 0.008;
                    if (orbitRing2) orbitRing2.rotation.x -= 0.007;
                    if (tertiaryMesh) tertiaryMesh.rotation.y -= 0.002;
                }}
            }} else if (domain === "saas") {{
                if (autoRotate && !isDragging) {{
                    mainMesh.rotation.x += 0.003;
                    mainMesh.rotation.y += 0.006;
                }}
                const pulse = 0.82 + Math.sin(t * 2.2) * 0.1;
                if (secondaryMesh) secondaryMesh.scale.set(pulse, pulse, pulse);
                if (tertiaryMesh) tertiaryMesh.rotation.y -= 0.002;
            }} else if (domain === "dashboard") {{
                if (autoRotate && !isDragging) {{
                    mainMesh.rotation.y += 0.005;
                }}
                if (orbitRing1) orbitRing1.rotation.z += 0.006;
                if (orbitRing2) orbitRing2.rotation.z -= 0.005;
                if (satBeacon1) {{
                    satBeacon1.position.x = Math.cos(t * 0.9) * 2.5;
                    satBeacon1.position.y = Math.sin(t * 0.9) * 1.2;
                    satBeacon1.position.z = Math.sin(t * 0.9) * 2.0;
                }}
                if (satBeacon2) {{
                    satBeacon2.position.x = Math.cos(-t * 0.7) * 2.9;
                    satBeacon2.position.y = Math.sin(-t * 0.7) * 1.6;
                    satBeacon2.position.z = Math.sin(t * 0.7) * 1.4;
                }}
            }} else {{
                if (autoRotate && !isDragging) {{
                    if (mainMesh) {{
                        mainMesh.rotation.x += 0.004;
                        mainMesh.rotation.y += 0.006;
                    }}
                    if (secondaryMesh) {{
                        secondaryMesh.rotation.x -= 0.007;
                        secondaryMesh.rotation.y += 0.004;
                    }}
                }}
                if (tertiaryMesh) tertiaryMesh.rotation.y -= 0.001;
            }}

            if (!isDragging) {{
                targetX += (mouseX * 0.35 - targetX) * 0.04;
                targetY += (mouseY * 0.35 - targetY) * 0.04;
                group.position.x = targetX;
                group.position.y = targetY;
            }}

            renderer.render(scene, camera);
        }}
        animate();

        function onResize() {{
            const w = targetCanvas.clientWidth || container.clientWidth || 550;
            const h = targetCanvas.clientHeight || container.clientHeight || 440;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        }}
        window.addEventListener('resize', onResize);
        if (typeof ResizeObserver !== 'undefined') {{
            const ro = new ResizeObserver(onResize);
            ro.observe(container);
        }}
    }}

    function initHighSpeedParticleCanvas(targetCanvas) {{
        const ctx = targetCanvas.getContext('2d');
        let width = targetCanvas.width = targetCanvas.clientWidth || window.innerWidth;
        let height = targetCanvas.height = targetCanvas.clientHeight || 600;

        const particles = [];
        const numParticles = Math.min(90, Math.floor(width / 14));
        const maxDistance = 120;

        let mouse = {{ x: null, y: null, radius: 140 }};
        window.addEventListener('mousemove', (e) => {{
            const rect = targetCanvas.getBoundingClientRect();
            mouse.x = e.clientX - rect.left;
            mouse.y = e.clientY - rect.top;
        }});
        window.addEventListener('mouseleave', () => {{
            mouse.x = null;
            mouse.y = null;
        }});

        class Particle {{
            constructor() {{
                this.x = Math.random() * width;
                this.y = Math.random() * height;
                this.vx = (Math.random() - 0.5) * 1.4;
                this.vy = (Math.random() - 0.5) * 1.4;
                this.radius = Math.random() * 2.0 + 1.2;
                this.baseAlpha = Math.random() * 0.5 + 0.35;
            }}
            update() {{
                this.x += this.vx;
                this.y += this.vy;
                if (this.x < 0 || this.x > width) this.vx *= -1;
                if (this.y < 0 || this.y > height) this.vy *= -1;

                if (mouse.x !== null) {{
                    const dx = mouse.x - this.x;
                    const dy = mouse.y - this.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < mouse.radius) {{
                        const force = (mouse.radius - dist) / mouse.radius;
                        this.x -= (dx / dist) * force * 3;
                        this.y -= (dy / dist) * force * 3;
                    }}
                }}
            }}
            draw() {{
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                ctx.fillStyle = '{primary_hex}';
                ctx.globalAlpha = this.baseAlpha;
                ctx.fill();
            }}
        }}

        for (let i = 0; i < numParticles; i++) {{
            particles.push(new Particle());
        }}

        function animate() {{
            ctx.clearRect(0, 0, width, height);
            for (let i = 0; i < particles.length; i++) {{
                particles[i].update();
                particles[i].draw();

                for (let j = i + 1; j < particles.length; j++) {{
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < maxDistance) {{
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = '{accent_hex}';
                        ctx.globalAlpha = (1 - dist / maxDistance) * 0.3;
                        ctx.lineWidth = 1;
                        ctx.stroke();
                    }}
                }}
            }}
            requestAnimationFrame(animate);
        }}
        animate();

        window.addEventListener('resize', () => {{
            width = targetCanvas.width = targetCanvas.clientWidth || window.innerWidth;
            height = targetCanvas.height = targetCanvas.clientHeight || 600;
        }});
    }}
}}

if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', init3DHeroCanvas);
}} else {{
    init3DHeroCanvas();
}}
"""


def generate_3d_tilt_script() -> str:
    """
    Generates interactive 3D perspective tilt effect for cards and bento boxes.
    Adds specular glare and perspective rotation on cursor hover.
    """
    return """// ==========================================================================
// ForgeWebStudio 3.0 — 3D Tilt Card Perspective Engine
// ==========================================================================

function init3DTiltCards() {
    const cards = document.querySelectorAll('.tilt-card, .glass-card, .product-card');
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = ((y - centerY) / centerY) * -6;
            const rotateY = ((x - centerX) / centerX) * 6;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';
            card.style.transition = 'transform 0.4s ease';
        });

        card.addEventListener('mouseenter', () => {
            card.style.transition = 'none';
        });
    });
}

document.addEventListener('DOMContentLoaded', init3DTiltCards);
"""


class Web3DEngine:
    """Convenience wrapper for 3D scripts and particle physics engines."""

    @staticmethod
    def generate_engine_js(
        canvas_id: str = "webstudio-3d-canvas",
        scene_mode: str = "portfolio",
        primary_hex: str = "#6366f1",
        accent_hex: str = "#a855f7",
        domain_type: str | None = None,
    ) -> str:
        return generate_three_d_scene_script(
            canvas_id, scene_mode, primary_hex, accent_hex, domain_type=domain_type
        )

    @staticmethod
    def generate_card_tilt_js() -> str:
        return generate_3d_tilt_script()
