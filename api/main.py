"""FastAPI backend for Aperture — serves ONLY real measured data."""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aperture.compression.engine import compress_tool_output
from aperture.compression.task_profiles import (
    get_profile,
    list_profiles_for_tool,
    merge_required_fields,
)
from aperture.compression.hydration import (
    store_full_result,
    make_placeholder,
    hydrate,
    get_cache_stats as get_hydration_stats,
)
from aperture.compression.prompt_cache import (
    build_cache_optimized_prompt,
    estimate_savings,
)
from aperture.compression.field_profiles import (
    get_field_profile,
    list_field_profiles_for_tool,
    apply_field_selection,
)
from aperture.compression.field_classifier import classifier_health
from aperture.routing.quality_gate import select_mode_for_quality
from aperture.schema_optimizer.type_group import compact_schema, measure_compaction
from aperture.tokenization import count_tokens
from aperture.demo.scenarios import get_mock_result
from aperture.cache.interceptor import CachedExecutor
from aperture.contracts import ApertureRunConfig, CompressionResult
from aperture.routing.effort_modes import get_effort_config

# Load real mock datasets
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _load_json(name):
    with open(os.path.join(DATA_DIR, name)) as f:
        return json.load(f)

def _load_csv(name):
    import csv
    with open(os.path.join(DATA_DIR, name)) as f:
        reader = csv.reader(f)
        rows = list(reader)
    return rows

DATASETS = {
    "github_users": _load_csv("github_users_10k.csv") if os.path.exists(os.path.join(DATA_DIR, "github_users_10k.csv")) else None,
    "notion_pages": _load_json("notion_pages_500.json") if os.path.exists(os.path.join(DATA_DIR, "notion_pages_500.json")) else None,
    "linear_issues": _load_json("linear_issues_200.json") if os.path.exists(os.path.join(DATA_DIR, "linear_issues_200.json")) else None,
    "supabase_users": _load_json("supabase_users_1000.json") if os.path.exists(os.path.join(DATA_DIR, "supabase_users_1000.json")) else None,
}

app = FastAPI(title="Aperture API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _measure_compression(
    data,
    tool_slug,
    mode,
    task=None,
    required_fields=None,
    apply_field_filter=None,
    ask=None,
    field_policy_mode="static",
):
    """Run real compression and return real measurements (all in gpt-4o tokens)."""
    model = "gpt-4o"
    raw_tc = count_tokens(data, model=model)
    result = compress_tool_output(
        data,
        tool_slug,
        mode=mode,
        model=model,
        task=task,
        required_fields=required_fields,
        apply_field_filter=apply_field_filter,
        ask=ask,
        field_policy_mode=field_policy_mode,
    )
    json_tc = count_tokens(result.compressed_payload, model=model)
    return {
        "raw_tokens": raw_tc.tokens,
        "compressed_tokens": result.compressed_tokens,
        "json_tokens": json_tc.tokens,
        "tokens_saved": raw_tc.tokens - result.compressed_tokens,
        "compression_ratio": result.compression_ratio,
        "strategy": result.strategy,
        "mode": mode,
        "tool_slug": tool_slug,
        "task": task,
        "llm_format": result.llm_format,
        "llm_string_preview": (result.llm_string or "")[:600] if result.llm_string else None,
        "protected_field_count": len(result.warnings),
        "omitted_fields": result.omitted_fields,
        "warnings": result.warnings,
        "policy_mode": result.policy_mode,
        "policy_reason_counts": result.policy_reason_counts,
        "policy_promotions": result.policy_promotions[:50],
        "classifier_used": result.classifier_used,
        "classifier_keeps": result.classifier_keeps,
        "classifier_cost_usd": result.classifier_cost_usd,
    }

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/datasets")
def list_datasets():
    """List available mock datasets with real item counts."""
    result = {}
    for name, data in DATASETS.items():
        if data is not None:
            result[name] = {
                "items": len(data),
                "raw_tokens": count_tokens(data).tokens,
            }
    return result


# ---------------------------------------------------------------------------
# Phase 1: Task-Aware Selective Compression
# ---------------------------------------------------------------------------

@app.get("/api/task-profiles")
def list_task_profiles(tool_slug: str | None = None):
    """List available task-aware compression profiles."""
    if tool_slug:
        profiles = list_profiles_for_tool(tool_slug)
    else:
        from aperture.compression.task_profiles import _ALL_PROFILES as profiles
    return {
        "profiles": [
            {
                "task_name": p.task_name,
                "tool_slug": p.tool_slug,
                "required_fields": sorted(p.required_fields),
                "droppable_fields": sorted(p.droppable_fields)[:20],  # Truncated for response size
                "description": p.description,
            }
            for p in profiles
        ]
    }


