from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MeshAgentManifestTests(unittest.TestCase):
    def test_registry_declares_ten_agents(self):
        registry_source = (ROOT / "mesh" / "registry.py").read_text(encoding="utf-8")
        agent_ids = re.findall(r'"agent_id":\s*"([a-f0-9-]+)"', registry_source)
        self.assertEqual(len(agent_ids), 10)
        self.assertEqual(len(set(agent_ids)), 10)

    def test_registry_includes_vyralx(self):
        registry_source = (ROOT / "mesh" / "registry.py").read_text(encoding="utf-8")
        self.assertIn("VyralX", registry_source)
        self.assertIn("http://vyralx:8000", registry_source)

    def test_transport_and_keepalive_include_vyralx(self):
        transport_source = (ROOT / "mesh" / "transport.py").read_text(encoding="utf-8")
        keepalive_source = (ROOT / "mesh" / "keepalive_loop.py").read_text(encoding="utf-8")
        self.assertIn('"VYRALX"', transport_source)
        self.assertIn('("vyralx"', keepalive_source)


if __name__ == "__main__":
    unittest.main()
