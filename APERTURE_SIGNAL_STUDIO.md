# APERTURE_SIGNAL_STUDIO.md

# Aperture Signal Studio  
## Customer, Product, and Engineering Intelligence Agent

---

## 1. One-Sentence Summary

**Aperture Signal Studio** is a multi-source intelligence agent built on top of Aperture that reads messy enterprise signals from support, sales, Slack, GitHub, Notion, email, docs, and market research, compresses them into structured decision-ready context, and produces clear product, engineering, and roadmap recommendations.

---

## 2. Core Thesis

Modern companies have the answer to “what should we build, fix, or prioritize next?” scattered across many noisy systems:

- support tickets
- customer emails
- Slack discussions
- GitHub issues
- GitHub PRs
- Notion docs
- CRM notes
- sales call notes
- app reviews
- survey responses
- product analytics summaries
- competitor research
- strategy documents

A normal agent can access these through tools, but the raw outputs are huge, repetitive, and full of metadata the model does not need.

Aperture Signal Studio uses Aperture to turn noisy raw tool outputs into compact signal packs.

The main idea:

```text
Messy enterprise data
    ↓
Composio tools
    ↓
Aperture output compression + token measurement + caching
    ↓
Structured signal intelligence
    ↓
Product/engineering/business decisions
```

---

## 3. Why This Is the Perfect Aperture Agent

Aperture is designed to optimize tool-heavy agents by reducing token waste from:

1. Large tool outputs
2. Repeated tool calls
3. Verbose schemas
4. Noisy API payloads
5. Long multi-step workflows

Aperture Signal Studio naturally stresses all of these.

It reads many sources, gets huge outputs, repeats lookups, clusters signals, links evidence, and produces a decision report.

This makes it a perfect before/after benchmark:

```text
Composio only
vs.
Composio + Aperture
```

The demo can clearly show:

- raw tokens
- compressed tokens
- tokens saved
- compression ratio
- cache hits
- API calls avoided
- task success rate
- output quality
- raw vs compressed signal examples

---

## 4. What the Agent Does

The user asks a question like:

```text
What are all our recent customer and team signals saying about OAuth login failures?
Check support emails/tickets, Slack, GitHub, Notion release docs, and CRM notes.
Cluster the issues, identify affected customers, link them to engineering work,
estimate severity, identify owners, and recommend next actions.
```

The agent then:

1. Searches support tickets and emails.
2. Searches Slack discussions.
3. Reads GitHub issues, PRs, and comments.
4. Reads Notion project/release docs.
5. Reads CRM or sales notes.
6. Optionally checks market/competitor context.
7. Compresses all raw outputs using Aperture.
8. Clusters related signals.
9. Identifies affected customer segments.
10. Links customer pain to engineering work.
11. Estimates severity and urgency.
12. Recommends roadmap/product/engineering actions.
13. Produces a stakeholder-ready report.
14. Shows token savings and efficiency metrics.

---

## 5. The Main Output

The agent produces a **Signal Intelligence Report**.

Example sections:

```md
# OAuth Signal Intelligence Report

## Executive Summary
OAuth login failures are affecting Safari/mobile users and three enterprise customers.
The main issue appears to be session cookie persistence after the redirect callback.

## Top Signal Clusters
1. Safari callback cookie issue — high severity
2. Mobile redirect loop — medium severity
3. Confusing login error copy — low severity

## Evidence Summary
- 14 support tickets
- 3 customer escalation emails
- 5 GitHub issues
- 2 Slack threads
- 1 Notion release-risk note

## Linked Engineering Work
- Issue #42 — Login fails after OAuth redirect
- Issue #57 — Users logged out after callback
- PR #88 — Patch OAuth callback cookie settings

## Recommended Actions
1. Hold release until Safari/mobile OAuth regression passes.
2. Merge PR #88 after QA signoff.
3. Create separate issue for mobile redirect loop.
4. Draft customer update for affected accounts.
5. Add clearer login-error copy to roadmap.

## Owners
| Area | Owner |
|---|---|
| Backend OAuth callback | Nikos |
| Frontend login flow | Sarah |
| QA regression | Alex |
| Customer comms | Mohammed |
```

---

## 6. Why This Agent Is Useful on Its Own

This is not just a benchmark toy.

