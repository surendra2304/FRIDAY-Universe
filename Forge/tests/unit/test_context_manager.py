"""
Unit tests for ContextManager (token budgeting, log summarization, diff tracking).
"""

from app.core.context import ContextManager


def test_token_estimation():
    cm = ContextManager()
    assert cm.estimate_tokens("") == 0
    assert cm.estimate_tokens("abcd") == 1
    assert cm.estimate_tokens("a" * 400) == 100


def test_summarize_text_within_budget():
    cm = ContextManager()
    text = "Short log message"
    summarized = cm.summarize_text(text, max_tokens=100)
    assert summarized == text


def test_summarize_text_exceeding_budget():
    cm = ContextManager()
    large_text = "HEAD_" + ("x" * 2000) + "_TAIL"
    summarized = cm.summarize_text(large_text, max_tokens=100)

    assert "HEAD_" in summarized
    assert "_TAIL" in summarized
    assert "Context truncated" in summarized
    assert len(summarized) < len(large_text)


def test_record_and_retrieve_terminal_logs():
    cm = ContextManager()
    task_id = "task-test-context-1"

    cm.record_terminal_output(
        task_id=task_id,
        command="pytest -v",
        exit_code=1,
        stdout="collected 5 items",
        stderr="AssertionError: test failed",
        role="tester",
    )

    logs = cm.get_recent_terminal_logs(task_id)
    assert "pytest -v" in logs
    assert "FAILED (exit 1)" in logs
    assert "AssertionError" in logs


def test_record_diff():
    cm = ContextManager()
    task_id = "task-test-diff-1"

    cm.record_diff(task_id, "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new")
    diffs = cm.get_recent_diffs(task_id)
    assert "+new" in diffs
