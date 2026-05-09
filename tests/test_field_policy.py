"""Tests for the smart field policy."""

from aperture.compression.field_policy import (
    _OBVIOUS_API_FIELDS,
    FieldPolicy,
    _alternate_forms,
    _ask_mentions,
    make_policy,
)


class TestAskMatching:
    def test_alt_forms_for_snake_case(self):
        forms = _alternate_forms("avatar_url")
        assert "avatar_url" in forms
        assert "avatar url" in forms

    def test_alt_forms_for_camel_case(self):
        forms = _alternate_forms("historyId")
        assert "historyid" in forms
        assert "history_id" in forms or "history id" in forms

    def test_ask_mention_word_bounded(self):
        assert _ask_mentions("show me the avatar_url please", "avatar_url")
        assert _ask_mentions("clone the repo via clone_url", "clone_url")
        # `url` alone shouldn't match inside `urlencode` etc.
        assert not _ask_mentions("urlencode the path", "url")

    def test_ask_mention_handles_camel(self):
        assert _ask_mentions("the historyId is required", "historyId")


class TestFieldPolicy:
    def test_static_drops_avatar_url(self):
        p = make_policy()
        assert p.is_dropped("avatar_url")
        assert not p.is_dropped("title")

    def test_explicit_signal_overrides_denial(self):
        p = make_policy(required_signals={"avatar_url"})
        assert not p.is_dropped("avatar_url")
        d = p.decide("avatar_url")
        assert d.reason == "explicit"

    def test_explicit_descendant_via_dot_path(self):
        p = make_policy(required_signals={"user.avatar_url"})
        d = p.decide("user")
        assert d.decision == "keep"
        assert d.reason == "explicit_descendant"

    def test_ask_promotes_denied_field(self):
        p = make_policy(ask="please render the avatar_url next to each user")
        assert not p.is_dropped("avatar_url")
        d = p.decide("avatar_url")
        assert d.reason == "ask"

    def test_ask_does_not_demote_other_fields(self):
        # Asking about avatar_url shouldn't make `title` get dropped.
        p = make_policy(ask="show avatar_url")
        d = p.decide("title")
        assert d.decision == "keep"
        assert d.reason == "default"

    def test_classifier_only_adds_keeps(self):
        p = make_policy(classifier_keeps={"clone_url"})
        # Classifier promoted clone_url (which is in the denial list).
        d = p.decide("clone_url")
        assert d.decision == "keep"
        assert d.reason == "model"
        # But classifier can't demote a default-keep field.
        d2 = p.decide("title")
        assert d2.decision == "keep"

    def test_decisions_are_recorded(self):
        p = make_policy()
        p.decide("title")
        p.decide("avatar_url")
        p.decide("clone_url")
        counts = p.reason_counts()
        assert counts.get("default", 0) == 1
        assert counts.get("denial_list", 0) == 2

    def test_promotions_returns_only_kept(self):
        p = make_policy(ask="show avatar_url and clone_url")
        p.decide("avatar_url")
        p.decide("clone_url")
        p.decide("title")
        promotions = p.promotions()
        assert any(d.name == "avatar_url" for d in promotions)
        assert any(d.name == "clone_url" for d in promotions)
        # Default-keep doesn't count as a "promotion" (no rescue from drop list)
        assert not any(d.name == "title" for d in promotions)


class TestObviousList:
    def test_static_set_is_immutable(self):
        # Make sure callers can't accidentally mutate the canonical set.
        with __import__("pytest").raises(AttributeError):
            _OBVIOUS_API_FIELDS.add("foo")  # type: ignore[attr-defined]
