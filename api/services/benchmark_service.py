import os
import time
import random
from collections import deque
from . import cache_manager, llm_provider, metrics_manager

# Curated semantic clusters guaranteed to have high cosine similarity (>= 0.80) on BGE models
BENCHMARK_CLUSTERS = [
    [
        "What is machine learning?",
        "What is machine learning?",  # exact repeat
        "  what is machine learning?! ",  # normalized exact repeat
        "Can you explain machine learning to me?",  # semantic paraphrase
        "How does machine learning work and what is it?",  # semantic paraphrase
        "Explain the concept of machine learning",  # semantic paraphrase
    ],
    [
        "What is the capital of France?",
        "What is the capital of France?",  # exact repeat
        "what is the capital of france",  # normalized exact repeat
        "Tell me the capital city of France",  # semantic paraphrase
        "Which city is the capital of France?",  # semantic paraphrase
    ],
    [
        "How does a neural network work?",
        "How does a neural network work?",  # exact repeat
        "Can you explain how a neural network works?",  # semantic paraphrase
        "Describe how artificial neural networks work",  # semantic paraphrase
        "How do neural networks function?",  # semantic paraphrase
    ],
    [
        "What is photosynthesis?",
        "What is photosynthesis?",  # exact repeat
        "Can you explain photosynthesis simply?",  # semantic paraphrase
        "What is the biological process of photosynthesis?",  # semantic paraphrase
    ],
    [
        "What is the largest planet in our solar system?",
        "What is the largest planet in our solar system?",  # exact repeat
        "Which planet is the biggest in our solar system?",  # semantic paraphrase
        "What's the largest planet in the solar system?",  # semantic paraphrase
    ],
    [
        "How do I install Docker?",
        "How do I install Docker?",  # exact repeat
        "How can I install Docker on my system?",  # semantic paraphrase
        "What are the steps to install Docker?",  # semantic paraphrase
    ],
]

NOVEL_PROMPTS_POOL = [
    "What is the theory of relativity?",
    "Who wrote the tragedy of Hamlet?",
    "What is a central processing unit (CPU)?",
    "Explain quantum computing principles.",
    "What is the difference between Python and Java?",
    "How does the water cycle operate on Earth?",
    "What is the significance of the Rosetta Stone?",
    "Describe the double-helix structure of DNA.",
    "How do relational databases maintain ACID properties?",
    "What is the Fibonacci sequence in mathematics?",
]


def _build_benchmark_workload(num_prompts: int) -> list[str]:
    """
    Constructs a realistic, reproducible workload of `num_prompts` queries:
    - Phase A (Cold Start): Initial cluster seed queries + novel queries
    - Phase B (Warming): Mix of semantic paraphrases, exact repeats, and occasional novel queries
    - Phase C (Warm Steady-State): High ratio of semantic paraphrases and exact repeats
    """
    rng = random.Random(42)
    workload: list[str] = []

    # 1. Seed the first wave with the canonical first prompt of each cluster + a couple novel prompts
    for idx, cluster in enumerate(BENCHMARK_CLUSTERS):
        if len(workload) < num_prompts:
            workload.append(cluster[0])
        if idx % 2 == 1 and len(workload) < num_prompts:
            workload.append(NOVEL_PROMPTS_POOL[idx % len(NOVEL_PROMPTS_POOL)])

    # 2. Fill the remaining slots with a realistic ~78% clustered (paraphrases + exact repeats) / ~22% novel mix
    all_paraphrases_and_repeats: list[str] = []
    for cluster in BENCHMARK_CLUSTERS:
        all_paraphrases_and_repeats.extend(cluster[1:])

    novel_idx = 2
    cluster_idx = 0
    while len(workload) < num_prompts:
        step_pos = len(workload)
        # Every 5th prompt is a novel query; all others are paraphrases or exact repeats
        if step_pos % 5 == 4:
            base_novel = NOVEL_PROMPTS_POOL[novel_idx % len(NOVEL_PROMPTS_POOL)]
            novel_idx += 1
            workload.append(base_novel)
        else:
            candidate = all_paraphrases_and_repeats[cluster_idx % len(all_paraphrases_and_repeats)]
            cluster_idx += 1
            workload.append(candidate)

    return workload[:num_prompts]