Every product, engineering, support, and growth team needs to answer questions like:

- What are customers complaining about?
- Which complaints are duplicates?
- Which issues are urgent?
- Which bugs are tied to revenue or enterprise customers?
- What are people saying internally in Slack?
- Which GitHub issues already exist?
- Which PRs are supposed to fix the issue?
- Who owns the next action?
- What should go on the roadmap?
- What should we tell stakeholders?

Aperture Signal Studio turns scattered signals into decisions.

It is valuable as a real enterprise tool and as a perfect Aperture showcase.

---

## 7. Why This Is Better Than a Simple Demo Agent

A simple email assistant, calendar bot, or single-tool agent would not stress Aperture enough.

The best Aperture demo needs:

- large raw tool outputs
- repeated reads
- multi-source reasoning
- noisy JSON
- long text
- nested metadata
- measurable compression savings
- clear task success criteria
- visually understandable output

Aperture Signal Studio has all of these.

It naturally uses many Composio-style integrations and produces large model-facing context unless Aperture optimizes it.

---

## 8. Core Data Sources

## 8.1 Support / Customer Sources

Possible sources:

- Zendesk
- Intercom
- Front
- Gmail
- Outlook
- HubSpot conversations
- Salesforce cases
- app reviews
- survey forms

Signals extracted:

- customer complaint
- affected account
- severity
- sentiment
- frequency
- requested feature
- bug description
- business impact
- representative quote

---

## 8.2 Engineering Sources

Possible sources:

- GitHub issues
- GitHub PRs
- GitHub comments
- GitHub Actions/build status
- Linear/Jira
- Sentry
- Datadog
- incident docs

Signals extracted:

- related bug
- issue status
- PR status
- owner
- labels
- severity
- duplicate issues
- risk
- technical root cause
- blocking dependency

---

## 8.3 Internal Communication Sources

Possible sources:

- Slack
- Microsoft Teams
- Discord
- Notion comments
- Google Docs comments

Signals extracted:

- team decision
- blocker
- owner
- disagreement
- unresolved question
- launch concern
- timeline risk

---

## 8.4 Product / Strategy Sources

Possible sources:

- Notion docs
- Google Docs
- product briefs
- roadmap docs
- launch docs
- annual plans
- strategy decks
- market research docs

Signals extracted:

- strategic priority
- product requirement
- target segment
- launch criteria
- risk
- constraint
- business rationale

---

## 8.5 Market / External Sources

Possible sources:

- web search
- competitor sites
- release notes
- social/review data
- public forums
- news

Signals extracted:

- competitor feature
- market trend
- pricing signal
- customer expectation
- industry benchmark

---

## 9. Aperture-Native Signal Packs

Instead of sending all raw outputs to the model, Aperture compresses them into compact structured packs.

## 9.1 Customer Signal Pack

```json
{
  "signal_type": "customer_pain",
  "theme": "OAuth login failure",
  "affected_segments": ["enterprise customers", "Safari users", "mobile users"],
  "severity": "high",
  "frequency": {
    "support_tickets": 14,
    "emails": 3,
    "crm_notes": 2
  },
  "representative_quotes": [
    "Users are redirected but remain logged out.",
    "Safari users cannot complete login."
  ],
  "business_impact": "Affects onboarding and renewal risk for three enterprise accounts.",
  "linked_engineering_work": ["GITHUB_ISSUE_42", "PR_88"],
  "recommended_action": "Hold release until Safari/mobile OAuth regression passes.",
  "raw_reference_ids": [
    "support_ticket_cluster_001",
    "email_thread_003"
  ]
}
```

---

## 9.2 Engineering Link Pack

```json
{
  "signal_type": "engineering_cluster",
  "theme": "OAuth callback/session bugs",
  "issues": [
    {
      "number": 42,
      "title": "Login fails after OAuth redirect",
      "state": "open",
      "labels": ["bug", "auth"],
      "owner": "backend",
      "summary": "Callback succeeds but session cookie is not persisted."
    }
  ],
  "related_prs": [
    {
      "number": 88,
      "title": "Patch OAuth callback cookie settings",
      "status": "waiting_for_qa",
      "risk": "medium"
    }
  ],
  "blockers": [
    "Safari/mobile regression not complete"
  ],
  "raw_reference_ids": [
    "github_issue_cluster_auth_001"
  ]
}
```

