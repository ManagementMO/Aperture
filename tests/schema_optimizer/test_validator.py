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


def test_validator_rejects_tool_slug_change():
    original = _schema()
    candidate = deepcopy(original)
    candidate["slug"] = "OTHER_TOOL"
    assert validate_schema_rewrite(original, candidate).rejection_reason == "tool_slug_changed"


def test_validator_rejects_parameter_name_change():
    original = _schema()
    candidate = deepcopy(original)
    candidate["parameters"]["properties"]["display_name"] = candidate["parameters"]["properties"].pop("name")
    assert validate_schema_rewrite(original, candidate).rejection_reason == "parameter_names_changed"


def test_validator_rejects_parameter_type_change():
    original = _schema()
    candidate = deepcopy(original)
    candidate["parameters"]["properties"]["name"]["type"] = "integer"
    assert validate_schema_rewrite(original, candidate).rejection_reason == "parameter_types_changed"


def test_validator_rejects_removed_safety_terms():
    original = _schema()
    original["description"] = "Delete private item."
    candidate = set_description_at_path(original, "description", "Remove item.")
    result = validate_schema_rewrite(original, candidate)
    assert not result.passed
    assert result.rejection_reason == "safety_terms_removed:delete,private"
