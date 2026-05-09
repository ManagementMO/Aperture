from aperture.benchmarks.report import build_benchmark_report, write_benchmark_outputs
from aperture.types import BenchmarkMetrics, BenchmarkRunResult


def test_report_includes_token_and_quality_metrics(tmp_path):
    metric = BenchmarkMetrics("t1", "raw", 100, 60, 40, 0.6, 1, 1, 5, True, 1.0, False, 0, False, 10)
    run = BenchmarkRunResult("raw", [metric])
    report = build_benchmark_report([run])
    assert "tokens_saved" in report
    write_benchmark_outputs([run], tmp_path)
    assert (tmp_path / "benchmark_metrics.json").exists()
    assert (tmp_path / "benchmark_report.md").exists()

