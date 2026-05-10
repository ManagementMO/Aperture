# Schema Description Optimization (Component C)

Pipeline that rewrites tool description fields to fewer tokens without
changing what the schema conveys to the LLM. Output is an overlay JSON
file (`aperture/schema_optimizer/_overlay.json`) that the proxy applies
to outbound `tools/list`, `COMPOSIO_GET_TOOL_SCHEMAS`, and `COMPOSIO_SEARCH_TOOLS`
responses.

## What can be rewritten

- Tool description text
- Parameter description text
- Enum description text
- Verbose / repeated phrasing in any of the above

## What is NEVER rewritten

The validator rejects any candidate that touches:
- Tool slug or name
- Parameter names
- Required fields list
- Parameter types
- Safety/auth keywords (`delete | send | auth | oauth | token | permission | private | public`)

These are structural invariants. A rewrite that strips them is auto-rejected
by `aperture/schema_optimizer/validator.py:validate_schema_rewrite`.

The overlay writer is a positive list, not a deny list: it accepts only
tools classified as `operation_type: read` in `policy.yaml`. `write`,
`auth`, AND `unknown` operation types are all rejected. This prevents a
write tool that hasn't been explicitly classified yet from sneaking in.

The minimum LLM-judged validation case count is `MIN_OVERLAY_VALIDATION_CASES`
in `aperture/schema_optimizer/reports.py` (currently `50`, matching the
handoff §6.4 plan-spec target). The prompt fixtures in
`aperture/schema_optimizer/prompts/*.jsonl` ship at least 50 per toolkit:
github=50, gmail=50, linear=60, notion=50, slack=50.

The proxy SchemaOverlay loader (`aperture/proxy/overlay.py`) applies the
same `read`-only filter at startup. So even if a hand-edit puts a write
tool in `_overlay.json`, the proxy refuses to substitute it.

## Pipeline

```
fetch_schemas.fetch_tool_schemas(live=False)
  → load fixtures or pull live from Composio SDK
extract_fields.extract_description_fields(schema)
  → flat list of (tool_slug, field_path, text) records
tokenize_schemas.tokenize_schema_fields(fields)
  → per-field token count (tiktoken)
rank_candidates.rank_schema_candidates(token_counts)
  → sorted desc by token_count × frequency_prior
rewrite_rules.generate_schema_rewrite_candidates(field)
  → list of up to 3 candidates [light, medium, heavy]
validator.validate_schema_rewrite(orig, candidate)
  → structural check (params/types/required/safety) — fast pre-filter
llm_judge.run_judge(orig, candidate, prompts, ...)
  → Haiku + Sonnet spot-check — accepts only if 100% prompt agreement
reports.write_schema_optimization_report(out_path)
  → reports/schema_optimization_report.md
reports.write_overlay(out_path, results)
  → aperture/schema_optimizer/_overlay.json
```

## Rewrite rules

Three compression levels (`aperture/schema_optimizer/rewrite_rules.py`):

- **Light** — strip preambles ("Creates a new" → "Create"), drop
  redundant type prose ("a string containing the" → ""). Safest;
  preserves disambiguation.
- **Medium** — light + collapse "You must provide…" / "Optionally, you
  may include…" into "Required: ... Optional: ...".
- **Heavy** — medium + multi-token compound shortenings ("repository" →
  "repo", "authenticated user" → "user").

Candidates run through the structural validator first (fast, free) and
then through the LLM judge (real, paid).

## LLM judge

`aperture/schema_optimizer/llm_judge.py:run_judge(...)`

Two-stage:
1. **Haiku judges every prompt × {original, candidate}.** For each prompt,
   Anthropic Haiku is given the schema (plus optional `similar_tools` for
   disambiguation) and asked to use it. The judge compares
   `tool_use.name` and `normalize_args(tool_use.input)` between original
   and candidate. Disagreement on either → reject the candidate.
2. **Sonnet spot-checks 10% of accepted prompts.** For each prompt
   selected by `random.Random(seed).sample(...)`, run Sonnet with the
   same schema variants and compare. If Sonnet disagrees, reject — even
   when Haiku said yes. Mitigates Plan-Agent 3 risk-#2 (Haiku
   false-positive accepts).

`normalize_args()` recursively sorts dict keys and drops None values, so
"{a:1, b:None}" and "{a:1}" compare equal across runs.

## Budget tracking

`aperture/schema_optimizer/budget.py:BudgetTracker` (cap default $50).

