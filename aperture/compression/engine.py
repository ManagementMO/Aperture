"""Schema-aware output compression engine.

Pipeline:
1. Optional upstream field selection (Phase 4).
2. Tool-specific normalization (Gmail headers → top-level fields, Slack noise drop).
3. Tabular vs. record vs. object dispatch.
4. Mode-driven pruning, flattening, list compaction with task-aware protection.
"""

from typing import Any

from aperture.compression.field_classifier import ClassifierResult, classify_fields
from aperture.compression.field_policy import FieldPolicy, make_policy
from aperture.compression.field_profiles import apply_field_selection
from aperture.compression.stopwords import prune_payload as caveman_prune_payload
from aperture.compression.task_profiles import merge_required_fields
from aperture.compression.toon import is_tabular_records, to_toon
from aperture.contracts import CompressionResult
from aperture.tokenization import count_tokens

_VALID_MODES: frozenset[str] = frozenset({"off", "safe", "balanced", "low", "aggressive"})

# Backwards-compat alias for tests/imports that still reference the old name.
from aperture.compression.field_policy import _OBVIOUS_API_FIELDS  # noqa: E402,F401


def _collect_field_names(payload: object, depth: int = 0, max_depth: int = 4) -> list[str]:
    """Walk a payload and return every field name that appears at any level.
    Used to feed the optional model classifier — it never sees values."""
    seen: set[str] = set()

    def walk(obj: object, level: int) -> None:
        if level > max_depth:
            return
        if isinstance(obj, dict):
            for key, val in obj.items():
                if isinstance(key, str):
                    seen.add(key)
                walk(val, level + 1)
        elif isinstance(obj, list):
            for item in obj[:5]:  # sample — same fields will repeat
                walk(item, level + 1)

    walk(payload, depth)
    return sorted(seen)


