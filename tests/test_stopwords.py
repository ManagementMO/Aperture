"""Tests for caveman-style prose pruning."""

from aperture.compression.stopwords import (
    caveman_prune,
    looks_like_prose,
    prune_payload,
)


CODE_SNIPPET = """def foo(x):
    return x + 1
"""

LONG_PROSE = (
    "You should always make sure to run the test suite before pushing any changes "
    "to the main branch. Furthermore, it would be good to actually verify the build "
    "passes locally. The reason is because broken builds are very, very disruptive. "
    "It might be worth checking the CI logs as well, just in case. Of course, if "
    "tests fail, simply revert the commit and start again. Additionally, please "
    "note that the deploy script utilize the same build artifacts."
)


class TestProseDetection:
    def test_short_text_not_prose(self):
        assert not looks_like_prose("Hello world")

    def test_code_not_prose(self):
        assert not looks_like_prose(CODE_SNIPPET * 10)

    def test_long_prose_detected(self):
        assert looks_like_prose(LONG_PROSE)


class TestCavemanPrune:
    def test_drops_filler_words(self):
        out = caveman_prune(LONG_PROSE, level="full")
        assert "really" not in out.lower().split()
        assert "actually" not in out.lower().split()
        assert "just" not in out.lower().split()
        # Shorter than the original.
        assert len(out) < len(LONG_PROSE)

    def test_phrase_rewrites(self):
        out = caveman_prune(LONG_PROSE, level="full")
        assert "in order to" not in out.lower()
        assert "make sure to" not in out.lower()
        assert "the reason is because" not in out.lower()
        assert "utilize" not in out.lower()

    def test_preserves_urls(self):
        text = (
            "Please visit https://example.com/very/long/path?a=1&b=2 to actually "
            "really see the docs because the reason is because we just need them "
            "and that is essentially the truth of the matter, you should know."
        )
        out = caveman_prune(text, level="full")
        assert "https://example.com/very/long/path?a=1&b=2" in out

    def test_preserves_backticks(self):
        text = (
            "You should actually really run `npm install` because the reason is "
            "because dependencies might not be installed and you should just verify."
        )
        out = caveman_prune(text, level="full")
        assert "`npm install`" in out

    def test_short_text_unchanged(self):
        assert caveman_prune("Hello", level="full") == "Hello"

    def test_lite_keeps_articles(self):
        out = caveman_prune(LONG_PROSE, level="lite")
        # `lite` doesn't drop articles, only filler/hedging.
        assert " the " in f" {out.lower()} "


class TestPrunePayload:
    def test_walks_dict(self):
        payload = {"subject": "hi", "body": LONG_PROSE, "id": 1}
        out = prune_payload(payload, level="full")
        assert out["id"] == 1
        assert out["subject"] == "hi"
        assert len(out["body"]) < len(LONG_PROSE)

    def test_walks_list(self):
        payload = [{"body": LONG_PROSE} for _ in range(3)]
        out = prune_payload(payload, level="full")
        assert all(len(item["body"]) < len(LONG_PROSE) for item in out)

    def test_does_not_touch_non_strings(self):
        payload = {"count": 42, "active": True, "tags": ["a", "b"]}
        assert prune_payload(payload, level="full") == payload
