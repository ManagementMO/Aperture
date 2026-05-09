from aperture.benchmarks.metrics import aggregate_run_metrics
from aperture.types import BenchmarkMetrics, BenchmarkRunResult


def test_metrics_aggregate_correctly():
    metric = BenchmarkMetrics("t1", "raw", 100, 60, 40, 0.6, 1, 1, 5, True, 1.0, False, 0, False, 10)
    summary = aggregate_run_metrics(BenchmarkRunResult("raw", [metric]))
    assert summary["tokens_saved"] == 40
    assert summary["success_rate"] == 1.0

