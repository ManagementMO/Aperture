from aperture.benchmarks.evaluators import field_presence_score, has_missing_critical_info, llm_judge_export


def test_field_presence_and_judge_export():
    payload = {"aperture_compressed": True, "data": [{"title": "Bug", "state": "open"}]}
    assert field_presence_score(payload, ["title", "state"]) == 1.0
    assert not has_missing_critical_info(payload, ["title"])
    assert llm_judge_export(payload)["judge_required"] is False

