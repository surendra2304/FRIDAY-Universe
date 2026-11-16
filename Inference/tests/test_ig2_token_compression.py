"""TASK-IG2-INF-04: rule-based token compression (OmniRoute pattern).

Pins: short prompts bypass untouched, duplicated long context blocks are
replaced by the omission marker (first occurrence kept), duplicated whole
messages are dropped, fenced code blocks pass through byte-for-byte, the
original ProviderRequest is never mutated, and measured savings are
reported by compression_stats().
"""

from app.providers.base import ProviderMessage, ProviderRequest
from app.providers.token_compression import (
    compress_messages,
    compress_provider_request,
    compression_stats,
)

LONG_BLOCK = (
    "The fleet runs ten agents on two small Oracle VMs. Gemini is the voice "
    "provider and Groq is text-only. Stratex trades demo only until a proven "
    "forward record exists. This paragraph is repeated context on purpose."
)


def _long_messages():
    return [
        ("system", LONG_BLOCK),
        ("user", f"{LONG_BLOCK}\n\nFirst question."),
        ("assistant", "An answer."),
        ("user", f"{LONG_BLOCK}\n\nSecond question."),
    ]


def test_short_prompt_bypasses():
    result = compress_messages([("user", "hello")], None)
    assert result.bypassed
    assert result.messages == [("user", "hello")]
    assert not result.changed


def test_repeated_block_is_deduped_first_occurrence_kept():
    result = compress_messages(_long_messages(), None, min_tokens=10)
    assert not result.bypassed
    assert result.blocks_deduped >= 2
    joined = "\n".join(content for _role, content in result.messages)
    assert joined.count(LONG_BLOCK) == 1
    assert "repeated context omitted" in joined
    assert result.est_tokens_saved > 0
    # Non-repeated content survives intact.
    assert "First question." in joined
    assert "Second question." in joined


def test_duplicate_whole_messages_dropped():
    messages = [("user", LONG_BLOCK), ("user", LONG_BLOCK), ("user", "unique tail " + "x" * 200)]
    result = compress_messages(messages, None, min_tokens=10)
    assert result.messages_deduped == 1
    assert len(result.messages) == 2


def test_fenced_code_block_is_byte_for_byte():
    code = "```python\nx  =   1\n\n\n\nprint( x )\n```"
    text = f"{LONG_BLOCK}\n\n{code}\n\n{LONG_BLOCK}"
    result = compress_messages([("user", text)], None, min_tokens=10)
    content = result.messages[0][1]
    assert code in content


def test_whitespace_normalised_outside_code():
    text = ("word   with    spaces   \n" * 60) + "\n\n\n\n" + ("tail" * 100)
    result = compress_messages([("user", text)], None, min_tokens=10)
    content = result.messages[0][1]
    assert "   " not in content
    assert "\n\n\n" not in content


def test_disabled_bypasses():
    result = compress_messages(_long_messages(), None, enabled=False)
    assert result.bypassed
    assert result.messages == _long_messages()


def test_provider_request_not_mutated_and_compressed():
    request = ProviderRequest(
        messages=[ProviderMessage(role=r, content=c) for r, c in _long_messages()],
        system_instruction=None,
    )
    import app.providers.token_compression as tc

    original_min = tc.MIN_TOKENS
    tc.MIN_TOKENS = 10
    try:
        compressed = compress_provider_request(request)
    finally:
        tc.MIN_TOKENS = original_min
    assert compressed is not request
    assert request.messages[1].content.startswith(LONG_BLOCK)  # original untouched
    joined = "\n".join(m.content for m in compressed.messages)
    assert joined.count(LONG_BLOCK) == 1


def test_stats_accumulate():
    before = compression_stats()
    compress_messages(_long_messages(), None, min_tokens=10)
    after = compression_stats()
    assert after["requests_seen"] == before["requests_seen"] + 1
    assert after["requests_compressed"] >= before["requests_compressed"] + 1
    assert after["est_tokens_saved"] >= before["est_tokens_saved"]