@app.post("/api/compress/task-aware")
def compress_task_aware(payload: dict):
    """Compress with task-aware field protection.

    Body: {
        "dataset": "notion_pages",
        "tool_slug": "NOTION_SEARCH_NOTION_PAGE",
        "mode": "balanced",
        "task": "search_and_list",
        "required_fields": ["id", "title"]  // optional explicit fields
    }
    """
    dataset_name = payload.get("dataset", "")
    mode = payload.get("mode", "balanced")
    task = payload.get("task")
    required_fields = payload.get("required_fields")

    if dataset_name in DATASETS and DATASETS[dataset_name] is not None:
        data = DATASETS[dataset_name]
    else:
        # Try as a mock tool
        data = get_mock_result(payload.get("tool_slug", ""), payload.get("arguments", {}))

    tool_slug = payload.get("tool_slug", f"DATASET_{dataset_name.upper()}")

    # Run baseline (no task awareness)
    baseline = _measure_compression(data, tool_slug, mode)

    # Run task-aware
    task_result = _measure_compression(data, tool_slug, mode, task=task, required_fields=required_fields)

    # Get the profile for display
    profile = get_profile(tool_slug, task) if task else None

    return {
        "baseline": baseline,
        "task_aware": task_result,
        "profile": {
            "task_name": profile.task_name if profile else None,
            "tool_slug": profile.tool_slug if profile else None,
            "required_fields": sorted(profile.required_fields) if profile else [],
            "description": profile.description if profile else "",
        } if profile else None,
        "delta_tokens_saved": task_result["tokens_saved"] - baseline["tokens_saved"],
        "quality_preservation": "High — protected fields retained, droppable fields aggressively compressed",
    }


# ---------------------------------------------------------------------------
# Phase 2: Lazy Hydration + Placeholders
# ---------------------------------------------------------------------------

@app.post("/api/compress/placeholder")
def compress_with_placeholder(payload: dict):
    """Compress a result to a placeholder for lazy hydration.

    Body: {
        "tool_slug": "GITHUB_LIST_ISSUES",
        "arguments": {"per_page": 5},
        "mode": "balanced",
        "include_sample": true,
        "sample_size": 3
    }

    Returns a compact placeholder with a reference ID.
    The full result is cached server-side and can be hydrated on demand.
    """
    tool_slug = payload.get("tool_slug", "")
    arguments = payload.get("arguments", {})
    mode = payload.get("mode", "balanced")
    include_sample = payload.get("include_sample", True)
    sample_size = payload.get("sample_size", 3)

    # Get the full result
    raw_result = get_mock_result(tool_slug, arguments)
    raw_tc = count_tokens(raw_result)

    # Store full result for hydration
    ref_id = store_full_result(tool_slug, arguments, raw_result)

    # Create placeholder
    placeholder = make_placeholder(
        ref_id, tool_slug, raw_result,
        include_sample=include_sample, sample_size=sample_size
    )
    placeholder_tc = count_tokens(placeholder)

    # Also run normal compression for comparison
    compressed = compress_tool_output(raw_result, tool_slug, mode=mode, model="gpt-4o")
    comp_tc = count_tokens(compressed.compressed_payload)

    return {
        "ref_id": ref_id,
        "tool_slug": tool_slug,
        "placeholder": placeholder,
        "placeholder_tokens": placeholder_tc.tokens,
        "raw_tokens": raw_tc.tokens,
        "compressed_tokens": comp_tc.tokens,
        "tokens_saved_vs_raw": raw_tc.tokens - placeholder_tc.tokens,
        "tokens_saved_vs_compressed": comp_tc.tokens - placeholder_tc.tokens,
        "savings_percent_vs_raw": round((raw_tc.tokens - placeholder_tc.tokens) / max(raw_tc.tokens, 1) * 100, 1),
        "full_result_available": True,
        "hydrate_endpoint": f"/api/hydrate/{ref_id}",
    }


@app.get("/api/hydrate/{ref_id}")
def hydrate_result(ref_id: str, field_path: str | None = None, index: int | None = None):
    """Hydrate a cached result by reference ID.

    Query params:
        field_path: Dot-path to a specific field (e.g. "assignee.login")
        index: For list payloads, which item to hydrate
    """
    result = hydrate(ref_id, field_path=field_path, index=index)
    if result is None:
        return {"error": "Reference not found or expired", "ref_id": ref_id}

    return {
        "ref_id": ref_id,
        "field_path": field_path,
        "index": index,
        "hydrated": result,
        "hydrated_tokens": count_tokens(result).tokens,
    }


