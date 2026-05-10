# Quava — Scope (do not drift)

Quava is the **token-efficiency layer between an agent and Composio**. We are
NOT a replacement for any Composio capability. Every tool call still goes
through Composio. We just make those calls cheaper, faster, and shorter.

If you're tempted to add code that *replaces* a Composio tool with a Quava
local equivalent, stop. That's drift.

---

## The three pillars (the only things we ship)

### 1. Cache — skip work that's already been done
* **Schema prompt cache** — Anthropic `cache_control: ephemeral` on the
  tools array + system prompt. After the first call within 5 min, schema
  reads cost ~10% of input price.
* **Tool-call cache** — keyed on `(slug, sorted_args, user_id)`,
  5-min TTL. **Composio is NOT billed** when Claude asks for the same
  `(slug, args)` twice. Write-class slugs (`SEND/CREATE/...`) bypass.
* **Result cache** — keyed on `(ask, model, effort_mode)`, 5-min TTL.
  Identical re-asks return in <1 ms with $0.000000 cost. No Claude call,
  no Composio call.

### 2. Tokenization-aware compression
* **Compact JSON** — `(",", ":")` separators, no whitespace tokens.
* **TOON tabular encoding** — when a payload is a list of homogenous
  dicts (or wraps one in `{result: [...]}`), we declare the keys once
  in a header and emit each row as a comma-separated tuple. ~80–90%
  smaller than JSON for tabular data.
* **Ultra-summary headline** — for known shapes (GitHub repo, Linear
  issue list, Gmail messages, table rows), prepend a 17–25 token
  symbol-encoded summary so the model can answer single-fact questions
  without parsing the body. Strictly additive.
* **Context-overflow triage** — pre-flight estimate of the messages
  array; if approaching 200k, replace the oldest tool_result blocks
  with size-summary placeholders so we never hit Anthropic's hard cap.

### 3. Schema control — what reaches the prompt
* **Field-policy denial list** — drop bookkeeping fields the agent
  doesn't reason over (URLs, `composio_execution_message`, sub-resource
  links, internal IDs that aren't referenced).
* **Ask-aware promotion** — if the user asks for a field by name in the
  ask, promote it back into keeps for that call.
* **Model-assisted classifier** — Llama-3.1-8B via Groq scores
  candidate fields against the ask. **Asymmetric trust**: classifier
  can only ADD names to the keep set, never remove.
* **3-tier degradation marker** — `full / degraded / passthrough`.
  Passthrough fires when compression itself raised; degraded fires
  when we fell back to a lighter mode. The agent never reads a
  silently-corrupted payload.

---

## Not in scope (do not build)

* **Workbench / sandbox / scratchpad for the agent.** That's Composio's
  `COMPOSIO_REMOTE_WORKBENCH`. If the agent calls Workbench, we
  compress its *response* on the way back like any other tool — we do
  not replace it with a Quava-side eval.
* **Tool execution.** We never run a tool ourselves. Every
  `client.tools.execute(...)` goes to Composio.
* **Tool discovery.** We curate a slug allowlist per toolkit but we
  don't implement search or registry.
* **Auth flows.** Composio's `MANAGE_CONNECTIONS` owns OAuth.
* **Bash / remote code.** Composio's `REMOTE_BASH_TOOL` owns it.

If the agent ever asks "did Quava do this, or did Composio?" — Composio
did it. Quava made the round trip cheaper.

---

## How we benefit Composio (not just users)

Every call we make goes through `composio.tools.execute(...)`. We do not
re-implement any tool. The cache-hit path is the only place Composio
isn't billed, and that's a feature *for the user* — Composio doesn't
lose a real call there because the user would have run it anyway and
gotten the same result. By making every call cheaper for the model that
reads it, we make Composio's product more attractive: an agent built on
Composio + Quava costs less to operate than one built on Composio
alone, which keeps the user on Composio longer.

The redundancy we strip (every key repeated per row, sub-resource URLs
the agent never follows, `null` bookkeeping fields, whitespace tokens)
is redundancy that Composio ships out of the box because they're
optimizing for *correctness*, not for token-efficiency on the model
side. We're the layer that takes their correct output and tunes it for
the model that's about to read it. The user's bill goes down. Composio
keeps every dollar of execution revenue.
