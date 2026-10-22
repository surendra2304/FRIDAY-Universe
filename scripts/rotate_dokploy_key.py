#!/usr/bin/env python3
"""
Secure Dokploy API Key Rotator using Better-Auth SHA256 Hashing.
Rotates the API key in the database and updates local configuration files without logging the secret.
"""

import base64
import hashlib
import os
import secrets
import subprocess

def rotate():
    # 1. Generate new 64-char cryptographically secure token
    new_raw = secrets.token_urlsafe(48)
    start_6 = new_raw[:6]
    hashed_key = base64.urlsafe_b64encode(hashlib.sha256(new_raw.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
    
    # 2. Get container ID
    cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]
    
    # 3. Update apikey table
    sql = f"""
    UPDATE apikey 
    SET start = '{start_6}', key = '{hashed_key}', updated_at = NOW()
    WHERE reference_id = 'yd7n7cO7bbRAgS7dyWCWro2VNnhJKZ2m';
    """
    subprocess.check_call(["docker", "exec", cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", sql])
    
    # 4. Save to /opt/oracle_mcp/.dokploy_key (chmod 600)
    os.makedirs("/opt/oracle_mcp", exist_ok=True)
    with open("/opt/oracle_mcp/.dokploy_key", "w", encoding="utf-8") as f:
        f.write(new_raw.strip() + "\n")
    os.chmod("/opt/oracle_mcp/.dokploy_key", 0o600)
    
    # 5. Save to /opt/dokploy_mcp/.env (chmod 600)
    dokploy_env = "/opt/dokploy_mcp/.env"
    with open(dokploy_env, "w", encoding="utf-8") as f:
        f.write(f"DOKPLOY_API_KEY={new_raw.strip()}\n")
        f.write("DOKPLOY_URL=http://dokploy:3000\n")
    os.chmod(dokploy_env, 0o600)
    
    # 6. Restart dokploy-mcp
    subprocess.run("docker restart dokploy-mcp", shell=True)
    
    # 7. Test new key against live API
    test_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1/api/project.all -H 'x-api-key: {new_raw}'"
    status_code = subprocess.check_output(test_cmd, shell=True).decode().strip()
    
    if status_code == "200":
        print("ROTATION_STATUS=SUCCESS_HTTP_200")
    else:
        print(f"ROTATION_STATUS=FAILED_HTTP_{status_code}")

if __name__ == "__main__":
    rotate()
