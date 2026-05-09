import json
from pathlib import Path

from aperture.schema_optimizer.extract_fields import extract_description_fields


def test_extract_description_fields():
    schema = json.loads(Path("aperture/fixtures/schemas/github_list_issues.json").read_text())
    fields = extract_description_fields(schema)
    assert any(field.field_path == "description" for field in fields)
    assert any("owner" in field.field_path for field in fields)

