"""Schema-aware output compression engine."""

from typing import Any

from aperture.contracts import CompressionResult
from aperture.tokenization import count_tokens


# Fields to drop from common tool outputs
_OBVIOUS_API_FIELDS = {
    "node_id",
    "gravatar_id",
    "avatar_url",
    "followers_url",
    "following_url",
    "gists_url",
    "starred_url",
    "subscriptions_url",
    "organizations_url",
    "repos_url",
    "events_url",
    "received_events_url",
    "labels_url",
    "comments_url",
    "repository_url",
    "commits_url",
    "statuses_url",
    "pull_request_url",
    "archive_url",
    "assignees_url",
    "blobs_url",
    "branches_url",
    "clone_url",
    "collaborators_url",
    "compare_url",
    "contents_url",
    "contributors_url",
    "deployments_url",
    "downloads_url",
    "forks_url",
    "git_commits_url",
    "git_refs_url",
    "git_tags_url",
    "hooks_url",
    "issue_comment_url",
    "issue_events_url",
    "issues_url",
    "keys_url",
    "merges_url",
    "milestones_url",
    "notifications_url",
    "pulls_url",
    "releases_url",
    "stargazers_url",
    "tags_url",
    "teams_url",
    "trees_url",
    "ssh_url",
    "svn_url",
    "mirror_url",
    "languages_url",
    "subscribers_url",
    "subscription_url",
    "raw_url",
    "html_url",
    "url",
    "href",
    "self",
    "uri",
    "permalink",
    "api_url",
    "preview_url",
    "download_url",
    "upload_url",
    "video_html_url",
    "image_url",
    "thumbnail_url",
    # Gmail/Slack specific
    "history_id",
    "internal_date",
    "size_estimate",
    "raw_headers",
    "payload",
    "parts",
    "mimeType",
    "filename",
    "body.attachmentId",
    "headers",
    "thread_id",
    "in_reply_to",
    "references",
    "delivery_status",
    "image_24",
    "image_32",
    "image_48",
    "image_72",
    "image_192",
    "image_512",
    "avatar_hash",
    "team",
    "is_bot",
    "is_app_user",
    "updated",
    "color",
    "real_name",
    "display_name",
    "display_name_normalized",
    "real_name_normalized",
    "status_text",
    "status_emoji",
    "status_expiration",
}


def compress_tool_output(
    raw_payload: object,
    tool_slug: str,
    mode: str = "balanced",
    model: str | None = None,
) -> CompressionResult:
    """Compress a raw tool output into a compact model-facing payload.

    Args:
        raw_payload: The raw tool result from Composio.
        tool_slug: Tool identifier for profile selection.
        mode: Compression mode — safe, balanced, or aggressive.
        model: Model hint for token counting.

    Returns:
        CompressionResult with compressed payload and metrics.
    """
    raw_count = count_tokens(raw_payload, model)

    if mode == "off":
        return CompressionResult(
            compressed_payload=raw_payload,
            raw_tokens=raw_count.tokens,
            compressed_tokens=raw_count.tokens,
            tokens_saved=0,
            compression_ratio=1.0,
            strategy="off",
        )

    # Detect tabular data (2D arrays from Google Sheets, Excel, etc.)
    if _is_tabular(raw_payload):
        compressed = _compress_tabular(raw_payload, mode=mode)
        compressed_count = count_tokens(compressed, model)
        tokens_saved = raw_count.tokens - compressed_count.tokens
        return CompressionResult(
            compressed_payload=compressed,
            raw_tokens=raw_count.tokens,
            compressed_tokens=compressed_count.tokens,
            tokens_saved=max(0, tokens_saved),
            compression_ratio=round(compressed_count.tokens / max(raw_count.tokens, 1), 3),
            strategy=f"tabular_{mode}",
            omitted_fields=[],
        )

    if mode == "safe":
        compressed = _safe_compress(raw_payload)
    elif mode == "balanced":
        compressed = _balanced_compress(raw_payload)
    else:
        compressed = _safe_compress(raw_payload)

    compressed_count = count_tokens(compressed, model)
    tokens_saved = raw_count.tokens - compressed_count.tokens

    return CompressionResult(
        compressed_payload=compressed,
        raw_tokens=raw_count.tokens,
        compressed_tokens=compressed_count.tokens,
        tokens_saved=max(0, tokens_saved),
        compression_ratio=round(compressed_count.tokens / max(raw_count.tokens, 1), 3),
        strategy=mode,
        omitted_fields=_collect_omitted_fields(raw_payload, compressed),
    )


def _is_tabular(payload: object) -> bool:
    """Detect if payload is tabular data (2D array from Sheets/Excel)."""
    if not isinstance(payload, list):
        return False
    if not payload:
        return False
    # Check if it's a list of lists (rows)
    return all(isinstance(row, list) for row in payload[:10])


