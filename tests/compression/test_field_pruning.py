from aperture.compression.field_pruning import prune_fields
from aperture.compression.profile_loader import load_compression_profile


def test_prune_fields_preserves_critical_and_drops_metadata():
    profile = load_compression_profile("GITHUB_LIST_ISSUES")
    payload = {"title": "Bug", "url": "api", "html_url": "web", "empty": "", "body": "keep"}
    pruned, omitted = prune_fields(payload, profile)
    assert pruned["title"] == "Bug"
    assert pruned["html_url"] == "web"
    assert pruned["body"] == "keep"
    assert "url" not in pruned
    assert "empty" not in pruned
    assert "url" in omitted

