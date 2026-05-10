"""Tests for SessionRegistry."""

from __future__ import annotations

from aperture.proxy.session import SessionRegistry


def test_open_returns_stable_uuid_per_connection():
    reg = SessionRegistry()
    sid_1 = reg.open("conn_a", user_id="u1")
    sid_2 = reg.open("conn_a", user_id="u1")
    assert sid_1 == sid_2  # idempotent


def test_open_returns_distinct_ids_for_distinct_connections():
    reg = SessionRegistry()
    a = reg.open("conn_a", user_id="u1")
    b = reg.open("conn_b", user_id="u2")
    assert a != b


def test_increment_turn_starts_at_one():
    reg = SessionRegistry()
    reg.open("conn_a")
    assert reg.increment_turn("conn_a") == 1
    assert reg.increment_turn("conn_a") == 2
    assert reg.increment_turn("conn_a") == 3


def test_increment_turn_auto_opens_session():
    """If a caller forgets open(), increment_turn still works."""
    reg = SessionRegistry()
    assert reg.increment_turn("ghost_conn") == 1


def test_upgrade_with_composio_sid_does_not_replace_aperture_sid():
    reg = SessionRegistry()
    aperture_sid = reg.open("conn_a", user_id="u1")
    reg.upgrade_with_composio_sid("conn_a", "trs_abc")
    ctx = reg.context_for("conn_a")
    # Aperture sid stays stable for telemetry
    assert ctx.session_id == aperture_sid


def test_context_for_returns_executioncontext_with_session_id():
    reg = SessionRegistry()
    reg.open("conn_a", user_id="user_42")
    ctx = reg.context_for(
        "conn_a",
        toolkit_slug="github",
        tool_slug="GITHUB_GET_REPO",
        meta_tool_slug=None,
        model="gpt-4o",
    )
    assert ctx.user_id == "user_42"
    assert ctx.session_id is not None
    assert ctx.toolkit_slug == "github"
    assert ctx.model == "gpt-4o"


def test_close_removes_session():
    reg = SessionRegistry()
    reg.open("conn_a", user_id="u1")
    reg.close("conn_a")
    assert reg.turn_for("conn_a") is None
