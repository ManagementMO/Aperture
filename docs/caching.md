# Caching

Aperture caching is exact-match only. Policies are deny-by-default and require a
read operation, TTL, exact matching, and a valid privacy scope. Writes, auth
flows, failed responses, and missing private scope identifiers are not cached.

Cache events log key hashes, not raw keys.

