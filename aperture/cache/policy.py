"""Cache policy: deny-by-default with explicit allowlists."""

# Tools that are safe to cache (read-only, idempotent)
_CACHEABLE_TOOLS = {
    # GitHub
    "GITHUB_GET_REPO",
    "GITHUB_GET_A_REPOSITORY",
    "GITHUB_LIST_ISSUES",
    "GITHUB_LIST_REPOSITORY_ISSUES",
    "GITHUB_GET_ISSUE",
    "GITHUB_GET_AN_ISSUE",
    "GITHUB_LIST_PULL_REQUESTS",
    "GITHUB_FIND_PULL_REQUESTS",
    "GITHUB_GET_PULL_REQUEST",
    "GITHUB_LIST_COMMITS",
    "GITHUB_LIST_REPOSITORY_LANGUAGES",
    "GITHUB_GET_COMMIT",
    "GITHUB_LIST_BRANCHES",
    "GITHUB_GET_BRANCH",
    "GITHUB_LIST_REPOS",
    "GITHUB_SEARCH_REPOS",
    "GITHUB_GET_USER",
    "GITHUB_LIST_COLLABORATORS",
    "GITHUB_LIST_RELEASES",
    "GITHUB_GET_RELEASE",
    "GITHUB_LIST_TAGS",
    # Gmail
    "GMAIL_SEARCH_EMAILS",
    "GMAIL_FETCH_EMAILS",
    "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
    "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
    "GMAIL_LIST_THREADS",
    # Slack
    "SLACK_SEARCH_MESSAGES",
    "SLACK_LIST_CHANNELS",
    "SLACK_GET_CHANNEL",
    "SLACK_LIST_USERS",
    "SLACK_GET_USER",
    # Notion
    "NOTION_SEARCH_PAGES",
    "NOTION_GET_PAGE",
    "NOTION_LIST_DATABASES",
    "NOTION_QUERY_DATABASE",
    # Google Sheets
    "GOOGLESHEETS_BATCH_GET",
    "GOOGLESHEETS_GET_VALUE",
    "GOOGLESHEETS_GET_VALUES",
}

# Tools that must NEVER be cached
_NEVER_CACHE = {
    # Writes
    "GITHUB_CREATE_ISSUE",
    "GITHUB_UPDATE_ISSUE",
    "GITHUB_CREATE_PULL_REQUEST",
    "GITHUB_MERGE_PULL_REQUEST",
    "GMAIL_SEND_EMAIL",
    "GMAIL_BATCH_MODIFY_MESSAGES",
    "SLACK_POST_MESSAGE",
    "SLACK_UPDATE_MESSAGE",
    "NOTION_CREATE_PAGE",
    "NOTION_UPDATE_PAGE",
    # Auth
    "COMPOSIO_MANAGE_CONNECTIONS",
    "COMPOSIO_INITIATE_CONNECTION",
}


def is_cacheable(tool_slug: str) -> bool:
    """Return True if the tool is explicitly allowed to be cached."""
    if tool_slug in _NEVER_CACHE:
        return False
    return tool_slug in _CACHEABLE_TOOLS


def get_cache_scope(tool_slug: str) -> str:
    """Return the privacy scope required for a cacheable tool.

    Public repository metadata can be cached without a user/account scope. Most
    other reads may expose private or personalized data, so they require a
    connected account scope before a key can be built.
    """
    if tool_slug in {
        "GITHUB_GET_REPO",
        "GITHUB_GET_A_REPOSITORY",
        "GITHUB_SEARCH_REPOS",
    }:
        return "public"
    return "account"


def get_cache_ttl(tool_slug: str) -> int:
    """Return default TTL in seconds for a cacheable tool."""
    # Short TTL for volatile data
    if "SLACK" in tool_slug or "GMAIL" in tool_slug:
        return 60  # 1 minute
    if "GITHUB" in tool_slug and "LIST" in tool_slug:
        return 120  # 2 minutes
    if "GITHUB" in tool_slug:
        return 300  # 5 minutes
    return 300  # default 5 minutes
