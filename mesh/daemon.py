"""Agent daemon and execution supervisor for the FRIDAY Universe.

Supports two operational modes:
1. CLOUD_FIRST (Default): 100% offloaded to Render cloud microservices (0% local CPU strain).
2. LOCAL_ON_DEMAND: Spawns local uvicorn / background processes when requested for offline/local development.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Optional


class ExecutionMode(str, Enum):
    CLOUD_FIRST = "cloud_first"
    LOCAL_ON_DEMAND = "local_on_demand"


class AgentDaemon:
    def __init__(
        self,
        name: str,
        port: int,
        cwd: str = ".",
        module_path: Optional[str] = None,
        cloud_url: Optional[str] = None,
    ):
        self.name = name.upper()
        self.port = port
        self.cwd = cwd
        self.module_path = module_path or (
            "app.main:app" if "forge" in name.lower() else "sentinel.apps.api.main:app"
        )
        self.cloud_url = cloud_url
        self.process: Optional[subprocess.Popen] = None
        self.started_at: float = 0.0

    def start_local(self) -> tuple[bool, str]:
        """Launch agent locally on demand."""
        if self.process is not None and self.is_running():
            return False, f"{self.name}: already running locally (PID {self.process.pid})"

        cmd = [
            sys.executable, "-m", "uvicorn",
            self.module_path,
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--timeout-keep-alive", "30",
        ]
        try:
            cwd_path = Path(self.cwd)
            cwd_str = str(cwd_path.resolve()) if cwd_path.exists() else "."
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd_str,
            )
            self.started_at = time.time()
            return True, f"{self.name}: started locally on port {self.port} (PID {self.process.pid})"
        except Exception as e:
            return False, f"{self.name}: local startup failed: {e}"

    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def stop_local(self) -> tuple[bool, str]:
        """Stop local running process."""
        if self.process is None or not self.is_running():
            return False, f"{self.name}: not running locally"
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=3)
            pid = self.process.pid
            self.process = None
            return True, f"{self.name}: stopped local process (PID {pid})"
        except Exception as e:
            return False, f"{self.name}: stop error: {e}"

    def get_active_endpoint(self, prefer_local: bool = False) -> str:
        """Returns local URL if running and preferred, otherwise cloud URL."""
        if prefer_local and self.is_running():
            return f"http://127.0.0.1:{self.port}"
        if self.cloud_url:
            return self.cloud_url
        return f"http://127.0.0.1:{self.port}"


class DaemonSupervisor:
    """Coordinates cloud vs local execution for all agents."""

    def __init__(self, default_mode: ExecutionMode = ExecutionMode.CLOUD_FIRST):
        self.mode = default_mode
        self.daemons: dict[str, AgentDaemon] = {}
        self._init_agents()

    def _init_agents(self):
        root = Path(__file__).resolve().parent.parent

        self.daemons["friday"] = AgentDaemon(
            name="FRIDAY",
            port=9000,
            cwd=str(root / "FRIDAY"),
            cloud_url="http://friday:10000",
        )
        self.daemons["inference"] = AgentDaemon(
            name="INFERENCE",
            port=8000,
            cwd=str(root / "Inference"),
            module_path="app.main:app",
            cloud_url="http://inference:8000",
        )
        self.daemons["memora"] = AgentDaemon(
            name="MEMORA",
            port=8002,
            cwd=str(root / "Memora"),
            cloud_url="http://memora:8000",
        )
        self.daemons["forge"] = AgentDaemon(
            name="FORGE",
            port=8001,
            cwd=str(root / "Forge"),
            module_path="app.main:app",
            cloud_url="http://forge:8000",
        )
        self.daemons["sentinel"] = AgentDaemon(
            name="SENTINEL",
            port=8003,
            cwd=str(root / "Sentinel"),
            module_path="sentinel.apps.api.main:app",
            cloud_url="http://sentinel:8000",
        )
        self.daemons["stratex"] = AgentDaemon(
            name="STRATEX",
            port=8004,
            cwd=str(root / "Stratex"),
            cloud_url="http://stratex:8000",
        )
        self.daemons["intelx"] = AgentDaemon(
            name="INTELX",
            port=8005,
            cwd=str(root / "IntelX"),
            cloud_url="http://intelx:8000",
        )
        self.daemons["futuris"] = AgentDaemon(
            name="FUTURIS",
            port=8006,
            cwd=str(root / "Futuris"),
            cloud_url="http://futuris:8000",
        )
        self.daemons["cortex"] = AgentDaemon(
            name="CORTEX",
            port=8007,
            cwd=str(root / "Cortex"),
            cloud_url="http://cortex:8000",
        )
        self.daemons["vyralx"] = AgentDaemon(
            name="VyralX",
            port=8010,
            cwd=str(root / "VyralX"),
            module_path="app.main:app",
            cloud_url="http://vyralx:8000",
        )

    def get_endpoint(self, agent_name: str) -> str:
        """Get best routing endpoint based on mode and local status."""
        key = agent_name.lower()
        if key in self.daemons:
            prefer_local = self.mode == ExecutionMode.LOCAL_ON_DEMAND
            return self.daemons[key].get_active_endpoint(prefer_local=prefer_local)
        return ""

    def launch_local(self, agent_name: str) -> tuple[bool, str]:
        """Launch a specific agent locally on demand."""
        key = agent_name.lower()
        if key in self.daemons:
            return self.daemons[key].start_local()
        return False, f"Unknown agent: {agent_name}"

    def stop_local(self, agent_name: str) -> tuple[bool, str]:
        """Stop a specific locally running agent."""
        key = agent_name.lower()
        if key in self.daemons:
            return self.daemons[key].stop_local()
        return False, f"Unknown agent: {agent_name}"

    def status(self) -> dict[str, dict]:
        """Summary of all agent endpoints and local running states."""
        return {
            name: {
                "local_running": d.is_running(),
                "active_endpoint": d.get_active_endpoint(
                    prefer_local=(self.mode == ExecutionMode.LOCAL_ON_DEMAND)
                ),
                "cloud_url": d.cloud_url,
                "local_port": d.port,
            }
            for name, d in self.daemons.items()
        }
