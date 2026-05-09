"""Tests for tool-specific normalization in the compression engine."""

import json

from aperture.compression.engine import (
    _normalize_gmail,
    _normalize_slack,
    compress_tool_output,
)


GMAIL_THREAD = {
    "id": "thread_42",
    "historyId": "9001",
    "messages": [
        {
            "id": "msg_42",
            "threadId": "thread_42",
            "labelIds": ["INBOX", "IMPORTANT"],
            "snippet": "Hello team, the OAuth bug is back...",
            "payload": {
                "partId": "",
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "To", "value": "team@composio.dev"},
                    {"name": "Subject", "value": "OAuth session bug"},
                    {"name": "Date", "value": "2026-05-08T12:00:00Z"},
                    {"name": "Message-Id", "value": "<msg_42@mail.gmail.com>"},
                ],
                "parts": [
                    {"partId": "0", "body": {"size": 99999, "data": "AAAA" * 200}},
                ],
            },
            "sizeEstimate": 50_000,
            "internalDate": "1715241600000",
        }
    ],
}


class TestGmailNormalization:
    def test_lifts_headers_to_top_level(self):
        normalized = _normalize_gmail(GMAIL_THREAD)
        assert normalized["id"] == "thread_42"
        msg = normalized["messages"][0]
        assert msg["from"] == "Alice <alice@example.com>"
        assert msg["to"] == "team@composio.dev"
        assert msg["subject"] == "OAuth session bug"
        assert msg["date"] == "2026-05-08T12:00:00Z"

    def test_drops_payload_and_base64_blobs(self):
        normalized = _normalize_gmail(GMAIL_THREAD)
        msg = normalized["messages"][0]
        assert "payload" not in msg
        assert "parts" not in msg
        assert "sizeEstimate" not in msg

    def test_preserves_snippet(self):
        normalized = _normalize_gmail(GMAIL_THREAD)
        msg = normalized["messages"][0]
        assert "snippet" in msg
        assert "OAuth bug" in msg["snippet"]

    def test_compressed_output_keeps_email_signal(self):
        result = compress_tool_output(GMAIL_THREAD, "GMAIL_SEARCH_EMAILS", mode="balanced")
        body = json.dumps(result.compressed_payload)
        assert "OAuth session bug" in body
        assert "alice@example.com" in body
        assert "team@composio.dev" in body
        assert result.compressed_tokens < result.raw_tokens


class TestSlackNormalization:
    def test_drops_blocks_and_attachments(self):
        msg = {
            "type": "message",
            "user": "U12345",
            "text": "release at 3pm",
            "ts": "1715241600.000123",
            "channel": {"id": "C123", "name": "engineering"},
            "blocks": [{"type": "rich_text", "elements": []}],
            "attachments": [],
            "client_msg_id": "abc-def",
            "reactions": [
                {"name": "eyes", "count": 1, "users": ["U1"]},
                {"name": "white_check_mark", "count": 2, "users": ["U2", "U3"]},
            ],
            "subscribed": False,
            "last_read": "1715241600.000000",
        }
        normalized = _normalize_slack(msg)
        assert "blocks" not in normalized
        assert "attachments" not in normalized
        assert "client_msg_id" not in normalized
        assert "subscribed" not in normalized
        assert normalized["channel"] == "engineering"
        assert normalized["reactions"] == ["eyes", "white_check_mark"]
        assert normalized["text"] == "release at 3pm"
