from forge_upgrade.secret_redaction import redact


def test_redact():
    text = "token=supersecret"
    out = redact(text)
    assert "supersecret" not in out


# Fake credentials with real token shapes (TASK-SEN-011 regression tests for
# SEN-005 finding F-1: a GitHub token persisted in plaintext in Forge
# workspace terminal.log files via a logged git remote command).
FAKE_CLASSIC_PAT = "ghp_" + "A1" * 18  # 40 chars, classic PAT shape
FAKE_FINE_GRAINED_PAT = "github_pat_" + "B2c" * 12


def test_redact_masks_token_embedded_in_git_remote_url():
    command = (
        "git remote set-url origin "
        f"https://x-access-token:{FAKE_CLASSIC_PAT}@github.com/surendra2304/Forge.git"
    )
    out = redact(command)
    assert FAKE_CLASSIC_PAT not in out
    assert "[REDACTED]" in out


def test_redact_masks_fine_grained_pat():
    out = redact(f"git clone https://{FAKE_FINE_GRAINED_PAT}@github.com/x/y.git")
    assert FAKE_FINE_GRAINED_PAT not in out
    assert "[REDACTED]" in out


def test_redact_masks_generic_url_userinfo_password():
    # No keyword and no known token prefix: only the URL-userinfo pattern
    # can catch this shape.
    out = redact("curl https://deploy:SomePassw0rd@example.com/feed")
    assert "SomePassw0rd" not in out
    assert "https://deploy:[REDACTED]@example.com/feed" in out
