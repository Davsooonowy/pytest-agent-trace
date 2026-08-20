from agent_test.core.redaction import Redactor


def test_redacts_email_in_a_plain_string():
    redactor = Redactor()
    assert redactor.redact("contact dawid@example.com for help") == (
        "contact [REDACTED_EMAIL] for help"
    )


def test_redacts_api_key_looking_token():
    redactor = Redactor()
    text = "here is the key: sk-abcdEFGH12345678"
    assert "sk-abcdEFGH12345678" not in redactor.redact(text)
    assert "[REDACTED_API_KEY]" in redactor.redact(text)


def test_redacts_credit_card_looking_number():
    redactor = Redactor()
    text = "card on file: 4111 1111 1111 1111"
    assert "4111 1111 1111 1111" not in redactor.redact(text)
    assert "[REDACTED_CARD_NUMBER]" in redactor.redact(text)


def test_leaves_ordinary_text_unchanged():
    redactor = Redactor()
    assert redactor.redact("W Warszawie jest 18 stopni") == "W Warszawie jest 18 stopni"


def test_redacts_dict_value_by_key_name_case_insensitive():
    redactor = Redactor()
    result = redactor.redact({"API_KEY": "anything-at-all", "city": "Warszawa"})
    assert result == {"API_KEY": "[REDACTED]", "city": "Warszawa"}


def test_recurses_into_nested_dicts_and_lists():
    redactor = Redactor()
    result = redactor.redact(
        {
            "user": {"email": "a@b.com", "note": "reach me at a@b.com"},
            "history": [{"password": "hunter2"}, "no secrets here"],
        }
    )
    assert result == {
        "user": {"email": "[REDACTED_EMAIL]", "note": "reach me at [REDACTED_EMAIL]"},
        "history": [{"password": "[REDACTED]"}, "no secrets here"],
    }


def test_non_string_non_container_values_pass_through():
    redactor = Redactor()
    assert redactor.redact(42) == 42
    assert redactor.redact(None) is None
    assert redactor.redact(True) is True


def test_custom_patterns_and_keys_override_defaults():
    redactor = Redactor(patterns=(), keys=("custom_secret",))
    result = redactor.redact({"custom_secret": "x", "email": "a@b.com"})
    # default email pattern is gone (patterns=()), but the custom key still redacts
    assert result == {"custom_secret": "[REDACTED]", "email": "a@b.com"}
