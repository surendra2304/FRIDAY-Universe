import subprocess
import secrets
from pathlib import Path

# Generate a brand new high-entropy 64-character hex secret
new_secret = secrets.token_hex(32)

# Save locally to D:\ChatGPT\.env.gateway_secret
local_secret_file = Path(r"D:\ChatGPT\.env.gateway_secret")
with open(local_secret_file, "w", encoding="utf-8") as f:
    f.write(f"GATEWAY_SECRET={new_secret}\n")
print(f"SUCCESS: Saved new gateway secret locally to {local_secret_file} (length {len(new_secret)})")

# Remote script to update /opt/oracle_mcp/.gateway_secret and service
REMOTE_SCRIPT = """
import os, subprocess, re

secret = "__REPLACE_SECRET__"
secret_file = "/opt/oracle_mcp/.gateway_secret"

with open(secret_file, "w") as f:
    f.write(secret + "\\n")
os.chmod(secret_file, 0o600)
print("SUCCESS: Updated secret_file on Oracle VM")

# Update systemd service Environment to read from file or var
service_path = "/etc/systemd/system/oracle-cloud-mcp.service"
with open(service_path, "r") as f:
    srv = f.read()

srv = re.sub(r"Environment=ORACLE_MCP_TOKEN=.*", f"Environment=ORACLE_MCP_TOKEN={secret}", srv)
with open(service_path, "w") as f:
    f.write(srv)

subprocess.run(["systemctl", "daemon-reload"])
subprocess.run(["systemctl", "restart", "oracle-cloud-mcp"])
print("SUCCESS: systemd daemon-reload and oracle-cloud-mcp restarted.")
""".replace("__REPLACE_SECRET__", new_secret)

SSH_CMD = [
    "ssh", "-o", "BatchMode=yes",
    "-i", r"C:\Users\Surendra\.ssh\friday_universe_oracle.key",
    "ubuntu@140.245.208.100",
    "sudo python3 -"
]

proc = subprocess.run(SSH_CMD, input=REMOTE_SCRIPT, capture_output=True, text=True)
print("REMOTE OUT:", proc.stdout)
if proc.stderr:
    print("REMOTE ERR:", proc.stderr)
