from aperture.compression.profile_loader import load_compression_profile
from aperture.compression.text_summarization import compress_long_text_fields
from aperture.tokenization.token_counter import count_tokens_for_payload


def test_long_text_is_compressed_when_allowed():
    profile = load_compression_profile("GITHUB_LIST_ISSUES")
    payload = {"body": "Sentence one. Sentence two. Sentence three. " * 80}
    result = compress_long_text_fields(payload, profile)
    assert count_tokens_for_payload(result["body"]).tokens <= 80
    assert result["body_compressed"] is True

