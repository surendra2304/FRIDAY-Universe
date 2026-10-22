import subprocess
import json
import secrets

def register_vyralx():
    cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]
    
    # Check if app_vyralx already exists
    chk_sql = "SELECT count(*) FROM application WHERE \"applicationId\"='app_vyralx' OR name='VyralX';"
    count = int(subprocess.check_output(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-tAc', chk_sql]).decode().strip() or "0")
    if count > 0:
        print("VyralX already registered in Dokploy database! Updating configuration...")
        update_sql = """
        UPDATE application 
        SET "repository"='VyralX', "owner"='surendra2304', "branch"='main', "autoDeploy"=true, "buildType"='dockerfile', "dockerfile"='Dockerfile'
        WHERE "applicationId"='app_vyralx' OR name='VyralX';
        """
        subprocess.check_call(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-c', update_sql])
        print("VyralX updated successfully in Dokploy.")
        return

    # Clone structure from app_friday
    sql_sample = 'SELECT row_to_json(a) FROM application a WHERE "applicationId"=\'app_friday\';'
    friday = json.loads(subprocess.check_output(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-tAc', sql_sample]).decode().strip())

    vyralx_env = """APP_NAME=VyralX
APP_ENV=production
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
API_KEY=vyralx_sec_7890123456789abcdef
DATABASE_URL=sqlite:///./data/vyralx.db
DATA_DIR=./data
MEDIA_DIR=./media
RENDER_DIR=./renders
FFMPEG_BIN=ffmpeg
FFPROBE_BIN=ffprobe
MAX_UPLOAD_MB=2048
MAX_STOCK_CLIP_MB=150
MAX_RENDER_SECONDS=14400
MAX_CONCURRENT_RENDERS=1
WORKER_REQUIRED=false

# FRIDAY Ecosystem Mesh Connections
FRIDAY_URL=http://friday:10000
FRIDAY_API_KEY=friday_Kh3angM6yJ_t41HROO3rmeGyzW1Ihiex45tf
INFERENCE_URL=http://inference:8000
INFERENCE_API_KEY=inference_JrnLmMGomQTeU6aT2XIYrBbLPUvc-gNQ4
INTELX_URL=http://intelx:8000
INTELX_API_KEY=intelx_3lEg1IlOGTdNVTEqwBvTRhgjIkpJ9cZddYNX
MEMORA_URL=http://memora:8000
MEMORA_API_KEY=memora_kzZnPXMEtve2dk1tbh8A0bFAL88NSbXFybmJ
SENTINEL_URL=http://sentinel:8000
SENTINEL_API_KEY=sentinel_jF-bgAo6XWDQqV-TaRW1MiG36QbC3YUY6c
"""

    friday["applicationId"] = "app_vyralx"
    friday["name"] = "VyralX"
    friday["appName"] = "VyralX"
    friday["repository"] = "VyralX"
    friday["owner"] = "surendra2304"
    friday["branch"] = "main"
    friday["buildPath"] = "/"
    friday["dockerfile"] = "Dockerfile"
    friday["buildType"] = "dockerfile"
    friday["autoDeploy"] = True
    friday["applicationStatus"] = "idle"
    friday["replicas"] = 1
    friday["env"] = vyralx_env
    friday["createdAt"] = "NOW()"

    # Construct INSERT SQL
    cols = []
    vals = []
    for k, v in friday.items():
        if k in ("createdAt",):
            cols.append(f'"{k}"')
            vals.append("NOW()")
        elif v is None:
            cols.append(f'"{k}"')
            vals.append("NULL")
        elif isinstance(v, bool):
            cols.append(f'"{k}"')
            vals.append("TRUE" if v else "FALSE")
        elif isinstance(v, (int, float)):
            cols.append(f'"{k}"')
            vals.append(str(v))
        elif isinstance(v, list):
            cols.append(f'"{k}"')
            vals.append(f"'{json.dumps(v)}'::jsonb" if "json" in k.lower() else "'{}'")
        else:
            safe_str = str(v).replace("'", "''")
            cols.append(f'"{k}"')
            vals.append(f"'{safe_str}'")

    insert_sql = f'INSERT INTO application ({", ".join(cols)}) VALUES ({", ".join(vals)});'
    subprocess.check_call(['docker', 'exec', cid, 'psql', '-U', 'dokploy', '-d', 'dokploy', '-c', insert_sql])
    print("SUCCESS: VyralX registered in Dokploy as 10th FRIDAY Universe agent!")

if __name__ == "__main__":
    register_vyralx()
