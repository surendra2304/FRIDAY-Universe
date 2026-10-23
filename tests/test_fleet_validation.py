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

    def test_current_monorepo_structure_and_workflows(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(validate_repository(root), [])


if __name__ == "__main__":
    unittest.main()
