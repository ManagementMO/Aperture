from aperture.schema_optimizer.reports import optimize_schemas, write_schema_optimization_report


def test_schema_report_includes_validation_status(tmp_path):
    results = write_schema_optimization_report(tmp_path / "schema.md")
    assert results
    assert "Accepted" in (tmp_path / "schema.md").read_text()
    assert any(result.validation_cases_run > 0 for result in optimize_schemas())

