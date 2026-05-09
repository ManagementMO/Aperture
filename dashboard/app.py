"""Streamlit dashboard for Aperture token-efficiency demo."""

import json
import uuid
from pathlib import Path

import streamlit as st

# Must be first Streamlit call
st.set_page_config(page_title="Aperture Dashboard", page_icon="🔭", layout="wide")

from aperture.contracts import ApertureRunConfig
from aperture.integration import ApertureRunner
from aperture.tokenization import count_tokens

st.title("🔭 Aperture — Context Engineering for Composio")
st.caption("Token-efficiency layer: measure, compact, compress, cache")

# --- Sidebar: Configuration ---
with st.sidebar:
    st.header("⚙️ Run Configuration")
    effort_mode = st.selectbox("Effort Mode", ["off", "low", "medium", "high"], index=2)
    use_cache = st.toggle("Enable Cache", value=True)
    model = st.selectbox("Model", ["gpt-4o", "gpt-4", "gpt-3.5-turbo"], index=0)

    st.divider()
    st.header("🛠️ Tool Selection")
    tool_family = st.selectbox("Tool Family", ["GitHub", "Gmail", "Slack"])

    if tool_family == "GitHub":
        tool_slug = st.selectbox(
            "Tool",
            ["GITHUB_GET_REPO", "GITHUB_LIST_ISSUES", "GITHUB_GET_ISSUE"],
        )
        owner = st.text_input("Owner", value="composioHQ")
        repo = st.text_input("Repo", value="composio")
        args = {"owner": owner, "repo": repo}
        if "LIST_ISSUES" in tool_slug:
            args["state"] = "open"
            args["per_page"] = 5

    elif tool_family == "Gmail":
        tool_slug = "GMAIL_SEARCH_EMAILS"
        args = {"query": "from:github", "max_results": 5}

    else:
        tool_slug = "SLACK_SEARCH_MESSAGES"
        args = {"query": "hello", "count": 5}

    run_button = st.button("🚀 Run with Aperture", type="primary", use_container_width=True)


# --- Simulated outputs ---
def simulate_output(tool_slug: str, arguments: dict):
    """Return realistic tool output for demo."""
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
        for i in range(arguments.get("per_page", 5)):
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

    return {"message": "Simulated output", "tool": tool_slug, "args": arguments}


# --- Main content ---
if run_button:
    run_id = str(uuid.uuid4())[:8]

    config = ApertureRunConfig(
        run_id=run_id,
        model=model,
        effort_mode=effort_mode,
        cache_bypass=not use_cache,
    )

    # Progress
    with st.spinner("Running Aperture..."):
        # Baseline
        raw_result = simulate_output(tool_slug, args)
        raw_tokens = count_tokens(raw_result, model)

        # Aperture run
        runner = ApertureRunner(config)

        def executor():
            return simulate_output(tool_slug, args)

        result = runner.run_tool(
            tool_slug=tool_slug,
            arguments=args,
            executor=executor,
            toolkit_slug=tool_family.upper(),
        )

        compression = result["compression"]
        cache_event = result["cache_event"]
        summary = runner.finish()

    # --- Metrics Cards ---
    st.subheader("📊 Results")

    cols = st.columns(4)
    with cols[0]:
        st.metric("Raw Tokens", f"{compression.raw_tokens:,}")
    with cols[1]:
        st.metric("Compressed Tokens", f"{compression.compressed_tokens:,}")
    with cols[2]:
        st.metric("Tokens Saved", f"{compression.tokens_saved:,}", delta=f"-{compression.compression_ratio:.0%}")
    with cols[3]:
        st.metric("Cache Status", cache_event.cache_status)

    # --- Token Waterfall ---
    st.subheader("🌊 Token Waterfall")

    waterfall_data = {
        "Raw Output": compression.raw_tokens,
        "Compressed Output": compression.compressed_tokens,
        "Saved": compression.tokens_saved,
    }

    st.bar_chart(waterfall_data)

    # --- Comparison ---
    st.subheader("🔍 Before vs After")

    tab1, tab2 = st.tabs(["Raw Output", "Compressed Output"])

    with tab1:
        st.json(raw_result, expanded=False)
        st.caption(f"{compression.raw_tokens:,} tokens")

    with tab2:
        st.json(compression.compressed_payload, expanded=False)
        st.caption(f"{compression.compressed_tokens:,} tokens")

    # --- Omitted Fields ---
    if compression.omitted_fields:
        with st.expander(f"🗑️ Omitted Fields ({len(compression.omitted_fields)})"):
            st.write(", ".join(compression.omitted_fields[:20]))
            if len(compression.omitted_fields) > 20:
                st.caption(f"... and {len(compression.omitted_fields) - 20} more")

    # --- Run Summary ---
    st.subheader("📋 Run Summary")
    st.json(summary)

    # --- Run Again for Cache Demo ---
    if use_cache and cache_event.cache_status != "hit":
        st.divider()
        if st.button("🔄 Run Again (Test Cache)", use_container_width=True):
            with st.spinner("Checking cache..."):
                runner2 = ApertureRunner(
                    ApertureRunConfig(
                        run_id=str(uuid.uuid4())[:8],
                        model=model,
                        effort_mode=effort_mode,
                    )
                )
                result2 = runner2.run_tool(
                    tool_slug=tool_slug,
                    arguments=args,
                    executor=executor,
                    toolkit_slug=tool_family.upper(),
                )

            if result2["cache_event"].cache_status == "hit":
                st.success("✅ Cache hit! No API call made. Result served from Redis in milliseconds.")
            else:
                st.error("❌ Cache miss — this shouldn't happen for identical calls.")

else:
    # Default state
    st.info("👈 Configure a tool run in the sidebar and click **Run with Aperture**")

    st.markdown("""
    ### What Aperture does

    1. **Measures** every token Composio adds to your context
    2. **Compacts** verbose tool schemas before they hit the model
    3. **Compresses** raw API outputs by 60-80%
    4. **Caches** safe repeated reads in Redis

    ### Demo tools
    - **GitHub**: `GITHUB_GET_REPO`, `GITHUB_LIST_ISSUES`
    - **Gmail**: `GMAIL_SEARCH_EMAILS`
    - **Slack**: `SLACK_SEARCH_MESSAGES`
    """)
