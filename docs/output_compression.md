# Output Compression

Compression is profile-driven and deterministic by default. Supported modes are
`off`, `shadow`, `safe`, and `balanced`. Balanced mode adds flattening, list
compaction, configured deduplication, and deterministic long-text compression.

Every compressed payload includes an `aperture_compressed` marker, compression
metrics, omitted fields, and a raw reference when raw storage is enabled.