def compress_tool_output(
    raw_payload: object,
    tool_slug: str,
    mode: str = "balanced",
    model: str | None = None,
    task: str | None = None,
    required_fields: list[str] | None = None,
    apply_field_filter: list[str] | None = None,
    ask: str | None = None,
    field_policy_mode: str = "static",
) -> CompressionResult:
    """Compress a raw tool output into a compact model-facing payload.

    Args:
        raw_payload: The raw tool result from Composio.
        tool_slug: Tool identifier for profile + normalizer selection.
        mode: off | safe | balanced | low | aggressive.
        model: Optional model name for tokenizer selection.
        task: Optional task name for task-aware field protection.
        required_fields: Explicit dot-paths that must be preserved.
        apply_field_filter: Phase 4 — simulate upstream field selection.
        ask: User's natural-language ask. Enables ask-aware promotion of
            denied fields when `field_policy_mode != "static"`.
        field_policy_mode: `static` (denial list only) | `ask_aware`
            (also keep fields the ask mentions) | `model_assisted`
            (ask-aware + Anthropic Haiku classifier on ambiguous fields).
    """
    if mode not in _VALID_MODES:
        mode = "safe"

    if apply_field_filter:
        raw_payload = apply_field_selection(raw_payload, apply_field_filter)

    raw_count = count_tokens(raw_payload, model)

    if mode == "off":
        return CompressionResult(
            compressed_payload=raw_payload,
            raw_tokens=raw_count.tokens,
            compressed_tokens=raw_count.tokens,
            tokens_saved=0,
            compression_ratio=1.0,
            strategy="off",
            omitted_fields=[],
        )

    normalized = _normalize_for_tool(raw_payload, tool_slug)
    protected_fields = merge_required_fields(tool_slug, task, required_fields)

    # Build the FieldPolicy. Static mode → no ask, no classifier. Ask-aware
    # mode → ask flows through to word-bounded matches. Model-assisted →
    # also asks Haiku once per (tool, ask) and merges its keep-set.
    classifier_result: ClassifierResult | None = None
    classifier_keeps: set[str] = set()
    if field_policy_mode == "model_assisted" and ask:
        classifier_result = classify_fields(
            tool_slug=tool_slug,
            ask=ask,
            field_names=_collect_field_names(normalized),
            enabled=True,
        )
        classifier_keeps = classifier_result.keeps

    policy = make_policy(
        required_signals=protected_fields,
        ask=ask if field_policy_mode in ("ask_aware", "model_assisted") else None,
        classifier_keeps=classifier_keeps,
    )

    if _is_tabular(normalized):
        is_small = (
            isinstance(normalized, list)
            and len(normalized) <= 10
            and raw_count.tokens < 3000
        )
        if is_small:
            compressed = _compress_records(
                normalized, mode=mode, protected_fields=protected_fields, skip_wrapper=True, policy=policy
            )
            strategy = f"inplace_{mode}"
        else:
            compressed = _compress_tabular(
                normalized, mode=mode, protected_fields=protected_fields, policy=policy
            )
            strategy = f"tabular_{mode}"
    elif mode == "safe":
        compressed = _safe_compress(normalized, protected_fields=protected_fields, policy=policy)
        strategy = "safe"
    elif mode == "balanced":
        compressed = _balanced_compress(normalized, protected_fields=protected_fields, policy=policy)
        strategy = "balanced"
    elif mode == "low":
        compressed = _low_compress(normalized, protected_fields=protected_fields, policy=policy)
        strategy = "low"
    else:  # aggressive
        compressed = _aggressive_compress(normalized, protected_fields=protected_fields, policy=policy)
        compressed = caveman_prune_payload(compressed, level="full")
        strategy = "aggressive_caveman"

    json_count = count_tokens(compressed, model)
    llm_format = "json"
    llm_string: str | None = None
    llm_tokens = json_count.tokens

    # TOON encoding for tabular output — denser than JSON for uniform records.
    if mode in ("balanced", "low", "aggressive") and _toon_friendly(compressed):
        toon_str = to_toon(compressed, name=tool_slug.lower())
        toon_tokens = count_tokens(toon_str, model).tokens
        if toon_tokens < json_count.tokens:
            llm_format = "toon"
            llm_string = toon_str
            llm_tokens = toon_tokens

    tokens_saved = max(0, raw_count.tokens - llm_tokens)
    ratio = round(llm_tokens / max(raw_count.tokens, 1), 3)

    warnings: list[str] = []
    if task:
        warnings.append(f"task_profile={task}")
    if protected_fields:
        warnings.append(f"protected_fields={len(protected_fields)}")
    if llm_format == "toon":
        warnings.append("encoding=toon")
    if field_policy_mode != "static":
        warnings.append(f"field_policy={field_policy_mode}")
    if classifier_keeps:
        warnings.append(f"classifier_promoted={len(classifier_keeps)}")

    promotions = [
        {"name": d.name, "path": d.full_path, "reason": d.reason}
        for d in policy.promotions()
    ]

    return CompressionResult(
        compressed_payload=compressed,
        raw_tokens=raw_count.tokens,
        compressed_tokens=llm_tokens,
        tokens_saved=tokens_saved,
        compression_ratio=ratio,
        strategy=strategy if not task else f"{strategy}_task={task}",
        omitted_fields=_collect_omitted_fields(raw_payload, compressed),
        warnings=warnings,
        llm_format=llm_format,
        llm_string=llm_string,
        policy_mode=field_policy_mode,
        policy_reason_counts=policy.reason_counts(),
        policy_promotions=promotions,
        classifier_used=bool(classifier_result and classifier_result.available),
        classifier_keeps=sorted(classifier_keeps),
        classifier_cost_usd=classifier_result.cost_estimate_usd if classifier_result else 0.0,
    )


def _toon_friendly(payload: object) -> bool:
    """Decide whether a compressed payload renders better as TOON than JSON."""
    if isinstance(payload, list):
        return is_tabular_records(payload)
    if isinstance(payload, dict) and "_aperture_summary" in payload:
        sample = payload.get("sample")
        return isinstance(sample, list) and is_tabular_records(sample)
    return False


# ---------------------------------------------------------------------------
# Tool-specific normalization
# ---------------------------------------------------------------------------

def _normalize_for_tool(payload: object, tool_slug: str) -> object:
    """Apply tool-specific cleanups before generic compression."""
    if "GMAIL" in tool_slug:
        return _normalize_gmail(payload)
    if "SLACK" in tool_slug:
        return _normalize_slack(payload)
    return payload


def _normalize_gmail(payload: object) -> object:
    """Lift Gmail message headers to top-level fields, drop raw MIME parts.

    Gmail responses bury Subject/From/To inside payload.headers and dump huge
    base64 parts under payload.parts[].body.data. The LLM only needs the
    snippet plus the addressing headers — everything else is base64 noise.
    """
    if isinstance(payload, list):
        return [_normalize_gmail(item) for item in payload]

    if not isinstance(payload, dict):
        return payload

    if "messages" in payload and isinstance(payload["messages"], list):
        return {
            **{k: v for k, v in payload.items() if k != "messages"},
            "messages": [_normalize_gmail_message(m) for m in payload["messages"]],
        }

    if "payload" in payload and isinstance(payload.get("payload"), dict):
        return _normalize_gmail_message(payload)

    return payload


