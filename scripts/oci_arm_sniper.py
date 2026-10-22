#!/usr/bin/env python3
"""
FRIDAY Universe — OCI ARM A1 Active Sniper & Status Checker
Can query the cloud service status, check OCI inventory, or trigger allocation checks.
"""

import json
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SSH_KEY = r"C:\Users\Surendra\.ssh\friday_universe_oracle.key"
CLOUD_HOST = "ubuntu@140.245.208.100"

def get_remote_status():
    cmd = [
        "ssh",
        "-i", SSH_KEY,
        "-o", "StrictHostKeyChecking=no",
        CLOUD_HOST,
        "sudo systemctl status friday-oci-a1-allocator --no-pager; echo '--- STATE ---'; sudo cat /var/lib/friday-arm-sniper/state.json 2>/dev/null; echo '\n--- RECENT LOGS ---'; sudo journalctl -u friday-oci-a1-allocator -n 10 --no-pager"
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout

if __name__ == "__main__":
    print("=" * 65)
    print("FRIDAY UNIVERSE — 24/7 OCI ARM SNIPER TELEMETRY")
    print("=" * 65)
    output = get_remote_status()
    print(output)
