from copy import deepcopy

from aperture.schema_optimizer.validator import set_description_at_path, validate_schema_rewrite


def _schema():
    return {
        "slug": "TOOL",
        "description": "Create item.",
        "parameters": {
            "required": ["name"],
            "properties": {"name": {"type": "string", "description": "Name."}},
        },
    }


def test_validator_accepts_description_only_change():
    original = _schema()
    candidate = set_description_at_path(original, "description", "Create item quickly.")
    assert validate_schema_rewrite(original, candidate).passed


def test_validator_rejects_required_field_change():
    original = _schema()
    candidate = deepcopy(original)
    candidate["parameters"]["required"] = []
    assert not validate_schema_rewrite(original, candidate).passed

