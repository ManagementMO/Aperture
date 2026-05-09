"""Rich, realistic mock tool outputs that mirror real Composio verbosity.

These payloads are intentionally large and nested — just like real Composio
responses — so Aperture's compression value is visible and meaningful."""

from __future__ import annotations

import random
from datetime import datetime, timedelta


def _rand_date(days_back: int = 90) -> str:
    dt = datetime.utcnow() - timedelta(days=random.randint(0, days_back))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _user(login: str, uid: int) -> dict:
    """A realistic GitHub user object — exactly what Composio returns."""
    return {
        "login": login,
        "id": uid,
        "node_id": f"U_kgDO{uid:08x}",
        "avatar_url": f"https://avatars.githubusercontent.com/u/{uid}?v=4",
        "gravatar_id": "",
        "url": f"https://api.github.com/users/{login}",
        "html_url": f"https://github.com/{login}",
        "followers_url": f"https://api.github.com/users/{login}/followers",
        "following_url": f"https://api.github.com/users/{login}/following{{/other_user}}",
        "gists_url": f"https://api.github.com/users/{login}/gists{{/gist_id}}",
        "starred_url": f"https://api.github.com/users/{login}/starred{{/owner}}{{/repo}}",
        "subscriptions_url": f"https://api.github.com/users/{login}/subscriptions",
        "organizations_url": f"https://api.github.com/users/{login}/orgs",
        "repos_url": f"https://api.github.com/users/{login}/repos",
        "events_url": f"https://api.github.com/users/{login}/events{{/privacy}}",
        "received_events_url": f"https://api.github.com/users/{login}/received_events",
        "type": "User",
        "site_admin": False,
    }


def _label(name: str, color: str, lid: int) -> dict:
    return {
        "id": lid,
        "node_id": f"MDU6TGFiZWw{lid}",
        "url": f"https://api.github.com/repos/composioHQ/composio/labels/{name}",
        "name": name,
        "color": color,
        "default": name in ("bug", "enhancement", "help wanted"),
        "description": f"{name} label",
    }


