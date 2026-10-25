import json
import secrets
import subprocess
import sys
from pathlib import Path

SSH_KEY = r"USER_HOME\.ssh\friday_universe_oracle.key"
SSH_USER = "ubuntu"
SSH_HOST = "140.245.208.100"
CREDENTIALS_FILE = Path(r"FRIDAY_UNIVERSE_HOME\CREDENTIALS_PHASE3_POSTGRES.json")

DATABASES = [
    {"app_id": "app_friday",    "name": "FRIDAY",    "db": "friday_db",    "user": "friday_user"},
    {"app_id": "app_inference", "name": "Inference", "db": "inference_db", "user": "inference_user"},
    {"app_id": "app_memora",    "name": "Memora",    "db": "memora_db",    "user": "memora_user"},
    {"app_id": "app_stratex",   "name": "Stratex",   "db": "stratex_db",   "user": "stratex_user"},
    {"app_id": "app_forge",     "name": "Forge",     "db": "forge_db",     "user": "forge_user"},
    {"app_id": "app_cortex",    "name": "Cortex",    "db": "cortex_db",    "user": "cortex_user"},
    {"app_id": "app_sentinel",  "name": "Sentinel",  "db": "sentinel_db",  "user": "sentinel_user"},
    {"app_id": "app_intelx",    "name": "IntelX",    "db": "intelx_db",    "user": "intelx_user"},
    {"app_id": "app_futuris",   "name": "Futuris",   "db": "futuris_db",   "user": "futuris_user"},
    {"app_id": "app_vyralx",    "name": "VyralX",    "db": "vyralx_db",    "user": "vyralx_user"},
]

def load_or_generate_credentials():
    if CREDENTIALS_FILE.exists():
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            creds = json.load(f)
    else:
        creds = {}
    
    updated = False
    for item in DATABASES:
        db = item["db"]
        user = item["user"]
        if db not in creds:
            # Generate 24-character cryptographically secure password
            pwd = secrets.token_urlsafe(18)
            creds[db] = {
                "app_id": item["app_id"],
                "name": item["name"],
                "database": db,
                "username": user,
                "password": pwd,
                "host": "dokploy-postgres",
                "port": 5432,
                "async_url": f"postgresql+asyncpg://{user}:{pwd}@dokploy-postgres:5432/{db}",
                "sync_url": f"postgresql://{user}:{pwd}@dokploy-postgres:5432/{db}"
            }
            updated = True
            
    if updated or not CREDENTIALS_FILE.exists():
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
        print(f"Saved database credentials to {CREDENTIALS_FILE}")
        
    return creds

def run_remote_python(script_str):
    res = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{SSH_USER}@{SSH_HOST}", "python3"],
        input=script_str.encode("utf-8"),
        capture_output=True
    )
    if res.returncode != 0:
        print("Remote error:", res.stderr.decode("utf-8", errors="replace"))
        raise RuntimeError(f"Remote command failed with code {res.returncode}")
    return res.stdout.decode("utf-8", errors="replace")

def execute_provisioning(creds):
    print("=" * 70)
    print("PHASE 3: PROVISIONING 10 ISOLATED POSTGRESQL 18 LOGICAL DATABASES")
    print("=" * 70)
    
    remote_script = f"""
import subprocess
import json

creds = {json.dumps(creds)}

cid = subprocess.check_output('docker ps -q -f name=dokploy-postgres', shell=True).decode().strip()
print(f"Targeting PostgreSQL Container: {{cid}}")

results = []

for db_name, info in creds.items():
    user = info["username"]
    pwd = info["password"]
    app_name = info["name"]
    
    print(f"\\n--- Provisioning {{db_name}} for {{app_name}} (User: {{user}}) ---")
    
    # 1. Create role if not exists and set password
    role_sql = f'''
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{{user}}') THEN
            CREATE ROLE {{user}} WITH LOGIN PASSWORD '{{pwd}}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
        ELSE
            ALTER ROLE {{user}} WITH PASSWORD '{{pwd}}';
        END IF;
    END
    $$;
    '''
    subprocess.check_call(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'postgres', '-c', role_sql])
    print(f"  Role '{{user}}' verified and password synchronized.")
    
    # 2. Create database if not exists
    chk_db = subprocess.check_output(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'postgres', '-tAc', f"SELECT count(*) FROM pg_database WHERE datname='{{db_name}}';"]).decode().strip()
    if int(chk_db) == 0:
        subprocess.check_call(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'postgres', '-c', f"CREATE DATABASE {{db_name}} OWNER {{user}};"])
        print(f"  Database '{{db_name}}' created with owner '{{user}}'.")
    else:
        print(f"  Database '{{db_name}}' already exists.")
        
    # 3. Grant and isolate database access
    perm_sql = f'''
    GRANT ALL PRIVILEGES ON DATABASE {{db_name}} TO {{user}};
    GRANT ALL PRIVILEGES ON DATABASE {{db_name}} TO dokploy;
    REVOKE CONNECT ON DATABASE {{db_name}} FROM PUBLIC;
    GRANT CONNECT ON DATABASE {{db_name}} TO {{user}};
    GRANT CONNECT ON DATABASE {{db_name}} TO dokploy;
    '''
    subprocess.check_call(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'postgres', '-c', perm_sql])
    
    # 4. Initialize schema permissions and standard extensions inside target database
    init_db_sql = f'''
    GRANT ALL ON SCHEMA public TO {{user}};
    ALTER SCHEMA public OWNER TO {{user}};
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    '''
    subprocess.check_call(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', db_name, '-c', init_db_sql])
    print(f"  Schema 'public' ownership granted and extensions installed in '{{db_name}}'.")
    
    # 5. Verify direct connectivity as the isolated user
    verify_out = subprocess.check_output(['docker', 'exec', cid, 'psql', '-U', user, '-d', db_name, '-tAc', 'SELECT current_user, current_database();']).decode().strip()
    print(f"  Direct connection verified: {{verify_out}}")
    results.append({{"database": db_name, "user": user, "verified": verify_out == f"{{user}}|{{db_name}}"}})

print("\\n" + "=" * 70)
print("PROVISIONING SUMMARY:")
for r in results:
    status = "SUCCESS" if r["verified"] else "FAILED"
    print(f"  {{r['database']:15s}} | User: {{r['user']:15s}} | Status: {{status}}")
print("=" * 70)
"""
    output = run_remote_python(remote_script)
    print(output)

