from aperture.schema_optimizer.models import SchemaField
from aperture.schema_optimizer.tokenize_schemas import tokenize_schema_fields


def test_tokenize_schema_fields_is_deterministic():
    field = SchemaField("TOOL", "description", "Create a GitHub issue.")
    first = tokenize_schema_fields([field])[0]
    second = tokenize_schema_fields([field])[0]
    assert first.tokens == second.tokens