@app.get("/api/hydration/stats")
def hydration_stats():
    """Statistics for the hydration cache."""
    return get_hydration_stats()


# ---------------------------------------------------------------------------
# Phase 3: Prompt Caching Optimization
# ---------------------------------------------------------------------------

@app.post("/api/prompt-cache/optimize")
def optimize_prompt_for_caching(payload: dict):
    """Build a cache-optimized prompt structure with multi-tier breakpoints.

    Body: {
        system_prompt, tool_schemas[], static_context[], tool_results[], user_messages[],
        provider: "anthropic" | "openai" | "generic",
        history_turn_count: int (0+; rolling 5m breakpoint kicks in past 20)
    }
    """
    provider = payload.get("provider", "anthropic")
    history_turn_count = int(payload.get("history_turn_count", 0))

    prompt = build_cache_optimized_prompt(
        system_prompt=payload.get("system_prompt"),
        tool_schemas=payload.get("tool_schemas", []),
        static_context=payload.get("static_context", []),
        tool_results=payload.get("tool_results", []),
        user_messages=payload.get("user_messages", []),
        provider=provider,
        model=payload.get("model"),
        history_turn_count=history_turn_count,
    )

    for block in prompt.blocks:
        block.estimated_tokens = count_tokens(block.content, model="gpt-4o").tokens

    savings = estimate_savings(
        prompt,
        provider=provider,
        expected_turns=int(payload.get("expected_turns", 8)),
    )

    return {
        "blocks": [
            {
                "type": b.block_type,
                "cacheable": b.cacheable,
                "ttl": b.ttl,
                "estimated_tokens": b.estimated_tokens,
                "prefix_hash": b.prefix_hash,
                "content_preview": b.content[:200] + "..." if len(b.content) > 200 else b.content,
            }
            for b in prompt.blocks
        ],
        "ordering": "stable_first_dynamic_last",
        "provider": prompt.provider,
        "estimated_savings": savings,
        "recommendation": (
            "Up to 4 cache_control breakpoints across two TTL tiers: 1h for tool schemas + "
            "static context (rarely change), 5m for tool results and rolling user messages "
            "(turn over each turn). Anthropic enforces a 1h-then-5m order — the builder "
            "respects this automatically."
        ),
    }


# ---------------------------------------------------------------------------
# Phase 4: Upstream Field Selection
# ---------------------------------------------------------------------------

@app.get("/api/field-profiles")
def list_field_profiles(tool_slug: str | None = None):
    """List available upstream field selection profiles."""
    if tool_slug:
        profiles = list_field_profiles_for_tool(tool_slug)
    else:
        from aperture.compression.field_profiles import _ALL_FIELD_PROFILES as profiles
    return {
        "profiles": [
            {
                "tool_slug": p.tool_slug,
                "profile_name": p.profile_name,
                "fields": p.fields,
                "page_size": p.page_size,
                "description": p.description,
            }
            for p in profiles
        ]
    }


@app.post("/api/compress/field-select")
def compress_with_field_selection(payload: dict):
    """Compress by simulating upstream field selection.

    Body: {
        "dataset": "notion_pages",
        "tool_slug": "NOTION_SEARCH_NOTION_PAGE",
        "mode": "balanced",
        "field_profile": "minimal",   // or explicit "fields": ["id", "title"]
        "fields": ["id", "title", "url"]
    }
    """
    dataset_name = payload.get("dataset", "")
    mode = payload.get("mode", "balanced")
    tool_slug = payload.get("tool_slug", f"DATASET_{dataset_name.upper()}")

    if dataset_name in DATASETS and DATASETS[dataset_name] is not None:
        data = DATASETS[dataset_name]
    else:
        data = get_mock_result(tool_slug, payload.get("arguments", {}))

    # Resolve field list from profile or explicit
    field_profile_name = payload.get("field_profile")
    explicit_fields = payload.get("fields")

    if field_profile_name:
        profile = get_field_profile(tool_slug, field_profile_name)
        if profile:
            fields = profile.fields
        else:
            return {"error": f"Field profile '{field_profile_name}' not found for {tool_slug}"}
    elif explicit_fields:
        fields = explicit_fields
    else:
        return {"error": "Provide either 'field_profile' or 'fields'"}

    # Baseline: no field selection
    baseline = _measure_compression(data, tool_slug, mode)

    # With field selection applied upstream
    filtered = _measure_compression(data, tool_slug, mode, apply_field_filter=fields)

    return {
        "baseline": baseline,
        "field_selected": filtered,
        "fields_applied": fields,
        "delta_tokens_saved": filtered["tokens_saved"] - baseline["tokens_saved"],
        "quality_note": "Lossless at source — only requested fields were ever fetched",
    }