def update_dokploy_environment_variables(creds):
    print("\n" + "=" * 70)
    print("UPDATING DOKPLOY APPLICATION ENVIRONMENT VARIABLES")
    print("=" * 70)
    
    remote_script = f"""
import subprocess
import json

creds = {json.dumps(creds)}

cid = subprocess.check_output('docker ps -q -f name=dokploy-postgres', shell=True).decode().strip()

for db_name, info in creds.items():
    app_id = info["app_id"]
    app_name = info["name"]
    user = info["username"]
    pwd = info["password"]
    db = info["database"]
    async_url = info["async_url"]
    sync_url = info["sync_url"]
    
    # Fetch current env string
    sql_get = f"SELECT env FROM application WHERE \\\"applicationId\\\"='{{app_id}}' OR name='{{app_name}}';"
    current_env = subprocess.check_output(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-tAc', sql_get]).decode()
    
    lines = [l for l in current_env.splitlines() if l.strip()]
    env_dict = {{}}
    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            env_dict[k.strip()] = v.strip()
            
    # Inject database URLs
    env_dict["DATABASE_URL"] = async_url if app_name in ["Futuris", "Memora", "Sentinel", "IntelX", "Cortex"] else sync_url
    env_dict["SYNC_DATABASE_URL"] = sync_url
    env_dict["ASYNC_DATABASE_URL"] = async_url
    
    if app_name == "Sentinel":
        env_dict["SENTINEL_DB_HOST"] = "dokploy-postgres"
        env_dict["SENTINEL_DB_PORT"] = "5432"
        env_dict["SENTINEL_DB_USER"] = user
        env_dict["SENTINEL_DB_PASSWORD"] = pwd
        env_dict["SENTINEL_DB_NAME"] = db
    elif app_name == "Cortex":
        env_dict["POSTGRES_DSN"] = async_url
    elif app_name == "IntelX":
        env_dict["INTELX_DB_URL"] = async_url
    elif app_name == "FRIDAY":
        env_dict["FRIDAY_DATABASE_URL"] = sync_url
    elif app_name == "Stratex":
        env_dict["STRATEX_DATABASE_URL"] = sync_url
    elif app_name == "Forge":
        env_dict["FORGE_DATABASE_URL"] = sync_url
        
    # Reassemble env string
    new_env_lines = [f"{{k}}={{v}}" for k, v in env_dict.items()]
    new_env_str = "\\n".join(new_env_lines)
    
    # Update dokploy db
    escaped_env = new_env_str.replace("'", "''")
    update_sql = f"UPDATE application SET env='{{escaped_env}}' WHERE \\\"applicationId\\\"='{{app_id}}' OR name='{{app_name}}';"
    subprocess.check_call(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-c', update_sql])
    print(f"Synchronized DATABASE_URL for {{app_name}} in Dokploy registry.")

print("\\nAll 10 applications successfully synchronized with their PostgreSQL 18 databases in Dokploy.")
"""
    output = run_remote_python(remote_script)
    print(output)

def verify_cross_database_isolation(creds):
    print("\n" + "=" * 70)
    print("VERIFYING CROSS-DATABASE ISOLATION (ZERO-TRUST SECURITY CHECK)")
    print("=" * 70)
    
    remote_script = f"""
import subprocess

cid = subprocess.check_output('docker ps -q -f name=dokploy-postgres', shell=True).decode().strip()

# Test that friday_user cannot connect to sentinel_db or memora_db
tests = [
    ("friday_user", "sentinel_db", "CONNECT denied to sentinel_db"),
    ("friday_user", "memora_db", "CONNECT denied to memora_db"),
    ("sentinel_user", "stratex_db", "CONNECT denied to stratex_db"),
    ("vyralx_user", "friday_db", "CONNECT denied to friday_db"),
]

for user, target_db, test_desc in tests:
    res = subprocess.run(
        ['docker', 'exec', cid, 'psql', '-U', user, '-d', target_db, '-c', 'SELECT 1;'],
        capture_output=True,
        text=True
    )
    if "permission denied" in res.stderr.lower() or "fatal" in res.stderr.lower():
        print(f"  PASS [ISOLATED]: {{user}} -> {{target_db}} | {{test_desc}}")
    else:
        print(f"  FAIL [LEAK]: {{user}} was able to connect to {{target_db}}!")
"""
    output = run_remote_python(remote_script)
    print(output)

if __name__ == "__main__":
    creds = load_or_generate_credentials()
    execute_provisioning(creds)
    update_dokploy_environment_variables(creds)
    verify_cross_database_isolation(creds)
