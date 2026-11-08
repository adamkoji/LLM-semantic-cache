import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure deterministic, fast offline execution during automated verification
os.environ["FORCE_FALLBACK_LLM"] = "true"
os.environ["SIMULATE_LLM_LATENCY"] = "false"

from api.main import app
from api.services import cache_manager

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_clean_state():
    """Resets caches and metrics once at the start of the test module."""
    client.delete("/cache/clear")
    client.post("/metrics/reset")
    cache_manager.set_threshold(0.78)
    yield


def test_1_cache_miss_and_miss_logging():
    """
    1. Cache Miss & Miss Logging:
    "What is machine learning?" -> from_cache == False, cache_tier is None,
    and prompt is logged in /cache/misses.
    """
    res = client.post("/process-prompt/", json={"prompt": "What is machine learning?"})
    assert res.status_code == 200
    data = res.json()
    assert data["from_cache"] is False
    assert data["cache_tier"] is None
    assert len(data["response"]) > 20
    assert "latency_ms" in data and "latency" in data

    misses_res = client.get("/cache/misses")
    assert misses_res.status_code == 200
    misses_data = misses_res.json()
    assert "What is machine learning?" in misses_data["missed_prompts"]


def test_2_tier1_normalized_exact_hit():
    """
    2. Tier-1 Normalized Exact Hit:
    "  what is machine learning?! " -> from_cache == True, cache_tier == 1,
    similarity == 1.0, embedding_time_ms == 0.
    """
    res = client.post("/process-prompt/", json={"prompt": "  what is machine learning?! "})
    assert res.status_code == 200
    data = res.json()
    assert data["from_cache"] is True
    assert data["cache_tier"] == 1
    assert data["similarity"] == 1.0
    assert data["embedding_time_ms"] == 0


def test_3_tier2_semantic_hit_and_tier1_promotion():
    """
    3. Tier-2 Semantic Hit + Tier-1 Promotion:
    "Can you explain machine learning to me?" -> from_cache == True, cache_tier == 2,
    similarity >= threshold, and repeating it immediately hits cache_tier == 1.
    """
    threshold = cache_manager.get_threshold()
    query = "Can you explain machine learning to me?"

    res1 = client.post("/process-prompt/", json={"prompt": query})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["from_cache"] is True
    assert data1["cache_tier"] == 2
    assert data1["similarity"] >= threshold
    assert data1["embedding_time_ms"] > 0

    # Immediate repeat should hit Tier-1 due to promotion
    res2 = client.post("/process-prompt/", json={"prompt": query})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["from_cache"] is True
    assert data2["cache_tier"] == 1
    assert data2["similarity"] == 1.0
    assert data2["embedding_time_ms"] == 0


def test_4_false_positive_guard_protection():
    """
    4. False-Positive Guard Protection:
    After caching "What is the capital of France?", asking "What is the capital of Germany?"
    AND after caching "How do I install Docker?", asking "How do I uninstall Docker?"
    MUST NOT falsely hit Tier-2 (from_cache == False).
    """
    # Seed France
    res_fr = client.post("/process-prompt/", json={"prompt": "What is the capital of France?"})
    assert res_fr.status_code == 200
    assert "Paris" in res_fr.json()["response"]

    # Query Germany -> must NOT hit France
    res_de = client.post("/process-prompt/", json={"prompt": "What is the capital of Germany?"})
    assert res_de.status_code == 200
    data_de = res_de.json()
    assert data_de["from_cache"] is False
    assert data_de["cache_tier"] is None
    assert data_de["guard_blocked"] is True
    assert "Berlin" in data_de["response"]

    # Seed Install Docker
    res_inst = client.post("/process-prompt/", json={"prompt": "How do I install Docker?"})
    assert res_inst.status_code == 200

    # Query Uninstall Docker -> must NOT hit Install Docker
    res_uninst = client.post("/process-prompt/", json={"prompt": "How do I uninstall Docker?"})
    assert res_uninst.status_code == 200
    data_uninst = res_uninst.json()
    assert data_uninst["from_cache"] is False
    assert data_uninst["cache_tier"] is None
    assert data_uninst["guard_blocked"] is True
    assert "uninstall" in data_uninst["response"].lower()


