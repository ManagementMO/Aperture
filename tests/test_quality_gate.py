"""Tests for quality-gated effort selection."""

import pytest

from aperture.demo.scenarios import get_mock_result
from aperture.routing.intelligent_effort import TaskComplexity
from aperture.routing.quality_gate import (
    _resolve_dot_path,
    _signal_present,
    select_mode_for_quality,
)


class TestSignalPresent:
    def test_dot_path_resolves(self):
        payload = {"user": {"login": "nikos"}, "title": "x"}
        assert _signal_present(payload, None, "user.login")
        assert _signal_present(payload, None, "title")

    def test_substring_in_json(self):
        payload = {"messages": ["Hello world"]}
        assert _signal_present(payload, None, "hello")
        assert _signal_present(payload, None, "WORLD")

    def test_substring_in_llm_string_for_toon(self):
        payload = {"_aperture_summary": {"total_rows": 5}}
        toon = "issues[5]{id,title}:\n  1,foo bar\n"
        assert _signal_present(payload, toon, "foo bar")
        assert not _signal_present(payload, toon, "missing")

    def test_dotpath_skips_when_unresolved(self):
        payload = {"a": {}}
        assert not _signal_present(payload, None, "a.missing.nested")


class TestResolveDotPath:
    def test_through_list(self):
        payload = {"items": [{"name": "a"}, {"name": "b"}]}
        assert _resolve_dot_path(payload, "items.name") == ["a", "b"]


class TestQualityGate:
    def test_simple_ask_can_use_aggressive(self):
        raw = get_mock_result("GITHUB_GET_A_REPOSITORY", {})
        gate = select_mode_for_quality(
            raw_payload=raw,
            tool_slug="GITHUB_GET_A_REPOSITORY",
            required_signals=["name"],
            ask="what's the repo name",
        )
        assert gate.difficulty == "simple"
        assert gate.max_aggression == "aggressive"
        assert gate.selected_mode == "aggressive"

    def test_complex_ask_floors_at_balanced(self):
        raw = get_mock_result("GITHUB_LIST_ISSUES", {"per_page": 5})
        # Use signals that vary across rows — `title` and `OAuth` (one of the
        # specific titles). `state` is constant ("open" for every issue) so
        # the engine correctly drops it during compression.
        gate = select_mode_for_quality(
            raw_payload=raw,
            tool_slug="GITHUB_LIST_ISSUES",
            required_signals=["title", "OAuth"],
            ask="analyze the priority and severity of every open issue and recommend triage",
        )
        assert gate.difficulty in ("complex", "deep")
        assert gate.max_aggression in ("balanced", "safe")
        assert gate.selected_mode in ("balanced", "safe")

    def test_unsatisfiable_signal_falls_through_to_off(self):
        raw = get_mock_result("GITHUB_GET_A_REPOSITORY", {})
        gate = select_mode_for_quality(
            raw_payload=raw,
            tool_slug="GITHUB_GET_A_REPOSITORY",
            required_signals=["this string does not exist anywhere xyz123"],
            ask="who cares",
        )
        assert gate.selected_mode == "off"
        assert "no allowed mode preserved every signal" in gate.reason

    def test_no_signals_picks_floor_immediately(self):
        raw = get_mock_result("GITHUB_GET_A_REPOSITORY", {})
        gate = select_mode_for_quality(
            raw_payload=raw,
            tool_slug="GITHUB_GET_A_REPOSITORY",
            required_signals=[],
            ask="describe the repo",
        )
        # No signals to fail → first mode in allowed range wins.
        assert gate.selected_mode == gate.attempts[0].mode

    def test_difficulty_override(self):
        raw = get_mock_result("GITHUB_LIST_ISSUES", {"per_page": 5})
        gate = select_mode_for_quality(
            raw_payload=raw,
            tool_slug="GITHUB_LIST_ISSUES",
            required_signals=["title"],
            ask="anything",
            difficulty_override=TaskComplexity.DEEP,
        )
        assert gate.difficulty == "deep"
        assert gate.max_aggression == "safe"
        assert gate.selected_mode in ("safe", "off")

    def test_attempts_recorded_in_order(self):
        raw = get_mock_result("GITHUB_LIST_ISSUES", {"per_page": 5})
        gate = select_mode_for_quality(
            raw_payload=raw,
            tool_slug="GITHUB_LIST_ISSUES",
            required_signals=["body"],
            ask="just count",
        )
        # Aggressive truncates body to 80 chars — but the body content
        # ("Description") still appears so signal "body" passes.
        # Either way, attempts should be in order from cheapest upward.
        modes_tried = [a.mode for a in gate.attempts if a.mode != "off"]
        order = ["aggressive", "low", "balanced", "safe"]
        last_idx = -1
        for m in modes_tried:
            idx = order.index(m)
            assert idx > last_idx
            last_idx = idx

    def test_saved_percent_meaningful(self):
        raw = get_mock_result("GITHUB_LIST_ISSUES", {"per_page": 5})
        gate = select_mode_for_quality(
            raw_payload=raw,
            tool_slug="GITHUB_LIST_ISSUES",
            required_signals=["title"],
            ask="who cares about the title",
        )
        assert 0 <= gate.saved_percent <= 100
        if gate.selected_mode != "off":
            assert gate.saved_percent > 0