def github_repo(owner: str = "composioHQ", repo: str = "composio") -> dict:
    """Full GitHub GET /repos/{owner}/{repo} response — ~1,900 tokens."""
    rid = random.randint(100_000, 999_999)
    return {
        "id": rid,
        "node_id": f"R_kgDO{rid:08x}",
        "name": repo,
        "full_name": f"{owner}/{repo}",
        "private": False,
        "owner": _user("composioHQ", 149_123),
        "html_url": f"https://github.com/{owner}/{repo}",
        "description": "Composio powers 1000+ toolkits, tool search, context management, authentication, and a sandboxed workbench to help you build AI agents that turn intent into action.",
        "fork": False,
        "url": f"https://api.github.com/repos/{owner}/{repo}",
        "forks_url": f"https://api.github.com/repos/{owner}/{repo}/forks",
        "keys_url": f"https://api.github.com/repos/{owner}/{repo}/keys{{/key_id}}",
        "collaborators_url": f"https://api.github.com/repos/{owner}/{repo}/collaborators{{/collaborator}}",
        "teams_url": f"https://api.github.com/repos/{owner}/{repo}/teams",
        "hooks_url": f"https://api.github.com/repos/{owner}/{repo}/hooks",
        "issue_events_url": f"https://api.github.com/repos/{owner}/{repo}/issues/events{{/number}}",
        "events_url": f"https://api.github.com/repos/{owner}/{repo}/events",
        "assignees_url": f"https://api.github.com/repos/{owner}/{repo}/assignees{{/user}}",
        "branches_url": f"https://api.github.com/repos/{owner}/{repo}/branches{{/branch}}",
        "tags_url": f"https://api.github.com/repos/{owner}/{repo}/tags",
        "blobs_url": f"https://api.github.com/repos/{owner}/{repo}/git/blobs{{/sha}}",
        "git_tags_url": f"https://api.github.com/repos/{owner}/{repo}/git/tags{{/sha}}",
        "git_refs_url": f"https://api.github.com/repos/{owner}/{repo}/git/refs{{/sha}}",
        "trees_url": f"https://api.github.com/repos/{owner}/{repo}/git/trees{{/sha}}",
        "statuses_url": f"https://api.github.com/repos/{owner}/{repo}/statuses/{{sha}}",
        "languages_url": f"https://api.github.com/repos/{owner}/{repo}/languages",
        "stargazers_url": f"https://api.github.com/repos/{owner}/{repo}/stargazers",
        "contributors_url": f"https://api.github.com/repos/{owner}/{repo}/contributors",
        "subscribers_url": f"https://api.github.com/repos/{owner}/{repo}/subscribers",
        "subscription_url": f"https://api.github.com/repos/{owner}/{repo}/subscription",
        "commits_url": f"https://api.github.com/repos/{owner}/{repo}/commits{{/sha}}",
        "git_commits_url": f"https://api.github.com/repos/{owner}/{repo}/git/commits{{/sha}}",
        "comments_url": f"https://api.github.com/repos/{owner}/{repo}/comments{{/number}}",
        "issue_comment_url": f"https://api.github.com/repos/{owner}/{repo}/issues/comments{{/number}}",
        "contents_url": f"https://api.github.com/repos/{owner}/{repo}/contents/{{+path}}",
        "compare_url": f"https://api.github.com/repos/{owner}/{repo}/compare/{{base}}...{{head}}",
        "merges_url": f"https://api.github.com/repos/{owner}/{repo}/merges",
        "archive_url": f"https://api.github.com/repos/{owner}/{repo}/{{archive_format}}{{/ref}}",
        "downloads_url": f"https://api.github.com/repos/{owner}/{repo}/downloads",
        "issues_url": f"https://api.github.com/repos/{owner}/{repo}/issues{{/number}}",
        "pulls_url": f"https://api.github.com/repos/{owner}/{repo}/pulls{{/number}}",
        "milestones_url": f"https://api.github.com/repos/{owner}/{repo}/milestones{{/number}}",
        "notifications_url": f"https://api.github.com/repos/{owner}/{repo}/notifications{{?since,all,participating}}",
        "labels_url": f"https://api.github.com/repos/{owner}/{repo}/labels{{/name}}",
        "releases_url": f"https://api.github.com/repos/{owner}/{repo}/releases{{/id}}",
        "deployments_url": f"https://api.github.com/repos/{owner}/{repo}/deployments",
        "created_at": "2024-02-23T13:58:27Z",
        "updated_at": _rand_date(7),
        "pushed_at": _rand_date(2),
        "git_url": f"git://github.com/{owner}/{repo}.git",
        "ssh_url": f"git@github.com:{owner}/{repo}.git",
        "clone_url": f"https://github.com/{owner}/{repo}.git",
        "svn_url": f"https://github.com/{owner}/{repo}",
        "homepage": "https://composio.dev",
        "size": 45_832,
        "stargazers_count": 28_127,
        "watchers_count": 28_127,
        "language": "Python",
        "has_issues": True,
        "has_projects": True,
        "has_downloads": True,
        "has_wiki": True,
        "has_pages": True,
        "has_discussions": True,
        "forks_count": 4_553,
        "mirror_url": None,
        "archived": False,
        "disabled": False,
        "open_issues_count": 342,
        "license": {
            "key": "apache-2.0",
            "name": "Apache License 2.0",
            "spdx_id": "Apache-2.0",
            "url": "https://api.github.com/licenses/apache-2.0",
            "node_id": "MDc6TGljZW5zZTI=",
        },
        "allow_forking": True,
        "is_template": False,
        "web_commit_signoff_required": False,
        "topics": ["ai-agents", "tools", "composio", "llm", "automation", "mcp", "openapi", "api"],
        "visibility": "public",
        "forks": 4_553,
        "open_issues": 342,
        "watchers": 28_127,
        "default_branch": "next",
        "temp_clone_token": None,
        "custom_properties": {"vanta_production_branch_name": "master"},
        "organization": _user("composioHQ", 149_123),
        "network_count": 4_553,
        "subscribers_count": 412,
        "score": 1.0,
    }