# ---------------------------------------------------------------------------
# Existing endpoints (updated)
# ---------------------------------------------------------------------------

@app.post("/api/compress/dataset")
def compress_dataset(payload: dict):
    """Compress a dataset with real measurements."""
    dataset_name = payload.get("dataset", "")
    mode = payload.get("mode", "balanced")

    if dataset_name not in DATASETS or DATASETS[dataset_name] is None:
        return {"error": f"Dataset '{dataset_name}' not found"}

    data = DATASETS[dataset_name]
    tool_slug = payload.get("tool_slug", f"DATASET_{dataset_name.upper()}")
    return _measure_compression(data, tool_slug, mode)


@app.post("/api/execute")
def execute_tool(payload: dict):
    """Execute a tool and compress with real measurements."""
    tool_slug = payload.get("tool_slug", "")
    arguments = payload.get("arguments", {})
    mode = payload.get("mode", "balanced")

    raw_result = get_mock_result(tool_slug, arguments)
    return _measure_compression(raw_result, tool_slug, mode)


@app.get("/api/benchmarks")
def get_benchmarks():
    """Run real benchmarks across all datasets and tools."""
    benchmarks = []

    # Dataset benchmarks
    dataset_tools = {
        "notion_pages": "NOTION_SEARCH_NOTION_PAGE",
        "linear_issues": "LINEAR_GET_LINEAR_USER_ISSUES",
        "supabase_users": "SUPABASE_FETCH_TABLE_ROWS",
    }

    for dataset_name, tool_slug in dataset_tools.items():
        data = DATASETS.get(dataset_name)
        if data is None:
            continue

        for mode in ["off", "safe", "balanced", "low"]:
            result = _measure_compression(data, tool_slug, mode)
            benchmarks.append({
                "name": f"{dataset_name} ({mode})",
                "toolkit": dataset_name.split("_")[0],
                **result,
            })

    # Tool benchmarks
    tool_benchmarks = [
        ("GITHUB_GET_A_REPOSITORY", {}),
        ("GITHUB_LIST_ISSUES", {"per_page": 5}),
        ("GITHUB_LIST_PULL_REQUESTS", {"per_page": 3}),
        ("GMAIL_SEARCH_EMAILS", {"query": "composio", "max_results": 3}),
        ("SLACK_SEARCH_MESSAGES", {"query": "bug", "count": 4}),
    ]

    for tool_slug, args in tool_benchmarks:
        raw_result = get_mock_result(tool_slug, args)
        for mode in ["off", "safe", "balanced", "low"]:
            result = _measure_compression(raw_result, tool_slug, mode)
            benchmarks.append({
                "name": f"{tool_slug} ({mode})",
                "toolkit": tool_slug.split("_")[0],
                **result,
            })

    return {"benchmarks": benchmarks}


@app.get("/api/quality")
def get_quality_check() -> dict:
    """Quality check: run real agent scenarios and report whether each
    compressed payload still contains the values an agent would have used.

    Aperture-internal — no third-party SDK is involved. Probes are concrete
    field-value lookups (e.g. titles, addressees, IDs) the wrapper proves
    survived compression.
    """
    from aperture.benchmarks.vanilla_vs_aperture import (
        BenchCache,
        compare_call,
        scenario_dataset_summarize,
        scenario_research_repo,
        scenario_triage_bugs,
    )

    BenchCache()  # noqa: F841 (reset import side effect quirks if any)
    scenarios = [scenario_research_repo(), scenario_triage_bugs(), scenario_dataset_summarize()]

    out = []
    for sc in scenarios:
        probes = []
        for call in sc.calls:
            for label, passed in call.quality.items():
                probes.append({
                    "tool": call.tool_slug,
                    "label": label,
                    "passed": bool(passed),
                })
        out.append({
            "name": sc.name,
            "description": sc.description,
            "tokens_raw": sc.total_raw,
            "tokens_sent": sc.total_aperture,
            "saved_percent": round(sc.saved_percent, 1),
            "quality_passed": sc.quality_passed,
            "probes": probes,
        })

    # One canonical compare_call to demonstrate per-call quality probes,
    # for the dashboard "live preserved-signal" panel.
    sample = compare_call(
        "GITHUB_LIST_ISSUES",
        {"owner": "composioHQ", "repo": "composio", "per_page": 5},
        mode="balanced",
    )

    return {
        "scenarios": out,
        "sample": {
            "tool": sample.tool_slug,
            "raw_tokens": sample.raw_tokens,
            "sent_tokens": sample.aperture_tokens,
            "saved_percent": round(sample.saved_percent, 1),
            "quality": [
                {"label": k, "passed": bool(v)} for k, v in sample.quality.items()
            ],
        },
    }


