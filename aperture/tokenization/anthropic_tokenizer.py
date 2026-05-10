"""Real Anthropic tokenizer behind an opt-in env flag.

The salvage branch's `token_counter.py` previously fell back to a chars/4
heuristic for every Claude model and silently marked it `approximate=True`.
This module wires the actual `client.messages.count_tokens(...)` API so that
when `APERTURE_USE_ANTHROPIC_TOKENIZER=true` is set, Claude tokenizations
become real and `approximate=False`.

The flag is **opt-in**, not on by default, for privacy reasons (handoff
decision #5): every payload sent through `count_tokens()` leaves the
process for Anthropic's servers, including when the user's actual LLM
provider is OpenAI or anything other than Anthropic. Defaulting that on
would silently exfiltrate tool outputs to Anthropic regardless of provider.

Failure modes are silent. If `ANTHROPIC_API_KEY` is missing, the API call
times out, or the API returns an error, this module returns `None` and the
caller falls back to the cl100k approximation. Compression and benchmark
runs MUST never fail or stall because Anthropic's tokenizer endpoint had a
bad day.

Caching: because this module hits the network, callers should cache results
by `(model, sha256(serialized_payload))` in Redis with a long TTL. The
caching itself lives in `aperture/proxy/tokenize.py` (Phase 3); this module
is a thin synchronous wrapper that's easy to test.
"""

from __future__ import annotations

import os

from aperture.tokenization.serializers import stable_serialize_payload


def is_enabled() -> bool:
    """Return True if `APERTURE_USE_ANTHROPIC_TOKENIZER` is set to a truthy value."""

    value = os.getenv("APERTURE_USE_ANTHROPIC_TOKENIZER", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def count_anthropic_tokens(payload: object, model: str) -> int | None:
    """Return real Claude input-token count for `payload` under `model`.

    Returns:
        - int: precise token count from Anthropic's `messages.count_tokens` API.
        - None: env flag disabled, or API key missing, or call failed. Caller
          must fall back (cl100k approximation in token_counter.py).
    """

    if not is_enabled():
        return None
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic()
        text = payload if isinstance(payload, str) else stable_serialize_payload(payload)
        resp = client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": text}],
        )
        return int(getattr(resp, "input_tokens", 0)) or None
    except Exception:
        # Silent fallback — never fail the caller's hot path.
        return None
