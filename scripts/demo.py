#!/usr/bin/env python3
"""CLI demo script for Aperture.

Usage:
    uv run python scripts/demo.py --tool GITHUB_GET_REPO --owner composioHQ --repo composio --mode medium
    uv run python scripts/demo.py --tool GITHUB_LIST_ISSUES --owner composioHQ --repo composio --mode medium
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import uuid
from typing import Any

from rich.console import Console
from rich.table import Table

from aperture.contracts import ApertureRunConfig
from aperture.integration import ApertureRunner
from aperture.tokenization import count_tokens

console = Console()


def make_composio_executor(tool_slug: str, arguments: dict):
    """Create an executor that calls Composio (or returns fixture data)."""
    from aperture.config import Config

    api_key = Config.COMPOSIO_API_KEY
    if not api_key or api_key == "your_composio_api_key_here":
        console.print("[yellow]COMPOSIO_API_KEY not configured, using simulated data[/yellow]")

        def execute():
            return _simulate_output(tool_slug, arguments)

        return execute

    try:
        from composio import Composio

        composio = Composio(api_key=api_key)

        def execute():
            try:
                resp = composio.tools.execute(slug=tool_slug, arguments=arguments)
                return resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
            except Exception as e:
                console.print(f"[yellow]Composio API call failed ({e}), using simulated data[/yellow]")
                return _simulate_output(tool_slug, arguments)

        return execute
    except Exception as e:
        console.print(f"[yellow]Composio SDK error ({e}), using simulated data[/yellow]")

        def execute():
            return _simulate_output(tool_slug, arguments)

        return execute


def _simulate_output(tool_slug: str, arguments: dict) -> dict[str, Any]:
    """Return realistic simulated tool output for demo purposes."""
    if "GITHUB_GET_REPO" in tool_slug:
        return {
            "id": 123456,
            "node_id": "R_kgDOExample",
            "name": arguments.get("repo", "repo"),
            "full_name": f"{arguments.get('owner', 'owner')}/{arguments.get('repo', 'repo')}",
            "private": False,
            "owner": {
                "login": arguments.get("owner", "owner"),
                "id": 123,
                "node_id": "U_kgDOExample",
                "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/example",
                "html_url": "https://github.com/example",
                "followers_url": "https://api.github.com/users/example/followers",
                "following_url": "https://api.github.com/users/example/following{/other_user}",
                "gists_url": "https://api.github.com/users/example/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/example/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/example/subscriptions",
                "organizations_url": "https://api.github.com/users/example/orgs",
                "repos_url": "https://api.github.com/users/example/repos",
                "events_url": "https://api.github.com/users/example/events{/privacy}",
                "received_events_url": "https://api.github.com/users/example/received_events",
                "type": "Organization",
                "site_admin": False,
            },
            "html_url": f"https://github.com/{arguments.get('owner', 'owner')}/{arguments.get('repo', 'repo')}",
            "description": "The tool framework for AI agents",
            "fork": False,
            "url": f"https://api.github.com/repos/{arguments.get('owner', 'owner')}/{arguments.get('repo', 'repo')}",
            "forks_url": "https://api.github.com/repos/example/repo/forks",
            "keys_url": "https://api.github.com/repos/example/repo/keys{/key_id}",
            "collaborators_url": "https://api.github.com/repos/example/repo/collaborators{/collaborator}",
            "teams_url": "https://api.github.com/repos/example/repo/teams",
            "hooks_url": "https://api.github.com/repos/example/repo/hooks",
            "issue_events_url": "https://api.github.com/repos/example/repo/issues/events{/number}",
            "events_url": "https://api.github.com/repos/example/repo/events",
            "assignees_url": "https://api.github.com/repos/example/repo/assignees{/user}",
            "branches_url": "https://api.github.com/repos/example/repo/branches{/branch}",
            "tags_url": "https://api.github.com/repos/example/repo/tags",
            "blobs_url": "https://api.github.com/repos/example/repo/git/blobs{/sha}",
            "git_tags_url": "https://api.github.com/repos/example/repo/git/tags{/sha}",
            "git_refs_url": "https://api.github.com/repos/example/repo/git/refs{/sha}",
            "trees_url": "https://api.github.com/repos/example/repo/git/trees{/sha}",
            "statuses_url": "https://api.github.com/repos/example/repo/statuses/{sha}",
            "languages_url": "https://api.github.com/repos/example/repo/languages",
            "stargazers_url": "https://api.github.com/repos/example/repo/stargazers",
            "contributors_url": "https://api.github.com/repos/example/repo/contributors",
            "subscribers_url": "https://api.github.com/repos/example/repo/subscribers",
            "subscription_url": "https://api.github.com/repos/example/repo/subscription",
            "commits_url": "https://api.github.com/repos/example/repo/commits{/sha}",
            "git_commits_url": "https://api.github.com/repos/example/repo/git/commits{/sha}",
            "comments_url": "https://api.github.com/repos/example/repo/comments{/number}",
            "issue_comment_url": "https://api.github.com/repos/example/repo/issues/comments{/number}",
            "contents_url": "https://api.github.com/repos/example/repo/contents/{+path}",
            "compare_url": "https://api.github.com/repos/example/repo/compare/{base}...{head}",
            "merges_url": "https://api.github.com/repos/example/repo/merges",
            "archive_url": "https://api.github.com/repos/example/repo/{archive_format}{/ref}",
            "downloads_url": "https://api.github.com/repos/example/repo/downloads",
            "issues_url": "https://api.github.com/repos/example/repo/issues{/number}",
            "pulls_url": "https://api.github.com/repos/example/repo/pulls{/number}",
            "milestones_url": "https://api.github.com/repos/example/repo/milestones{/number}",
            "notifications_url": "https://api.github.com/repos/example/repo/notifications{?since,all,participating}",
            "labels_url": "https://api.github.com/repos/example/repo/labels{/name}",
            "releases_url": "https://api.github.com/repos/example/repo/releases{/id}",
            "deployments_url": "https://api.github.com/repos/example/repo/deployments",
            "created_at": "2023-01-15T10:30:00Z",
            "updated_at": "2024-05-08T14:22:00Z",
            "pushed_at": "2024-05-08T12:00:00Z",
            "git_url": "git://github.com/example/repo.git",
            "ssh_url": "git@github.com:example/repo.git",
            "clone_url": "https://github.com/example/repo.git",
            "svn_url": "https://github.com/example/repo",
            "homepage": "https://example.com",
            "size": 12345,
            "stargazers_count": 4200,
            "watchers_count": 4200,
            "language": "Python",
            "forks_count": 350,
            "open_issues_count": 42,
            "master_branch": "main",
            "default_branch": "main",
            "score": 1.0,
        }

    if "GITHUB_LIST_ISSUES" in tool_slug:
        issues = []
        for i in range(5):
            issues.append(
                {
                    "id": 1000000 + i,
                    "node_id": f"I_kwDOExample{i}",
                    "url": f"https://api.github.com/repos/example/repo/issues/{i+1}",
                    "repository_url": "https://api.github.com/repos/example/repo",
                    "labels_url": f"https://api.github.com/repos/example/repo/issues/{i+1}/labels{{/name}}",
                    "comments_url": f"https://api.github.com/repos/example/repo/issues/{i+1}/comments",
                    "events_url": f"https://api.github.com/repos/example/repo/issues/{i+1}/events",
                    "html_url": f"https://github.com/example/repo/issues/{i+1}",
                    "number": i + 1,
                    "title": f"Issue #{i+1}: Login fails after OAuth redirect" if i == 0 else f"Issue #{i+1}: Something else",
                    "user": {
                        "login": f"user{i}",
                        "id": 1000 + i,
                        "avatar_url": f"https://avatars.githubusercontent.com/u/{1000+i}?v=4",
                        "gravatar_id": "",
                        "url": f"https://api.github.com/users/user{i}",
                        "html_url": f"https://github.com/user{i}",
                        "followers_url": f"https://api.github.com/users/user{i}/followers",
                        "following_url": f"https://api.github.com/users/user{i}/following{{/other_user}}",
                        "gists_url": f"https://api.github.com/users/user{i}/gists{{/gist_id}}",
                        "starred_url": f"https://api.github.com/users/user{i}/starred{{/owner}}{{/repo}}",
                        "subscriptions_url": f"https://api.github.com/users/user{i}/subscriptions",
                        "organizations_url": f"https://api.github.com/users/user{i}/orgs",
                        "repos_url": f"https://api.github.com/users/user{i}/repos",
                        "events_url": f"https://api.github.com/users/user{i}/events{{/privacy}}",
                        "received_events_url": f"https://api.github.com/users/user{i}/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "labels": [
                        {
                            "id": i,
                            "node_id": f"MDU6TGFiZWw{i}",
                            "url": f"https://api.github.com/repos/example/repo/labels/bug",
                            "name": "bug",
                            "color": "d73a4a",
                            "default": True,
                            "description": "Something isn't working",
                        }
                    ],
                    "state": "open",
                    "locked": False,
                    "assignee": None,
                    "assignees": [],
                    "milestone": None,
                    "comments": 3,
                    "created_at": "2024-05-01T10:00:00Z",
                    "updated_at": "2024-05-08T14:00:00Z",
                    "closed_at": None,
                    "author_association": "NONE",
                    "active_lock_reason": None,
                    "body": "Very long markdown body describing the issue in detail...\n\n## Steps to reproduce\n1. Go to login page\n2. Click OAuth\n3. Redirect succeeds but session cookie not set\n\n## Expected behavior\nUser should be logged in after redirect.",
                    "reactions": {
                        "url": f"https://api.github.com/repos/example/repo/issues/{i+1}/reactions",
                        "total_count": 2,
                        "+1": 1,
                        "-1": 0,
                        "laugh": 0,
                        "hooray": 0,
                        "confused": 0,
                        "heart": 0,
                        "rocket": 0,
                        "eyes": 1,
                    },
                    "timeline_url": f"https://api.github.com/repos/example/repo/issues/{i+1}/timeline",
                    "performed_via_github_app": None,
                    "state_reason": None,
                }
            )
        return issues

    # Fallback
    return {"message": "Simulated output", "tool": tool_slug, "args": arguments}


def main():
    parser = argparse.ArgumentParser(description="Aperture demo")
    parser.add_argument("--tool", required=True, help="Tool slug")
    parser.add_argument("--owner", default="composioHQ", help="Repo owner")
    parser.add_argument("--repo", default="composio", help="Repo name")
    parser.add_argument("--mode", default="medium", choices=["off", "low", "medium", "high"])
    parser.add_argument("--cache", action="store_true", help="Enable caching")
    args = parser.parse_args()

    run_id = str(uuid.uuid4())[:8]
    config = ApertureRunConfig(
        run_id=run_id,
        model="gpt-4o",
        effort_mode=args.mode,
        cache_bypass=not args.cache,
    )

    arguments = {"owner": args.owner, "repo": args.repo}
    if "LIST_ISSUES" in args.tool:
        arguments["state"] = "open"
        arguments["per_page"] = 5

    console.print(f"\n[bold blue]Aperture Demo[/bold blue] — run_id={run_id}, mode={args.mode}\n")

    # Baseline: raw tokens without Aperture
    executor = make_composio_executor(args.tool, arguments)
    raw_result = executor()
    raw_tokens = count_tokens(raw_result, config.model)

    console.print(f"[dim]Raw result type:[/dim] {type(raw_result).__name__}")
    console.print(f"[dim]Raw tokens:[/dim] {raw_tokens.tokens:,}")

    # With Aperture
    runner = ApertureRunner(config)
    result = runner.run_tool(
        tool_slug=args.tool,
        arguments=arguments,
        executor=executor,
        toolkit_slug="GITHUB",
    )

    compression = result["compression"]
    cache_event = result["cache_event"]

    # Display results
    table = Table(title="Aperture Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Mode", args.mode)
    table.add_row("Raw Tokens", f"{compression.raw_tokens:,}")
    table.add_row("Compressed Tokens", f"{compression.compressed_tokens:,}")
    table.add_row("Tokens Saved", f"{compression.tokens_saved:,}")
    table.add_row("Compression Ratio", f"{compression.compression_ratio:.1%}")
    table.add_row("Cache Status", cache_event.cache_status)
    table.add_row("Strategy", compression.strategy)

    console.print(table)

    if compression.omitted_fields:
        console.print(f"\n[dim]Omitted fields ({len(compression.omitted_fields)}):[/dim]")
        console.print(", ".join(compression.omitted_fields[:10]) + "..." if len(compression.omitted_fields) > 10 else "")

    # Run summary
    summary = runner.finish()
    console.print(f"\n[bold]Run Summary:[/bold]")
    console.print(f"  Total raw tokens: {summary.get('total_raw_tokens', 0):,}")
    console.print(f"  Total saved: {summary.get('total_tokens_saved', 0):,}")
    console.print(f"  Cache hits: {summary.get('cache_hits', 0)}")
    console.print(f"  API calls avoided: {summary.get('api_calls_avoided', 0)}")

    # Show cache hit if running again with same args
    if args.cache and cache_event.cache_status != "hit":
        console.print("\n[yellow]Running again to test cache...[/yellow]")
        runner2 = ApertureRunner(
            ApertureRunConfig(run_id=str(uuid.uuid4())[:8], model="gpt-4o", effort_mode=args.mode)
        )
        result2 = runner2.run_tool(
            tool_slug=args.tool,
            arguments=arguments,
            executor=executor,
            toolkit_slug="GITHUB",
        )
        if result2["cache_event"].cache_status == "hit":
            console.print("[green]✓ Cache hit! No API call made.[/green]")
        else:
            console.print("[red]✗ Cache miss[/red]")


if __name__ == "__main__":
    main()
