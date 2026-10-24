"""
tools/universe_health_check.py — Production health check for FRIDAY Universe.

Checks all 10 agents' health endpoints, dispatch bus, and reports status.
Designed to run on Oracle Cloud or any deployment environment.

Usage:
    python3 tools/universe_health_check.py              # Check all
    python3 tools/universe_health_check.py --dispatch   # Also test dispatch
    python3 tools/universe_health_check.py --verbose    # Show details
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Agent registry: name -> (port, health_path)
AGENTS = {
    "FRIDAY":      {"port": 5000, "health": "/health"},
    "Inference":   {"port": 8005, "health": "/health"},
    "Memora":      {"port": 8006, "health": "/health"},
    "Stratex":     {"port": 8007, "health": "/health"},
    "Forge":       {"port": 8008, "health": "/health"},
    "Cortex":      {"port": 8009, "health": "/health"},
    "Sentinel":    {"port": 8010, "health": "/health"},
    "IntelX":      {"port": 8011, "health": "/health"},
    "Futuris":     {"port": 8012, "health": "/health"},
    "VyralX":      {"port": 8013, "health": "/health"},
}

DASHBOARD = {"port": 5001, "health": "/"}


def check_agent(name: str, config: dict, timeout: float = 5.0) -> dict:
    """Check a single agent's health."""
    url = f"http://localhost:{config['port']}{config['health']}"
    result = {"agent": name, "url": url, "status": "unknown", "latency_ms": 0, "error": ""}
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        result["status"] = "online" if resp.status < 400 else "degraded"
        result["latency_ms"] = round((time.time() - start) * 1000, 2)
    except urllib.error.HTTPError as e:
        result["status"] = "degraded" if e.code < 500 else "offline"
        result["latency_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = f"HTTP {e.code}"
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError) as e:
        result["status"] = "offline"
        result["latency_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "offline"
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def check_all(timeout: float = 5.0) -> dict:
    """Check all agents and the dashboard."""
    results = []
    for name, config in AGENTS.items():
        results.append(check_agent(name, config, timeout))
    results.append(check_agent("Dashboard", DASHBOARD, timeout))
    return results


def print_report(results: list[dict], verbose: bool = False):
    """Print a formatted health report."""
    print("=" * 70)
    print("  FRIDAY Universe Health Check")
    print("=" * 70)
    print(f"  {'Agent':<15} {'Status':<10} {'Latency':<10} {'Error'}")
    print("-" * 70)
    online = 0
    for r in results:
        icon = {"online": "✅", "degraded": "⚠️ ", "offline": "❌"}.get(r["status"], "❓")
        print(f"  {icon} {r['agent']:<13} {r['status']:<10} {r['latency_ms']:>7}ms  {r['error']}")
        if r["status"] == "online":
            online += 1
    print("-" * 70)
    print(f"  Total: {len(results)} agents, {online} online")
    if verbose:
        print(f"\n  Details:")
        for r in results:
            print(f"    {r['agent']}: {json.dumps(r, indent=4)}")
    print("=" * 70)
    return online == len(results)


def test_dispatch():
    """Test the dispatch bus by routing to all agents."""
    print("\n📡 Testing Dispatch Bus...")
    try:
        sys.path.insert(0, str(ROOT / "FRIDAY/apps/core/src"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_hc_bus", str(ROOT / "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_hc_bus"] = mod
        spec.loader.exec_module(mod)
        bus = mod.engine

        agents = ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                  "Sentinel", "IntelX", "Futuris", "VyralX"]
        results = []
        for agent in agents:
            receipt = bus.dispatch(agent, "health_check", {"test": True})
            results.append({"agent": agent, "status": receipt.status, "latency_ms": receipt.latency_ms})
            status = "✅" if receipt.status == "completed" else "❌"
            print(f"  {status} Dispatch to {agent}: {receipt.status} ({receipt.latency_ms:.2f}ms)")

        completed = sum(1 for r in results if r["status"] == "completed")
        print(f"\n  Dispatch: {completed}/{len(results)} agents responded")
        return completed == len(results)
    except Exception as e:
        print(f"  ❌ Dispatch test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="FRIDAY Universe Health Check")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Show detailed results")
    parser.add_argument("--dispatch", action="store_true", help="Also test dispatch bus")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    results = check_all(args.timeout)

    if args.json:
        output = {"timestamp": time.time(), "agents": results}
        if args.dispatch:
            output["dispatch"] = test_dispatch()
        print(json.dumps(output, indent=2))
    else:
        all_healthy = print_report(results, args.verbose)
        if args.dispatch:
            dispatch_ok = test_dispatch()
            all_healthy = all_healthy and dispatch_ok
        # Exit code
        sys.exit(0 if all_healthy else 1)


if __name__ == "__main__":
    main()
