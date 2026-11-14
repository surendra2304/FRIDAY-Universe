"""Small, offline truth-preserving summaries for owner-workflow audit receipts."""
from __future__ import annotations

from urllib.parse import urlsplit


def safe_url(value: str) -> str:
    """Exclude credentials, query tokens and fragments from persisted network logs."""
    try:
        parts = urlsplit(value)
        if parts.scheme not in {'http', 'https', 'ws', 'wss'} or not parts.hostname:
            return '[invalid-url]'
        host = parts.hostname
        if ':' in host:
            host = '[' + host + ']'
        port = ':' + str(parts.port) if parts.port else ''
        return parts.scheme + '://' + host + port + parts.path
    except ValueError:
        return '[invalid-url]'


def lighthouse_summary(report: dict) -> dict:
    result = {'state': 'incomplete', 'scope': 'one Lighthouse run, not owner workflow acceptance',
              'owner_audio_accepted': False, 'metrics': {}}
    if report.get('runtimeError'):
        result['state'] = 'audit_failed'
        return result
    score = report.get('categories', {}).get('performance', {}).get('score')
    audits = report.get('audits', {})
    for key in ['first-contentful-paint', 'largest-contentful-paint', 'total-blocking-time', 'cumulative-layout-shift']:
        value = audits.get(key, {}).get('numericValue')
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result['metrics'][key] = value
    if isinstance(score, (int, float)) and not isinstance(score, bool) and len(result['metrics']) == 4:
        result.update(state='measured', performance_score=score)
    return result


def classify_ci_audit(log: str, job_conclusion: str) -> dict:
    no_audits = ('0 URL(s), 0 total run(s)' in log
                 or 'Failed to automatically determine `staticDistDir`' in log)
    return {'job_conclusion': job_conclusion,
            'audit_state': 'no_audits_executed' if no_audits else 'requires_report_inspection',
            'performance_budget_verified': False}
