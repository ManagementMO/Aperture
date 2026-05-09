from aperture.cache.bypass import cache_bypass_requested


def test_cache_bypass_headers_and_metadata():
    assert cache_bypass_requested(headers={"X-Aperture-Cache-Bypass": "true"})
    assert cache_bypass_requested(metadata={"aperture_cache_bypass": True})
    assert not cache_bypass_requested(headers={"X-Aperture-Cache-Bypass": "false"})