def github_issues(owner: str = "composioHQ", repo: str = "composio", count: int = 5) -> list[dict]:
    """Full GitHub issue list — each issue is ~600 tokens, so 5 = ~3,000 tokens."""
    titles = [
        "OAuth redirect drops session cookie after GitHub login",
        "TypeError in tool router when schema has circular refs",
        "Slack webhook payload too large — truncated at 3000 chars",
        "Gmail search returns duplicate thread IDs intermittently",
        "Notion page properties missing after nested block update",
    ]
    issues = []
    for i in range(count):
        iid = 10_000 + i
        issues.append({
            "url": f"https://api.github.com/repos/{owner}/{repo}/issues/{iid}",
            "repository_url": f"https://api.github.com/repos/{owner}/{repo}",
            "labels_url": f"https://api.github.com/repos/{owner}/{repo}/issues/{iid}/labels{{/name}}",
            "comments_url": f"https://api.github.com/repos/{owner}/{repo}/issues/{iid}/comments",
            "events_url": f"https://api.github.com/repos/{owner}/{repo}/issues/{iid}/events",
            "html_url": f"https://github.com/{owner}/{repo}/issues/{iid}",
            "id": iid,
            "node_id": f"I_kwDO{iid:08x}",
            "number": iid,
            "title": titles[i],
            "user": _user(f"reporter{i}", 1_000_000 + i),
            "labels": [
                _label("bug", "d73a4a", i),
                _label("high-priority", "b60205", i + 100),
            ],
            "state": "open",
            "locked": False,
            "assignee": _user(f"maintainer{i % 3}", 2_000_000 + i),
            "assignees": [_user(f"maintainer{i % 3}", 2_000_000 + i)],
            "milestone": {
                "url": f"https://api.github.com/repos/{owner}/{repo}/milestones/{i + 1}",
                "html_url": f"https://github.com/{owner}/{repo}/milestones/v{i+1}.0",
                "labels_url": f"https://api.github.com/repos/{owner}/{repo}/milestones/{i+1}/labels",
                "id": i + 1,
                "node_id": f"MDk6TWlsZXN0b25l{i+1}",
                "number": i + 1,
                "title": f"v{i+1}.0 Release",
                "description": f"Target release for {titles[i].split()[0]} fixes",
                "creator": _user("composioHQ", 149_123),
                "open_issues": random.randint(3, 12),
                "closed_issues": random.randint(5, 30),
                "state": "open",
                "created_at": _rand_date(60),
                "updated_at": _rand_date(7),
                "due_on": None,
                "closed_at": None,
            },
            "comments": random.randint(2, 15),
            "created_at": _rand_date(30),
            "updated_at": _rand_date(5),
            "closed_at": None,
            "author_association": "NONE",
            "active_lock_reason": None,
            "body": f"""## Description
{titles[i]} — this is affecting production users.

## Environment
- Python 3.11
- composio-sdk 0.7.2
- OS: macOS 14 / Ubuntu 22.04

## Steps to Reproduce
1. Initialize Composio client
2. Call the relevant toolkit method
3. Observe the error

## Expected Behavior
The operation should complete without errors.

## Actual Behavior
Error traceback attached in comments.

## Additional Context
- Related to issue #{iid - 1}
- Affects ~{random.randint(10, 200)} users based on Sentry data
""",
            "reactions": {
                "url": f"https://api.github.com/repos/{owner}/{repo}/issues/{iid}/reactions",
                "total_count": random.randint(1, 8),
                "+1": random.randint(0, 3),
                "-1": random.randint(0, 1),
                "laugh": 0,
                "hooray": 0,
                "confused": random.randint(0, 2),
                "heart": random.randint(0, 2),
                "rocket": random.randint(0, 1),
                "eyes": random.randint(0, 3),
            },
            "timeline_url": f"https://api.github.com/repos/{owner}/{repo}/issues/{iid}/timeline",
            "performed_via_github_app": None,
            "state_reason": None,
        })
    return issues


