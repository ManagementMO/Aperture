# ISSUES

Local issue files from the root `issues/open/` directory are provided at start of context. Parse them to understand the open issues.

You will work on the AFK issues only, not the HITL ones.

**AFK** — tasks completable by writing code (features, tests, tooling, infra). Building an editor UI is AFK even if that editor will later be used for manual authoring.
**HITL** — tasks that require a human to manually operate a running tool or UI (e.g. "author these 10 bases in the editor"). These cannot be done by writing code alone.

You've also been passed a file containing the last few commits. Review these to understand what work has been done.

If all AFK tasks are complete, output <promise>NO MORE TASKS</promise>.

# TASK SELECTION

Pick the next task. Prioritize tasks in this order:

1. Critical bugfixes
2. Development infrastructure

Getting development infrastructure like tests and types and dev scripts ready is an important precursor to building features.

3. Tracer bullets for new features

Tracer bullets are small slices of functionality that go through all layers of the system, allowing you to test and validate your approach early. This helps in identifying potential issues and ensures that the overall architecture is sound before investing significant time in development.

TL;DR - build a tiny, end-to-end slice of the feature first, then expand it out.

4. Polish and quick wins
5. Refactors

# EXPLORATION

Explore the repo.

# IMPLEMENTATION

Use /tdd to complete the task.

# FEEDBACK LOOPS

Before committing, run the feedback loops:

- `pytest -m "not slow"` to run the fast tests (slow tests are reserved for CI)
- `pyright` to run the type checker
- `ruff check .` to run the linter

# COMMIT

Make a git commit. The commit message must:

1. Include key decisions made
2. Include files changed
3. Blockers or notes for next iteration
4. Include a trailing line `Closes #<N>` where `<N>` is the GitHub issue number read from the issue file's `**GitHub Issue:** #<N>` line. This auto-closes the corresponding GitHub Issue when the commit is pushed to `origin`.

# THE ISSUE

If the task is complete, move the issue file from `issues/open/` to `issues/done/`.

If the task is not complete, add a note to the issue file with what was done.

# FINAL RULES

ONLY WORK ON A SINGLE TASK.
