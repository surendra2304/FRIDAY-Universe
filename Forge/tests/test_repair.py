from forge_upgrade.recovery import RepairController


def test_duplicate_patch_blocked():
    c = RepairController()
    ok, _ = c.allow("t", "test_failure", "same fail", "patch")
    assert ok
    c.record("t", "test_failure", "same fail", "patch", "repair")
    ok2, _ = c.allow("t", "test_failure", "same fail", "patch")
    assert not ok2
