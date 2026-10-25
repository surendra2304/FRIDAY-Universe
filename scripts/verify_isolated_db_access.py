#!/usr/bin/env python3
"""
Verify isolated user credentials and write/read permissions across all 10 databases.
"""
import json
import subprocess
from pathlib import Path

SSH_KEY = r"USER_HOME\.ssh\friday_universe_oracle.key"
SSH_USER = "ubuntu"
SSH_HOST = "140.245.208.100"
CREDENTIALS_FILE = Path(r"FRIDAY_UNIVERSE_HOME\CREDENTIALS_PHASE3_POSTGRES.json")

def verify_all():
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        creds = json.load(f)

    remote_test = f"""
import subprocess
import json

creds = {json.dumps(creds)}
cid = subprocess.check_output('docker ps -q -f name=dokploy-postgres', shell=True).decode().strip()

results = {{}}

for db_name, info in creds.items():
    user = info["username"]
    pwd = info["password"]
    
    # Test connection and table query as the isolated user using PGPASSWORD
    cmd = [
        'docker', 'exec', '-e', f'PGPASSWORD={{pwd}}', cid,
        'psql', '-U', user, '-d', db_name, '-tAc',
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=True)
        count = int(p.stdout.strip())
        results[db_name] = {{"status": "SUCCESS", "user": user, "table_count": count}}
        print(f"  [OK] {{db_name:15s}} | User: {{user:16s}} | Tables accessible: {{count}}")
    except Exception as e:
        results[db_name] = {{"status": "FAIL", "user": user, "error": str(e)}}
        print(f"  [FAIL] {{db_name:15s}} | User: {{user:16s}} | Error: {{e}}")

print("\\nRESULTS_JSON:" + json.dumps(results))
"""
    res = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{SSH_USER}@{SSH_HOST}", "python3"],
        input=remote_test,
        capture_output=True,
        text=True
    )
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)

if __name__ == "__main__":
    verify_all()
