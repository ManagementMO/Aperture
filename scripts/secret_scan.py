"""Minimal repository secret scanner for pre-commit.

This intentionally targets the credential formats this repo has already
leaked. It is not a replacement for provider-side rotation or a full history
scan, but it blocks reintroducing live keys in ordinary commits.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


PATTERNS = {
    "Composio API key": re.compile(r"\bak_[A-Za-z0-9_-]{16,}\b"),
    "Anthropic API key": re.compile(r"\bsk-ant-api[0-9A-Za-z_-]{8,}\b"),
    "Composio connected account": re.compile(r"\bca__[A-Za-z0-9_-]{8,}\b"),
}

def _scan(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[str] = []
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{path}:{line}: possible {label}")
    return findings


def main(argv: list[str]) -> int:
    findings: list[str] = []
    for name in argv:
        findings.extend(_scan(Path(name)))
    if findings:
        print("Secret scan failed:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
