# NIKOS.md

## Important Feedback from Nikos — Aperture Project Direction

This document summarizes key feedback from Nikos at Composio about the Aperture project. The purpose is to preserve the project-shaping insight from the conversation and make it easy for coding agents, teammates, and reviewers to understand why the project direction evolved.

---

## Context

We originally described Aperture as an infrastructure project focused on three main ideas:

1. **Measure token cost** from Composio tool/meta-tool responses.
2. **Cache repeated tool calls** to reduce waste.
3. **Optimize tool schemas** to make tool definitions cheaper for models to read.

Nikos said the **token cost idea is interesting**, but pushed us toward a stronger and more practical angle:

> Build something between Composio tool outputs and what the model sees, where verbose outputs are compressed/optimized before entering model context.

This feedback changed the project from primarily “token measurement + caching + schema optimization” into a more focused project around **schema-aware tool output compression**, while still retaining the original three features.

---

## Core Feedback

Nikos suggested that tool outputs themselves may be a major source of token waste.

For example, if an agent calls a tool like:

- `GITHUB_LIST_REPOS`
- `GITHUB_LIST_ISSUES`
- `GMAIL_SEARCH_EMAILS`
- `SLACK_SEARCH_MESSAGES`
- `NOTION_QUERY_DATABASE`

the returned output may contain many verbose or repeated fields that the model does not actually need.

Examples of wasteful output fields:

- API URLs
- avatar URLs
- repeated parent objects
- nested user objects
- empty/null fields
- internal IDs
- raw metadata
- verbose markdown bodies
- duplicate objects
- pagination or bookkeeping fields

Nikos’ suggestion was to compress these outputs before they hit the model.

---

## Updated Main Project Idea

The strongest version of Aperture is now:

> **Aperture is a schema-aware tool output compression layer for Composio agents. It measures raw tool-output token cost, compresses verbose outputs before they reach the model, and benchmarks token savings against task-performance degradation.**

This means Aperture should not only make schemas cheaper. It should also transform large tool results into compact, model-useful representations.

Example:

### Raw tool output

```json
{
  "id": 123,
  "node_id": "I_kwDOExample",
  "url": "https://api.github.com/repos/acme/app/issues/42",
  "repository_url": "https://api.github.com/repos/acme/app",
  "labels_url": "https://api.github.com/repos/acme/app/issues/42/labels{/name}",
  "comments_url": "https://api.github.com/repos/acme/app/issues/42/comments",
  "html_url": "https://github.com/acme/app/issues/42",
  "title": "Login fails after OAuth redirect",
  "body": "Very long markdown body...",
  "user": {
    "login": "nikos",
    "avatar_url": "https://avatars.githubusercontent.com/u/999",
    "followers_url": "...",
    "repos_url": "..."
  },
  "labels": [
    {
      "id": 1,
      "name": "bug",
      "color": "d73a4a",
      "url": "..."
    }
  ]
}
```

### Compressed model-facing output

```json
{
  "number": 42,
  "title": "Login fails after OAuth redirect",
  "state": "open",
  "author": "nikos",
  "labels": ["bug"],
  "summary": "OAuth login redirects but user remains unauthenticated.",
  "url": "https://github.com/acme/app/issues/42"
}
```

The goal is not to delete useful information. The goal is to remove noise while preserving what the model needs to complete the task.

---

## Nikos’ Key Evaluation Advice

Nikos emphasized that the project needs proof, not just a clever idea.

The benchmark should answer two questions:

1. **How many tokens are saved?**
2. **Does agent performance degrade?**

The recommended evaluation:

> Run the same set of tasks with raw tool outputs and with compressed tool outputs, then compare token savings and task success.

A strong benchmark could include around 100 tasks across common toolkits such as:

- GitHub
- Gmail
- Slack
- Notion
- Calendar
- mixed multi-tool workflows

Metrics to track:

- raw output tokens
- compressed output tokens
- tokens saved
- compression ratio
- task success rate
- final answer quality
- tool selection accuracy
- parameter accuracy
- extra turns caused by compression
- how often the agent needs to fetch raw details again

This benchmark is central because reviewers will immediately ask:

> “Did this save tokens, and did it hurt performance?”

---

## Important Workbench Warning

Nikos also warned to be careful about **Workbench**.

Composio Workbench already helps with large outputs by giving agents a place to store/process data outside normal model context.

So Aperture must be clearly different.

The distinction:

> **Workbench stores or processes large outputs outside the model. Aperture optimizes the compact version of the output that the model actually sees.**

They can work together:

```text
Raw tool output
    ↓
Store full raw output in Workbench/object store if needed
    ↓
Aperture creates compressed model-facing payload
    ↓
Model sees compact result
    ↓
Model can request raw details later if necessary
```

This prevents Aperture from looking like it duplicates Workbench.

---

## Final Updated Feature Set

The original three features are still included, but the priority changed.

### 1. Token Cost Measurement

Still core.

Aperture measures:

- raw output tokens
- compressed output tokens
- tokens saved
- compression ratio
- token cost by tool
- token cost by session
- token cost by toolkit
- token cost from meta-tool/schema responses

This gives the proof layer for the whole project.

---

### 2. Tool Output Compression

Now the main feature.

Aperture compresses verbose tool outputs before they hit the model using:

- field pruning
- null/empty field removal
- nested object flattening
- list compaction
- duplicate removal
- long-text summarization
- raw output references
- schema-aware compression profiles

This helps even on the first tool call.

---

### 3. Tool-Calling Cache

Still included, but secondary.

Caching helps when the same safe read-only tool call repeats.

Aperture should use exact-match caching only for MVP:

```text
same tool + same normalized params + same user/account/project scope = cache hit
```

Never cache:

- writes
- sends
- creates
- deletes
- auth flows
- unsafe private cross-user data

Caching reduces repeated API calls, latency, and repeated output cost.

---

### 4. Schema Optimization

Still included, but secondary.

Aperture can still optimize tool descriptions and parameter descriptions, but this is no longer the main centerpiece.

Schema optimization reduces the cost of tool discovery/schema exposure.

Output compression reduces the cost of tool results.

Both are useful, but output compression is the stronger project story.

---

## New Priority Order

Recommended project priority:

1. **Token attribution**
2. **Tool output compression**
3. **Semantic benchmark suite**
4. **Safe repeated-call caching**
5. **Schema optimization**

This gives the clearest story:

> Measure the cost → compress the output → prove the savings → show performance does not meaningfully degrade → add caching/schema optimization as extra efficiency layers.

---

## Why This Feedback Matters

Nikos’ feedback makes the project stronger because it identifies a more direct token-waste surface than schemas alone.

Schemas are important, but tool outputs can be much larger and more repetitive.

The new version of Aperture is more compelling because it can show concrete before/after examples:

- raw GitHub issue output vs compressed output
- raw Gmail thread output vs compressed output
- raw Slack search results vs compressed output
- raw Notion database query vs compressed output

And it can quantify:

- tokens saved
- compression ratio
- performance impact
- failure cases

This makes the project more defensible to engineers and judges.

---

## Final Takeaway

Nikos’ feedback should be treated as important project guidance.

The best current framing is:

> **Aperture is a schema-aware output compression and token-efficiency layer for Composio agents. It reduces verbose tool outputs before they reach the model, measures token savings, preserves access to raw outputs, and benchmarks whether agent performance remains strong.**

The original three ideas remain in the project, but the main centerpiece is now **tool output compression + token measurement + benchmark proof**.
