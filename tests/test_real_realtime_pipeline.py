"""
tests/test_real_realtime_pipeline.py — Functional tests for realtime pipeline.

Tests real working real-time streaming:
- EventQueue: priority-based queue
- PipelineStage: individual stages
- RealtimePipeline: multi-stage streaming
- MetricsCollector: metrics collection
- AnomalyDetector: anomaly detection
- PerformanceBenchmark: performance benchmarks
"""
import sys
import pytest
import importlib.util
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rt = load_module("FRIDAY/apps/core/src/friday_core/real_realtime_pipeline.py", "realtime")


class TestEventQueue:
    def test_enqueue_dequeue(self):
        q = rt.EventQueue()
        q.enqueue("test", {"data": 1}, priority=5)
        q.enqueue("test", {"data": 2}, priority=10)

        assert q.size() == 2
        first = q.dequeue()
        assert first.priority == 10  # Higher priority first
        assert first.data["data"] == 2

        second = q.dequeue()
        assert second.priority == 5
        assert second.data["data"] == 1

        assert q.dequeue() is None

    def test_queue_stats(self):
        q = rt.EventQueue()
        q.enqueue("test", {}, priority=5)
        q.enqueue("test", {}, priority=3)
        q.dequeue()

        stats = q.stats()
        assert stats["queued"] == 1
        assert stats["processed"] == 1
        assert stats["total"] == 2

    def test_max_size(self):
        q = rt.EventQueue(max_size=3)
        for i in range(5):
            q.enqueue("test", {"i": i}, priority=5)
        assert q.size() == 3  # Should cap at max_size


class TestPipelineStage:
    def test_successful_stage(self):
        stage = rt.PipelineStage("test", lambda et, d: {"processed": True})
        event = rt.QueuedEvent("evt_1", "test", {}, 5, time.time())
        result = stage.process(event)
        assert result.success is True
        assert result.result["processed"] is True

    def test_failing_stage(self):
        stage = rt.PipelineStage("test", lambda et, d: 1/0)
        event = rt.QueuedEvent("evt_1", "test", {}, 5, time.time())
        result = stage.process(event)
        assert result.success is False
        assert result.error


class TestRealtimePipeline:
    def test_single_stage(self):
        pipeline = rt.RealtimePipeline()
        pipeline.add_stage("test", lambda et, d: {"result": et})

        results = pipeline.process_event("test_event", {"key": "value"})
        assert len(results) == 1
        assert results[0].success is True

    def test_multi_stage(self):
        pipeline = rt.RealtimePipeline()
        pipeline.add_stage("stage1", lambda et, d: {"stage1": True})
        pipeline.add_stage("stage2", lambda et, d: {"stage2": True})
        pipeline.add_stage("stage3", lambda et, d: {"stage3": True})

        results = pipeline.process_event("test", {})
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_batch_process(self):
        pipeline = rt.RealtimePipeline()
        pipeline.add_stage("test", lambda et, d: {"ok": True})

        events = [{"type": f"event_{i}", "data": {"i": i}} for i in range(10)]
        results = pipeline.batch_process(events)
        assert len(results) == 10

    def test_metrics(self):
        pipeline = rt.RealtimePipeline()
        pipeline.add_stage("test", lambda et, d: {"ok": True})
        pipeline.process_event("test", {})
        pipeline.process_event("test", {})

        metrics = pipeline.get_metrics()
        assert metrics["total_events"] == 2
        assert metrics["total_processed"] == 2
        assert metrics["stages"] == 1


class TestMetricsCollector:
    def test_record_and_stats(self):
        collector = rt.MetricsCollector()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            collector.record("test", v)

        stats = collector.get_stats("test")
        assert stats["count"] == 5
        assert stats["mean"] == 3.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["std"] > 0

    def test_multiple_metrics(self):
        collector = rt.MetricsCollector()
        collector.record("m1", 1.0)
        collector.record("m2", 10.0)

        all_stats = collector.get_all_stats()
        assert "m1" in all_stats
        assert "m2" in all_stats


class TestAnomalyDetector:
    def test_normal_data(self):
        detector = rt.AnomalyDetector(window_size=50, threshold=2.0)
        values = [100 + random.uniform(-2, 2) for _ in range(50)]
        anomalies = [detector.update(v) for v in values]
        anomaly_count = sum(1 for a in anomalies if a)
        assert anomaly_count < 5  # Should have very few anomalies

    def test_anomalous_data(self):
        detector = rt.AnomalyDetector(window_size=50, threshold=2.0)
        # Normal data
        for _ in range(50):
            detector.update(100.0)
        # Anomaly
        is_anomaly = detector.update(200.0)
        assert is_anomaly is True

    def test_get_anomalies(self):
        detector = rt.AnomalyDetector(window_size=50, threshold=2.0)
        for _ in range(50):
            detector.update(100.0)
        detector.update(500.0)
        detector.update(500.0)

        anomalies = detector.get_anomalies()
        assert len(anomalies) >= 2
        assert anomalies[0]["value"] == 500.0


class TestPerformanceBenchmark:
    def test_decision_engine_benchmark(self):
        bench = rt.PerformanceBenchmark()
        result = bench.benchmark_decision_engine(iterations=10)
        assert result["operations"] == 10
        assert result["ops_per_second"] > 0
        assert result["avg_ms"] >= 0

    def test_trading_engine_benchmark(self):
        bench = rt.PerformanceBenchmark()
        result = bench.benchmark_trading_engine(iterations=10)
        assert result["operations"] == 10
        assert result["ops_per_second"] > 0

    def test_security_engine_benchmark(self):
        bench = rt.PerformanceBenchmark()
        result = bench.benchmark_security_engine(iterations=10)
        assert result["operations"] == 10
        assert result["ops_per_second"] > 0

    def test_forecast_engine_benchmark(self):
        bench = rt.PerformanceBenchmark()
        result = bench.benchmark_forecast_engine(iterations=10)
        assert result["operations"] == 10
        assert result["ops_per_second"] > 0

    def test_all_benchmarks(self):
        bench = rt.PerformanceBenchmark()
        results = bench.run_all_benchmarks()
        assert len(results) == 5
        assert all("ops_per_second" in r for r in results.values())
