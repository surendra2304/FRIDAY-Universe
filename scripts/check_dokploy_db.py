import subprocess
import json

def run():
    cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]
    sql = 'SELECT json_agg(t) FROM (SELECT "applicationId", "name", "appName", "repository", "branch", "buildType", "autoDeploy", "dockerfile", "sourceType", "environmentId" FROM application) t;'
    raw = subprocess.check_output(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-tAc', sql]).decode().strip()
    data = json.loads(raw)
    print("Found applications in Dokploy DB:", len(data))
    for app in data:
        print(f"App: {app.get('name')} (ID: {app.get('applicationId')}, appName: {app.get('appName')})")
        print(f"   Repo: {app.get('repository')}, Branch: {app.get('branch')}, BuildType: {app.get('buildType')}, AutoDeploy: {app.get('autoDeploy')}")
        print(f"   Env: {app.get('environmentId')}")

    # Check full columns and sample FRIDAY row
    sql_sample = 'SELECT row_to_json(a) FROM application a WHERE name=\'FRIDAY\';'
    sample = subprocess.check_output(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-tAc', sql_sample]).decode().strip()
    print("\nSample FRIDAY row keys:")
    print(list(json.loads(sample).keys()))
    print("\nSample FRIDAY full row:")
    print(sample)

if __name__ == "__main__":
    run()
