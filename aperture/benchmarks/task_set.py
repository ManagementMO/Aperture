"""Benchmark task loading."""

from __future__ import annotations

import json
from pathlib import Path

from aperture.types import BenchmarkTask


def load_tasks(path: Path) -> list[BenchmarkTask]:
    """Load benchmark tasks from a JSONL file or directory of JSONL files."""

    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    tasks: list[BenchmarkTask] = []
    for file_path in files:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                data = json.loads(stripped)
                tasks.append(
                    BenchmarkTask(
                        task_id=data["task_id"],
                        category=data["category"],
                        user_prompt=data["user_prompt"],
                        tool_slug=data["tool_slug"],
                        params=data.get("params", {}),
                        fixture=data["fixture"],
                        expected_fields=list(data.get("expected_fields", [])),
                        critical_fields=list(data.get("critical_fields", [])),
                        evaluation_type=data.get("evaluation_type", "field_presence"),
                    )
                )
    return tasks