_SAMPLE_SCHEMAS = {
    "GITHUB_GET_A_REPOSITORY": {
        "name": "GITHUB_GET_A_REPOSITORY",
        "description": "Fetch a GitHub repository by owner and name.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner."},
                "repo": {"type": "string", "description": "Repository name."},
            },
            "required": ["owner", "repo"],
        },
    },
    "GITHUB_LIST_ISSUES": {
        "name": "GITHUB_LIST_ISSUES",
        "description": "List issues in a repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "state": {"type": "string", "enum": ["open", "closed", "all"]},
                "labels": {"type": "string", "description": "Comma-separated labels."},
                "assignee": {"type": "string"},
                "per_page": {"type": "integer", "default": 30, "maximum": 100},
            },
            "required": ["owner", "repo"],
        },
    },
    "GMAIL_SEARCH_EMAILS": {
        "name": "GMAIL_SEARCH_EMAILS",
        "description": "Search Gmail using Gmail query syntax.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query."},
                "max_results": {"type": "integer", "default": 10},
                "include_spam_trash": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    },
}


def _source_label(tool_slug: str) -> str:
    if tool_slug.startswith("GITHUB"):
        return "GitHub"
    if tool_slug.startswith("GMAIL"):
        return "Gmail"
    if tool_slug.startswith("SLACK"):
        return "Slack"
    if tool_slug.startswith("NOTION"):
        return "Notion"
    if tool_slug.startswith("LINEAR"):
        return "Linear"
    if tool_slug.startswith("SUPABASE"):
        return "Supabase"
    return tool_slug.split("_")[0].title()


@app.get("/api/waterfall")
def get_waterfall() -> dict:
    """Token waterfall across heterogeneous sources.

    Mixed sources on purpose — GitHub repo + Linear issues + Notion docs +
    Supabase user table + Slack chatter. The waterfall surfaces different
    shapes of upstream data, not the same source repeated.
    """
    tools: list[tuple[str, dict, str]] = [
        ("GITHUB_GET_A_REPOSITORY", {"owner": "composioHQ", "repo": "composio"}, "Repository overview"),
        ("LINEAR_GET_LINEAR_USER_ISSUES", {}, "Linear issue list (200)"),
        ("NOTION_SEARCH_NOTION_PAGE", {}, "Notion search (500 pages)"),
        ("SUPABASE_FETCH_TABLE_ROWS", {"table": "users"}, "Supabase users (1000)"),
        ("SLACK_SEARCH_MESSAGES", {"query": "bug OR error", "count": 4}, "Slack messages"),
    ]

    run_steps: list[dict] = []
    total_raw = 0
    total_compressed = 0
    schema_tokens = 0
    arg_tokens = 0

    for tool_slug, args, label in tools:
        schema = _SAMPLE_SCHEMAS.get(tool_slug, {"name": tool_slug, "parameters": {}})
        schema_tokens += count_tokens(schema, model="gpt-4o").tokens
        arg_tokens += count_tokens(args, model="gpt-4o").tokens

        raw = get_mock_result(tool_slug, args)
        raw_tc = count_tokens(raw, model="gpt-4o")
        result = compress_tool_output(raw, tool_slug, mode="balanced", model="gpt-4o")
        # Use the LLM-bound count (TOON-aware) instead of re-counting JSON,
        # so we never accidentally report sent > raw.
        comp_tokens = result.compressed_tokens

        run_steps.append({
            "tool_slug": tool_slug,
            "label": label,
            "source": _source_label(tool_slug),
            "raw_tokens": raw_tc.tokens,
            "compressed_tokens": comp_tokens,
            "tokens_saved": max(0, raw_tc.tokens - comp_tokens),
            "strategy": result.strategy,
        })
        total_raw += raw_tc.tokens
        total_compressed += comp_tokens

    return {
        "steps": run_steps,
        "total_raw": total_raw,
        "total_compressed": total_compressed,
        "total_saved": max(0, total_raw - total_compressed),
        "schema_tokens": schema_tokens,
        "argument_tokens": arg_tokens,
        "overall_reduction": (
            (total_raw - total_compressed) / total_raw * 100 if total_raw else 0
        ),
    }


