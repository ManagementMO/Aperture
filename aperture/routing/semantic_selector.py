"""Semantic toolkit selector — maps agent intent to the right tools + effort.

Instead of hardcoding "if user says X, use tool Y", Aperture analyzes:
1. What the agent is trying to accomplish (intent)
2. What each toolkit provides (capabilities)
3. The relationship between intent and capability (semantic match)

This makes Aperture work with ANY Composio toolkit — even ones added after
Aperture was deployed. No hardcoded mappings needed."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from aperture.routing.intelligent_effort import TaskComplexity, select_effort
from aperture.tokenization import count_tokens


@dataclass
class ToolCapability:
    """What a tool does, in semantic terms."""

    slug: str
    toolkit: str
    description: str
    verbs: list[str] = field(default_factory=list)
    nouns: list[str] = field(default_factory=list)
    domain: str = ""  # "code", "communication", "calendar", "crm", etc.


@dataclass
class IntentMatch:
    """Result of matching an agent intent to a tool capability."""

    tool_slug: str
    toolkit: str
    score: float  # 0.0-1.0 semantic relevance
    reasoning: str
    suggested_arguments: dict = field(default_factory=dict)
    effort_mode: str = "medium"


# Domain taxonomy — each toolkit belongs to a domain
_TOOLKIT_DOMAINS = {
    "github": "code",
    "gitlab": "code",
    "bitbucket": "code",
    "gmail": "communication",
    "slack": "communication",
    "discord": "communication",
    "teams": "communication",
    "google_calendar": "calendar",
    "outlook": "calendar",
    "notion": "knowledge",
    "confluence": "knowledge",
    "linear": "project_management",
    "jira": "project_management",
    "asana": "project_management",
    "trello": "project_management",
    "hubspot": "crm",
    "salesforce": "crm",
    "zendesk": "support",
    "intercom": "support",
    "stripe": "payments",
    "paypal": "payments",
    "shopify": "ecommerce",
    "woocommerce": "ecommerce",
}

# Intent → domain mapping
_INTENT_DOMAINS = {
    "code": ["repo", "repository", "commit", "branch", "pull request", "pr", "issue", "bug", "merge", "code review", "github", "gitlab"],
    "communication": ["email", "mail", "message", "chat", "slack", "notification", "channel", "thread", "conversation", "inbox"],
    "calendar": ["schedule", "meeting", "event", "calendar", "appointment", "reminder", "availability", "booking"],
    "knowledge": ["document", "page", "wiki", "note", "knowledge base", "docs", "confluence", "notion"],
    "project_management": ["task", "ticket", "sprint", "backlog", "milestone", "project", "board", "kanban"],
    "crm": ["contact", "lead", "customer", "deal", "opportunity", "pipeline", "prospect", "account"],
    "support": ["ticket", "support", "help desk", "customer service", "issue", "complaint", "feedback"],
    "payments": ["payment", "invoice", "billing", "subscription", "charge", "refund", "transaction"],
    "ecommerce": ["product", "order", "inventory", "shop", "store", "cart", "checkout", "shipping"],
}

# Verb extraction — what action is the agent trying to do?
_INTENT_VERBS = {
    "read": ["get", "fetch", "show", "display", "view", "read", "retrieve", "lookup", "find", "search", "list"],
    "write": ["create", "make", "add", "post", "send", "write", "submit", "open", "start"],
    "update": ["update", "edit", "modify", "change", "rename", "move", "set", "assign"],
    "delete": ["delete", "remove", "close", "archive", "cancel", "revoke"],
    "analyze": ["analyze", "summarize", "categorize", "classify", "count", "compare", "trend", "pattern"],
}


def _extract_domain(intent: str) -> set[str]:
    """Extract which domains the intent touches."""
    intent_lower = intent.lower()
    domains = set()
    for domain, keywords in _INTENT_DOMAINS.items():
        for kw in keywords:
            if kw in intent_lower:
                domains.add(domain)
                break
    return domains


def _extract_verbs(intent: str) -> set[str]:
    """Extract action verbs from the intent."""
    intent_lower = intent.lower()
    verbs = set()
    for verb_class, verb_list in _INTENT_VERBS.items():
        for v in verb_list:
            if v in intent_lower:
                verbs.add(verb_class)
                break
    return verbs


def _build_tool_capabilities(tool_slug: str) -> ToolCapability:
    """Derive capability metadata from a tool slug.

    This is the key scalability feature: we don't hardcode capabilities.
    We derive them from the tool's name, which follows Composio's
    {TOOLKIT}_{ACTION}_{TARGET} convention.
    """
    parts = tool_slug.split("_")
    toolkit = parts[0].lower() if parts else "unknown"
    domain = _TOOLKIT_DOMAINS.get(toolkit, "general")

    # Derive verbs from action words in the slug
    action_words = {
        "GET": ["read", "fetch"],
        "LIST": ["read", "search"],
        "SEARCH": ["read", "search", "analyze"],
        "FETCH": ["read", "fetch"],
        "CREATE": ["write"],
        "POST": ["write"],
        "SEND": ["write"],
        "UPDATE": ["update"],
        "EDIT": ["update"],
        "DELETE": ["delete"],
        "REMOVE": ["delete"],
        "CLOSE": ["delete", "update"],
    }

    verbs = []
    nouns = []
    for part in parts[1:]:
        upper = part.upper()
        if upper in action_words:
            verbs.extend(action_words[upper])
        else:
            nouns.append(part.lower())

    # Build a human-readable description
    action = " ".join(parts[1:]).lower() if len(parts) > 1 else "execute"
    description = f"{action} using {toolkit} ({domain} domain)"

    return ToolCapability(
        slug=tool_slug,
        toolkit=toolkit,
        description=description,
        verbs=list(set(verbs)) if verbs else ["execute"],
        nouns=nouns,
        domain=domain,
    )


def match_intent_to_tools(
    intent: str,
    available_tools: list[str],
    context_used: int = 0,
    context_limit: int = 128_000,
) -> list[IntentMatch]:
    """Match an agent's intent to available Composio tools.

    Returns ranked list of IntentMatch objects with relevance scores.
    The top match is the best tool for the job.

    This is fully dynamic — works with any Composio toolkit, even ones
    added after Aperture was deployed.
    """
    intent_domains = _extract_domain(intent)
    intent_verbs = _extract_verbs(intent)
    intent_lower = intent.lower()

    matches: list[IntentMatch] = []

    for tool_slug in available_tools:
        cap = _build_tool_capabilities(tool_slug)
        scores = []
        reasons = []

        # Domain match — highest weight
        if cap.domain in intent_domains:
            scores.append(0.4)
            reasons.append(f"domain match: {cap.domain}")
        elif intent_domains and cap.domain == "general":
            scores.append(0.1)
            reasons.append("general domain fallback")

        # Verb match — action alignment
        verb_overlap = set(cap.verbs) & intent_verbs
        if verb_overlap:
            scores.append(0.3)
            reasons.append(f"verb match: {', '.join(verb_overlap)}")

        # Noun/keyword match — direct text overlap
        keyword_hits = 0
        for noun in cap.nouns:
            if noun in intent_lower:
                keyword_hits += 1
        if keyword_hits:
            scores.append(min(0.2 * keyword_hits, 0.3))
            reasons.append(f"keyword hits: {keyword_hits}")

        # Toolkit name match — e.g., "github" in intent
        if cap.toolkit in intent_lower:
            scores.append(0.15)
            reasons.append(f"toolkit named: {cap.toolkit}")

        # Penalize write/delete actions for read intents
        if "read" in intent_verbs and "write" in cap.verbs:
            scores.append(-0.1)
            reasons.append("write tool for read intent (penalty)")

        total_score = max(0.0, min(1.0, sum(scores)))

        if total_score > 0.05:  # Minimum relevance threshold
            # Auto-select effort
            effort = select_effort(
                tool_slug=tool_slug,
                arguments={},
                user_query=intent,
                context_used=context_used,
            )

            # Suggest arguments from intent
            suggested_args = _suggest_arguments(intent, tool_slug)

            matches.append(IntentMatch(
                tool_slug=tool_slug,
                toolkit=cap.toolkit,
                score=round(total_score, 3),
                reasoning="; ".join(reasons) if reasons else "fallback match",
                suggested_arguments=suggested_args,
                effort_mode=effort.effort_mode,
            ))

    # Sort by score descending
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def _suggest_arguments(intent: str, tool_slug: str) -> dict:
    """Naive argument extraction from intent text.

    Looks for patterns like 'owner/repo', email addresses, dates, etc.
    """
    args: dict[str, str | int] = {}
    intent_lower = intent.lower()

    # Extract owner/repo pattern
    repo_match = re.search(r"([\w-]+)/([\w-]+)", intent)
    if repo_match:
        args["owner"] = repo_match.group(1)
        args["repo"] = repo_match.group(2)

    # Extract email
    email_match = re.search(r"[\w.-]+@[\w.-]+\.\w+", intent)
    if email_match:
        args["email"] = email_match.group(0)

    # Extract per_page / count
    count_match = re.search(r"(\d+)\s+(results?|items?|emails?|messages?|issues?)", intent_lower)
    if count_match:
        args["per_page"] = int(count_match.group(1))
        args["max_results"] = int(count_match.group(1))
        args["count"] = int(count_match.group(1))

    # Extract state
    if "open" in intent_lower:
        args["state"] = "open"
    elif "closed" in intent_lower:
        args["state"] = "closed"

    # Extract query for search tools
    if "SEARCH" in tool_slug:
        # Use the intent as the query, minus obvious stop words
        query = re.sub(r"\b(find|search|for|get|show|me|the|in|on|with|about)\b", "", intent_lower)
        query = re.sub(r"\s+", " ", query).strip()
        if query:
            args["query"] = query

    return args


class DynamicAgent:
    """A scalable agent that discovers and uses Composio tools dynamically.

    Instead of pre-wiring tool calls, the agent:
    1. Receives a user intent
    2. Matches intent to available Composio tools via semantic matching
    3. Auto-selects effort mode based on task complexity
    4. Executes with Aperture optimization

    New Composio toolkits are automatically available — no code changes needed.
    """

    def __init__(self, available_tools: list[str] | None = None):
        self.available_tools = available_tools or []
        self.execution_history: list[dict] = []

    def register_toolkit(self, tools: list[str]) -> None:
        """Dynamically add new tools from a Composio toolkit."""
        for tool in tools:
            if tool not in self.available_tools:
                self.available_tools.append(tool)

    def plan(self, intent: str, context_used: int = 0) -> list[IntentMatch]:
        """Plan which tools to call for a given intent."""
        if not self.available_tools:
            raise ValueError("No tools registered. Call register_toolkit() first.")

        matches = match_intent_to_tools(
            intent=intent,
            available_tools=self.available_tools,
            context_used=context_used,
        )
        return matches

    def execute_plan(
        self,
        intent: str,
        executor_factory: Callable[[str, dict], Callable[[], object]],
        context_used: int = 0,
    ) -> list[dict]:
        """Plan and execute tools for an intent, with full Aperture optimization.

        Returns execution results with token savings and effort decisions.
        """
        from aperture.integration import ApertureRunner
        from aperture.contracts import ApertureRunConfig

        matches = self.plan(intent, context_used=context_used)
        results = []
        total_compressed = 0

        for match in matches[:3]:  # Top 3 matches
            config = ApertureRunConfig(
                run_id=f"dynamic-{uuid.uuid4().hex[:8]}",
                model="gpt-4o",
                effort_mode="auto",
                cache_bypass=False,
            )
            runner = ApertureRunner(config)

            executor = executor_factory(match.tool_slug, match.suggested_arguments)
            result = runner.run_tool(
                tool_slug=match.tool_slug,
                arguments=match.suggested_arguments,
                executor=executor,
                toolkit_slug=match.toolkit.upper(),
                user_query=intent,
            )

            summary = runner.finish()
            total_compressed += summary.get("total_compressed_tokens", 0)

            results.append({
                "match": match,
                "result": result,
                "summary": summary,
            })

            self.execution_history.append({
                "intent": intent,
                "tool": match.tool_slug,
                "score": match.score,
                "effort": result.get("effort_decision", {}),
                "tokens_saved": result["compression"].tokens_saved if "compression" in result else 0,
            })

        return results