def github_pull_requests(owner: str = "composioHQ", repo: str = "composio", count: int = 3) -> list[dict]:
    """Full GitHub PR list — each PR is ~700 tokens."""
    titles = [
        "feat: add retry logic with exponential backoff to HTTP client",
        "fix: handle null schema refs in OpenAPI parser",
        "docs: update MCP integration guide with new examples",
    ]
    prs = []
    for i in range(count):
        pid = 5_000 + i
        prs.append({
            "url": f"https://api.github.com/repos/{owner}/{repo}/pulls/{pid}",
            "id": pid,
            "node_id": f"PR_kwDO{pid:08x}",
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pid}",
            "diff_url": f"https://github.com/{owner}/{repo}/pull/{pid}.diff",
            "patch_url": f"https://github.com/{owner}/{repo}/pull/{pid}.patch",
            "issue_url": f"https://api.github.com/repos/{owner}/{repo}/issues/{pid}",
            "number": pid,
            "state": "open",
            "locked": False,
            "title": titles[i],
            "user": _user(f"contributor{i}", 3_000_000 + i),
            "body": f"## Summary\n{titles[i]}\n\n## Changes\n- Modified core parser\n- Added 12 new test cases\n- Updated documentation\n\n## Testing\n- [x] Unit tests pass\n- [x] Integration tests pass\n- [x] Manual QA verified\n\n## Breaking Changes\nNone.",
            "created_at": _rand_date(14),
            "updated_at": _rand_date(3),
            "closed_at": None,
            "merged_at": None,
            "merge_commit_sha": f"abc{pid:06x}",
            "assignee": _user("maintainer0", 2_000_000),
            "assignees": [_user("maintainer0", 2_000_000)],
            "requested_reviewers": [_user("reviewer0", 4_000_000), _user("reviewer1", 4_000_001)],
            "requested_teams": [],
            "labels": [_label("enhancement", "a2eeef", i + 200)],
            "milestone": None,
            "draft": False,
            "commits_url": f"https://api.github.com/repos/{owner}/{repo}/pulls/{pid}/commits",
            "review_comments_url": f"https://api.github.com/repos/{owner}/{repo}/pulls/{pid}/comments",
            "review_comment_url": f"https://api.github.com/repos/{owner}/{repo}/pulls/comments{{/number}}",
            "comments_url": f"https://api.github.com/repos/{owner}/{repo}/issues/{pid}/comments",
            "statuses_url": f"https://api.github.com/repos/{owner}/{repo}/statuses/{{sha}}",
            "head": {
                "label": f"{owner}:feature-branch-{i}",
                "ref": f"feature-branch-{i}",
                "sha": f"head{i:040x}",
                "user": _user("contributor0", 3_000_000),
                "repo": {
                    "id": 123_456,
                    "name": repo,
                    "full_name": f"{owner}/{repo}",
                    "private": False,
                    "owner": _user(owner, 149_123),
                    "html_url": f"https://github.com/{owner}/{repo}",
                    "description": "Agent toolkit framework",
                    "fork": False,
                    "url": f"https://api.github.com/repos/{owner}/{repo}",
                    "created_at": "2024-02-23T13:58:27Z",
                    "updated_at": _rand_date(7),
                    "pushed_at": _rand_date(2),
                    "homepage": "https://composio.dev",
                    "size": 45_832,
                    "stargazers_count": 28_127,
                    "watchers_count": 28_127,
                    "language": "Python",
                    "forks_count": 4_553,
                    "open_issues_count": 342,
                    "master_branch": "next",
                    "default_branch": "next",
                },
            },
            "base": {
                "label": f"{owner}:next",
                "ref": "next",
                "sha": f"base{i:040x}",
                "user": _user(owner, 149_123),
                "repo": {
                    "id": 123_456,
                    "name": repo,
                    "full_name": f"{owner}/{repo}",
                    "private": False,
                    "owner": _user(owner, 149_123),
                    "html_url": f"https://github.com/{owner}/{repo}",
                    "description": "Agent toolkit framework",
                    "fork": False,
                    "url": f"https://api.github.com/repos/{owner}/{repo}",
                    "created_at": "2024-02-23T13:58:27Z",
                    "updated_at": _rand_date(7),
                    "pushed_at": _rand_date(2),
                    "homepage": "https://composio.dev",
                    "size": 45_832,
                    "stargazers_count": 28_127,
                    "watchers_count": 28_127,
                    "language": "Python",
                    "forks_count": 4_553,
                    "open_issues_count": 342,
                    "master_branch": "next",
                    "default_branch": "next",
                },
            },
            "_links": {
                "self": {"href": f"https://api.github.com/repos/{owner}/{repo}/pulls/{pid}"},
                "html": {"href": f"https://github.com/{owner}/{repo}/pull/{pid}"},
                "issue": {"href": f"https://api.github.com/repos/{owner}/{repo}/issues/{pid}"},
                "comments": {"href": f"https://api.github.com/repos/{owner}/{repo}/issues/{pid}/comments"},
                "review_comments": {"href": f"https://api.github.com/repos/{owner}/{repo}/pulls/{pid}/comments"},
                "review_comment": {"href": f"https://api.github.com/repos/{owner}/{repo}/pulls/comments{{/number}}"},
                "commits": {"href": f"https://api.github.com/repos/{owner}/{repo}/pulls/{pid}/commits"},
                "statuses": {"href": f"https://api.github.com/repos/{owner}/{repo}/statuses/{{sha}}"},
            },
            "author_association": "CONTRIBUTOR",
            "auto_merge": None,
            "active_lock_reason": None,
        })
    return prs