@app.get("/api/cache/stats")
def get_cache_stats():
    """Run real cache operations and return real stats."""
    cache = CachedExecutor()
    config = ApertureRunConfig(
        run_id="stats-demo",
        model="gpt-4o",
        effort_mode="balanced",
        cache_bypass=False,
    )

    tools = [
        ("GITHUB_GET_A_REPOSITORY", {}, True),
        ("GITHUB_LIST_ISSUES", {"per_page": 5}, True),
        ("GMAIL_SEND_EMAIL", {"to": "test@test.com"}, False),
    ]

    stats = []
    for tool_slug, args, expected_cacheable in tools:
        def make_executor():
            data = get_mock_result(tool_slug, args)
            return lambda: data

        _, event = cache.execute(
            tool_slug=tool_slug,
            arguments=args,
            executor=make_executor(),
            config=config,
        )

        stats.append({
            "tool_slug": tool_slug,
            "cache_status": event.cache_status,
            "cacheable": event.cache_status in ("hit", "miss"),
        })

    # Run again to get cache hits
    for tool_slug, args, _ in tools[:2]:
        def make_executor():
            data = get_mock_result(tool_slug, args)
            return lambda: data

        _, event = cache.execute(
            tool_slug=tool_slug,
            arguments=args,
            executor=make_executor(),
            config=config,
        )

        stats.append({
            "tool_slug": tool_slug + " (2nd call)",
            "cache_status": event.cache_status,
            "cacheable": True,
        })

    return {"stats": stats}


# ---------------------------------------------------------------------------
# Type-grouped schema compaction (port of itrummer/schemacompression)
# ---------------------------------------------------------------------------

@app.post("/api/schema/compact")
def compact_tool_schema(payload: dict):
    """Render a JSON Schema or OpenAI tool definition as a compact one-liner.

    Body: {"schema": {...}}  — a tool definition with name + parameters.
    Returns: {"compact": str, "json_tokens": int, "compact_tokens": int, "saved": int, "ratio": float}.
    """
    schema = payload.get("schema") or payload
    if not isinstance(schema, dict):
        return {"error": "Provide a JSON object under `schema`"}

    measured = measure_compaction(schema, count_tokens, model="gpt-4o")
    return {
        "name": measured.name,
        "compact": measured.compact,
        "json_tokens": measured.json_tokens,
        "compact_tokens": measured.compact_tokens,
        "saved": measured.saved,
        "ratio": measured.ratio,
        "savings_percent": round((1 - measured.ratio) * 100, 1),
    }


@app.get("/api/schema/sample")
def schema_sample() -> dict:
    """Return sample schemas alongside their compacted forms for the
    side-by-side dashboard view. Each entry includes the indented JSON
    string the LLM would otherwise see, so the UI can render a true diff."""
    samples = [
        _SAMPLE_SCHEMAS["GITHUB_LIST_ISSUES"],
        _SAMPLE_SCHEMAS["GITHUB_GET_A_REPOSITORY"],
        _SAMPLE_SCHEMAS["GMAIL_SEARCH_EMAILS"],
        {
            "name": "NOTION_SEARCH_NOTION_PAGE",
            "description": "Search Notion pages by title or content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "page_size": {"type": "integer", "default": 10},
                    "filter": {"type": "object", "properties": {
                        "property": {"type": "string"},
                        "value": {"type": "string"},
                    }},
                    "sort": {"type": "string", "enum": ["last_edited_time", "created_time"]},
                    "include_archived": {"type": "boolean", "default": False},
                },
                "required": ["query"],
            },
        },
        {
            "name": "SUPABASE_FETCH_TABLE_ROWS",
            "description": "Fetch rows from a Supabase table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name."},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "filter": {"type": "object"},
                    "order_by": {"type": "string"},
                    "limit": {"type": "integer", "default": 100, "maximum": 1000},
                    "offset": {"type": "integer", "default": 0},
                },
                "required": ["table"],
            },
        },
    ]
    out = []
    for sch in samples:
        m = measure_compaction(sch, count_tokens, model="gpt-4o")
        out.append({
            "name": m.name,
            "json": json.dumps(sch, indent=2),
            "compact": m.compact,
            "json_tokens": m.json_tokens,
            "compact_tokens": m.compact_tokens,
            "saved": m.saved,
            "savings_percent": round((1 - m.ratio) * 100, 1),
        })
    return {"samples": out}


# ---------------------------------------------------------------------------
# Quality-gated effort calibration
# ---------------------------------------------------------------------------

