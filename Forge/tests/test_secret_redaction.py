from forge_upgrade.secret_redaction import redact


def test_redact():
    text = "token=supersecret"
    out = redact(text)
    assert "supersecret" not in out
