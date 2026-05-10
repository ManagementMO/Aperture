# Aperture Benchmark Report

Deterministic fixture benchmark comparing raw Composio-style outputs against Aperture modes.

## Summary

| mode | tasks | raw_tokens | compressed_tokens | tokens_saved | compression_ratio | cache_hits | api_calls_avoided | schema_tokens_saved | success_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw | 20 | 4550 | 4550 | 0 | 1.000 | 0 | 0 | 0 | 0.650 |
| aperture_compressed | 20 | 4550 | 4223 | 636 | 0.928 | 0 | 0 | 0 | 0.750 |
| aperture_cached | 20 | 4550 | 4223 | 636 | 0.928 | 20 | 20 | 0 | 0.750 |
| aperture_full | 20 | 4550 | 4223 | 636 | 0.928 | 20 | 20 | 55 | 0.750 |

## Failure Cases

- `raw` / `github_005`: score=0.75
- `raw` / `gmail_004`: score=0.75
- `raw` / `mixed_003`: score=0.75
- `raw` / `slack_001`: score=0.75
- `raw` / `slack_002`: score=0.50
- `raw` / `slack_003`: score=0.50
- `raw` / `slack_004`: score=0.25
- `aperture_compressed` / `github_005`: score=0.75
- `aperture_compressed` / `gmail_004`: score=0.75
- `aperture_compressed` / `slack_002`: score=0.75
- `aperture_compressed` / `slack_003`: score=0.50
- `aperture_compressed` / `slack_004`: score=0.25
- `aperture_cached` / `github_005`: score=0.75
- `aperture_cached` / `gmail_004`: score=0.75
- `aperture_cached` / `slack_002`: score=0.75
- `aperture_cached` / `slack_003`: score=0.50
- `aperture_cached` / `slack_004`: score=0.25
- `aperture_full` / `github_005`: score=0.75
- `aperture_full` / `gmail_004`: score=0.75
- `aperture_full` / `slack_002`: score=0.75
- `aperture_full` / `slack_003`: score=0.50
- `aperture_full` / `slack_004`: score=0.25

## Recommendation

Use `balanced` compression with exact-match caching for profiled read tools. Keep raw references enabled.