def run_live_mechanism_comparison(
    num_prompts: int = 40,
    reset_cache_first: bool = True,
) -> dict:
    """
    Runs a live 3-way caching mechanism comparison and cold-start analysis:
    1. No-Cache Baseline (0% hit rate, full LLM latency & cost on every query)
    2. Simple Exact Cache (Tier-1 normalized exact-match only)
    3. 3-Tier Semantic Cache (Tier-1 Exact + Tier-2 ChromaDB Cosine + Tier-1 Promotion)
    """
    wall_start = time.perf_counter()
    num_prompts = max(15, min(120, int(num_prompts)))

    if reset_cache_first:
        cache_manager.clear_all_caches()
        metrics_manager.reset_metrics()

    workload = _build_benchmark_workload(num_prompts)
    rng = random.Random(101)

    # Cost model: ~$0.0005 per LLM call (~150 tokens total)
    COST_PER_LLM_CALL_USD = 0.0005

    # Tracking for System 1: No-Cache Baseline
    baseline_latencies: list[float] = []

    # Tracking for System 2: Simple Exact Cache (isolated set of normalized keys)
    simple_cache_store: dict[str, str] = {}
    simple_hits = 0
    simple_misses = 0
    simple_latencies: list[float] = []

    # Tracking for System 3: 3-Tier Hybrid Semantic Cache (uses live Tier-1 & Tier-2!)
    hybrid_t1_hits = 0
    hybrid_t2_hits = 0
    hybrid_misses = 0
    hybrid_latencies: list[float] = []

    timeline: list[dict] = []
    rolling_window = 8
    rolling_hybrid_buf: deque[float] = deque(maxlen=rolling_window)
    rolling_baseline_buf: deque[float] = deque(maxlen=rolling_window)

    # Temporarily bypass sleep inside llm_provider so benchmark completes in ~1-2s
    prev_sim_env = os.environ.get("SIMULATE_LLM_LATENCY")
    prev_fallback_env = os.environ.get("FORCE_FALLBACK_LLM")
    os.environ["SIMULATE_LLM_LATENCY"] = "false"
    os.environ["FORCE_FALLBACK_LLM"] = "true"

    try:
        for step_idx, prompt in enumerate(workload, start=1):
            norm_key = cache_manager.get_exact_cache_key(prompt)
            simulated_llm_ms = round(rng.uniform(650.0, 840.0), 2)

            # --- 1. No-Cache Baseline ---
            baseline_latencies.append(simulated_llm_ms)

            # --- 2. Simple Exact Cache (Tier-1 Only) ---
            if norm_key in simple_cache_store:
                tier1_only_hit = True
                simple_hits += 1
                simple_latencies.append(round(rng.uniform(0.35, 1.25), 2))
            else:
                tier1_only_hit = False
                simple_misses += 1
                simple_latencies.append(simulated_llm_ms)
                simple_cache_store[norm_key] = "cached"

            # --- 3. 3-Tier Hybrid Semantic Cache (Real Tier-1 + Real Tier-2 ChromaDB) ---
            t0 = time.perf_counter()
            t1_resp = cache_manager.get_from_tier1(prompt)
            if t1_resp is not None:
                real_t1_ms = max(0.25, round((time.perf_counter() - t0) * 1000.0, 2))
                hybrid_t1_hits += 1
                hybrid_tier = 1
                hybrid_lat_ms = real_t1_ms
                sim_score = 1.0
                metrics_manager.update_metrics(
                    is_hit=True,
                    cache_tier=1,
                    latency_ms=hybrid_lat_ms,
                    embedding_time_ms=0.0,
                    prompt=prompt,
                    similarity=1.0,
                    matched_prompt=cache_manager.normalize_prompt(prompt),
                )
            else:
                t2_res = cache_manager.search_semantic_cache_detailed(prompt)
                emb_ms = t2_res["embedding_time_ms"]
                if t2_res["hit"]:
                    cache_manager.set_in_tier1(prompt, t2_res["response"])
                    real_t2_ms = max(2.0, round((time.perf_counter() - t0) * 1000.0, 2))
                    hybrid_t2_hits += 1
                    hybrid_tier = 2
                    hybrid_lat_ms = real_t2_ms
                    sim_score = t2_res["similarity"]
                    metrics_manager.update_metrics(
                        is_hit=True,
                        cache_tier=2,
                        latency_ms=hybrid_lat_ms,
                        embedding_time_ms=emb_ms,
                        prompt=prompt,
                        similarity=sim_score,
                        matched_prompt=t2_res["matched_prompt"],
                    )
                else:
                    llm_out = llm_provider.generate_llm_answer(prompt)
                    ans = llm_out["response"]
                    cache_manager.set_in_tier1(prompt, ans)
                    cache_manager.add_to_semantic_cache(prompt, ans, source="benchmark")
                    hybrid_misses += 1
                    hybrid_tier = None
                    hybrid_lat_ms = round(simulated_llm_ms + emb_ms, 2)
                    sim_score = t2_res["similarity"]
                    metrics_manager.update_metrics(
                        is_hit=False,
                        cache_tier=None,
                        latency_ms=hybrid_lat_ms,
                        embedding_time_ms=emb_ms,
                        prompt=prompt,
                        similarity=sim_score,
                        matched_prompt=t2_res["matched_prompt"],
                        guard_blocked=t2_res["guard_blocked"],
                        guard_reason=t2_res["guard_reason"],
                    )

            hybrid_latencies.append(hybrid_lat_ms)
            rolling_hybrid_buf.append(hybrid_lat_ms)
            rolling_baseline_buf.append(simulated_llm_ms)

            timeline.append(
                {
                    "step": step_idx,
                    "prompt": prompt,
                    "tier1_only_hit": tier1_only_hit,
                    "hybrid_tier": hybrid_tier,
                    "hybrid_latency_ms": round(hybrid_lat_ms, 2),
                    "baseline_latency_ms": round(simulated_llm_ms, 2),
                    "rolling_hybrid_latency_ms": round(sum(rolling_hybrid_buf) / len(rolling_hybrid_buf), 2),
                    "rolling_baseline_latency_ms": round(sum(rolling_baseline_buf) / len(rolling_baseline_buf), 2),
                    "similarity": round(sim_score, 4),
                }
            )
    finally:
        if prev_sim_env is None:
            os.environ.pop("SIMULATE_LLM_LATENCY", None)
        else:
            os.environ["SIMULATE_LLM_LATENCY"] = prev_sim_env

        if prev_fallback_env is None:
            os.environ.pop("FORCE_FALLBACK_LLM", None)
        else:
            os.environ["FORCE_FALLBACK_LLM"] = prev_fallback_env

    # Compute aggregate metrics for the 3 systems
    baseline_avg_ms = round(sum(baseline_latencies) / num_prompts, 2)
    baseline_total_s = round(sum(baseline_latencies) / 1000.0, 2)
    baseline_cost = round(num_prompts * COST_PER_LLM_CALL_USD, 5)

    simple_hit_rate = round((simple_hits / num_prompts) * 100.0, 2)
    simple_avg_ms = round(sum(simple_latencies) / num_prompts, 2)
    simple_total_s = round(sum(simple_latencies) / 1000.0, 2)
    simple_cost = round(simple_misses * COST_PER_LLM_CALL_USD, 5)

    hybrid_total_hits = hybrid_t1_hits + hybrid_t2_hits
    hybrid_hit_rate = round((hybrid_total_hits / num_prompts) * 100.0, 2)
    hybrid_avg_ms = round(sum(hybrid_latencies) / num_prompts, 2)
    hybrid_total_s = round(sum(hybrid_latencies) / 1000.0, 2)
    hybrid_cost = round(hybrid_misses * COST_PER_LLM_CALL_USD, 5)

    api_calls_reduced_pct = round(((num_prompts - hybrid_misses) / num_prompts) * 100.0, 2)
    speedup_factor = round(baseline_avg_ms / max(1.0, hybrid_avg_ms), 2)
    cost_saved_pct = round(((baseline_cost - hybrid_cost) / max(1e-9, baseline_cost)) * 100.0, 2)
    semantic_uplift_pct = round(hybrid_hit_rate - simple_hit_rate, 2)

    systems = [
        {
            "name": "No-Cache Baseline",
            "hit_rate_percent": 0.0,
            "t1_hits": 0,
            "t2_hits": 0,
            "misses": num_prompts,
            "avg_latency_ms": baseline_avg_ms,
            "total_time_s": baseline_total_s,
            "llm_calls_made": num_prompts,
            "estimated_cost_usd": baseline_cost,
        },
        {
            "name": "Simple Exact Cache",
            "hit_rate_percent": simple_hit_rate,
            "t1_hits": simple_hits,
            "t2_hits": 0,
            "misses": simple_misses,
            "avg_latency_ms": simple_avg_ms,
            "total_time_s": simple_total_s,
            "llm_calls_made": simple_misses,
            "estimated_cost_usd": simple_cost,
        },
        {
            "name": "3-Tier Semantic Cache",
            "hit_rate_percent": hybrid_hit_rate,
            "t1_hits": hybrid_t1_hits,
            "t2_hits": hybrid_t2_hits,
            "misses": hybrid_misses,
            "avg_latency_ms": hybrid_avg_ms,
            "total_time_s": hybrid_total_s,
            "llm_calls_made": hybrid_misses,
            "estimated_cost_usd": hybrid_cost,
        },
    ]

    return {
        "num_prompts": num_prompts,
        "execution_wall_time_ms": round((time.perf_counter() - wall_start) * 1000.0, 2),
        "systems": systems,
        "summary": {
            "api_calls_reduced_percent": api_calls_reduced_pct,
            "speedup_factor": speedup_factor,
            "cost_saved_percent": cost_saved_pct,
            "semantic_uplift_over_simple_percent": semantic_uplift_pct,
        },
        "timeline": timeline,
    }


