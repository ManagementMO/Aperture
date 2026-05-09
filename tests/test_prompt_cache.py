"""Tests for prompt-caching block ordering, breakpoints, and savings estimate."""

from aperture.compression.prompt_cache import (
    build_cache_optimized_prompt,
    estimate_savings,
)


def _build(history_turn_count: int = 0):
    return build_cache_optimized_prompt(
        system_prompt="You are a helpful agent.",
        tool_schemas=['{"name":"GITHUB_LIST_ISSUES"}'],
        static_context=["AGENTS.md content"],
        tool_results=[{"_aperture_ref": "abc", "summary": {"count": 3}}],
        user_messages=["Find open bugs"],
        provider="anthropic",
        history_turn_count=history_turn_count,
    )


class TestBuildPrompt:
    def test_stable_blocks_come_before_dynamic(self):
        prompt = _build()
        # System / schema / static_context / tool_result are all cacheable;
        # only user_message is dynamic.
        first_user = min(
            i for i, b in enumerate(prompt.blocks) if b.block_type == "user_message"
        )
        last_stable = max(
            i for i, b in enumerate(prompt.blocks) if b.block_type != "user_message"
        )
        assert last_stable < first_user

    def test_breakpoints_have_ttl_tiers(self):
        prompt = _build()
        ttls = [bp.ttl for bp in prompt.breakpoints]
        # Schema and static_context get the 1h tier; tool_results get 5m.
        assert "1h" in ttls
        assert "5m" in ttls

    def test_max_four_breakpoints(self):
        prompt = _build(history_turn_count=30)
        assert len(prompt.breakpoints) <= 4

    def test_anthropic_format_emits_multiple_markers(self):
        prompt = _build()
        for block in prompt.blocks:
            block.estimated_tokens = 600
        messages = prompt.to_provider_format()
        markers = [m for m in messages if "cache_control" in m]
        assert 2 <= len(markers) <= 4
        for m in markers:
            assert m["cache_control"]["type"] == "ephemeral"
            assert m["cache_control"]["ttl"] in ("5m", "1h")

    def test_prefix_hash_is_stable(self):
        a = _build()
        b = _build()
        a_hashes = [block.prefix_hash for block in a.blocks]
        b_hashes = [block.prefix_hash for block in b.blocks]
        assert a_hashes == b_hashes

    def test_tool_results_are_cacheable(self):
        prompt = _build()
        tool_results = [b for b in prompt.blocks if b.block_type == "tool_result"]
        assert tool_results
        assert all(b.cacheable for b in tool_results)


class TestSavings:
    def test_anthropic_amortized_beats_naive(self):
        prompt = _build()
        for block in prompt.blocks:
            block.estimated_tokens = 600
        result = estimate_savings(prompt, provider="anthropic", expected_turns=10)
        # Once tokens clear the 1024 threshold, amortized cost across 10 turns
        # must be cheaper than naive.
        assert result["amortized_cost"] < result["naive_cost"]
        assert result["savings_percent"] > 0

    def test_anthropic_better_than_generic_at_scale(self):
        prompt = _build()
        for block in prompt.blocks:
            block.estimated_tokens = 1500  # all blocks comfortably above threshold
        anthropic = estimate_savings(prompt, provider="anthropic", expected_turns=10)
        generic = estimate_savings(prompt, provider="generic", expected_turns=10)
        # 0.10 read mult vs 0.25 read mult — anthropic must win.
        assert anthropic["savings_percent"] > generic["savings_percent"]

    def test_below_threshold_is_skipped(self):
        prompt = _build()
        for block in prompt.blocks:
            block.estimated_tokens = 50
        result = estimate_savings(prompt, provider="anthropic")
        assert result["skipped_below_threshold"] > 0
        assert result["cacheable_tokens"] == 0

    def test_no_cacheable_zero_savings(self):
        prompt = build_cache_optimized_prompt(
            system_prompt=None,
            tool_schemas=[],
            static_context=[],
            tool_results=[],
            user_messages=["hi"],
            provider="anthropic",
        )
        for block in prompt.blocks:
            block.estimated_tokens = 100
        result = estimate_savings(prompt, provider="anthropic")
        assert result["cacheable_tokens"] == 0
        assert result["tokens_saved"] == 0