---

## 9.3 Slack Decision Pack

```json
{
  "signal_type": "internal_decision",
  "theme": "OAuth release readiness",
  "decisions": [
    {
      "decision": "Do not ship until Safari regression passes.",
      "source": "Slack #auth-release",
      "owner": "QA",
      "confidence": "high"
    }
  ],
  "open_questions": [
    "Is callback domain mismatch fully fixed in staging?"
  ],
  "owners": {
    "backend": "Nikos",
    "qa": "Alex",
    "frontend": "Sarah"
  },
  "raw_reference_ids": [
    "slack_thread_2026_05_09_auth"
  ]
}
```

---

## 9.4 Product Roadmap Pack

```json
{
  "signal_type": "roadmap_recommendation",
  "theme": "Login reliability",
  "priority": "P0/P1",
  "recommended_actions": [
    "Fix Safari OAuth session persistence",
    "Create separate issue for mobile redirect loop",
    "Improve login error copy",
    "Add automated OAuth regression coverage"
  ],
  "evidence_strength": "high",
  "customer_impact": "enterprise onboarding risk",
  "owner_recommendations": {
    "backend": "OAuth callback/session",
    "frontend": "error messaging",
    "qa": "browser/mobile regression"
  }
}
```

These packs are the heart of the agent.

They show how Aperture turns verbose tool results into compact, decision-ready context.

---

## 10. How It Uses Aperture

## 10.1 Token Measurement

Aperture measures:

- raw support ticket output tokens
- raw email thread tokens
- raw GitHub issue/PR tokens
- raw Slack thread tokens
- raw Notion doc tokens
- compressed signal pack tokens
- tokens saved
- compression ratio
- savings by tool/source/session

Example:

```text
Raw tokens: 118,000
Compressed signal packs: 24,500
Tokens saved: 93,500
Compression ratio: 79%
```

---

## 10.2 Tool Output Compression

Aperture compresses large noisy outputs into compact packs.

Examples:

```text
25 support tickets
    → Customer Signal Pack

5 GitHub issues + 2 PRs
    → Engineering Link Pack

3 Slack threads
    → Slack Decision Pack

2 Notion docs
    → Product Roadmap Pack
```

This helps even on first-time calls.

---

## 10.3 Tool-Calling Cache

The agent repeatedly asks for similar information:

- repo metadata
- issue lists
- PR lists
- Slack search results
- Notion docs
- CRM account records
- company/product profile
- previously processed signal clusters

Aperture can cache safe read-only calls.

Cache rule:

```text
same safe tool + same normalized params + same user/account/project scope = cache hit
```

Never cache:

- writes
- sends
- deletes
- updates
- auth flows
- private data across users

---

## 10.4 Schema Optimization

Because this agent uses many tools, schema/meta-tool cost matters.

Schema optimization reduces the cost of tool discovery and schema exposure.

This is secondary to output compression, but still useful.

---

## 11. Agent Architecture

## 11.1 High-Level Architecture

```text
User question
    ↓
Planner agent
    ↓
Tool retrieval via Composio
    ↓
Raw source outputs
    ↓
Aperture token measurement
    ↓
Aperture output compression
    ↓
Signal pack generation
    ↓
Clustering + linking
    ↓
Recommendation engine
    ↓
Stakeholder report
    ↓
Aperture metrics dashboard
```

---

## 11.2 Multi-Agent Pipeline

Aperture Signal Studio can be implemented as multiple specialized agents.

### 1. Signal Collector Agent

Purpose:

- Query all relevant systems.
- Retrieve raw support/customer/product/engineering signals.

Tools:

- Gmail/Outlook
- Slack
- GitHub
- Notion
- CRM
- web search
- docs/files

Output:

- raw tool outputs
- source metadata

Aperture role:

- measure raw token cost
- compress outputs

---

### 2. Compression / Context Pack Agent

Purpose:

- Convert raw outputs into structured signal packs.

Outputs:

- Customer Signal Pack
- Engineering Link Pack
- Slack Decision Pack
- Product Roadmap Pack
- Market Context Pack

Aperture role:

- primary layer
- compress and track savings
- preserve raw references

---

### 3. Signal Clusterer Agent

Purpose:

- Group repeated/duplicate signals.
- Detect themes and severity.

Outputs:

- clusters
- themes
- counts
- representative quotes
- confidence scores

---

### 4. Engineering Linker Agent

Purpose:

- Connect customer/product signals to GitHub issues, PRs, incidents, and owners.

Outputs:

- linked issues
- related PRs
- owner map
- unresolved blockers

---

### 5. Product Strategist Agent

Purpose:

- Turn clusters into roadmap recommendations.

Outputs:

- priority
- recommended actions
- product/engineering implications
- stakeholder summary

---

### 6. Report Writer Agent

Purpose:

- Produce the final stakeholder-facing report.

Outputs:

- executive summary
- evidence table
- action plan
- owner map
- roadmap recommendations

---

### 7. Evaluation Agent

Purpose:

- Compare raw Composio vs Composio + Aperture runs.

Outputs:

- success score
- missing information score
- quality comparison
- token savings report

---

## 12. UI / Dashboard Concept

## 12.1 Main Layout

```text
┌───────────────────────────────────────────────┐
│ Aperture Signal Studio                        │
│ Customer + Product + Engineering Intelligence │
└───────────────────────────────────────────────┘

Prompt:
[ Analyze recent signals about OAuth login failures ]

Mode:
[ Composio Only ] [ Composio + Aperture ]

┌───────────────────────────────┬─────────────────────────────┐
│ Signal Intelligence Report    │ Aperture Efficiency Metrics  │
│                               │                             │
│ Executive summary             │ Raw tokens                   │
│ Top clusters                  │ Compressed tokens            │
│ Evidence                      │ Tokens saved                 │
│ Linked GitHub issues          │ Compression ratio            │
│ Owners                        │ Cache hits                   │
│ Recommended actions           │ API calls avoided            │
└───────────────────────────────┴─────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Raw vs Compressed Inspector                                 │
│ Support tickets → Customer Signal Pack                      │
│ GitHub issues → Engineering Link Pack                       │
│ Slack threads → Slack Decision Pack                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 12.2 Visual Sections

### Signal Clusters

Cards showing:

- cluster name
- severity
- frequency
- affected customers
- linked engineering work
- confidence

Example:

```text
Safari OAuth Cookie Failure
Severity: High
Signals: 14 tickets, 3 emails, 2 Slack threads, 5 GitHub issues
Owner: Backend
Recommended action: block release until regression passes
```

---

### Evidence Graph

A graph linking:

```text
Customer tickets
    ↓
Signal cluster
    ↓
GitHub issue
    ↓
PR
    ↓
Owner
    ↓
Roadmap action
```

---

### Aperture Metrics Panel

Shows:

```text
Raw tokens: 118,000
Compressed tokens: 24,500
Tokens saved: 93,500
Compression ratio: 79%

Cache hits: 18
API calls avoided: 11
Extra tool calls due to compression: 1
Task success: same
```

---

### Raw vs Compressed Inspector

Shows a before/after:

```text
Raw: 25 support tickets, 32,000 tokens
Compressed: Customer Signal Pack, 4,800 tokens
Saved: 27,200 tokens
```

---

## 13. Example Demo Prompt

```text
Analyze all recent signals about OAuth login failures.

Check:
- support emails and tickets
- Slack discussions
- GitHub issues and PRs
- Notion release docs
- CRM/customer notes

Then:
1. cluster the complaints
2. identify affected customer segments
3. link issues to engineering work
4. identify owners
5. estimate severity
6. recommend roadmap or engineering actions
7. draft a stakeholder update
```

---

## 14. Example Final Output

```md
# OAuth Signal Intelligence Report

## Executive Summary

OAuth login failures are affecting Safari/mobile users and at least three enterprise customers. The highest-confidence root cause is session cookie persistence after OAuth redirect. The release should stay blocked until Safari/mobile regression passes.

## Signal Clusters

### 1. Safari callback cookie issue

- Severity: High
- Signals: 14 support tickets, 3 emails, 2 Slack threads
- Affected users: Safari/mobile users
- Linked engineering work: Issue #42, PR #88
- Owner: Backend
- Recommendation: Hold release until regression passes.

### 2. Mobile redirect loop

- Severity: Medium
- Signals: 6 tickets, 1 Slack thread
- Linked engineering work: create new issue
- Owner: Frontend
- Recommendation: create dedicated bug ticket and add reproduction steps.

