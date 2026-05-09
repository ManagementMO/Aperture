from aperture.compression.envelope import build_compression_envelope
from aperture.types import CompressionContext


def test_envelope_marks_compression_visible():
    context = CompressionContext(None, None, "s1", None, "GITHUB", "GITHUB_LIST_ISSUES", None, None, "balanced")
    envelope = build_compression_envelope(
        {"title": "Bug"},
        raw_tokens=100,
        compressed_tokens=25,
        tokens_saved=75,
        compression_ratio=0.25,
        raw_reference_id="raw_1",
        omitted_fields=["url"],
        context=context,
    )
    assert envelope["aperture_compressed"] is True
    assert envelope["raw_reference_id"] == "raw_1"