def test_5_temporal_query_bypass():
    """
    5. Temporal Query Bypass:
    Asking "What is the weather today in Delhi?" bypasses the cache
    (temporal_bypass == True, from_cache == False).
    """
    res1 = client.post("/process-prompt/", json={"prompt": "What is the weather today in Delhi?"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["temporal_bypass"] is True
    assert data1["from_cache"] is False
    assert data1["cache_tier"] is None

    # Asking a second time must STILL bypass the cache
    res2 = client.post("/process-prompt/", json={"prompt": "What is the weather today in Delhi?"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["temporal_bypass"] is True
    assert data2["from_cache"] is False


def test_6_proactive_cache_warming():
    """
    6. Proactive Cache Warming (/warm-cache/ & /cache/proactive-warm):
    Test that warming the cache with solar system queries clusters the misses via DBSCAN,
    generates a canonical Q&A + paraphrases, and populates the cache.
    """
    client.delete("/cache/clear")

    # Test direct /warm-cache/ endpoint first
    warm_res = client.post(
        "/warm-cache/",
        json={
            "prompt": "What is photosynthesis?",
            "answer": "Photosynthesis is the biochemical process by which plants convert sunlight into chemical energy.",
        },
    )
    assert warm_res.status_code == 200
    assert warm_res.json()["status"] == "success"

    # Send related solar system queries to generate cache misses in cache_misses.log
    solar_queries = [
        "what is the largest planet in our solar system?",
        "which planet is known for its rings?",
        "how many planets are in the solar system?",
        "describe the great red spot on jupiter",
    ]
    for q in solar_queries:
        r = client.post("/process-prompt/", json={"prompt": q})
        assert r.status_code == 200

    # Trigger DBSCAN proactive warming pipeline via /cache/proactive-warm
    proactive_res = client.post(
        "/cache/proactive-warm",
        json={"min_cluster_size": 3, "eps": 0.48},
    )
    assert proactive_res.status_code == 200
    report = proactive_res.json()
    assert report["status"] == "warmed"
    assert len(report["cluster_prompts"]) >= 3
    assert report["canonical_question"] is not None
    assert report["canonical_answer"] is not None
    assert len(report["paraphrases"]) >= 3
    assert report["entries_warmed"] >= 5

    # Verify a newly warmed paraphrase now hits the cache immediately
    paraphrase_to_test = report["paraphrases"][0]
    hit_res = client.post("/process-prompt/", json={"prompt": paraphrase_to_test})
    assert hit_res.status_code == 200
    assert hit_res.json()["from_cache"] is True


def test_7_baseline_and_management_endpoints():
    """
    7. Baseline & Management Endpoints:
    /process-prompt-no-cache/, /process-prompt-simple-cache/, /health, /metrics/,
    /cache/config, /cache/entries, and /cache/clear all return 200 OK.
    """
    # /health and /
    r_root = client.get("/")
    assert r_root.status_code == 200
    r_health = client.get("/health")
    assert r_health.status_code == 200
    health_data = r_health.json()
    assert health_data["status"] == "healthy"
    assert "gemini-3.8-flash" in health_data["gemini_model_cascade"]

    # /process-prompt-no-cache/
    r_nocache = client.post("/process-prompt-no-cache/", json={"prompt": "What is a CPU?"})
    assert r_nocache.status_code == 200
    assert r_nocache.json()["from_cache"] is False

    # /process-prompt-simple-cache/
    r_simple1 = client.post("/process-prompt-simple-cache/", json={"prompt": "Unique simple cache test prompt"})
    assert r_simple1.status_code == 200
    assert r_simple1.json()["from_cache"] is False

    r_simple2 = client.post("/process-prompt-simple-cache/", json={"prompt": "Unique simple cache test prompt"})
    assert r_simple2.status_code == 200
    assert r_simple2.json()["from_cache"] is True

    # /metrics/
    r_metrics = client.get("/metrics/")
    assert r_metrics.status_code == 200
    m_data = r_metrics.json()
    for required_key in (
        "cache_hits",
        "cache_misses",
        "total_requests",
        "total_latency_saved",
        "t1_hits",
        "t2_hits",
        "guard_blocks",
        "bypass_count",
        "proactive_warm_count",
        "recent_requests",
    ):
        assert required_key in m_data

    # /cache/config (GET & PUT)
    r_cfg = client.get("/cache/config")
    assert r_cfg.status_code == 200
    assert "threshold" in r_cfg.json()

    r_cfg_put = client.put("/cache/config", json={"threshold": 0.78, "max_size": 1000})
    assert r_cfg_put.status_code == 200
    assert r_cfg_put.json()["threshold"] == 0.78

    # /cache/entries & DELETE /cache/entries/{id}
    r_entries = client.get("/cache/entries")
    assert r_entries.status_code == 200
    entries_data = r_entries.json()
    assert "entries" in entries_data
    if entries_data["entries"]:
        first_id = entries_data["entries"][0]["id"]
        r_del = client.delete(f"/cache/entries/{first_id}")
        assert r_del.status_code == 200

    # /cache/clear
    r_clear = client.delete("/cache/clear")
    assert r_clear.status_code == 200
    assert r_clear.json()["status"] == "cleared"
