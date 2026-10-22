import subprocess

cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]

# 1. Fetch current owner organizationId
org_id = subprocess.check_output(f'docker exec {cid} psql -U dokploy -d dokploy -t -c "SELECT organization_id FROM member WHERE role=\'owner\' LIMIT 1;"', shell=True).decode().strip()
print(f"Current Owner Organization ID: {org_id}")

# 2. Insert project & environment
setup_sql = f"""
INSERT INTO project ("projectId", "name", "description", "createdAt", "env", "organizationId")
VALUES ('proj_friday_universe', 'FRIDAY Universe', 'Autonomous 9-Agent Sovereign Multi-Agent Network', NOW()::text, '', '{org_id}')
ON CONFLICT ("projectId") DO NOTHING;

INSERT INTO environment ("environmentId", "name", "description", "createdAt", "projectId", "env", "isDefault")
VALUES ('env_production_01', 'production', 'Production Environment', NOW()::text, 'proj_friday_universe', '', true)
ON CONFLICT ("environmentId") DO NOTHING;
"""

subprocess.run(["docker", "exec", cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", setup_sql], check=True)
print("Project 'FRIDAY Universe' and Environment 'production' created successfully!")

# 3. Read /tmp/register.sql, fix slugs to clean canonical names, and execute
with open('/tmp/register.sql', 'r') as f:
    sql = f.read()

# Update slugs to clean names
name_map = {
    "'friday-cortex'": "'Cortex'",
    "'friday-forge'": "'Forge'",
    "'friday-core'": "'FRIDAY'",
    "'friday-futuris'": "'Futuris'",
    "'friday-inference'": "'Inference'",
    "'friday-intelx'": "'IntelX'",
    "'friday-memora'": "'Memora'",
    "'friday-sentinel'": "'Sentinel'",
    "'friday-stratex'": "'Stratex'",
}
for old_slug, new_slug in name_map.items():
    sql = sql.replace(old_slug, new_slug)

with open('/tmp/clean_register.sql', 'w') as f:
    f.write(sql)

cmd = f"docker exec -i {cid} psql -U dokploy -d dokploy < /tmp/clean_register.sql"
subprocess.run(cmd, shell=True, check=True)
print("All 9 applications, environment variables, and domains loaded into Dokploy successfully!")