### 3. Confusing login error copy

- Severity: Low
- Signals: 4 support tickets
- Owner: Product/Frontend
- Recommendation: add improved error copy to roadmap.

## Linked GitHub Work

| Item | Status | Risk | Owner |
|---|---|---|---|
| Issue #42 — Login fails after OAuth redirect | Open | High | Backend |
| Issue #57 — Users logged out after callback | Open | Medium | Backend |
| PR #88 — Patch OAuth callback cookie settings | Waiting for QA | Medium | Nikos |

## Recommended Actions

1. Block release until Safari/mobile OAuth regression passes.
2. Merge PR #88 after QA signoff.
3. Create separate issue for mobile redirect loop.
4. Draft customer update for affected enterprise accounts.
5. Add improved login error copy to next sprint.

## Stakeholder Update Draft

We identified an OAuth login issue affecting Safari/mobile users and several enterprise customers. A backend fix is in progress through PR #88. The release is currently blocked pending QA regression testing across Safari and mobile browsers.
```

---

## 15. Benchmark Plan

The benchmark should compare:

```text
Baseline: Composio only
vs.
Aperture: Composio + Aperture output compression/cache/schema optimization
```

## 15.1 Task Set

Example benchmark tasks:

1. Find top product complaints from support tickets.
2. Cluster duplicate customer issues.
3. Link customer complaints to GitHub issues.
4. Summarize Slack decisions around a release.
5. Identify launch blockers from Notion docs and GitHub.
6. Draft stakeholder update.
7. Recommend roadmap actions.
8. Identify affected customer segments.
9. Detect whether a PR resolves a customer complaint.
10. Produce a release readiness report.

Scale to 50–100 tasks if possible.

---

## 15.2 Metrics

| Metric | Meaning |
|---|---|
| Raw output tokens | Tokens from uncompressed tool outputs |
| Compressed output tokens | Tokens after Aperture compression |
| Tokens saved | Raw minus compressed |
| Compression ratio | Compressed divided by raw |
| Task success rate | Whether agent completed the task |
| Success delta | Difference vs raw baseline |
| Missing critical info rate | Whether compression omitted needed info |
| Extra tool calls | Additional calls caused by compression |
| Raw fallback rate | How often agent requested full raw output |
| Cache hits | Repeated calls served from cache |
| API calls avoided | External calls skipped |
| Latency | Time to complete task |
| Report quality | LLM/human judged usefulness |

---

## 15.3 Success Targets

Initial target hypotheses:

```text
40%+ output token reduction
<5% absolute task success degradation
<3% critical information omission
<10% extra tool-call increase
<15% raw fallback rate
```

Final claims must be based on measured benchmark results, not guesses.

---

## 16. How This Showcases All Original Aperture Features

## 16.1 Token Cost Measurement

This agent creates many token-heavy outputs.

Aperture measures:

- support ticket output tokens
- email output tokens
- Slack output tokens
- GitHub output tokens
- Notion output tokens
- compressed signal pack tokens
- tokens saved by source/tool/session

---

## 16.2 Tool Output Compression

This is the main showcase.

Aperture compresses:

```text
raw support tickets → Customer Signal Packs
raw GitHub issues → Engineering Link Packs
raw Slack threads → Decision Packs
raw Notion docs → Roadmap Packs
raw CRM notes → Account Impact Packs
```

---

## 16.3 Tool-Calling Cache

The agent repeats reads often.

Cache examples:

- same GitHub repo metadata
- same issue list
- same Slack query
- same Notion doc
- same account record
- same support ticket cluster

Aperture avoids repeated work.

---

## 16.4 Schema Optimization

The agent uses many tools, so schema optimization reduces the cost of tool discovery and tool usage.

---

## 17. Why This Could Also Support Aucctus Prototype Studio

Aperture Signal Studio can connect naturally to the Aucctus-style prototype agent.

Flow:

```text
Customer/product signals
    ↓
roadmap recommendation
    ↓
new product/opportunity brief
    ↓
Aperture Prototype Studio
    ↓
interactive 3D prototype
```

Example:

```text
Signal Studio discovers:
Customers want a portable energy product with less sugar and easier usage than drinks.