def github_commits(owner: str = "composioHQ", repo: str = "composio", count: int = 5) -> list[dict]:
    """GitHub commit history — each commit ~400 tokens."""
    messages = [
        "Merge pull request #4521 from composioHQ/fix/oauth-session\n\nfix: preserve session cookie after OAuth redirect",
        "feat: add exponential backoff to all HTTP retries\n\n- Implements jittered exponential backoff\n- Max retry count configurable via env var\n- Adds 8 new test cases",
        "docs: update MCP server integration guide\n\n- New examples for StreamableHTTP transport\n- Troubleshooting section for auth errors",
        "refactor: extract schema optimizer into separate module\n\n- No functional changes\n- Improves testability\n- Reduces coupling between routing and compression",
        "chore: bump tiktoken to 0.8.0 and orjson to 3.10.0",
    ]
    commits = []
    for i in range(count):
        sha = f"{i:040x}"
        commits.append({
            "sha": sha,
            "node_id": f"C_kwDO{sha[:8]}",
            "commit": {
                "author": {
                    "name": f"Developer {i}",
                    "email": f"dev{i}@composio.dev",
                    "date": _rand_date(i),
                },
                "committer": {
                    "name": "GitHub",
                    "email": "noreply@github.com",
                    "date": _rand_date(i),
                },
                "message": messages[i],
                "tree": {
                    "sha": f"tree{i:040x}",
                    "url": f"https://api.github.com/repos/{owner}/{repo}/git/trees/tree{i:040x}",
                },
                "url": f"https://api.github.com/repos/{owner}/{repo}/git/commits/{sha}",
                "comment_count": random.randint(0, 4),
                "verification": {
                    "verified": True,
                    "reason": "valid",
                    "signature": f"-----BEGIN PGP SIGNATURE-----\n\niQIzBAABCgAdFiEE{i:08x}\n\n-----END PGP SIGNATURE-----",
                    "payload": f"tree tree{i:040x}\nparent parent{i:040x}\nauthor Developer {i} <dev{i}@composio.dev> {_rand_date(i)}\n\n{messages[i]}",
                },
            },
            "url": f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}",
            "html_url": f"https://github.com/{owner}/{repo}/commit/{sha}",
            "comments_url": f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/comments",
            "author": _user(f"developer{i}", 5_000_000 + i),
            "committer": _user("web-flow", 198_644),
            "parents": [{"sha": f"parent{i:040x}", "url": f"https://api.github.com/repos/{owner}/{repo}/commits/parent{i:040x}", "html_url": f"https://github.com/{owner}/{repo}/commit/parent{i:040x}"}],
        })
    return commits


