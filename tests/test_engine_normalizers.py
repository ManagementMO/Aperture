"""Tests for tool-specific normalization in the compression engine."""

import base64
import json

from aperture.compression.engine import (
    _normalize_gmail,
    _normalize_slack,
    compress_tool_output,
)


def _gmail_b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


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
                    {
                        "partId": "0",
                        "mimeType": "text/plain",
                        "body": {
                            "size": 99999,
                            "data": _gmail_b64(
                                "The production OAuth issue is back. "
                                "Safari users are being signed out repeatedly, "
                                "and the team should prioritize a session fix."
                            ),
                        },
                    },
                ],
            },
            "sizeEstimate": 50_000,
            "internalDate": "1715241600000",
        }
    ],
}

COMPOSIO_FLAT_GMAIL = {
    "messages": [
        {
            "messageId": "flat_msg_1",
            "sender": "Charlie <charlie@example.com>",
            "to": "launch@composio.dev",
            "subject": "Launch review moved",
            "messageTimestamp": "2026-05-09T10:00:00Z",
            "preview": "The launch review moved to Monday.",
            "messageText": (
                "<p>The launch review moved to Monday.</p>"
                "<p>Please summarize the blockers around billing and OAuth.</p>"
            ),
            "attachmentList": [
                {
                    "filename": "launch-plan.pdf",
                    "mimeType": "application/pdf",
                    "size": 12345,
                    "data": "raw attachment payload must not survive",
                    "download_url": "https://example.com/download",
                }
            ],
            "display_url": "https://mail.google.com/mail/u/0/#inbox/flat_msg_1",
        }
    ]
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
        assert "AAAA" not in json.dumps(msg)

    def test_preserves_snippet(self):
        normalized = _normalize_gmail(GMAIL_THREAD)
        msg = normalized["messages"][0]
        assert "snippet" in msg
        assert "OAuth bug" in msg["snippet"]

    def test_extracts_readable_body_text_for_summary(self):
        normalized = _normalize_gmail(GMAIL_THREAD)
        msg = normalized["messages"][0]
        assert "body_text" in msg
        assert "Safari users are being signed out" in msg["body_text"]

    def test_compressed_output_keeps_email_signal(self):
        result = compress_tool_output(GMAIL_THREAD, "GMAIL_SEARCH_EMAILS", mode="balanced")
        body = json.dumps(result.compressed_payload)
        assert "OAuth session bug" in body
        assert "Safari users are being signed out" in body
        assert "alice@example.com" in body
        assert "team@composio.dev" in body
        assert result.compressed_tokens < result.raw_tokens

    def test_summary_compression_keeps_more_than_snippet(self):
        huge_body = (
            "Customer reported a Gmail billing issue. "
            "The invoice is missing line items and needs finance review. "
        ) * 200
        payload = {
            "messages": [
                {
                    "id": "msg_big",
                    "threadId": "thread_big",
                    "snippet": "Customer reported a Gmail billing issue.",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Bob <bob@example.com>"},
                            {"name": "Subject", "value": "Invoice problem"},
                        ],
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": _gmail_b64(huge_body)},
                            }
                        ],
                    },
                }
            ]
        }

        result = compress_tool_output(
            payload,
            "GMAIL_FETCH_EMAILS",
            mode="balanced",
            ask="Pull my last Gmail email and summarize it",
        )
        body = json.dumps(result.compressed_payload)

        assert "body_text" in body
        assert "invoice is missing line items" in body
        assert result.compressed_tokens > 250
        assert result.compressed_tokens < result.raw_tokens

    def test_normalizes_composio_flat_gmail_fields(self):
        normalized = _normalize_gmail(COMPOSIO_FLAT_GMAIL)
        msg = normalized["messages"][0]

        assert msg["id"] == "flat_msg_1"
        assert msg["from"] == "Charlie <charlie@example.com>"
        assert msg["to"] == "launch@composio.dev"
        assert msg["subject"] == "Launch review moved"
        assert msg["date"] == "2026-05-09T10:00:00Z"
        assert msg["snippet"] == "The launch review moved to Monday."
        assert "billing and OAuth" in msg["body_text"]
        assert msg["attachments"] == [
            {
                "name": "launch-plan.pdf",
                "mime_type": "application/pdf",
                "size": 12345,
            }
        ]
        assert "messageText" not in msg
        assert "display_url" not in msg
        assert "data" not in json.dumps(msg)

    def test_flat_gmail_compression_keeps_message_text_content(self):
        result = compress_tool_output(
            COMPOSIO_FLAT_GMAIL,
            "GMAIL_FETCH_EMAILS",
            mode="balanced",
            ask="Pull my last Gmail email and summarize it",
        )
        body = json.dumps(result.compressed_payload)

        assert "body_text" in body
        assert "billing and OAuth" in body
        assert "Launch review moved" in body
        assert "launch@composio.dev" in body
        assert "messages[].messageText" not in result.omitted_fields
        assert "messages[].subject" not in result.omitted_fields
        assert "messages[].to" not in result.omitted_fields
        assert "messages[].display_url" in result.omitted_fields
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
