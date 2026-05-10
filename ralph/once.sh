#!/bin/bash

issues=$(cat issues/open/*.md 2>/dev/null || echo "No issues found")
commits=$(git log -n 5 --format="%H%n%ad%n%B---" --date=short 2>/dev/null || echo "No commits found")

{
  echo "Previous commits:"
  echo "$commits"
  echo
  echo "Issues:"
  echo "$issues"
  echo
  echo "Prompt:"
  cat ralph/prompt.md
} | claude -p --permission-mode acceptEdits