import json
from copy import deepcopy
from pathlib import Path

from aperture.compression.compressor import compress_tool_output
from aperture.types import CompressionContext


def test_compressor_reduces_fixture_and_does_not_mutate():
    payload = json.loads((Path("aperture/fixtures/tool_outputs/github_issues.json")).read_text())
    original = deepcopy(payload)
    context = CompressionContext(None, "u1", "s1", "a1", "GITHUB", "GITHUB_LIST_ISSUES", None, "gpt-4o-mini", "balanced")
    result = compress_tool_output(payload, context)
    assert payload == original
    assert result.tokens_saved > 0
    assert result.raw_reference_id
    assert result.compressed_payload["aperture_compressed"] is True
    assert result.compressed_payload["data"][0]["title"]

