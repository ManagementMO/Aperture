from aperture.compression.deduplication import deduplicate_repeated_objects
from aperture.compression.profile_loader import load_compression_profile


def test_deduplication_removes_repeated_configured_objects():
    profile = load_compression_profile("GITHUB_LIST_PULL_REQUESTS")
    payload = [{"head": {"repo": {"id": 1}}}, {"head": {"repo": {"id": 1}}}]
    result = deduplicate_repeated_objects(payload, profile)
    assert result[0]["head"]["repo"] == {"id": 1}
    assert "repo" not in result[1]["head"]

