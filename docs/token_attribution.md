# Token Attribution

Token attribution uses stable JSON serialization, a model-aware tokenizer
registry, and a fallback approximate counter. Events record token counts,
payload byte counts, tool/session metadata, and savings. Raw payloads are not
stored in token events by default.

Primary modules:

- `aperture.tokenization`
- `aperture.observability`

