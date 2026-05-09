# APERTURE_DEMO_AGENT.md

## Aperture Command Center  
### Engineering Triage & Release Intelligence Agent

---

## 1. One-Sentence Summary

**Aperture Command Center** is an engineering triage and release intelligence agent that uses Composio tools to inspect GitHub, Slack, Notion, Gmail, and Calendar, then produces a clean project/release report — while serving as the perfect benchmark and visual demo for how much better agents operate with Aperture enabled.

---

## 2. Why This Agent Is the Perfect Aperture Demo

Aperture is designed to reduce token waste from:

1. Large verbose tool outputs
2. Repeated tool calls
3. Expensive tool/meta-tool responses
4. Bloated schemas and noisy API payloads

An engineering triage agent naturally stresses all of those.

It has to read:

- GitHub issues
- GitHub PRs
- issue comments
- Slack threads
- Notion project docs
- Gmail escalation emails
- Calendar/release meetings

These sources produce large, nested, noisy outputs with lots of irrelevant metadata.

That makes this agent a perfect before/after comparison:

```text
Composio only
vs.
Composio + Aperture
```

The same task can be run both ways, and we can show:

- tokens saved
- compression ratio
- cache hits
- API calls avoided
- latency difference
- task success rate
- output quality comparison

---

## 3. Core Agent Concept

The agent acts like an AI engineering operations assistant.

A user can ask:

> “Analyze the current OAuth release. Check GitHub issues/PRs, Slack discussions, Notion docs, and relevant emails. Tell me blockers, risks, owners, duplicate issues, and what we should do next.”

The agent then investigates across connected tools and returns a structured release intelligence report.

---

## 4. What the Agent Does

The agent should be able to:

1. Search GitHub issues related to a feature, bug, release, or repo.
2. Search GitHub PRs and identify risky or blocked PRs.
3. Read issue/PR comments and summarize technical context.
4. Search Slack discussions for decisions, blockers, and owners.
5. Read Notion project pages, launch docs, or roadmap docs.
6. Search Gmail for customer escalations or internal update emails.
7. Check Calendar for relevant release/project meetings.
8. Cluster duplicate or related issues.
9. Identify owners and unresolved blockers.
10. Produce a release readiness report.
11. Optionally create follow-up GitHub issues, draft emails, or write a Notion update.

---

## 5. MVP Version

The MVP should start smaller and sharper:

# GitHub + Slack Engineering Triage Agent

MVP task:

> “Given a repo and a topic, find related GitHub issues/PRs and Slack discussions, summarize the situation, identify blockers, group duplicates, assign likely owners, and create an action plan.”

This is enough to demonstrate Aperture clearly because GitHub and Slack outputs are already large and noisy.

### MVP Toolkits

- GitHub
- Slack

### MVP Agent Capabilities

- Search issues by topic
- Search PRs by topic
- Read comments
- Search Slack messages
- Summarize related discussions
- Group duplicate issues
- Identify blockers
- Identify owners
- Generate action plan

---

## 6. Expanded Version

After the MVP works, expand to:

- Notion project docs
- Gmail customer/internal escalations
- Google Calendar release meetings
- Jira/Linear if available
- GitHub Actions/build status
- Incident management tools if available

Expanded agent prompt:

> “We are preparing to ship the OAuth login fix. Review GitHub, Slack, Notion, Gmail, and Calendar. Tell me whether we are ready to ship, what is blocked, what risks remain, who owns each item, and what actions should happen next.”

---

## 7. Why This Agent Is Useful on Its Own

This should not feel like a fake benchmark agent. It should be genuinely useful.

Engineering and product teams constantly need answers like:

- What are the top blockers this week?
- Which GitHub issues are duplicates?
- Which PRs are risky?
- What did the team decide in Slack?
- Which customer escalations relate to this bug?
- Who owns each issue?
- Are we ready to ship?
- What needs to happen next?
- What should go into the release update?

This agent can become a real engineering/productivity tool independent of Aperture.

Aperture makes it cheaper, faster, and cleaner.

---

## 8. How It Showcases Aperture

| Aperture Feature | How the Agent Demonstrates It |
|---|---|
| Token cost measurement | Shows raw token cost from GitHub, Slack, Notion, Gmail, and Calendar outputs. |
| Tool output compression | Compresses huge nested outputs before they hit the model. |
| Tool-call caching | Reuses repeated reads like repo metadata, issue lists, PR lists, and Slack searches. |
| Schema optimization | Reduces cost when many tools/schemas are exposed or fetched. |
| Benchmarking | Runs the same tasks with raw outputs vs Aperture-compressed outputs. |
| Workbench compatibility | Stores raw outputs while showing compact model-facing summaries. |

---

## 9. Demo Flow

### Demo Setup

Use a project/release scenario:

> “OAuth login release readiness”

The agent is asked to investigate whether the team is ready to ship.

### Demo Prompt

```text
We are shipping the OAuth login fix. Check GitHub issues and PRs, search Slack for related auth discussions, identify open blockers, summarize decisions, find duplicate issues, identify owners, and produce a release readiness report.
```