def _compress_tabular(payload: list[list], mode: str = "balanced") -> object:
    """Compress tabular data: sample rows, drop empty cols, truncate cells.

    For large datasets (10K+ rows), keeping all rows is pointless for an LLM.
    We keep the header + representative sample + summary statistics.
    """
    if not payload:
        return payload

    header = payload[0] if payload else []
    data_rows = payload[1:]
    total_rows = len(data_rows)

    if total_rows == 0:
        return payload

    # Determine sample size based on mode and dataset size
    if mode == "safe":
        sample_size = min(500, total_rows)
    elif mode == "balanced":
        sample_size = min(200, total_rows)
    else:  # aggressive / low
        sample_size = min(50, total_rows)

    # For very large datasets, use even smaller samples
    if total_rows > 5000:
        if mode == "safe":
            sample_size = min(200, total_rows)
        elif mode == "balanced":
            sample_size = min(100, total_rows)
        else:
            sample_size = min(20, total_rows)

    # Build sample: first N rows + evenly distributed samples
    if total_rows <= sample_size:
        sample = data_rows
    else:
        step = total_rows // sample_size
        indices = [0] + [i * step for i in range(1, sample_size)]
        # Ensure we don't go out of bounds
        indices = [min(i, total_rows - 1) for i in indices]
        sample = [data_rows[i] for i in sorted(set(indices))]

    # Drop empty columns
    col_count = len(header)
    empty_cols = set()
    for col_idx in range(col_count):
        if all(not str(row[col_idx]).strip() for row in sample if col_idx < len(row)):
            empty_cols.add(col_idx)

    def filter_row(row: list) -> list:
        return [cell for i, cell in enumerate(row) if i not in empty_cols and i < col_count]

    filtered_header = filter_row(header)
    filtered_sample = [filter_row(row) for row in sample]

    # Truncate long cells
    max_cell_len = 200 if mode == "safe" else 100
    truncated_sample = []
    for row in filtered_sample:
        truncated = []
        for cell in row:
            s = str(cell)
            if len(s) > max_cell_len:
                s = s[:max_cell_len - 3] + "..."
            truncated.append(s)
        truncated_sample.append(truncated)

    # Build result with summary
    result = {
        "_aperture_summary": {
            "total_rows": total_rows,
            "sampled_rows": len(truncated_sample),
            "columns_shown": len(filtered_header),
            "columns_dropped": len(empty_cols),
            "sampling_method": f"{mode}_tabular",
        },
        "headers": filtered_header,
        "sample": truncated_sample,
    }

    # Add simple stats for numeric columns
    stats = {}
    for col_idx, col_name in enumerate(filtered_header):
        # Try to detect numeric column
        numeric_values = []
        for row in truncated_sample:
            if col_idx < len(row):
                try:
                    v = float(str(row[col_idx]).replace(",", ""))
                    numeric_values.append(v)
                except (ValueError, TypeError):
                    pass
        if numeric_values and len(numeric_values) > len(truncated_sample) * 0.5:
            stats[col_name] = {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "avg": round(sum(numeric_values) / len(numeric_values), 1),
            }

    if stats:
        result["stats"] = stats

    return result


def _safe_compress(payload: object) -> object:
    """Safe mode: drop nulls, empty values, and obvious API metadata."""
    return _compress_value(payload, aggressive=False)


def _balanced_compress(payload: object) -> object:
    """Balanced mode: safe + flatten nested objects + compact lists."""
    return _compress_value(payload, aggressive=True)


def _compress_value(value: object, aggressive: bool = False) -> object:
    """Recursively compress a value."""
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float, str)):
        return value

    if isinstance(value, list):
        return _compress_list(value, aggressive)

    if isinstance(value, dict):
        return _compress_dict(value, aggressive)

    return value


def _compress_dict(d: dict[str, Any], aggressive: bool) -> dict[str, Any]:
    """Compress a dict by dropping low-value fields."""
    result = {}
    for key, val in d.items():
        # Skip nulls and empty values
        if val is None:
            continue
        if val == "" or val == [] or val == {}:
            continue

        # Skip obvious API metadata
        if key in _OBVIOUS_API_FIELDS:
            continue

        # In aggressive mode, flatten simple nested objects
        if aggressive and isinstance(val, dict):
            # If it's a user/repo object with just a login/name, flatten it
            if len(val) == 1 and "login" in val:
                result[key] = val["login"]
                continue
            if len(val) == 1 and "name" in val:
                result[key] = val["name"]
                continue
            # If it has login/name alongside URLs, extract just the useful part
            if "login" in val:
                result[key] = val["login"]
                continue
            if "name" in val:
                result[key] = val["name"]
                continue

        result[key] = _compress_value(val, aggressive)

    return result


def _compress_list(lst: list, aggressive: bool) -> list:
    """Compress a list by compressing each item."""
    result = []
    for item in lst:
        compressed = _compress_value(item, aggressive)
        if compressed is not None and compressed != {} and compressed != []:
            result.append(compressed)
    return result


def _collect_omitted_fields(raw: object, compressed: object) -> list[str]:
    """Collect top-level field names that were dropped."""
    if not isinstance(raw, dict) or not isinstance(compressed, dict):
        return []
    return [k for k in raw.keys() if k not in compressed]
