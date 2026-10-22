import pytest

from forge_upgrade.path_guard import PathGuard, SandboxViolation


def test_path_guard(tmp_path):
    g = PathGuard(tmp_path)
    assert g.resolve("a.txt").parent == tmp_path
    with pytest.raises(SandboxViolation):
        g.resolve("../secret")
