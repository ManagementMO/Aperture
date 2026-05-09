from aperture.cache.normalizer import normalize_params


def test_normalize_params_sorts_keys_and_removes_aperture_metadata():
    params = {"b": 2, "a": {"d": 4, "c": 3}, "aperture_cache_bypass": True}
    assert list(normalize_params("TOOL", params).keys()) == ["a", "b"]
    assert "aperture_cache_bypass" not in normalize_params("TOOL", params)

