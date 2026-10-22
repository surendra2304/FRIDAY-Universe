from forge_upgrade.command_policy import CommandPolicy, Decision


def test_low_risk():
    assert CommandPolicy().evaluate("pytest -q").decision == Decision.ALLOW


def test_high_risk_requires_approval():
    assert CommandPolicy().evaluate("git reset --hard HEAD").decision == Decision.APPROVE
