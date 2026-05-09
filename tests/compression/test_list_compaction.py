from aperture.compression.list_compaction import compact_lists
from aperture.compression.profile_loader import load_compression_profile


def test_compact_labels_to_names():
    profile = load_compression_profile("GITHUB_LIST_ISSUES")
    payload = {"labels": [{"name": "bug"}, {"name": "auth"}]}
    assert compact_lists(payload, profile)["labels"] == ["bug", "auth"]

