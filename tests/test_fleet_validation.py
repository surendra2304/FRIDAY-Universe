from pathlib import Path
import unittest

from scripts.validate_fleet import AGENTS, mirror_workflow_violations, validate_repository


class FleetValidationTests(unittest.TestCase):
    def test_mirror_workflow_rejects_force_push(self):
        unsafe = """
        agent: [FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, VyralX]
        token: ${{ secrets.GH_PAT_MIRROR }}
        run: |
          git push origin split-agent:main --force
          gh pr create
        """
        problems = mirror_workflow_violations(unsafe)
        self.assertTrue(any("force-push" in problem for problem in problems))
        self.assertTrue(any("directly" in problem for problem in problems))

    def test_mirror_workflow_rejects_automatic_file_deletion(self):
        unsafe = """
        agent: [FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, VyralX]
        token: ${{ secrets.GH_PAT_MIRROR }}
        rsync -a --delete source/ destination/
        gh pr create
        """
        self.assertTrue(any("delete standalone-only" in problem for problem in mirror_workflow_violations(unsafe)))

    def test_mirror_workflow_rejects_token_fallback(self):
        unsafe = """
        agent: [FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, VyralX]
        token: ${{ secrets.GH_PAT_MIRROR || github.token }}
        gh pr create
        """
        self.assertTrue(any("fall back" in problem for problem in mirror_workflow_violations(unsafe)))

    def test_agent_inventory_has_ten_unique_entries(self):
        self.assertEqual(len(AGENTS), 10)
        self.assertEqual(len(set(AGENTS)), 10)

    def test_mirror_workflow_is_manual_and_pr_based(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "mirror-subrepos.yml").read_text(encoding="utf-8")
        self.assertEqual(mirror_workflow_violations(workflow), [])
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("gh pr create", workflow)
        self.assertRegex(workflow, r"(?m)^\s*rsync -a")
        self.assertNotRegex(workflow, r"(?m)^\s*rsync\b[^\n]*--delete\b")
        self.assertIn("http.extraheader=AUTHORIZATION: basic", workflow)
        self.assertIn("ref: ${{ github.sha }}", workflow)

    def test_mirror_workflow_rejects_external_push_without_pr(self):
        unsafe = """
        on:
          workflow_dispatch:
        run: |
          git push origin main
        """
        problems = mirror_workflow_violations(unsafe)
        self.assertTrue(any("external repository" in problem for problem in problems))

    def test_mirror_workflow_requires_pull_request_for_cross_repo_changes(self):
        unsafe = """
        on:
          workflow_dispatch:
        run: |
          git push origin sync/monorepo-abc123
        """
        problems = mirror_workflow_violations(unsafe)
        self.assertTrue(any("pull request" in problem for problem in problems))

    def test_deployment_sources_do_not_embed_live_credentials(self):
        root = Path(__file__).resolve().parents[1]
        sensitive_paths = (
            "MASTER_AGENT_AWAKENING_DIRECTIVE.md",
            "FRIDAY_UNIVERSE_MASTER_ARCHITECTURE.md",
            "deploy/setup_fleet.sh",
            "scripts/register_vyralx_dokploy.py",
            "scripts/generate_master_architecture_pdf.py",
            "Memora/core/resilience/telemetry.py",
            "FRIDAY/tests/test_codex_invariants_and_mesh.py",
        )
        live_key_patterns = (
            r"(?m)^\s*SENTINEL_AUDIT_(?:HMAC|SIGNING)_KEY=[A-Fa-f0-9]{32,}\s*$",
            r"(?m)^\s*(?:SENTINEL_API_KEY|FRIDAY_API_KEY|INFERENCE_API_KEY|INTELX_API_KEY|MEMORA_API_KEY|VYRALX_API_KEY)=(?:sentinel|friday|inference|intelx|memora|vyralx)_[A-Za-z0-9_-]{20,}\s*$",
            r"oracle\+oracledb(?:_async)?://ADMIN:[^@\s]+@",
        )
        for relative in sensitive_paths:
            content = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("FridayUniverse2026", content, relative)
            for pattern in live_key_patterns:
                self.assertNotRegex(content, pattern, relative)

    def test_current_monorepo_structure_and_workflows(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(validate_repository(root), [])


if __name__ == "__main__":
    unittest.main()
