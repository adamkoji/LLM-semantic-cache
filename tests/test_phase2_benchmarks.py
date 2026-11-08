import os
import sys
import time
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["FORCE_FALLBACK_LLM"] = "true"
os.environ["SIMULATE_LLM_LATENCY"] = "false"

from api.main import app

client = TestClient(app)


def test_1_and_2_benchmark_run_and_mechanism_comparison():
    """
    1. POST /benchmark/run with {"num_prompts": 30, "reset_cache_first": true}
       returns 200 OK in under 10 seconds.
    2. Verify that in the returned systems data:
       - 3-Tier Semantic Cache has a strictly higher hit_rate_percent than Simple Exact Cache,
         which has a strictly higher hit_rate_percent than No-Cache Baseline (0%).
       - summary["api_calls_reduced_percent"] is >= 50.0 and summary["speedup_factor"] is > 2.0.
       - timeline contains 30 items with rolling_hybrid_latency_ms for the cold-start chart.
    """
    start_time = time.perf_counter()
    res = client.post(
        "/benchmark/run",
        json={"num_prompts": 30, "reset_cache_first": True},
    )
    elapsed_s = time.perf_counter() - start_time

    assert res.status_code == 200
    assert elapsed_s < 10.0, f"Benchmark took {elapsed_s:.2f}s (expected < 10s)"

    data = res.json()
    assert data["num_prompts"] == 30

    systems_by_name = {s["name"]: s for s in data["systems"]}
    assert "No-Cache Baseline" in systems_by_name
    assert "Simple Exact Cache" in systems_by_name
    assert "3-Tier Semantic Cache" in systems_by_name

    no_cache = systems_by_name["No-Cache Baseline"]
    simple_cache = systems_by_name["Simple Exact Cache"]
    semantic_cache = systems_by_name["3-Tier Semantic Cache"]

    assert no_cache["hit_rate_percent"] == 0.0
    assert simple_cache["hit_rate_percent"] > no_cache["hit_rate_percent"]
    assert semantic_cache["hit_rate_percent"] > simple_cache["hit_rate_percent"]
    assert semantic_cache["t2_hits"] > 0

    summary = data["summary"]
    assert summary["api_calls_reduced_percent"] >= 50.0
    assert summary["speedup_factor"] > 2.0
    assert summary["semantic_uplift_over_simple_percent"] > 0.0

    timeline = data["timeline"]
    assert len(timeline) == 30
    for idx, step_item in enumerate(timeline, start=1):
        assert step_item["step"] == idx
        assert "rolling_hybrid_latency_ms" in step_item
        assert "rolling_baseline_latency_ms" in step_item
        assert step_item["rolling_hybrid_latency_ms"] > 0


def test_3_benchmark_resources_calculator():
    """
    3. GET /benchmark/resources?num_entries=1000000&vector_dim=384 returns 200 OK
       with valid per-entry KB and 1M-scale GB calculations.
    """
    res = client.get("/benchmark/resources?num_entries=1000000&vector_dim=384")
    assert res.status_code == 200
    data = res.json()

    assert data["num_entries"] == 1_000_000
    assert data["vector_dim"] == 384
    assert data["raw_vector_bytes"] == 384 * 4  # 1536 bytes
    assert data["chromadb_kb_per_entry"] > 2.0
    assert data["redis_kb_per_entry"] > 0.5
    assert data["ram_gb"] > 1.5
    assert "1m" in data["scale_projections"]
    assert data["scale_projections"]["1m"]["chromadb_gb"] == data["ram_gb"]
    assert "live_usage" in data
