"""Audit evidence must not turn missing data or a green wrapper into acceptance."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('runtime_audit_report', Path(__file__).resolve().parents[1] / 'scripts/verification/runtime_audit/report.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.mark.parametrize('url,expected', [
    ('https://user:secret@example.org/path?token=private#fragment', 'https://example.org/path'),
    ('wss://example.org:444/activity?token=private', 'wss://example.org:444/activity'),
    ('http://[::1]:8000/api?key=private', 'http://[::1]:8000/api'),
    ('https://example.org:bad/api', '[invalid-url]'),
    ('file:///private/key', '[invalid-url]'),
])
def test_network_receipts_never_persist_query_or_userinfo_credentials(url, expected):
    assert m.safe_url(url) == expected


def test_missing_metrics_are_not_fabricated_as_zero_blocking_time():
    r = m.lighthouse_summary({'categories': {'performance': {'score': 1}}, 'audits': {}})
    assert r['state'] == 'incomplete'
    assert r['metrics'] == {}


def test_runtime_failure_is_not_a_passed_performance_run():
    assert m.lighthouse_summary({'runtimeError': {'code': 'PAGE_HUNG'}})['state'] == 'audit_failed'


def test_measurement_is_scoped_not_owner_audio_acceptance():
    audits = {k: {'numericValue': 1} for k in ['first-contentful-paint', 'largest-contentful-paint', 'total-blocking-time', 'cumulative-layout-shift']}
    r = m.lighthouse_summary({'categories': {'performance': {'score': .96}}, 'audits': audits})
    assert r['state'] == 'measured'
    assert r['owner_audio_accepted'] is False


def test_green_ci_wrapper_with_zero_audits_never_verifies_budget():
    r = m.classify_ci_audit('Error: Failed to automatically determine `staticDistDir`\nChecking assertions against 0 URL(s), 0 total run(s)', 'success')
    assert r['audit_state'] == 'no_audits_executed'
    assert r['performance_budget_verified'] is False
