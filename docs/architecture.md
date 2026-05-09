# Aperture Architecture

Aperture wraps Composio tool execution so verbose outputs can be measured,
cached safely, compressed, and benchmarked before they enter model context.

```text
tool request
  -> cache policy/key/store
  -> live or fixture execution
  -> raw token count
  -> compression profile
  -> raw reference store
  -> compressed envelope
  -> token/cache events
```

The package is fixture-first for deterministic tests and benchmarks, with a
thin Composio SDK adapter for live direct execution when credentials exist.

