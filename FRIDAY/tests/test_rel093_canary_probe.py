"""REL-093 canary probe (PROBE ONLY — never merge).

A deliberately uncollected test file: it is listed in NO workflow pytest
invocation, so the test-collection guard (scripts/ci_test_collection_audit.py)
must fail any PR that ships it. If the guard passes this file, the canary
is dead and the gap must be named instead.
"""


def test_rel093_probe_is_present():
    assert True
