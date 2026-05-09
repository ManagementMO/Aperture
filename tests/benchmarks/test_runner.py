from pathlib import Path

from aperture.benchmarks.runner import run_benchmarks_from_path


def test_runner_supports_all_modes():
    runs = run_benchmarks_from_path(Path("aperture/benchmarks/tasks"), ["raw", "aperture_compressed", "aperture_cached", "aperture_full", "shadow"])
    assert [run.mode for run in runs] == ["raw", "aperture_compressed", "aperture_cached", "aperture_full", "shadow"]
    assert all(run.metrics for run in runs)

