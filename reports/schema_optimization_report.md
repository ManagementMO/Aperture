# Schema Savings Report

| Tool | Tokens Saved |
| --- | --- |
| GITHUB_LIST_REPOSITORY_ISSUES | 8 |
| GMAIL_SEARCH_EMAILS | 4 |
| SLACK_SEARCH_MESSAGES | 3 |
| NOTION_QUERY_DATABASE | 1 |


## Details

| Tool | Field | Original | Optimized | Saved | Accepted | Rejection |
| --- | --- | --- | --- | --- | --- | --- |
| GITHUB_LIST_REPOSITORY_ISSUES | description | 46 | 44 | 2 | True |  |
| NOTION_QUERY_DATABASE | description | 30 | 29 | 1 | True |  |
| SLACK_SEARCH_MESSAGES | description | 30 | 29 | 1 | True |  |
| GMAIL_SEARCH_EMAILS | description | 29 | 28 | 1 | True |  |
| GITHUB_LIST_REPOSITORY_ISSUES | parameters.properties.state.description | 15 | 15 | 0 | False | no_token_reduction |
| GMAIL_SEARCH_EMAILS | parameters.properties.query.description | 14 | 11 | 3 | True |  |
| GMAIL_SEARCH_EMAILS | parameters.properties.limit.description | 13 | 13 | 0 | False | no_token_reduction |
| GITHUB_LIST_REPOSITORY_ISSUES | parameters.properties.owner.description | 12 | 9 | 3 | True |  |
| GITHUB_LIST_REPOSITORY_ISSUES | parameters.properties.repo.description | 12 | 9 | 3 | True |  |
| SLACK_SEARCH_MESSAGES | parameters.properties.channel.description | 12 | 12 | 0 | False | no_token_reduction |
| NOTION_QUERY_DATABASE | parameters.properties.query.description | 11 | 11 | 0 | False | no_token_reduction |
| SLACK_SEARCH_MESSAGES | parameters.properties.query.description | 10 | 8 | 2 | True |  |
| NOTION_QUERY_DATABASE | parameters.properties.database_id.description | 8 | 8 | 0 | False | no_token_reduction |