def calculate_resource_footprint(
    num_entries: int = 100000,
    vector_dim: int = 384,
) -> dict:
    """
    Calculates theoretical and live memory/storage footprints for Tier-1 (Redis)
    and Tier-2 (ChromaDB HNSW vector index + metadata) across scale tiers.
    """
    num_entries = max(1, int(num_entries))
    vector_dim = max(64, int(vector_dim))

    float_bytes = 4  # float32
    hnsw_overhead_factor = 1.5
    avg_prompt_bytes = 100
    avg_response_bytes = 800
    avg_metadata_overhead_bytes = 100
    doc_and_metadata_bytes = avg_prompt_bytes + avg_response_bytes + avg_metadata_overhead_bytes  # 1000 bytes

    raw_vector_bytes = vector_dim * float_bytes
    raw_vector_kb = raw_vector_bytes / 1024.0
    indexed_vector_kb = raw_vector_kb * hnsw_overhead_factor
    doc_metadata_kb = doc_and_metadata_bytes / 1024.0

    chromadb_kb_per_entry = indexed_vector_kb + doc_metadata_kb
    redis_kb_per_entry = (avg_prompt_bytes + avg_response_bytes) / 1024.0

    def _project(count: int) -> dict:
        chroma_mb = (chromadb_kb_per_entry * count) / 1024.0
        chroma_gb = chroma_mb / 1024.0
        redis_mb = (redis_kb_per_entry * count) / 1024.0
        redis_gb = redis_mb / 1024.0
        return {
            "entries": count,
            "chromadb_mb": round(chroma_mb, 2),
            "chromadb_gb": round(chroma_gb, 4),
            "redis_mb": round(redis_mb, 2),
            "redis_gb": round(redis_gb, 4),
        }

    proj_requested = _project(num_entries)
    proj_10k = _project(10_000)
    proj_100k = _project(100_000)
    proj_1m = _project(1_000_000)

    cfg = cache_manager.get_cache_config()

    return {
        "num_entries": num_entries,
        "vector_dim": vector_dim,
        "raw_vector_bytes": raw_vector_bytes,
        "raw_vector_kb": round(raw_vector_kb, 3),
        "hnsw_overhead_factor": hnsw_overhead_factor,
        "indexed_vector_kb": round(indexed_vector_kb, 3),
        "document_metadata_bytes": doc_and_metadata_bytes,
        "document_metadata_kb": round(doc_metadata_kb, 3),
        "chromadb_kb_per_entry": round(chromadb_kb_per_entry, 3),
        "redis_kb_per_entry": round(redis_kb_per_entry, 3),
        "total_kb_per_entry": round(chromadb_kb_per_entry, 3),
        "ram_mb": proj_requested["chromadb_mb"],
        "ram_gb": proj_requested["chromadb_gb"],
        "requested_scale": proj_requested,
        "scale_projections": {
            "10k": proj_10k,
            "100k": proj_100k,
            "1m": proj_1m,
        },
        "live_usage": {
            "tier1_backend": cfg["tier1"]["backend"],
            "tier1_entries": cfg["tier1"]["entries"],
            "tier2_backend": cfg["tier2"]["backend"],
            "tier2_entries": cfg["tier2"]["entries"],
        },
    }
