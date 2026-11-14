"""TASK-REL-018 regression: the secret scrubber must not eat prose.

Live incident (console test round 2, 2026-11-14): a Futuris forecast reply
displayed a literal "[REDACTED_SECRET]" where its final sentence should
have been. Root cause: the scrubber's Authorization-header pattern was
unanchored, so it matched the ordinary English phrase "authorization: "
in Futuris's standard sign-off -- "A prediction is not an authorization:
forecasts inform, they never execute anything." -- and replaced the words
after the colon with the redaction placeholder. The pattern is now
anchored to line starts (headers are line-oriented); real headers must
still be redacted.
"""

from friday.security.scrubber import recursive_sanitize, redact_secrets

SIGN_OFF = (
    "A prediction is not an authorization: forecasts inform, "
    "they never execute anything."
)


def test_forecast_sign_off_prose_survives_scrubbing() -> None:
    assert redact_secrets(SIGN_OFF) == SIGN_OFF


def test_authorization_word_in_prose_survives() -> None:
    text = "the authorization: yes, and the cookie: crumbled"
    assert redact_secrets(text) == text


def test_payload_field_name_in_text_form_survives() -> None:
    text = "'prediction_is_not_authorization': True"
    assert redact_secrets(text) == text


def test_real_authorization_header_at_line_start_is_redacted() -> None:
    text = "GET /v1 HTTP/1.1\nAuthorization: Basic dXNlcjpwYXNzd29yZA==\nAccept: */*"
    out = redact_secrets(text)
    assert "dXNlcjpwYXNzd29yZA" not in out
    assert "[REDACTED_SECRET]" in out
    assert "Accept: */*" in out


def test_bearer_token_is_still_redacted_anywhere() -> None:
    out = redact_secrets("header was Bearer abcdefghijklmnopqrstuvwxyz0123456789")
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in out


def test_cookie_header_at_line_start_is_redacted() -> None:
    out = redact_secrets("Cookie: session=abcdef0123456789; theme=dark")
    assert "abcdef0123456789" not in out


def test_recursive_sanitize_keeps_forecast_reply_intact() -> None:
    result = {
        "reply": f"🔮 [FUTURIS FORECAST]\n{SIGN_OFF}",
        "metadata": {"agent_id": "futuris", "prediction_is_not_authorization": True},
        "success": True,
    }
    cleaned = recursive_sanitize(result)
    assert "[REDACTED_SECRET]" not in cleaned["reply"]
    assert cleaned["metadata"]["prediction_is_not_authorization"] is True