Prototype Studio generates:
A brand-aligned caffeinated gum prototype.
```

So Signal Studio can become the upstream intelligence layer for idea generation, while Prototype Studio turns selected opportunities into prototypes.

---

## 18. MVP Build Plan

## Phase 1 — Aperture Core

Build:

- token measurement
- output compression
- raw reference storage
- compression event logging
- basic benchmark runner

---

## Phase 2 — Signal Studio MVP

Use two sources first:

- GitHub
- Slack

MVP task:

```text
Given a repo and a topic, find related GitHub issues/PRs and Slack discussions, cluster blockers, identify owners, and produce a report.
```

Outputs:

- Engineering Link Pack
- Slack Decision Pack
- Signal Intelligence Report
- Aperture metrics panel

---

## Phase 3 — Add Customer Signals

Add:

- Gmail/support tickets
- CRM notes
- customer impact analysis

Outputs:

- Customer Signal Pack
- Account Impact Pack

---

## Phase 4 — Add Product/Strategy Docs

Add:

- Notion docs
- Google Docs
- roadmap docs

Outputs:

- Product Roadmap Pack
- Launch Risk Pack

---

## Phase 5 — Visual Dashboard

Build UI with:

- report panel
- signal clusters
- evidence graph
- Aperture metrics
- raw vs compressed inspector
- Composio only vs Aperture toggle

---

## Phase 6 — Benchmark and Demo

Run:

```text
Composio only
vs.
Composio + Aperture
```

Measure:

- token savings
- success delta
- extra tool calls
- raw fallback rate
- output quality

---

## 19. Recommended Tech Stack

## Frontend

- Next.js / React
- Tailwind
- shadcn/ui
- Recharts for metrics
- React Flow or similar for evidence graph

## Backend

- Python or Node
- Composio tools
- Aperture compression layer
- Redis for cache
- local/S3-style raw reference store
- PostgreSQL or SQLite for events/benchmarks

## Evaluation

- deterministic checks where possible
- LLM judge for report quality
- human review for selected tasks
- benchmark JSONL task sets

---

## 20. Demo Script

## Step 1 — Prompt

Presenter enters:

```text
Analyze recent signals about OAuth login failures across support, Slack, GitHub, and Notion. Find clusters, affected customers, linked engineering work, owners, and recommended actions.
```

## Step 2 — Run Without Aperture

Show:

- large raw outputs
- high token count
- final report

## Step 3 — Run With Aperture

Show:

- compressed signal packs
- lower token count
- same or similar final report
- cache hits
- raw references preserved

## Step 4 — Dashboard

Show:

- raw tokens
- compressed tokens
- token savings
- compression ratio
- cache hits
- API calls avoided
- success comparison

## Step 5 — Raw vs Compressed Inspector

Show:

```text
25 support tickets → Customer Signal Pack
5 GitHub issues → Engineering Link Pack
3 Slack threads → Decision Pack
```

## Step 6 — Final Narrative

Say:

> Aperture lets tool-heavy agents reason over enterprise-scale context without flooding the model with raw, repetitive, expensive outputs.

---

## 21. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Data integrations are hard | Start with GitHub + Slack mocked/real fixtures |
| Compression removes important info | Preserve raw references and benchmark omissions |
| Benchmark is too subjective | Use exact checks + LLM judge + human spot checks |
| Output looks like generic summary | Link every recommendation to evidence |
| Token savings seem abstract | Show raw vs compressed inspector and metrics |
| Real data unavailable | Use realistic seeded fixtures |
| Too broad for MVP | Start with engineering triage, expand later |

---

## 22. Final Recommendation

The best general-purpose showcase agent for Aperture is:

# Aperture Signal Studio

## Customer, Product, and Engineering Intelligence Agent

It answers:

> “What are all our scattered customer, product, and engineering signals telling us, and what should we do next?”

This is ideal because it is:

- useful on its own
- enterprise-relevant
- multi-tool
- context-heavy
- visually demoable
- benchmarkable
- perfect for output compression
- perfect for caching repeated reads
- perfect for token measurement
- compatible with the Aucctus prototype idea

Final positioning:

> **Aperture Signal Studio turns noisy enterprise signals into clear product and engineering decisions, powered by Aperture’s token-efficient compression, caching, and measurement layer.**
