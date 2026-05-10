from pathlib import Path

from aperture.benchmarks.task_set import load_tasks


def test_tasks_load_from_jsonl_directory():
    tasks = load_tasks(Path("aperture/benchmarks/tasks"))
    assert len(tasks) >= 20
    assert {task.tool_slug for task in tasks}
