"""LangGraph adapter pattern for Aperture.

This module shows how to integrate Aperture with LangGraph agents.
LangGraph is not a hard dependency — install it separately:

    uv add langgraph langchain

Usage:
    from aperture.adapters.langgraph import ApertureToolNode

    # Wrap your Composio tools with Aperture
    tools = [composio_github_tool, composio_slack_tool]
    aperture_tools = [ApertureToolNode.wrap(t) for t in tools]

    # Build LangGraph with Aperture-optimized tools
    graph = StateGraph(AgentState)
    graph.add_node("tools", ApertureToolNode(aperture_tools))
"""

from __future__ import annotations

from typing import Any, Callable

# LangGraph is optional — we define the pattern without importing it
# so the core package doesn't depend on it.


class ApertureToolNode:
    """LangGraph-compatible tool node that applies Aperture optimization.

    Wraps each tool call with:
    - Intelligent effort selection (auto mode)
    - Compression based on context window pressure
    - Caching for repeated calls
    - Token counting and observability

    This is how Aperture scales: it sits BETWEEN LangGraph's tool node
    and Composio's actual tool execution, transparently optimizing every call.
    """

    def __init__(self, tools: list, config: dict | None = None):
        self.tools = {t.name: t for t in tools}
        self.config = config or {}
        self._aperture_runners: dict[str, Any] = {}

    @classmethod
    def wrap(cls, tool: Any, effort_mode: str = "auto") -> "ApertureToolNode":
        """Wrap a single LangGraph/Composio tool with Aperture."""
        return cls([tool], config={"effort_mode": effort_mode})

    def invoke(self, state: dict) -> dict:
        """Invoke tools with Aperture optimization.

        This mirrors LangGraph's ToolNode.invoke() interface.
        """
        from aperture.integration import ApertureRunner
        from aperture.contracts import ApertureRunConfig
        from aperture.tokenization.budget_manager import ContextBudgetManager

        messages = state.get("messages", [])
        tool_calls = self._extract_tool_calls(messages)

        budget = ContextBudgetManager()
        results = []

        for call in tool_calls:
            tool_name = call.get("name", "")
            arguments = call.get("args", {})

            # Get or create Aperture runner for this tool
            if tool_name not in self._aperture_runners:
                config = ApertureRunConfig(
                    run_id=f"lg-{tool_name}-{id(call)}",
                    model=self.config.get("model", "gpt-4o"),
                    effort_mode=self.config.get("effort_mode", "auto"),
                )
                self._aperture_runners[tool_name] = ApertureRunner(config)

            runner = self._aperture_runners[tool_name]

            # Get the underlying Composio tool
            base_tool = self.tools.get(tool_name)
            if not base_tool:
                results.append({"error": f"Tool {tool_name} not found"})
                continue

            # Execute with Aperture optimization
            result = runner.run_tool(
                tool_slug=tool_name,
                arguments=arguments,
                executor=lambda: base_tool.invoke(arguments),
            )

            summary = runner.finish()
            budget.add_tool_call(
                tool_slug=tool_name,
                raw_payload=result["raw_result"],
                compressed_payload=result["result"],
                cache_hit=result["cache_event"].cache_status == "hit",
            )

            results.append({
                "tool": tool_name,
                "result": result["result"],  # Return COMPRESSED result to LLM
                "raw_tokens": result["compression"].raw_tokens,
                "compressed_tokens": result["compression"].compressed_tokens,
                "tokens_saved": result["compression"].tokens_saved,
                "cache_status": result["cache_event"].cache_status,
                "budget_status": budget.snapshot.status,
            })

        return {"messages": results, "aperture_budget": budget.snapshot.to_dict()}

    def _extract_tool_calls(self, messages: list) -> list[dict]:
        """Extract tool calls from LangGraph message format."""
        calls = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                tool_calls_list = msg.get("tool_calls", [])
                for tc in tool_calls_list:
                    calls.append({
                        "name": tc.get("function", {}).get("name", ""),
                        "args": tc.get("function", {}).get("arguments", {}),
                    })
        return calls


def create_aperture_agent(
    model: Any,
    tools: list[Any],
    effort_mode: str = "auto",
    system_prompt: str | None = None,
) -> Any:
    """Create a LangGraph agent with Aperture-optimized tools.

    This is a factory function that builds a complete LangGraph agent
    where every tool call goes through Aperture.

    Usage:
        agent = create_aperture_agent(
            model=ChatOpenAI(model="gpt-4o"),
            tools=composio_tools,
            effort_mode="auto",
        )
        result = agent.invoke({"messages": [HumanMessage("Find open bugs")]})
    """
    # This is a pattern/example — actual implementation requires LangGraph
    raise NotImplementedError(
        "Install LangGraph to use this function: uv add langgraph langchain\n"
        "Then wire ApertureToolNode into your StateGraph."
    )