### Mode A — Composio Only

The model receives raw tool outputs:

- full GitHub issue objects
- nested user objects
- API URLs
- labels metadata
- PR metadata
- long comments
- Slack message metadata
- repeated user/channel fields

The dashboard shows:

```text
Raw output tokens: high
Tool calls: normal
API calls: normal
Final report: produced
```

### Mode B — Composio + Aperture

The model receives compressed tool outputs:

- compact issue objects
- compact PR summaries
- flattened author fields
- labels as simple arrays
- summarized comments
- Slack threads summarized by decision/blocker/owner
- raw output references preserved

The dashboard shows:

```text
Raw tokens: 82,400
Compressed tokens: 19,600
Tokens saved: 62,800
Reduction: 76%
Cache hits: 14
API calls avoided: 9
Task success: same or near-same
Extra tool calls: 0–low
```

The exact numbers will come from benchmark measurements.

---

## 10. Visual Dashboard Idea

The demo should be visually strong.

### Dashboard Layout

```text
┌────────────────────────────────────────────┐
│ Aperture Command Center                    │
│ Engineering Triage & Release Intelligence  │
└────────────────────────────────────────────┘

[ Toggle: Composio Only | Composio + Aperture ]

┌───────────────────────┬───────────────────────┐
│ Release Report         │ Aperture Metrics       │
│                       │                       │
│ Status: Yellow         │ Raw tokens: 82,400     │
│ Top blockers           │ Compressed: 19,600     │
│ Risk score             │ Saved: 62,800          │
│ Owners                 │ Reduction: 76%         │
│ Next actions           │ Cache hits: 14         │
│                       │ API calls avoided: 9   │
└───────────────────────┴───────────────────────┘

┌────────────────────────────────────────────┐
│ Raw vs Compressed Output Example           │
│ GitHub issue object: 3,200 → 420 tokens     │
└────────────────────────────────────────────┘
```

### Visual Sections

1. **Release Status**
   - Green / Yellow / Red
   - readiness score
   - risk score

2. **Blockers**
   - title
   - source
   - owner
   - severity

3. **Issue Clusters**
   - duplicate/related bugs grouped together

4. **Slack Decisions**
   - decision
   - who said it
   - timestamp/source link

5. **Aperture Metrics**
   - raw tokens
   - compressed tokens
   - tokens saved
   - compression ratio
   - cache hits
   - API calls avoided

6. **Raw vs Compressed Inspector**
   - side-by-side JSON preview
   - fields removed
   - fields preserved
   - raw reference ID

---

## 11. Example Final Agent Output

```md
# OAuth Release Readiness Report

## Status

**Yellow — almost ready, but one blocker remains.**

## Main Blocker

Session cookies are not consistently persisted after OAuth redirect, especially on Safari and mobile browsers.

## Related GitHub Issues

1. **#42 — Login fails after OAuth redirect**
   - State: open
   - Labels: bug, auth
   - Owner: Nikos
   - Summary: OAuth redirect succeeds, but user remains unauthenticated.

2. **#57 — Users logged out after callback**
   - State: open
   - Labels: bug
   - Owner: Backend team
   - Summary: Session state appears lost after callback domain transition.

3. **#61 — Safari OAuth cookie issue**
   - State: open
   - Labels: browser, auth
   - Owner: QA
   - Summary: Safari blocks cookie under current SameSite settings.

## Related Pull Requests

1. **PR #88 — Patch OAuth callback cookie settings**
   - Status: waiting for QA
   - Risk: medium
   - Needed action: test Safari/mobile flows before merge.

## Slack Decisions

- Nikos suggested testing `SameSite=None` on staging.
- Backend team suspects callback domain mismatch is the root cause.
- QA requested a regression pass on Safari and Chrome mobile.

## Risk Assessment

**Risk level: Medium-high**

The release should not ship until the Safari/mobile OAuth flow passes regression testing.

## Owners

| Area | Owner |
|---|---|
| Backend OAuth callback | Nikos |
| Frontend login flow | Sarah |
| QA regression | Alex |
| Customer update | Mohammed |

## Recommended Next Actions

1. Patch callback cookie settings in PR #88.
2. Run Safari/mobile OAuth regression suite.
3. Verify callback domain configuration in staging.
4. Merge PR #88 only after QA signoff.
5. Draft customer-facing update if issue affects production users.
```

---

## 12. Raw vs Compressed Example

### Raw GitHub Issue Output

Large raw objects may include:

```json
{
  "id": 123456,
  "node_id": "I_kwDOExample",
  "url": "https://api.github.com/repos/acme/app/issues/42",
  "repository_url": "https://api.github.com/repos/acme/app",
  "labels_url": "https://api.github.com/repos/acme/app/issues/42/labels{/name}",
  "comments_url": "https://api.github.com/repos/acme/app/issues/42/comments",
  "events_url": "https://api.github.com/repos/acme/app/issues/42/events",
  "html_url": "https://github.com/acme/app/issues/42",
  "number": 42,
  "state": "open",
  "title": "Login fails after OAuth redirect",
  "body": "Very long markdown body...",
  "user": {
    "login": "nikos",
    "id": 999,
    "avatar_url": "https://avatars.githubusercontent.com/u/999",
    "followers_url": "...",
    "following_url": "...",
    "repos_url": "...",
    "events_url": "..."
  },
  "labels": [
    {
      "id": 1,
      "node_id": "LA_kwDOExample",
      "url": "https://api.github.com/repos/acme/app/labels/bug",
      "name": "bug",
      "color": "d73a4a",
      "description": "Something is not working"
    }
  ]
}
```

### Aperture-Compressed Output

```json
{
  "aperture_compressed": true,
  "tool_slug": "GITHUB_LIST_ISSUES",
  "number": 42,
  "state": "open",
  "title": "Login fails after OAuth redirect",
  "author": "nikos",
  "labels": ["bug"],
  "comments": 4,
  "summary": "OAuth redirect succeeds, but the user remains unauthenticated.",
  "url": "https://github.com/acme/app/issues/42",
  "raw_reference_id": "wrk_abc123/issues_raw.json",
  "compression": {
    "raw_tokens": 3200,
    "compressed_tokens": 420,
    "tokens_saved": 2780,
    "compression_ratio": 0.131
  }
}
```

---

## 13. Benchmark Plan for the Agent

The benchmark should run the same tasks in two modes:

1. **Composio only**
2. **Composio + Aperture**

### Benchmark Task Examples

```text
1. Find top blockers for the OAuth release.
2. Summarize all open auth-related GitHub issues.
3. Find duplicate bug reports related to login redirects.
4. Search Slack for auth release decisions.
5. Identify owners for unresolved blockers.
6. Determine whether PR #88 is ready to merge.
7. Summarize customer escalations about login failures.
8. Create a release readiness report.
9. Draft a status update for the team.
10. Create follow-up issues for unresolved bugs.
```

### Benchmark Metrics

| Metric | Meaning |
|---|---|
| Raw output tokens | Tokens from uncompressed Composio outputs |
| Compressed output tokens | Tokens after Aperture compression |
| Tokens saved | Raw minus compressed |
| Compression ratio | Compressed divided by raw |
| Task success rate | Whether agent completed the task correctly |
| Success delta | Performance difference vs raw baseline |
| Extra tool calls | Whether compression caused the agent to ask for more data |
| Raw fallback rate | How often the agent needed full raw output |
| Cache hits | Repeated calls served from cache |
| API calls avoided | External calls skipped by cache |
| Latency | Time to complete task |

---

## 14. Why This Corresponds Perfectly to Aperture

This agent is almost tailor-made for Aperture.

### It creates large outputs

GitHub issues, Slack threads, PR comments, Notion pages, and emails can be very verbose.

### It creates repeated reads

The agent may repeatedly fetch the same repo, issue list, PR list, Slack thread, or project doc.

### It uses many tools

This makes schema/meta-tool cost visible.

### It requires reasoning over compressed information

The agent has to preserve enough detail to make correct decisions.

### It is easy to evaluate

The same tasks can be run with raw outputs and compressed outputs.

### It is visually demoable

The dashboard can show both:

- useful engineering intelligence
- Aperture’s efficiency metrics

---

## 15. Why Not a Simpler Agent?

A basic email assistant, calendar bot, or simple support bot would not stress Aperture enough.

The best demo agent should naturally produce:

- large raw outputs
- repeated calls
- multi-tool reasoning
- noisy JSON
- nested metadata
- long text
- visible before/after improvements

Engineering triage does all of that.

That is why **Aperture Command Center** is a better demo than a simple productivity assistant.

---

## 16. Final Recommendation

Build:

# Aperture Command Center

An engineering triage and release intelligence agent that uses Composio tools to inspect GitHub, Slack, Notion, Gmail, and Calendar, then produces a clean release/project status report.

The key demo:

> Same engineering task. Same tools. Same agent.  
> With Aperture enabled, the model sees compressed outputs, avoids repeated calls, spends fewer tokens, and produces the same-quality report.

This gives the project two wins:

1. **Aperture becomes measurable and impressive.**
2. **The demo agent is genuinely useful on its own.**

---

## 17. MVP Build Order

Recommended build order:

1. Build Aperture core:
   - token measurement
   - output compression
   - benchmark suite
   - optional caching
   - optional schema optimization

2. Build GitHub + Slack triage agent:
   - issue/PR search
   - Slack search
   - blocker extraction
   - duplicate grouping
   - release readiness report

3. Add Aperture metrics dashboard:
   - raw tokens
   - compressed tokens
   - token savings
   - cache hits
   - API calls avoided

4. Expand agent:
   - Notion
   - Gmail
   - Calendar

5. Run benchmark:
   - Composio only
   - Composio + Aperture

6. Final demo:
   - visual report
   - raw vs compressed output inspector
   - measured savings
   - performance comparison
