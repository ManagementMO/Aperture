"""Benchmark: measure the deterministic rewriter's compression on fixture
schemas and lock in a regression floor.

The previous rewriter was producing 0% reduction on the top-2 ranked
candidates during live LLM-judge runs. After this fix the heavy rules
should produce ≥20% average reduction on the top-15 ranked candidates.
"""

from __future__ import annotations

from aperture.schema_optimizer.extract_fields import extract_description_fields
from aperture.schema_optimizer.fetch_schemas import fetch_tool_schemas
from aperture.schema_optimizer.rank_candidates import rank_schema_candidates
from aperture.schema_optimizer.rewrite_rules import generate_schema_rewrite_candidates
from aperture.schema_optimizer.tokenize_schemas import tokenize_schema_fields
from aperture.tokenization.token_counter import count_tokens_for_payload


def _measure_top_n_reduction(top_n: int) -> tuple[int, int, int]:
    """Return (original_total, best_total, candidates_with_reduction).

    `original_total` is the sum of original tokens on the top-N ranked
    fields. `best_total` is the sum of the best (smallest) candidate's
    tokens for each field — falling back to original tokens when the
    rewriter returns no candidate.
    """

    schemas = fetch_tool_schemas(live=False)
    fields = []
    for schema in schemas:
        if isinstance(schema, dict):
            fields.extend(extract_description_fields(schema))
    ranked = rank_schema_candidates(tokenize_schema_fields(fields))[:top_n]

    orig_total = 0
    best_total = 0
    reduced_count = 0
    for r in ranked:
        cands = generate_schema_rewrite_candidates(r.field)
        orig_total += r.tokens
        if not cands:
            best_total += r.tokens
            continue
        best = min(count_tokens_for_payload(c).tokens for c in cands)
        best_total += best
        if best < r.tokens:
            reduced_count += 1
    return orig_total, best_total, reduced_count


def test_rewriter_achieves_at_least_20pct_reduction_on_top_15():
    """Regression floor: top-15 ranked candidates compress by ≥20% on average.

    Previous rewriter rules left two of the top-2 candidates at 0% reduction.
    After the rule expansion, the aggregate reduction across top-15 is
    measured at ≥27%; we set the gate at 20% to leave headroom for fixture
    drift while still catching a real regression.
    """

    orig, best, _ = _measure_top_n_reduction(15)
    assert orig > 0, "fixtures produced no fields — something is wrong upstream"
    reduction_pct = (orig - best) / orig
    assert reduction_pct >= 0.20, (
        f"top-15 compression dropped to {reduction_pct:.1%} — "
        f"expected at least 20% reduction. Did rewrite_rules.py regress?"
    )


def test_rewriter_compresses_majority_of_top_15():
    """At least 60% of the top-15 fields must produce a reduced candidate.

    Some fields have unmatched phrasings that the rewriter intentionally
    skips (returning `[]`). That's fine — but the majority should compress.
    """

    _, _, reduced_count = _measure_top_n_reduction(15)
    assert reduced_count >= 9, (
        f"only {reduced_count}/15 top-ranked fields produced a smaller "
        f"candidate; expected ≥9. Rule coverage may have regressed."
    )
