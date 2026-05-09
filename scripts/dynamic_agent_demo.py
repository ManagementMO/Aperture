#!/usr/bin/env python3
"""Dynamic agent demo — Aperture discovers and uses Composio tools automatically.

This demo shows how Aperture scales to new toolkits without manual configuration:
1. Agent receives a natural language intent
2. Aperture semantically matches intent to available Composio tools
3. Auto-generates compression profiles for matched tools
4. Executes with intelligent effort selection
5. Shows full reasoning chain

Usage:
    uv run python scripts/dynamic_agent_demo.py --intent "Find all open bugs in composio"
    uv run python scripts/dynamic_agent_demo.py --intent "Show me recent emails about OAuth"
    uv run python scripts/dynamic_agent_demo.py --intent "Summarize the composio repo"
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import uuid

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from aperture.demo.mock_data import (
    github_commits,
    github_issues,
    github_pull_requests,
    github_repo,
    gmail_search,
    slack_messages,
)
from aperture.demo.scenarios import get_mock_result
from aperture.integration import ApertureRunner
from aperture.contracts import ApertureRunConfig
from aperture.routing.semantic_selector import DynamicAgent
from aperture.schema_optimizer.auto_profile import ProfileRegistry
from aperture.tokenization import count_tokens

console = Console()

# Simulate a Composio toolkit catalog — in production this comes from Composio's API
AVAILABLE_TOOLS = [
    # GitHub
    "GITHUB_GET_A_REPOSITORY",
    "GITHUB_LIST_ISSUES",
    "GITHUB_LIST_PULL_REQUESTS",
    "GITHUB_LIST_COMMITS",
    "GITHUB_GET_ISSUE",
    "GITHUB_GET_USER",
    "GITHUB_SEARCH_REPOS",
    # Gmail
    "GMAIL_SEARCH_EMAILS",
    "GMAIL_FETCH_EMAILS",
    "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
    # Slack
    "SLACK_SEARCH_MESSAGES",
    "SLACK_LIST_CHANNELS",
    "SLACK_GET_CHANNEL",
    "SLACK_GET_USER",
    # Calendar
    "GOOGLE_CALENDAR_LIST_EVENTS",
    "GOOGLE_CALENDAR_GET_EVENT",
    # CRM
    "HUBSPOT_GET_CONTACT",
    "HUBSPOT_LIST_CONTACTS",
    "HUBSPOT_GET_DEAL",
    # Support
    "ZENDESK_LIST_TICKETS",
    "ZENDESK_GET_TICKET",
    # Ecommerce
    "SHOPIFY_LIST_PRODUCTS",
    "SHOPIFY_GET_ORDER",
]


def _make_executor(tool_slug: str, arguments: dict):
    def execute():
        return get_mock_result(tool_slug, arguments)
    return execute


def run_dynamic_agent(intent: str):
    """Run the dynamic agent with semantic routing."""
    console.print()
    console.print(Panel(
        f"[bold blue]🔬 Dynamic Agent Demo[/bold blue]\n"
        f"Intent: [italic]\"{intent}\"[/italic]\n"
        f"Available toolkits: {len(AVAILABLE_TOOLS)} tools across 9 domains",
        border_style="blue",
    ))

    # Step 1: Semantic matching
    console.print("\n[bold]🧠 Step 1: Semantic Intent Matching[/bold]")
    agent = DynamicAgent(available_tools=AVAILABLE_TOOLS)
    matches = agent.plan(intent)

    if not matches:
        console.print("[red]No tools matched this intent.[/red]")
        return

    match_table = Table(show_header=True, header_style="bold")
    match_table.add_column("Rank")
    match_table.add_column("Tool")
    match_table.add_column("Toolkit")
    match_table.add_column("Score")
    match_table.add_column("Effort")
    match_table.add_column("Reasoning")

    for i, match in enumerate(matches[:5]):
        match_table.add_row(
            str(i + 1),
            match.tool_slug,
            match.toolkit,
            f"{match.score:.2f}",
            match.effort_mode,
            match.reasoning[:60] + "..." if len(match.reasoning) > 60 else match.reasoning,
        )

    console.print(match_table)

    # Step 2: Auto-generate compression profiles
    console.print("\n[bold]📐 Step 2: Auto-Generated Compression Profiles[/bold]")
    registry = ProfileRegistry()

    for match in matches[:3]:
        # Get mock data for this tool
        sample_payload = get_mock_result(match.tool_slug, match.suggested_arguments)
        profile = registry.register(match.tool_slug, sample_payload)

        console.print(
            f"  [dim]{match.tool_slug}:[/dim] "
            f"{profile.typical_raw_tokens:,} raw → {profile.typical_compressed_tokens:,} compressed "
            f"([green]{profile.estimated_savings:.0%}[/green] savings, mode={profile.recommended_mode})"
        )
        console.print(f"    Critical: {', '.join(profile.critical_fields[:5])}")
        console.print(f"    Droppable: {', '.join(profile.droppable_fields[:5])}")

    # Step 3: Execute with Aperture
    console.print("\n[bold]⚡ Step 3: Execute with Aperture Optimization[/bold]")

    results = []
    total_raw = 0
    total_compressed = 0

    for match in matches[:3]:
        config = ApertureRunConfig(
            run_id=f"dyn-{uuid.uuid4().hex[:8]}",
            model="gpt-4o",
            effort_mode="auto",
            cache_bypass=False,
        )
        runner = ApertureRunner(config)

        executor = _make_executor(match.tool_slug, match.suggested_arguments)

        try:
            result = runner.run_tool(
                tool_slug=match.tool_slug,
                arguments=match.suggested_arguments,
                executor=executor,
                toolkit_slug=match.toolkit.upper(),
                user_query=intent,
            )

            summary = runner.finish()
            results.append({
                "match": match,
                "result": result,
                "summary": summary,
            })

            raw_t = result["compression"].raw_tokens if result["compression"] else 0
            comp_t = result["compression"].compressed_tokens if result["compression"] else 0
            total_raw += raw_t
            total_compressed += comp_t

            effort_decision = result.get("effort_decision")
            effort_str = effort_decision.reasoning if effort_decision else match.effort_mode
            if len(effort_str) > 50:
                effort_str = effort_str[:47] + "..."

            console.print(
                f"  ✅ {match.tool_slug} → {raw_t:,} raw → {comp_t:,} compressed "
                f"([green]{effort_str}[/green])"
            )

        except Exception as e:
            console.print(f"  ❌ {match.tool_slug} failed: {e}")

    # Step 4: Summary
    if results:
        console.print("\n[bold]📊 Agent Run Summary[/bold]")
        saved = total_raw - total_compressed
        ratio = saved / total_raw if total_raw > 0 else 0

        table = Table(show_header=True, header_style="bold")
        table.add_column("Metric")
        table.add_column("Value")

        table.add_row("Intent", intent)
        table.add_row("Tools Matched", str(len(matches)))
        table.add_row("Tools Executed", str(len(results)))
        table.add_row("Total Raw Tokens", f"{total_raw:,}")
        table.add_row("Total Compressed", f"{total_compressed:,}")
        table.add_row("Tokens Saved", f"{saved:,} ({ratio:.1%})")
        table.add_row("Registry Stats", str(registry.stats()))

        console.print(table)

        # Budget recommendation
        if results:
            last_summary = results[-1]["summary"]
            if "recommendation" in last_summary:
                rec = last_summary["recommendation"]
                if "CRITICAL" in rec or "WARNING" in rec:
                    console.print(f"\n[yellow]⚠️ {rec}[/yellow]")
                else:
                    console.print(f"\n[green]✅ {rec}[/green]")

    # Show dynamic toolkit expansion
    console.print("\n[bold]🚀 Scalability: Add New Toolkits Dynamically[/bold]")
    console.print("  [dim]Example: Registering a new 'shopify' toolkit...[/dim]")

    # Simulate registering a new toolkit
    new_tools = {
        "SHOPIFY_LIST_PRODUCTS": {
            "products": [
                {
                    "id": 12345,
                    "title": "Premium Widget",
                    "vendor": "Acme Corp",
                    "product_type": "electronics",
                    "created_at": "2024-01-15T10:00:00Z",
                    "updated_at": "2024-05-08T14:00:00Z",
                    "published_at": "2024-01-15T12:00:00Z",
                    "template_suffix": "",
                    "published_scope": "web",
                    "tags": "electronics, premium, new",
                    "variants": [
                        {
                            "id": 67890,
                            "product_id": 12345,
                            "title": "Default",
                            "price": "99.99",
                            "sku": "WIDGET-001",
                            "position": 1,
                            "inventory_policy": "deny",
                            "compare_at_price": "129.99",
                            "fulfillment_service": "manual",
                            "inventory_management": "shopify",
                            "option1": "Default",
                            "option2": None,
                            "option3": None,
                            "created_at": "2024-01-15T10:00:00Z",
                            "updated_at": "2024-05-08T14:00:00Z",
                            "taxable": True,
                            "barcode": "",
                            "grams": 500,
                            "image_id": None,
                            "weight": 0.5,
                            "weight_unit": "kg",
                            "inventory_item_id": 98765,
                            "inventory_quantity": 42,
                            "old_inventory_quantity": 42,
                            "requires_shipping": True,
                            "admin_graphql_api_id": "gid://shopify/ProductVariant/67890",
                        }
                    ],
                    "options": [
                        {
                            "id": 54321,
                            "product_id": 12345,
                            "name": "Title",
                            "position": 1,
                            "values": ["Default"],
                        }
                    ],
                    "images": [
                        {
                            "id": 11111,
                            "product_id": 12345,
                            "position": 1,
                            "created_at": "2024-01-15T10:00:00Z",
                            "updated_at": "2024-05-08T14:00:00Z",
                            "alt": None,
                            "width": 800,
                            "height": 600,
                            "src": "https://cdn.shopify.com/products/widget.jpg",
                            "variant_ids": [],
                            "admin_graphql_api_id": "gid://shopify/ProductImage/11111",
                        }
                    ],
                    "image": {
                        "id": 11111,
                        "product_id": 12345,
                        "position": 1,
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-05-08T14:00:00Z",
                        "alt": None,
                        "width": 800,
                        "height": 600,
                        "src": "https://cdn.shopify.com/products/widget.jpg",
                        "variant_ids": [],
                        "admin_graphql_api_id": "gid://shopify/ProductImage/11111",
                    },
                    "admin_graphql_api_id": "gid://shopify/Product/12345",
                    "status": "active",
                }
            ]
        },
    }

    new_profiles = registry.register_toolkit("shopify", new_tools)
    for slug, profile in new_profiles.items():
        console.print(
            f"    [dim]{slug}:[/dim] "
            f"auto-profiled → {profile.estimated_savings:.0%} compression "
            f"(critical: {len(profile.critical_fields)}, droppable: {len(profile.droppable_fields)})"
        )

    console.print(f"\n  [green]✅ Registry now has {registry.stats()['tools_registered']} tools across {registry.stats()['toolkits']} toolkits[/green]")


def main():
    parser = argparse.ArgumentParser(description="Dynamic Agent Demo")
    parser.add_argument(
        "--intent",
        default="Find all open bugs in composio and check if customers have reported them",
        help="Natural language intent for the agent",
    )
    args = parser.parse_args()

    run_dynamic_agent(args.intent)


if __name__ == "__main__":
    main()