Records `usage` from every Anthropic call (input_tokens, output_tokens,
cache_read 0.10×, cache_write 1.25×). When `total_usd >= cap_usd`,
the validator loop aborts gracefully (returns `ValidationResult` with
`rejection_reason="budget_exhausted"`).

Per-call USD computed from the published per-model rates:
- Haiku 4.5: $1/$5 per 1M (in/out)
- Sonnet 4.5/4.6: $3/$15 per 1M
- Opus 4.7: $15/$75 per 1M
- Default: $3/$15 per 1M

## Replay mode (CI)

Per handoff §14.4, NO live LLM in CI. Tests use replay-recorded outcomes:

```python
run_judge(
    original_schema=...,
    candidate_schema=...,
    prompts=[...],
    live=False,                   # required for tests
    replay_dir=Path("tests/schema_optimizer/replay"),
)
```

Outcomes are stored as JSON files keyed by `sha256(model::tool_slug::candN::pM)[:16].json`.
First-time recordings: run with `live=True, replay_dir=<dir>`; subsequent
runs replay from disk.

## Overlay JSON

Schema (`aperture/schema_optimizer/_overlay.json`):

```json
{
  "version": 1,
  "aperture_optimizer_version": "0.3.0",
  "generated_at": "2026-05-09T16:00:00Z",
  "tools": {
    "GITHUB_LIST_REPOSITORY_ISSUES": {
      "description": {
        "original": "Creates a new issue in a specified GitHub repository...",
        "optimized": "Create a GitHub issue. Required: owner, repo, title.",
        "original_tokens": 68,
        "optimized_tokens": 28,
        "reduction_tokens": 40,
        "reduction_pct": 0.59,
        "validation": {"cases_run": 50, "passed": true},
        "aperture_optimized": true,
        "aperture_optimizer_version": "0.3.0"
      }
    }
  },
  "stats": {
    "total_results": 100,
    "accepted": 25,
    "rejected": 75,
    "total_tokens_saved": 1024
  }
}
```

The proxy reads this on startup and substitutes `optimized` text
into the relevant schema responses before forwarding to the LLM. Tools
not in the overlay pass through unchanged.

## Running

```bash
# Generate a structural-only report from fixtures. Fast and free, but yields
# no overlay entries because write_overlay's safety filters require LLM-judged
# cases (MIN_OVERLAY_VALIDATION_CASES=25) AND operation_type=read.
uv run python -c "
from pathlib import Path
from aperture.schema_optimizer.reports import optimize_schemas, write_overlay
write_overlay(Path('aperture/schema_optimizer/_overlay.json'), optimize_schemas())
"

# Generate a live LLM-judged overlay (paid). The Haiku judge runs every prompt
# against original and candidate schemas; Sonnet spot-checks a fraction of
# accepted prompts. BudgetTracker aborts mid-run when the cap is hit.
ANTHROPIC_API_KEY=... uv run python -c "
from pathlib import Path
from aperture.schema_optimizer.budget import BudgetTracker
from aperture.schema_optimizer.reports import (
    optimize_schemas_with_llm_judge,
    write_overlay,
)
tracker = BudgetTracker(cap_usd=2.0)
results = optimize_schemas_with_llm_judge(
    live=True,
    tracker=tracker,
    max_candidates=15,
    spot_check_fraction=0.10,
)
print('budget:', tracker.summary())
write_overlay(Path('aperture/schema_optimizer/_overlay.json'), results)
"
```

`optimize_schemas_with_llm_judge` is the canonical entry point for shipping
a real overlay. Internally:

1. Run the deterministic ranking pipeline (top-N candidates by tokens × frequency).
2. Apply the structural validator as a fast pre-filter.
3. For each surviving candidate, dispatch
   `validate_schema_rewrite_with_llm_judge` with the toolkit's prompts (loaded
   from `aperture/schema_optimizer/prompts/*.jsonl` by default).
4. Record the judge's `cases_run` in the result so `write_overlay` can
   gate on `>= MIN_OVERLAY_VALIDATION_CASES` and `operation_type == "read"`.

`optimize_schemas()` (structural-only) is preserved as a free dry-run
diagnostic and exists to populate the `reports/schema_optimization_baseline.md`
report — it is **not** the path that writes a shippable overlay.

## Verifying

```bash
uv run pytest tests/schema_optimizer/   # 36 tests
```

Tests cover: structural validation, rewrite-rule output, candidate ranking,
fixture fetching, budget tracker (7 tests including dict/None usage and
cache discount), LLM judge replay (10 tests including accept/reject paths),
overlay writer (5 tests).
