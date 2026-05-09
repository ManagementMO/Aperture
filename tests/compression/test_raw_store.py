from aperture.compression.raw_store import get_raw_output, store_raw_output
from aperture.types import CompressionContext


def test_raw_store_roundtrip(tmp_path):
    context = CompressionContext(None, "u1", "s1", "a1", "GITHUB", "GITHUB_LIST_ISSUES", None, None, "balanced")
    ref = store_raw_output({"secret": "value"}, context, base_path=tmp_path)
    assert ref.startswith("raw_")
    assert get_raw_output(ref, base_path=tmp_path) == {"secret": "value"}


def test_raw_reference_is_deterministic(tmp_path):
    context = CompressionContext(None, "u1", "s1", "a1", "GITHUB", "GITHUB_LIST_ISSUES", None, None, "balanced")
    first = store_raw_output({"title": "Bug"}, context, base_path=tmp_path)
    second = store_raw_output({"title": "Bug"}, context, base_path=tmp_path)
    assert first == second
