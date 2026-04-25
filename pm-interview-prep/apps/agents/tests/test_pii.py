from agents.tools import redact_pii


def test_redacts_email_phone_url():
    text = (
        "Reach me at jane.doe@example.com or +1 (415) 555-1212. "
        "Portfolio: https://example.com/jane and linkedin.com/in/janedoe"
    )
    out = redact_pii(text)
    assert "jane.doe@example.com" not in out
    assert "555-1212" not in out
    assert "example.com/jane" not in out
    assert "janedoe" not in out
    assert "[EMAIL]" in out
    assert "[PHONE]" in out
    assert "[URL]" in out
    assert "[LINKEDIN]" in out


def test_passthrough_when_clean():
    text = "Senior PM with 8 years of experience."
    assert redact_pii(text) == text
