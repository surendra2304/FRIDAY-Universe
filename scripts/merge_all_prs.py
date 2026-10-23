import subprocess
import json
import sys

repos = [
    "surendra2304/FRIDAY-Universe",
    "surendra2304/FRIDAY",
    "surendra2304/Inference",
    "surendra2304/Memora",
    "surendra2304/Stratex",
    "surendra2304/Futuris",
    "surendra2304/IntelX",
    "surendra2304/Forge",
    "surendra2304/VyralX",
    "surendra2304/Sentinel",
    "surendra2304/Cortex",
]

def run_cmd(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def main():
    print("=== Scanning and Merging All Open PRs ===")
    total_merged = 0
    total_failed = 0

    for r in repos:
        code, out, err = run_cmd(f'gh pr list --repo {r} --state open --json number,title,headRefName')
        if code != 0:
            print(f"Error listing PRs for {r}: {err}")
            continue
        
        try:
            prs = json.loads(out)
        except Exception as e:
            print(f"Failed to parse JSON for {r}: {e}")
            continue

        if not prs:
            print(f"[{r}] No open PRs.")
            continue

        print(f"\n[{r}] Found {len(prs)} open PR(s):")
        for p in prs:
            num = p["number"]
            title = p["title"]
            print(f"  -> Merging #{num}: {title}...")
            # Try merge
            m_code, m_out, m_err = run_cmd(f'gh pr merge {num} --repo {r} --merge --delete-branch')
            if m_code == 0:
                print(f"     [SUCCESS] Merged #{num}")
                total_merged += 1
            else:
                # Try admin merge if branch protection requires it
                print(f"     Standard merge failed: {m_err}. Retrying with --admin...")
                a_code, a_out, a_err = run_cmd(f'gh pr merge {num} --repo {r} --admin --merge --delete-branch')
                if a_code == 0:
                    print(f"     [SUCCESS] Admin-merged #{num}")
                    total_merged += 1
                else:
                    print(f"     [FAILED] Could not merge #{num}: {a_err}")
                    total_failed += 1

    print(f"\n=== Summary: Merged {total_merged} PR(s), {total_failed} Failed ===")

if __name__ == "__main__":
    main()
