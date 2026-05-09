from aperture.schema_optimizer.models import SchemaField, SchemaFieldTokenCount
from aperture.schema_optimizer.rank_candidates import rank_schema_candidates


def test_rank_schema_candidates_by_token_count():
    low = SchemaFieldTokenCount(SchemaField("A", "description", "short"), 1)
    high = SchemaFieldTokenCount(SchemaField("B", "description", "long"), 10)

    assert rank_schema_candidates([low, high]) == [high, low]
