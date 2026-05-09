# Aperture Benchmark Report

Deterministic fixture benchmark comparing raw Composio-style outputs against Aperture modes.

## Summary

| mode | tasks | raw_tokens | compressed_tokens | tokens_saved | compression_ratio | cache_hits | api_calls_avoided | schema_tokens_saved | success_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw | 5 | 1242 | 1242 | 0 | 1.000 | 0 | 0 | 0 | 0.800 |
| aperture_compressed | 5 | 1242 | 1069 | 212 | 0.861 | 0 | 0 | 0 | 1.000 |
| aperture_cached | 5 | 1242 | 1069 | 212 | 0.861 | 5 | 5 | 0 | 1.000 |
| aperture_full | 5 | 1242 | 1069 | 212 | 0.861 | 5 | 5 | 20 | 1.000 |
| shadow | 5 | 1242 | 1242 | 0 | 1.000 | 0 | 0 | 0 | 0.800 |

## Failure Cases

- `raw` / `slack_001`: score=0.75
- `shadow` / `slack_001`: score=0.75

## Recommendation

Use `balanced` compression with exact-match caching for profiled read tools. Keep raw references enabled.