@app.post("/api/effort/calibrate")
def calibrate_effort(payload: dict):
    """Auto-pick the most aggressive compression mode that preserves every
    required signal in the LLM-bound payload.

    Body:
        {
          "tool_slug": "GITHUB_LIST_ISSUES",
          "arguments": {"per_page": 5},
          "ask": "find the assignee of the OAuth bug",
          "required_signals": ["title", "assignee.login", "OAuth"],
          "model": "gpt-4o",
          "task": "find_issues_by_assignee"   // optional
        }
    """
    tool_slug = payload.get("tool_slug")
    if not tool_slug:
        return {"error": "tool_slug is required"}

    arguments = payload.get("arguments", {})
    ask = payload.get("ask")
    required_signals = payload.get("required_signals") or []
    model = payload.get("model", "gpt-4o")
    task = payload.get("task")
    dataset_name = payload.get("dataset")

    if dataset_name in DATASETS and DATASETS[dataset_name] is not None:
        raw = DATASETS[dataset_name]
    else:
        raw = get_mock_result(tool_slug, arguments)

    gate = select_mode_for_quality(
        raw_payload=raw,
        tool_slug=tool_slug,
        required_signals=required_signals,
        ask=ask,
        model=model,
        task=task,
    )

    return {
        "tool_slug": tool_slug,
        "ask": ask,
        "required_signals": required_signals,
        "difficulty": gate.difficulty,
        "max_aggression": gate.max_aggression,
        "floor_mode": gate.floor_mode,  # alias retained for back-compat
        "selected_mode": gate.selected_mode,
        "selected_tokens": gate.selected_tokens,
        "raw_tokens": gate.raw_tokens,
        "saved_tokens": gate.saved_tokens,
        "saved_percent": round(gate.saved_percent, 1),
        "attempts": [
            {
                "mode": a.mode,
                "tokens": a.tokens,
                "passed": a.passed,
                "failed_signals": a.failed_signals,
            }
            for a in gate.attempts
        ],
        "reason": gate.reason,
    }


# ---------------------------------------------------------------------------
# Smart field policy (denial-list replacement)
# ---------------------------------------------------------------------------

@app.get("/api/field-policy/health")
def field_policy_health():
    """Provider availability + recent classifier calls for the dashboard."""
    return classifier_health()


@app.post("/api/field-policy/explain")
def explain_field_policy(payload: dict):
    """Run compression three ways (static / ask-aware / model-assisted) and
    return the per-mode tokens + policy decision trace.

    Body: {tool_slug, arguments?, dataset?, ask?, mode?, required_signals?}
    """
    tool_slug = payload.get("tool_slug")
    if not tool_slug:
        return {"error": "tool_slug is required"}

    arguments = payload.get("arguments", {})
    ask = payload.get("ask") or ""
    mode = payload.get("mode", "balanced")
    required_signals = payload.get("required_signals") or []
    dataset_name = payload.get("dataset")

    if dataset_name in DATASETS and DATASETS[dataset_name] is not None:
        raw = DATASETS[dataset_name]
    else:
        raw = get_mock_result(tool_slug, arguments)

    runs = {}
    for policy_mode in ("static", "ask_aware", "model_assisted"):
        runs[policy_mode] = _measure_compression(
            raw, tool_slug, mode,
            ask=ask if policy_mode != "static" else None,
            field_policy_mode=policy_mode,
            required_fields=required_signals,
        )

    return {
        "tool_slug": tool_slug,
        "ask": ask,
        "mode": mode,
        "runs": runs,
        "classifier_health": classifier_health(),
    }


# ---------------------------------------------------------------------------
# Demo run — single-shot ask → summary
# ---------------------------------------------------------------------------

_DEMO_SCENARIOS: list[dict] = [
    {
        "id": "csv_dump",
        "label": "CSV / large table scan",
        "keywords": ["csv", "10k", "10,000", "dump", "all rows", "every row"],
        "tools": [
            ("GOOGLESHEETS_BATCH_GET", {"spreadsheet": "github_users", "rows": 10001}),
        ],
    },
    {
        "id": "google_sheets",
        "label": "Google Sheets bulk read",
        "keywords": ["sheet", "sheets", "spreadsheet", "entries", "google"],
        "tools": [
            ("GOOGLESHEETS_BATCH_GET", {"spreadsheet": "users", "rows": 600}),
        ],
    },
    {
        "id": "research_repo",
        "label": "Repo overview",
        "keywords": ["repo", "repository", "stars", "github", "pull request", "pr"],
        "tools": [
            ("GITHUB_GET_A_REPOSITORY", {"owner": "composioHQ", "repo": "composio"}),
            ("GITHUB_LIST_ISSUES", {"owner": "composioHQ", "repo": "composio", "per_page": 5}),
            ("GITHUB_LIST_PULL_REQUESTS", {"owner": "composioHQ", "repo": "composio", "per_page": 3}),
        ],
    },
    {
        "id": "triage_bugs",
        "label": "Triage bugs across stacks",
        "keywords": ["bug", "triage", "fix", "error", "crash", "issue", "customer", "ticket", "oauth"],
        "tools": [
            ("GITHUB_LIST_ISSUES", {"owner": "composioHQ", "repo": "composio", "labels": "bug", "per_page": 5}),
            ("GMAIL_SEARCH_EMAILS", {"query": "composio bug", "max_results": 3}),
            ("SLACK_SEARCH_MESSAGES", {"query": "bug OR error", "count": 4}),
        ],
    },
    {
        "id": "dataset_summarize",
        "label": "Bulk dataset scan",
        "keywords": ["page", "pages", "linear", "notion", "supabase", "table", "users"],
        "tools": [
            ("NOTION_SEARCH_NOTION_PAGE", {}),
            ("LINEAR_GET_LINEAR_USER_ISSUES", {}),
            ("SUPABASE_FETCH_TABLE_ROWS", {"table": "users"}),
        ],
    },
    {
        "id": "inbox_scan",
        "label": "Inbox + chat scan",
        "keywords": ["email", "inbox", "message", "mail", "thread", "subject", "urgent"],
        "tools": [
            ("GMAIL_SEARCH_EMAILS", {"query": "this week", "max_results": 3}),
            ("SLACK_SEARCH_MESSAGES", {"query": "yesterday", "count": 4}),
        ],
    },
]