def gmail_search(query: str = "composio", max_results: int = 3) -> list[dict]:
    """Gmail search results — each thread ~500 tokens."""
    subjects = [
        "Re: OAuth session issue — need your input",
        "Fwd: Composio v0.7.2 release notes",
        "Urgent: Schema validation failing on circular refs",
    ]
    threads = []
    for i in range(max_results):
        tid = f"thread_{i:08d}"
        mid = f"msg_{i:08d}"
        threads.append({
            "id": tid,
            "historyId": f"{i}",
            "messages": [
                {
                    "id": mid,
                    "threadId": tid,
                    "labelIds": ["INBOX", "IMPORTANT", "CATEGORY_UPDATES"],
                    "snippet": f"{subjects[i][:40]}...",
                    "payload": {
                        "partId": "",
                        "mimeType": "multipart/alternative",
                        "filename": "",
                        "headers": [
                            {"name": "Delivered-To", "value": "team@composio.dev"},
                            {"name": "From", "value": f"Sender {i} <sender{i}@example.com>"},
                            {"name": "To", "value": "team@composio.dev"},
                            {"name": "Subject", "value": subjects[i]},
                            {"name": "Date", "value": _rand_date(i * 3)},
                            {"name": "Message-Id", "value": f"<{mid}@mail.gmail.com>"},
                            {"name": "In-Reply-To", "value": f"<prev_{mid}@mail.gmail.com>"},
                            {"name": "References", "value": f"<root_{mid}@mail.gmail.com> <prev_{mid}@mail.gmail.com>"},
                            {"name": "Content-Type", "value": "multipart/alternative; boundary=\"boundary_{i}\""},
                        ],
                        "body": {"size": 0},
                        "parts": [
                            {
                                "partId": "0",
                                "mimeType": "text/plain",
                                "filename": "",
                                "headers": [{"name": "Content-Type", "value": "text/plain; charset=\"UTF-8\""}],
                                "body": {
                                    "size": 1_200 + i * 300,
                                    "data": f"SGVsbG8gdGVhbSxcblxuVGhpcyBpcyBhIHJlcGx5IHJlZ2FyZGluZyB7c3ViamVjdHNbaV19LiBQbGVhc2UgdGFrZSBhIGxvb2suXG5cbkJlc3QsXG5TZW5kZXIge2l9",
                                },
                            },
                            {
                                "partId": "1",
                                "mimeType": "text/html",
                                "filename": "",
                                "headers": [{"name": "Content-Type", "value": "text/html; charset=\"UTF-8\""}],
                                "body": {
                                    "size": 2_400 + i * 600,
                                    "data": f"PGh0bWw+PGJvZHk+PHA+SGVsbG8gdGVhbSw8L3A+PHA+VGhpcyBpcyBhIHJlcGx5IHJlZ2FyZGluZyB7c3ViamVjdHNbaV19LiBQbGVhc2UgdGFrZSBhIGxvb2suPC9wPjwvYm9keT48L2h0bWw+",
                                },
                            },
                        ],
                    },
                    "sizeEstimate": 4_000 + i * 1_000,
                    "historyId": f"{i}",
                    "internalDate": "1715241600000",
                }
            ],
        })
    return threads


def slack_messages(query: str = "composio", count: int = 4) -> list[dict]:
    """Slack search results — each message ~300 tokens."""
    texts = [
        "Has anyone seen the new MCP transport docs? Looks like we need to update our integration.",
        "The OAuth session bug is now P0 — @channel please prioritize. Customer is blocked.",
        "Just pushed the schema optimizer refactor. 12% faster parsing on large OpenAPI specs.",
        "Reminder: demo dry run at 3pm today. Please have your slides ready.",
    ]
    messages = []
    for i in range(count):
        ts = f"171524160{i}.000{random.randint(100, 999)}"
        messages.append({
            "type": "message",
            "user": f"U{random.randint(10000000, 99999999)}",
            "text": texts[i],
            "ts": ts,
            "team": f"T{random.randint(10000000, 99999999)}",
            "channel": {"id": f"C{random.randint(10000000, 99999999)}", "name": "engineering"},
            "permalink": f"https://composio.slack.com/archives/engineering/p{ts.replace('.', '')}",
            "attachments": [],
            "blocks": [
                {
                    "type": "rich_text",
                    "block_id": f"block_{i}",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": texts[i]}],
                        }
                    ],
                }
            ],
            "reactions": [
                {"name": "eyes", "users": [f"U{random.randint(10000000, 99999999)}"], "count": 1},
                {"name": "white_check_mark", "users": [f"U{random.randint(10000000, 99999999)}"], "count": 1},
            ],
            "reply_count": random.randint(0, 5),
            "reply_users": [f"U{random.randint(10000000, 99999999)}" for _ in range(random.randint(0, 3))],
            "reply_users_count": random.randint(0, 3),
            "latest_reply": ts,
            "subscribed": False,
            "last_read": ts,
            "unread_count": 0,
            "client_msg_id": f"{random.randint(10000000, 99999999)}-{random.randint(10000000, 99999999)}",
        })
    return messages
