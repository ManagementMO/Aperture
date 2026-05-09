.PHONY: test benchmark reports

test:
	uv run pytest

benchmark:
	uv run aperture-benchmark --tasks aperture/benchmarks/tasks --out reports

reports: benchmark