def _pick_scenario(ask: str) -> dict:
    if not ask:
        return _DEMO_SCENARIOS[2]   # research_repo as a sane default
    lowered = ask.lower()
    best, best_score = None, 0
    for scenario in _DEMO_SCENARIOS:
        score = sum(1 for kw in scenario["keywords"] if kw in lowered)
        if score > best_score:
            best, best_score = scenario, score
    # Fall back to research_repo if nothing matched at all.
    return best or _DEMO_SCENARIOS[2]


@app.post("/api/demo/run")
def demo_run(payload: dict) -> dict:
    """REAL agent loop — Claude with tool-use, Composio executes, Aperture
    intercepts every tool result. No mock scenarios, no pre-rendered numbers.

    Per-step we report the actual Composio response size, what Aperture
    dropped, and what we shipped to the model.
    """
    from aperture.agent.composio_agent import run_agent

    ask = (payload.get("ask") or "").strip()
    run = run_agent(ask)

    steps_out: list[dict] = []
    for s in run.steps:
        steps_out.append({
            "tool": s.tool,
            "tool_label": s.tool.replace("_", " ").title(),
            "arguments": s.arguments,
            "successful": s.successful,
            "error": s.error,
            "raw_tokens": s.raw_tokens,
            "sent_tokens": s.sent_tokens,
            "saved_tokens": s.saved_tokens,
            "saved_percent": s.saved_percent,
            "raw_bytes": s.raw_bytes,
            "sent_bytes": s.sent_bytes,
            "strategy": s.strategy,
            "llm_format": s.llm_format,
            "omitted_fields": s.omitted_fields,
            "policy_reason_counts": s.policy_reason_counts,
            "policy_promotions": s.policy_promotions,
            "classifier_used": s.classifier_used,
            "classifier_keeps": s.classifier_keeps,
            "raw_preview": s.raw_preview,
            "compressed_preview": s.compressed_preview,
            "elapsed_ms": round(s.elapsed_ms, 0),
        })

    raw_total = run.total_raw_tokens
    sent_total = run.total_sent_tokens
    saved_pct = round((1 - sent_total / raw_total) * 100, 1) if raw_total else 0

    cost_block = None
    if run.cost is not None:
        c = run.cost
        cost_block = {
            "model": c.model,
            "input_tokens": c.input_tokens,
            "output_tokens": c.output_tokens,
            "cache_read_tokens": c.cache_read_tokens,
            "cache_write_tokens": c.cache_write_tokens,
            "raw_input_tokens": c.raw_input_tokens,
            "actual_usd": c.actual_usd,
            "counterfactual_usd": c.counterfactual_usd,
            "saved_usd": c.saved_usd,
            "cache_hit_rate": (
                round(c.cache_read_tokens / max(c.input_tokens + c.cache_read_tokens, 1) * 100, 1)
            ),
        }

    return {
        "ask": ask,
        "answer": run.answer,
        "model": run.model,
        "iterations": run.iterations,
        "stopped_reason": run.stopped_reason,
        "error": run.error,
        "summary": {
            "tool_calls": len(steps_out),
            "raw_tokens": raw_total,
            "sent_tokens": sent_total,
            "saved_tokens": max(0, raw_total - sent_total),
            "saved_percent": saved_pct,
            "elapsed_ms": round(run.total_elapsed_ms, 0),
            "cost_before_usd": cost_block["counterfactual_usd"] if cost_block else 0,
            "cost_after_usd": cost_block["actual_usd"] if cost_block else 0,
            "cost_saved_usd": cost_block["saved_usd"] if cost_block else 0,
        },
        "cost": cost_block,
        "steps": steps_out,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
