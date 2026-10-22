#!/usr/bin/env python3
"""
Repair Dokploy API Key Authentication in Dokploy PostgreSQL.
Restores the active API key row in the Better-Auth 'apikey' table without generating a new key,
and verifies direct connectivity to Dokploy API.
"""

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import urllib.request

DOKPLOY_KEY_PATH = "/opt/oracle_mcp/.dokploy_key"
DOKPLOY_ENV_PATH = "/opt/dokploy_mcp/.env"
DOKPLOY_API_URL = "http://127.0.0.1:3000/api"

def run_cmd(cmd_list):
    res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd_list)}\n{res.stderr}")
    return res.stdout.strip()

def main():
    print("=== DOKPLOY API AUTHENTICATION REPAIR ===")
    
    # 1. Read existing raw key
    if not os.path.exists(DOKPLOY_KEY_PATH):
        print(f"ERROR: {DOKPLOY_KEY_PATH} not found!")
        sys.exit(1)
        
    with open(DOKPLOY_KEY_PATH, "r", encoding="utf-8") as f:
        raw_key = f.read().strip()
        
    if not raw_key:
        print("ERROR: Dokploy key is empty!")
        sys.exit(1)
        
    start_6 = raw_key[:6]
    hashed_key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
    key_len = len(raw_key)
    print(f"Found existing key: length={key_len}, start_prefix={start_6}***")

    # 2. Find PostgreSQL container ID
    cid = run_cmd(["docker", "ps", "-q", "--filter", "name=dokploy-postgres"]).split()
    if not cid:
        print("ERROR: dokploy-postgres container not found!")
        sys.exit(1)
    postgres_cid = cid[0]
    print(f"PostgreSQL container: {postgres_cid}")

    # 3. Get admin user id
    get_user_sql = 'SELECT id, email FROM "user" LIMIT 1;'
    user_out = run_cmd(["docker", "exec", postgres_cid, "psql", "-U", "dokploy", "-d", "dokploy", "-t", "-A", "-c", get_user_sql])
    if not user_out:
        print("ERROR: No admin user found in 'user' table!")
        sys.exit(1)
    
    parts = user_out.split("|")
    admin_id = parts[0].strip()
    admin_email = parts[1].strip() if len(parts) > 1 else "unknown"
    print(f"Admin User ID: {admin_id} ({admin_email})")

    # 4. Check if key exists in apikey table
    check_sql = f"SELECT count(*) FROM apikey WHERE reference_id = '{admin_id}';"
    count_res = run_cmd(["docker", "exec", postgres_cid, "psql", "-U", "dokploy", "-d", "dokploy", "-t", "-A", "-c", check_sql])
    existing_count = int(count_res.strip()) if count_res.strip().isdigit() else 0
    print(f"Current rows in apikey for admin: {existing_count}")

    if existing_count > 0:
        print("Updating existing apikey row...")
        update_sql = f"""
        UPDATE apikey
        SET name = 'FRIDAY Universe x ChatGPT',
            start = '{start_6}',
            key = '{hashed_key}',
            enabled = true,
            updated_at = NOW()
        WHERE reference_id = '{admin_id}';
        """
        run_cmd(["docker", "exec", postgres_cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", update_sql])
    else:
        print("Inserting new apikey row...")
        row_id = secrets.token_hex(16)
        insert_sql = f"""
        INSERT INTO apikey (id, name, start, prefix, key, enabled, config_id, reference_id, created_at, updated_at)
        VALUES ('{row_id}', 'FRIDAY Universe x ChatGPT', '{start_6}', NULL, '{hashed_key}', true, 'default', '{admin_id}', NOW(), NOW());
        """
        run_cmd(["docker", "exec", postgres_cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", insert_sql])

    # 5. Verify row in database
    verify_sql = f"SELECT id, name, start, enabled FROM apikey WHERE reference_id = '{admin_id}';"
    verify_out = run_cmd(["docker", "exec", postgres_cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", verify_sql])
    print("Database verification:")
    print(verify_out)

    # 6. Synchronize /opt/dokploy_mcp/.env
    if os.path.exists(os.path.dirname(DOKPLOY_ENV_PATH)):
        with open(DOKPLOY_ENV_PATH, "w", encoding="utf-8") as f:
            f.write(f"DOKPLOY_API_KEY={raw_key}\n")
            f.write("DOKPLOY_URL=http://dokploy:3000\n")
        os.chmod(DOKPLOY_ENV_PATH, 0o600)
        print("Updated /opt/dokploy_mcp/.env (chmod 600)")

    # 7. Test direct call to Dokploy API
    url = f"{DOKPLOY_API_URL}/project.all"
    req = urllib.request.Request(url, headers={"x-api-key": raw_key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = json.loads(resp.read().decode())
            print(f"Direct API test: HTTP {status} OK")
            print(f"Projects returned: {len(body) if isinstance(body, list) else 0}")
    except Exception as e:
        print(f"Direct API test FAILED: {e}")
        sys.exit(1)

    # 8. Restart oracle-cloud-mcp service to refresh any cached state
    try:
        run_cmd(["systemctl", "restart", "oracle-cloud-mcp"])
        print("Restarted oracle-cloud-mcp service successfully.")
    except Exception as e:
        print(f"Warning: Failed to restart oracle-cloud-mcp: {e}")

    print("=== DOKPLOY AUTHENTICATION REPAIR COMPLETE ===")

if __name__ == "__main__":
    main()
