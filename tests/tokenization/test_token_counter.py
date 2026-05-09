from aperture.tokenization.token_counter import count_tokens_for_payload


def test_token_count_is_deterministic_and_falls_back_for_unknown_model():
    payload = {"b": 2, "a": 1}
    first = count_tokens_for_payload(payload, model="unknown-model")
    second = count_tokens_for_payload({"a": 1, "b": 2}, model="unknown-model")
    assert first.tokens == second.tokens
    assert first.payload_bytes == second.payload_bytes
    assert first.tokenizer_is_approximate is True


def test_large_payload_counts():
    result = count_tokens_for_payload({"items": ["hello world"] * 1000}, model="gpt-4o-mini")
    assert result.tokens > 0
    assert result.payload_bytes > 0

