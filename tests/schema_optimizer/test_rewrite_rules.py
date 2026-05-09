from aperture.schema_optimizer.models import SchemaField
from aperture.schema_optimizer.rewrite_rules import generate_schema_rewrite_candidates


def test_rewrite_candidate_is_shorter():
    field = SchemaField("GITHUB_CREATE_ISSUE", "description", "Creates a new issue in a specified GitHub repository. You must provide owner, repo, and title.")
    candidate = generate_schema_rewrite_candidates(field)[0]
    assert len(candidate) < len(field.text)

