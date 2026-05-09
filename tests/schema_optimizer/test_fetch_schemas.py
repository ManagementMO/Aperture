from aperture.schema_optimizer.fetch_schemas import fetch_fixture_schemas, fetch_tool_schemas


def test_fetch_fixture_schemas_loads_local_schemas():
    schemas = fetch_fixture_schemas()
    assert schemas
    assert any(schema.get("slug") == "GITHUB_LIST_REPOSITORY_ISSUES" for schema in schemas)


def test_fetch_tool_schemas_defaults_to_fixtures():
    assert fetch_tool_schemas(live=False) == fetch_fixture_schemas()
