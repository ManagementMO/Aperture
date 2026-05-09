"""Tests for the lazy hydration store."""

import pytest

from aperture.compression.hydration import (
    hydrate,
    make_placeholder,
    store_full_result,
)


@pytest.fixture
def issues_payload():
    return [
        {"id": 1, "title": "First", "user": {"login": "alice"}},
        {"id": 2, "title": "Second", "user": {"login": "bob"}},
        {"id": 3, "title": "Third", "user": {"login": "carol"}},
    ]


class TestHydrationStore:
    def test_round_trip(self, issues_payload):
        ref = store_full_result("GITHUB_LIST_ISSUES", {"per_page": 3}, issues_payload)
        assert isinstance(ref, str) and len(ref) == 16
        assert hydrate(ref) == issues_payload

    def test_hydrate_by_index(self, issues_payload):
        ref = store_full_result("GITHUB_LIST_ISSUES", {"per_page": 3}, issues_payload)
        assert hydrate(ref, index=1)["title"] == "Second"

    def test_hydrate_by_field_path(self, issues_payload):
        ref = store_full_result("GITHUB_LIST_ISSUES", {"per_page": 3}, issues_payload)
        assert hydrate(ref, field_path="title", index=2) == "Third"
        assert hydrate(ref, field_path="user.login", index=0) == "alice"

    def test_unknown_ref_returns_none(self):
        assert hydrate("not_a_real_ref") is None

    def test_out_of_range_index_returns_none(self, issues_payload):
        ref = store_full_result("GITHUB_LIST_ISSUES", {}, issues_payload)
        assert hydrate(ref, index=99) is None


class TestPlaceholder:
    def test_placeholder_has_ref(self, issues_payload):
        ref = store_full_result("GITHUB_LIST_ISSUES", {}, issues_payload)
        ph = make_placeholder(ref, "GITHUB_LIST_ISSUES", issues_payload, sample_size=2)
        assert ph["_aperture_ref"] == ref
        assert ph["_aperture_summary"]["count"] == 3
        assert ph["_aperture_sample"]
        assert len(ph["_aperture_sample"]) == 2

    def test_placeholder_can_skip_sample(self, issues_payload):
        ref = store_full_result("GITHUB_LIST_ISSUES", {}, issues_payload)
        ph = make_placeholder(ref, "GITHUB_LIST_ISSUES", issues_payload, include_sample=False)
        assert "_aperture_sample" not in ph
