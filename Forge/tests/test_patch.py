from forge_upgrade.patching import SafePatcher


def test_patch_apply_and_preview(tmp_path):
    p = SafePatcher(tmp_path)
    prev = p.preview({"a.txt": "hello\n"})
    assert prev.additions == 1
    changes = p.apply({"a.txt": "hello\n"})
    assert changes[0].operation == "create"
