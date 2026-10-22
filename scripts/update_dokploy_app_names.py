import subprocess

apps = [
    ('app_cortex', 'Cortex'),
    ('app_forge', 'Forge'),
    ('app_friday', 'FRIDAY'),
    ('app_futuris', 'Futuris'),
    ('app_inference', 'Inference'),
    ('app_intelx', 'IntelX'),
    ('app_memora', 'Memora'),
    ('app_sentinel', 'Sentinel'),
    ('app_stratex', 'Stratex')
]

cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]

for app_id, clean_name in apps:
    sql = f'UPDATE application SET "name" = \'{clean_name}\', "appName" = \'{clean_name}\' WHERE "applicationId" = \'{app_id}\';'
    subprocess.run(["docker", "exec", cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", sql], check=True)
    print(f"Updated {app_id} -> {clean_name}")

print("All 9 applications updated successfully!")
