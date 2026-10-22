# 🏛️ SYSTEM MANIFEST — Forge Autonomous Software Engineering

> **Official Subsystem Name:** Forge  
> **Role in Ecosystem:** Local Autonomous Software Engineering Engine, Code Synthesizer & Test Suite Generator  
> **Repository:** [surendra2304/Forge](https://github.com/surendra2304/Forge) (Branch: master)  
> **Workspace Path:** d:\FRIDAY Universe\Forge  

---

## ☁️ 1. Configured service (runtime unverified)

| Attribute | Repository configuration |
| :--- | :--- |
| **Configured Service URL (deployment unverified)** | [Local Execution (d:\FRIDAY Universe\Forge)](#) |
| **Health Check Endpoint** | Local CLI / Pytest Suite |
| **API key variable (keep value in secret environment)** | FORGE_API_KEY=<configure in secret environment> |
| **Authentication Header** | Authorization: Bearer <configured API key> |
| **Configured database topology (runtime unverified)** | Local File Workspace / Connected to Memora Cloud |
| **Configured database URL or namespace (not a secret)** | memora://forge/private |
| **Configured host (plan, region, and runtime unverified)** | Oracle Cloud Always Free (Ampere A1 ARM64 / AMD x86_64), Caddy Reverse Proxy, friday_mesh |

---

## 🎯 2. Purpose & Responsibilities

### What Forge IS:
* Forge is the autonomous code synthesis, execution sandbox, linting, and automated refactoring engine for the FRIDAY Universe. It synthesizes full projects, implements features, runs rigorous test generation suites, and executes self-repair cycles within isolated process sandboxes.

### What Forge DOES:
* Operates as the **Autonomous Code Synthesis, Execution Sandbox, & Self-Repair Agent** within the 9-agent FRIDAY Universe.
* Communicates directly with peer agents via authenticated REST and WebSocket protocols over the unified `friday_mesh` private network.
* Integrates with **Memora** for persistent lessons and execution history.

---

## 🌐 3. Ecosystem endpoint configuration

Configured private container mesh endpoints within `friday_mesh`:

```env
# ============================================================================== #
#               FRIDAY UNIVERSE MASTER ECOSYSTEM CONFIGURATION                  #
# ============================================================================== #

# 1. ⚡ Inference AI Multi-Model Gateway
INFERENCE_URL=http://inference:8000
INFERENCE_API_KEY=<configure in secret environment>

# 2. 🧠 Memora Cloud Memory Service
MEMORA_URL=http://memora:8000
MEMORA_API_KEY=<configure in secret environment>

# 3. 📈 Stratex Algorithmic Trading Platform
STRATEX_URL=http://stratex:8000
STRATEX_API_KEY=<configure in secret environment>

# 4. 🧠 IntelX Evidence & Intelligence Research Engine
INTELX_URL=http://intelx:8000
INTELX_API_KEY=<configure in secret environment>

# 5. 🔮 Futuris Calibrated Predictive Forecasting Engine
FUTURIS_URL=http://futuris:8000
FUTURIS_API_KEY=<configure in secret environment>

# 6. 🌐 Cortex Autonomous Web Operations & Intelligence
CORTEX_URL=http://cortex:8000
CORTEX_API_KEY=<configure in secret environment>

# 7. 🛠️ Forge Local Software Engineering Engine
FORGE_URL=http://forge:8000
FORGE_API_KEY=<configure in secret environment>

# 8. 🛡️ Sentinel Cybersecurity & Threat Defense Shield
SENTINEL_URL=http://sentinel:8000
SENTINEL_API_KEY=<configure in secret environment>

# 9. 🤖 FRIDAY Central Desktop Operating System Gateway
FRIDAY_URL=http://friday:10000
FRIDAY_API_KEY=<configure in secret environment>
```

---

## 🤖 4. Repository guide

When opening this repository:
* **Identity:** You are working inside **Forge** (d:\FRIDAY Universe\Forge).
* **Configured URL (deployment unverified): Local Execution (d:\FRIDAY Universe\Forge).
* **Authentication:** Incoming requests use FORGE_API_KEY=<configure in secret environment>
* **Never Fake Tests:** All tests and verifications must be executed against real code and real endpoints.
* **No Unapproved Git Pushes:** Keep modifications local unless explicitly instructed to push.