def _normalize_gmail_message(msg: dict) -> dict:
    if not isinstance(msg, dict):
        return msg

    out: dict[str, Any] = {}
    for key in ("id", "threadId", "snippet", "labelIds"):
        if key in msg and msg[key] not in (None, "", []):
            out[key] = msg[key]

    payload = msg.get("payload")
    if isinstance(payload, dict):
        headers = payload.get("headers", [])
        if isinstance(headers, list):
            wanted = {"From", "To", "Cc", "Subject", "Date", "Reply-To"}
            for header in headers:
                if isinstance(header, dict):
                    name = header.get("name")
                    if name in wanted and header.get("value"):
                        out[name.lower().replace("-", "_")] = header["value"]

    return out


def _normalize_slack(payload: object) -> object:
    """Drop heavy Slack scaffolding (blocks, attachments, reactions noise)."""
    if isinstance(payload, list):
        return [_normalize_slack(item) for item in payload]

    if not isinstance(payload, dict):
        return payload

    drop = {
        "blocks",
        "attachments",
        "client_msg_id",
        "subscribed",
        "last_read",
        "unread_count",
        "reply_users",
        "latest_reply",
    }
    out = {k: v for k, v in payload.items() if k not in drop}

    channel = out.get("channel")
    if isinstance(channel, dict) and "name" in channel:
        out["channel"] = channel["name"]

    reactions = out.get("reactions")
    if isinstance(reactions, list):
        out["reactions"] = [r.get("name") for r in reactions if isinstance(r, dict) and r.get("name")]

    return out


# ---------------------------------------------------------------------------
# Tabular detection + compression
# ---------------------------------------------------------------------------

def _is_tabular(payload: object) -> bool:
    if not isinstance(payload, list) or not payload:
        return False
    head = payload[:10]
    if all(isinstance(row, list) for row in head):
        return True
    if all(isinstance(row, dict) for row in head):
        if len(head) <= 1:
            return True
        keys = [set(row.keys()) for row in head]
        common = set.intersection(*keys)
        all_keys = set.union(*keys)
        return len(common) / max(len(all_keys), 1) >= 0.8
    return False


def _compress_tabular(
    payload: list, mode: str = "balanced", protected_fields: set[str] | None = None,
    policy: FieldPolicy | None = None,
) -> object:
    if not payload:
        return payload
    if isinstance(payload[0], dict):
        return _compress_records(payload, mode, protected_fields=protected_fields, policy=policy)
    return _compress_2d_array(payload, mode)


