import subprocess

cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]

# 1. Fetch githubId
gh_rows = subprocess.check_output(f'docker exec {cid} psql -U dokploy -d dokploy -t -c "SELECT \\"githubId\\" FROM github LIMIT 1;"', shell=True).decode().strip()
if not gh_rows:
    print("NO_GITHUB_FOUND")
    exit(1)

github_id = gh_rows.split()[0]
print(f"Discovered GitHub ID: {github_id}")

# 2. Read /tmp/register.sql
with open('/tmp/register.sql', 'r') as f:
    sql = f.read()

# Replace old githubId with newly authorized github_id
import re
sql = re.sub(r"'D148IQ5Uj8Hk5wRDKOta9'", f"'{github_id}'", sql)

# Clean app slugs
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

with open('/tmp/final_gitops_register.sql', 'w') as f:
    f.write(sql)

cmd = f"docker exec -i {cid} psql -U dokploy -d dokploy < /tmp/final_gitops_register.sql"
subprocess.run(cmd, shell=True, check=True)
print("SUCCESS: All 9 applications linked to GitHub with GitOps autoDeploy enabled!")
