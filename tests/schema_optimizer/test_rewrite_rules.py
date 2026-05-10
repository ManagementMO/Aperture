from aperture.schema_optimizer.models import SchemaField
from aperture.schema_optimizer.rewrite_rules import generate_schema_rewrite_candidates


def test_rewrite_candidate_is_shorter():
    field = SchemaField(
        "GITHUB_CREATE_ISSUE",
        "description",
        "Creates a new issue in a specified GitHub repository. You must provide owner, repo, and title.",
    )
    candidates = generate_schema_rewrite_candidates(field)
    assert candidates, "expected at least one rewrite candidate"
    assert all(len(c) < len(field.text) for c in candidates), (
        "every candidate must be strictly shorter than the original"
    )


def test_returns_progressively_shorter_candidates():
    """Light → medium → heavy: each level should compress at least as much."""

    field = SchemaField(
        "GITHUB_LIST_REPOSITORY_ISSUES",
        "description",
        "Retrieves a list of issues in a specified GitHub repository. "
        "You must provide the repository owner username and repository name. "
        "Optionally, you may include state, labels, assignee, and search terms "
        "to filter the returned issues.",
    )
    candidates = generate_schema_rewrite_candidates(field)
    assert len(candidates) >= 2, f"expected ≥2 distinct candidates, got {candidates!r}"
    # Each subsequent candidate must be at least as short as the previous.
    lengths = [len(c) for c in candidates]
    assert lengths == sorted(lengths, reverse=True), (
        f"candidates must be sorted from least to most compressed: {lengths}"
    )


def test_rewriter_returns_empty_when_no_rules_match():
    """No truncation fallback — short fields where rules don't match must
    return [] so the upper layer can mark them ``no_token_reduction`` cleanly,
    instead of getting a meaning-stripped truncation."""

    field = SchemaField(
        "X_TOOL",
        "parameters.properties.x.description",
        "Numeric ID for the row.",
    )
    candidates = generate_schema_rewrite_candidates(field)
    assert candidates == [], f"expected empty list for un-matchable text, got {candidates!r}"


def test_safety_keywords_preserved_in_heavy_rewrites():
    """Heavy rewrites must keep ``send``/``delete``/``auth`` so the validator
    structural-safety filter doesn't reject them — but more importantly so
    the LLM judge still sees the action verb."""

    field = SchemaField(
        "GMAIL_SEND_EMAIL",
        "description",
        "Sends an email message to a recipient email address through the connected user account.",
    )
    candidates = generate_schema_rewrite_candidates(field)
    for candidate in candidates:
        assert "send" in candidate.lower(), (
            f"heavy rewrite dropped the 'send' verb: {candidate!r}"
        )


def test_required_optional_collapse_inserts_period_separator():
    """Concatenating ``Required:`` + ``Optional:`` clauses should produce a
    period before ``Optional:``, even if the source had no comma there."""

    field = SchemaField(
        "X_TOOL",
        "description",
        "List X. You must provide an id and may include filtering or sorting options.",
    )
    candidates = generate_schema_rewrite_candidates(field)
    # The medium/heavy candidate should produce ``Required: an id. Optional: ...``
    assert candidates, "expected candidates"
    assert any(". Optional:" in c for c in candidates), (
        f"expected at least one candidate to use '. Optional:': {candidates!r}"
    )


def test_requires_substitution_only_at_sentence_start():
    """``\\bRequires\\b`` → ``Required:`` must NOT mangle mid-sentence prose
    like 'A filter that requires the user to authenticate'.

    Pre-fix: that input produced 'A filter that Required: user to authenticate'
    which is grammatically broken and wastes LLM-judge budget. Post-fix:
    only sentence-start matches are substituted.
    """

    field = SchemaField(
        "X_TOOL",
        "description",
        "A Gmail filter that requires the user to authenticate via OAuth.",
    )
    candidates = generate_schema_rewrite_candidates(field)
    for candidate in candidates:
        assert "that Required:" not in candidate, (
            f"mid-sentence Requires substitution leaked: {candidate!r}"
        )


def test_requires_substitution_at_sentence_start_still_works():
    """Sentence-start ``Requires`` should still collapse to ``Required:``."""

    field = SchemaField(
        "X_TOOL",
        "description",
        "List Y. Requires the user id. Returns a paginated result.",
    )
    candidates = generate_schema_rewrite_candidates(field)
    assert candidates, "expected candidates"
    assert any("Required: user id" in c for c in candidates), (
        f"expected at least one candidate with 'Required: user id': {candidates!r}"
    )