def _compress_2d_array(payload: list[list], mode: str = "balanced") -> object:
    header = payload[0] if payload else []
    data_rows = payload[1:]
    total_rows = len(data_rows)
    if total_rows == 0:
        return payload

    sample, _ = _build_sample(data_rows, mode)

    col_count = len(header)
    empty_cols: set[int] = set()
    for col_idx in range(col_count):
        if all(not str(row[col_idx]).strip() for row in sample if col_idx < len(row)):
            empty_cols.add(col_idx)

    def keep_row(row: list) -> list:
        return [cell for i, cell in enumerate(row) if i not in empty_cols and i < col_count]

    filtered_header = keep_row(header)
    filtered_sample = [keep_row(row) for row in sample]

    max_cell_len = 200 if mode == "safe" else 80
    truncated_sample: list[list[str]] = []
    for row in filtered_sample:
        truncated_sample.append([_truncate(cell, max_cell_len) for cell in row])

    result: dict[str, Any] = {
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

    stats = _column_stats(filtered_header, truncated_sample)
    if stats:
        result["stats"] = stats
    return result


def _column_stats(headers: list, sample: list[list]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for col_idx, col_name in enumerate(headers):
        numeric: list[float] = []
        for row in sample:
            if col_idx < len(row):
                try:
                    numeric.append(float(str(row[col_idx]).replace(",", "")))
                except (ValueError, TypeError):
                    pass
        if numeric and len(numeric) > len(sample) * 0.5:
            stats[col_name] = {
                "min": min(numeric),
                "max": max(numeric),
                "avg": round(sum(numeric) / len(numeric), 1),
            }
    return stats


def _truncate(cell: object, max_len: int) -> str:
    s = str(cell)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


# ---------------------------------------------------------------------------
# Record list compression
# ---------------------------------------------------------------------------

def _compress_records(
    payload: list[dict],
    mode: str = "balanced",
    protected_fields: set[str] | None = None,
    skip_wrapper: bool = False,
    policy: FieldPolicy | None = None,
) -> object:
    total_rows = len(payload)
    protected = protected_fields or set()
    policy = policy or make_policy(required_signals=protected)

    sample, _ = _build_sample(payload, mode)

    all_keys: set[str] = set()
    for row in payload[:100]:
        if isinstance(row, dict):
            all_keys.update(row.keys())

    empty_fields = {
        k for k in all_keys
        if all(
            isinstance(row, dict) and row.get(k) in (None, "", [], {})
            for row in payload[: min(100, total_rows)]
        )
    }

    # Build the drop set the same way the old engine did: every denied name,
    # minus anything the policy decided to keep (ask-aware / classifier /
    # explicit signals can promote a denied name back to keep). We use the
    # full _OBVIOUS_API_FIELDS so nested keys (avatar_url inside user, etc.)
    # are also dropped — the policy filter is the single arbiter.
    denial_drops = {
        k for k in _OBVIOUS_API_FIELDS
        if policy.decide(k, "").decision == "drop"
    }
    fields_to_drop = empty_fields | denial_drops

    constant_fields = set()
    if total_rows > 1:
        for key in all_keys - fields_to_drop:
            values = {
                str(row.get(key)) for row in payload[: min(50, total_rows)]
                if isinstance(row, dict)
            }
            if len(values) == 1:
                constant_fields.add(key)
        fields_to_drop |= constant_fields

    max_str_len = 200 if mode in ("safe", "balanced") else 80
    keep_list = {"low": 3, "aggressive": 2}.get(mode, 5)

    def is_protected(key: str, parent_path: str = "") -> bool:
        full_path = f"{parent_path}.{key}" if parent_path else key
        if full_path in protected or key in protected:
            return True
        for p in protected:
            if p.startswith(f"{full_path}.") or p.startswith(f"{key}."):
                return True
        return False

    def compress_record(row: dict, parent_path: str = "") -> dict:
        out: dict[str, Any] = {}
        for key, val in row.items():
            protected_key = is_protected(key, parent_path)
            if not protected_key:
                if key in fields_to_drop:
                    continue
                if val in (None, "", [], {}):
                    continue
            effective_max = max_str_len * 3 if protected_key else max_str_len
            new_path = f"{parent_path}.{key}" if parent_path else key

            if isinstance(val, str) and len(val) > effective_max:
                out[key] = val[: effective_max - 3] + "..."
            elif isinstance(val, dict):
                if not protected_key:
                    flat = _maybe_flatten(val)
                    if flat is not None:
                        out[key] = flat
                        continue
                inner = compress_record(val, new_path)
                if inner:
                    out[key] = inner
            elif isinstance(val, list):
                items = []
                for item in val:
                    if isinstance(item, dict):
                        ci = compress_record(item, new_path)
                        if ci:
                            items.append(ci)
                    elif item not in (None, ""):
                        items.append(item)
                if not items:
                    continue
                limit = keep_list * 3 if protected_key else keep_list
                if len(items) <= limit:
                    out[key] = items
                else:
                    out[key] = items[:limit] + [f"... ({len(items) - limit} more)"]
            else:
                out[key] = val
        return out

    compressed_sample = [compress_record(row) for row in sample if isinstance(row, dict)]
    compressed_sample = [r for r in compressed_sample if r]

    # Normalize to a uniform key set so TOON can encode densely. Compute the
    # union of keys actually present, then fill missing entries with None on
    # each row. JSON cost is similar (None is short); TOON cost drops sharply
    # because the header is written once per table.
    if compressed_sample:
        union_keys: list[str] = []
        seen: set[str] = set()
        for row in compressed_sample:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    union_keys.append(key)
        compressed_sample = [
            {k: row.get(k) for k in union_keys} for row in compressed_sample
        ]

    stats = _record_stats(sample, all_keys - fields_to_drop)

    if skip_wrapper:
        return compressed_sample

    result: dict[str, Any] = {
        "_aperture_summary": {
            "total_rows": total_rows,
            "sampled_rows": len(compressed_sample),
            "fields_shown": len(all_keys - fields_to_drop),
            "fields_dropped": len(fields_to_drop),
            "sampling_method": f"{mode}_records",
        },
        "sample": compressed_sample,
    }
    if stats:
        result["stats"] = stats
    return result


def _record_stats(sample: list, fields: set[str]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for key in fields:
        numeric: list[float] = []
        for row in sample:
            if not isinstance(row, dict):
                continue
            v = row.get(key)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                numeric.append(v)
            elif isinstance(v, str):
                try:
                    numeric.append(float(v.replace(",", "")))
                except (ValueError, TypeError):
                    pass
        if numeric and len(numeric) > len(sample) * 0.3:
            stats[key] = {
                "min": min(numeric),
                "max": max(numeric),
                "avg": round(sum(numeric) / len(numeric), 2),
            }
    return stats


def _build_sample(data_rows: list, mode: str) -> tuple[list, int]:
    total_rows = len(data_rows)

    sample_size = {
        "safe": 500,
        "balanced": 200,
        "low": 50,
        "aggressive": 25,
    }.get(mode, 100)

    if total_rows > 5000:
        sample_size = {
            "safe": 200,
            "balanced": 100,
            "low": 30,
            "aggressive": 15,
        }.get(mode, 50)

    sample_size = min(sample_size, total_rows)
    if total_rows <= sample_size:
        return data_rows, sample_size

    step = max(total_rows // sample_size, 1)
    indices = sorted({min(i * step, total_rows - 1) for i in range(sample_size)})
    return [data_rows[i] for i in indices], sample_size


# ---------------------------------------------------------------------------
# Generic value compression
# ---------------------------------------------------------------------------

def _safe_compress(payload: object, protected_fields: set[str] | None = None, policy: FieldPolicy | None = None) -> object:
    return _compress_value(payload, level="safe", protected_fields=protected_fields, policy=policy)


def _balanced_compress(payload: object, protected_fields: set[str] | None = None, policy: FieldPolicy | None = None) -> object:
    return _compress_value(payload, level="balanced", protected_fields=protected_fields, policy=policy)


def _low_compress(payload: object, protected_fields: set[str] | None = None, policy: FieldPolicy | None = None) -> object:
    return _compress_value(payload, level="low", protected_fields=protected_fields, policy=policy)


def _aggressive_compress(payload: object, protected_fields: set[str] | None = None, policy: FieldPolicy | None = None) -> object:
    return _compress_value(payload, level="aggressive", protected_fields=protected_fields, policy=policy)


def _compress_value(
    value: object,
    level: str = "balanced",
    protected_fields: set[str] | None = None,
    parent_path: str = "",
    policy: FieldPolicy | None = None,
) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        max_len = {"safe": 800, "balanced": 400, "low": 200, "aggressive": 120}.get(level, 400)
        if len(value) > max_len:
            return value[: max_len - 3] + "..."
        return value
    if isinstance(value, list):
        return _compress_list(value, level, protected_fields, parent_path, policy)
    if isinstance(value, dict):
        return _compress_dict(value, level, protected_fields, parent_path, policy)
    return value


def _compress_dict(
    d: dict[str, Any],
    level: str,
    protected_fields: set[str] | None,
    parent_path: str,
    policy: FieldPolicy | None = None,
) -> dict[str, Any]:
    protected = protected_fields or set()
    policy = policy or make_policy(required_signals=protected)
    result: dict[str, Any] = {}
    flatten = level in ("balanced", "low", "aggressive")

    for key, val in d.items():
        full_path = f"{parent_path}.{key}" if parent_path else key
        decision = policy.decide(key, parent_path)
        is_protected = decision.reason in ("explicit", "explicit_descendant")

        if not is_protected:
            if val is None or val == "" or val == [] or val == {}:
                continue
            if decision.decision == "drop":
                continue

        if flatten and isinstance(val, dict) and not is_protected:
            short = _maybe_flatten(val)
            if short is not None:
                result[key] = short
                continue

        result[key] = _compress_value(val, level, protected, full_path, policy)
    return result


def _compress_list(
    lst: list,
    level: str,
    protected_fields: set[str] | None,
    parent_path: str,
    policy: FieldPolicy | None = None,
) -> list:
    out = []
    for item in lst:
        compressed = _compress_value(item, level, protected_fields, parent_path, policy)
        if compressed not in (None, "", [], {}):
            out.append(compressed)

    cap = {"low": 5, "aggressive": 3}.get(level)
    if cap and len(out) > cap:
        return out[:cap] + [f"... ({len(out) - cap} more)"]
    return out


def _maybe_flatten(val: dict) -> object | None:
    """If a dict has a single dominant identity field, return that value."""
    if len(val) == 1:
        only = next(iter(val.values()))
        if isinstance(only, (str, int, float)):
            return only
        return None

    for key in ("login", "name", "title"):
        if key in val and isinstance(val[key], (str, int, float)):
            if len(val) <= 4:
                return val[key]
    return None


def _collect_omitted_fields(raw: object, compressed: object) -> list[str]:
    if not isinstance(raw, dict) or not isinstance(compressed, dict):
        return []
    return [k for k in raw.keys() if k not in compressed]
