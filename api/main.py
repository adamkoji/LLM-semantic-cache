import os
import time
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .services import cache_manager, llm_provider, metrics_manager, benchmark_service
import proactive_cacher

app = FastAPI(
    title="LLM Semantic Cache & Inference Optimization API",
    version="2.0.0",
    description="Multi-Tier Semantic Caching Architecture (Redis/In-Memory Tier-1 + ChromaDB Cosine Tier-2 + DBSCAN Proactive Warming)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Function to log cache misses ---
def log_cache_miss(prompt: str) -> None:
    """Appends a missed prompt to cache_misses.log for proactive DBSCAN clustering."""
    try:
        log_file = getattr(proactive_cacher, "LOG_FILE", "cache_misses.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(prompt.strip() + "\n")
    except Exception as e:
        print(f"Error logging cache miss: {e}")


# --- Pydantic Models ---
class PromptRequest(BaseModel):
    prompt: str


class WarmCacheRequest(BaseModel):
    prompt: str
    answer: str


class CacheConfigUpdateRequest(BaseModel):
    threshold: float | None = None
    max_size: int | None = None


class ProactiveWarmRequest(BaseModel):
    min_cluster_size: int = 3
    eps: float = 0.42


class BenchmarkRunRequest(BaseModel):
    num_prompts: int = 40
    reset_cache_first: bool = True


# --- Root & Health Endpoints ---
@app.get("/")
def root_endpoint():
    return health_endpoint()


@app.get("/health")
def health_endpoint():
    config = cache_manager.get_cache_config()
    return {
        "status": "healthy",
        "service": "LLM Semantic Cache API",
        "version": "2.0.0",
        "tier1": config["tier1"],
        "tier2": config["tier2"],
        "threshold": config["threshold"],
        "embedding_model": llm_provider.EMBEDDING_MODEL_NAME,
        "gemini_model_cascade": llm_provider.MODEL_CASCADE,
        "gemini_sdk_configured": llm_provider.genai_client is not None,
    }


# --- Core Inference & Semantic Cache Endpoint ---
@app.post("/process-prompt/")
def process_prompt(request: PromptRequest, background_tasks: BackgroundTasks):
    start_time = time.perf_counter()
    prompt = request.prompt
    norm_prompt = cache_manager.normalize_prompt(prompt)

    # --- GUARDRAIL #1: Temporal / Real-Time Query Bypass ---
    is_temporal, temporal_phrase = cache_manager.is_temporal_query(prompt)
    if is_temporal:
        llm_result = llm_provider.generate_llm_answer(prompt)
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        latency_sec = round(latency_ms / 1000.0, 4)

        metrics_manager.update_metrics(
            is_hit=False,
            cache_tier=None,
            latency_ms=latency_ms,
            embedding_time_ms=0.0,
            prompt=prompt,
            similarity=0.0,
            matched_prompt=None,
            guard_blocked=False,
            guard_reason=f"Temporal query bypass ('{temporal_phrase}')",
            temporal_bypass=True,
        )

        return {
            "response": llm_result["response"],
            "from_cache": False,
            "cache_tier": None,
            "latency_ms": latency_ms,
            "latency": latency_sec,
            "embedding_time_ms": 0,
            "similarity": 0.0,
            "matched_prompt": None,
            "guard_blocked": False,
            "guard_reason": f"Temporal query bypass ('{temporal_phrase}')",
            "temporal_bypass": True,
            "model": llm_result["model"],
            "pipeline_trace": {
                "normalized_prompt": norm_prompt,
                "temporal_bypass": True,
                "temporal_trigger": temporal_phrase,
                "tier1_checked": False,
                "tier2_checked": False,
                "llm_called": True,
            },
        }

    # --- TIER 1 CACHE CHECK: Exact Match (Redis / In-Memory Normalized SHA-256) ---
    t1_cached = cache_manager.get_from_tier1(prompt)
    if t1_cached is not None:
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        latency_sec = round(latency_ms / 1000.0, 4)
        print("DEBUG: T1 EXACT-MATCH CACHE HIT!")
        metrics_manager.update_metrics(
            is_hit=True,
            cache_tier=1,
            latency_ms=latency_ms,
            embedding_time_ms=0.0,
            prompt=prompt,
            similarity=1.0,
            matched_prompt=norm_prompt,
        )
        return {
            "response": t1_cached,
            "from_cache": True,
            "cache_tier": 1,
            "latency_ms": latency_ms,
            "latency": latency_sec,
            "similarity": 1.0,
            "matched_prompt": norm_prompt,
            "embedding_time_ms": 0,
            "guard_blocked": False,
            "guard_reason": None,
            "temporal_bypass": False,
            "model": "tier1-exact-cache",
            "pipeline_trace": {
                "normalized_prompt": norm_prompt,
                "temporal_bypass": False,
                "tier1_checked": True,
                "tier1_hit": True,
                "tier2_checked": False,
                "llm_called": False,
            },
        }

    # --- TIER 2 CACHE CHECK: ChromaDB Semantic Match + Entity/Negation Guardrail ---
    t2_detail = cache_manager.search_semantic_cache_detailed(prompt)
    embedding_time_ms = t2_detail["embedding_time_ms"]

    if t2_detail["hit"]:
        # Promote to Tier-1 for O(1) subsequent lookups
        cache_manager.set_in_tier1(prompt, t2_detail["response"])
        print("DEBUG: Promoted prompt to T1 cache.")
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        latency_sec = round(latency_ms / 1000.0, 4)

        metrics_manager.update_metrics(
            is_hit=True,
            cache_tier=2,
            latency_ms=latency_ms,
            embedding_time_ms=embedding_time_ms,
            prompt=prompt,
            similarity=t2_detail["similarity"],
            matched_prompt=t2_detail["matched_prompt"],
        )
        return {
            "response": t2_detail["response"],
            "from_cache": True,
            "cache_tier": 2,
            "latency_ms": latency_ms,
            "latency": latency_sec,
            "similarity": t2_detail["similarity"],
            "matched_prompt": t2_detail["matched_prompt"],
            "embedding_time_ms": embedding_time_ms,
            "guard_blocked": False,
            "guard_reason": None,
            "temporal_bypass": False,
            "model": "tier2-semantic-cache",
            "pipeline_trace": {
                "normalized_prompt": norm_prompt,
                "temporal_bypass": False,
                "tier1_checked": True,
                "tier1_hit": False,
                "tier2_checked": True,
                "tier2_hit": True,
                "promoted_to_tier1": True,
                "llm_called": False,
            },
        }

    # --- TIER 3: LLM Call (Cache Miss) ---
    print("DEBUG: T1 & T2 Cache Miss. Calling LLM.")
    log_cache_miss(prompt)

    llm_result = llm_provider.generate_llm_answer(prompt)
    llm_response = llm_result["response"]

    if cache_manager.is_response_high_quality(llm_response):
        cache_manager.set_in_tier1(prompt, llm_response)
        cache_manager.add_to_semantic_cache(prompt, llm_response, source="llm")

    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
    latency_sec = round(latency_ms / 1000.0, 4)

    metrics_manager.update_metrics(
        is_hit=False,
        cache_tier=None,
        latency_ms=latency_ms,
        embedding_time_ms=embedding_time_ms,
        prompt=prompt,
        similarity=t2_detail["similarity"],
        matched_prompt=t2_detail["matched_prompt"],
        guard_blocked=t2_detail["guard_blocked"],
        guard_reason=t2_detail["guard_reason"],
        temporal_bypass=False,
    )

    return {
        "response": llm_response,
        "from_cache": False,
        "cache_tier": None,
        "latency_ms": latency_ms,
        "latency": latency_sec,
        "embedding_time_ms": embedding_time_ms,
        "similarity": t2_detail["similarity"],
        "matched_prompt": t2_detail["matched_prompt"],
        "guard_blocked": t2_detail["guard_blocked"],
        "guard_reason": t2_detail["guard_reason"],
        "temporal_bypass": False,
        "model": llm_result["model"],
        "pipeline_trace": {
            "normalized_prompt": norm_prompt,
            "temporal_bypass": False,
            "tier1_checked": True,
            "tier1_hit": False,
            "tier2_checked": True,
            "tier2_hit": False,
            "guard_blocked": t2_detail["guard_blocked"],
            "guard_reason": t2_detail["guard_reason"],
            "llm_called": True,
        },
    }


# --- Metrics Endpoints ---
@app.get("/metrics/")
def get_metrics_endpoint():
    return metrics_manager.get_metrics()


@app.post("/metrics/reset")
def reset_metrics_endpoint():
    return metrics_manager.reset_metrics()


# --- Proactive Warming Endpoints ---
@app.post("/warm-cache/")
def warm_cache_endpoint(request: WarmCacheRequest):
    """Endpoint for proactive cache warming of both Tier-1 and Tier-2."""
    prompt = request.prompt
    answer = request.answer
    print(f"DEBUG: Received warming request for prompt: '{prompt}'")
    cache_manager.set_in_tier1(prompt, answer)
    doc_id = cache_manager.add_to_semantic_cache(prompt, answer, source="proactive_warm")
    metrics_manager.record_proactive_warm(1)
    return {
        "status": "success",
        "id": doc_id,
        "message": f"Cache warmed for prompt: '{prompt}'",
    }


@app.get("/cache/misses")
def get_cache_misses_endpoint():
    misses = proactive_cacher.get_missed_prompts()
    return {
        "count": len(misses),
        "missed_prompts": misses,
    }


@app.post("/cache/proactive-warm")
def trigger_proactive_warm_endpoint(request: ProactiveWarmRequest | None = None):
    min_cluster = request.min_cluster_size if request else proactive_cacher.MIN_CLUSTER_SIZE
    eps = request.eps if request else proactive_cacher.DBSCAN_EPS
    report = proactive_cacher.run_proactive_warming_pipeline(
        direct_mode=True,
        min_cluster_size=min_cluster,
        eps=eps,
    )
    return report


# --- Cache Configuration & Management Endpoints ---
@app.get("/cache/config")
def get_cache_config_endpoint():
    return cache_manager.get_cache_config()


@app.put("/cache/config")
def update_cache_config_endpoint(request: CacheConfigUpdateRequest):
    if request.threshold is not None:
        cache_manager.set_threshold(request.threshold)
    if request.max_size is not None:
        cache_manager.set_max_size(request.max_size)
    return cache_manager.get_cache_config()


@app.get("/cache/entries")
def list_cache_entries_endpoint(limit: int = 50):
    entries = cache_manager.list_cache_entries(limit=limit)
    return {
        "count": len(entries),
        "entries": entries,
    }


@app.delete("/cache/entries/{entry_id}")
def delete_cache_entry_endpoint(entry_id: str):
    deleted = cache_manager.delete_cache_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Cache entry '{entry_id}' not found.")
    return {"status": "deleted", "id": entry_id}


@app.delete("/cache/clear")
def clear_cache_endpoint():
    proactive_cacher.clear_missed_prompts()
    return cache_manager.clear_all_caches()


# --- Live Benchmark, Cold-Start & Resource Analytics Endpoints ---
@app.post("/benchmark/run")
def run_benchmark_endpoint(request: BenchmarkRunRequest | None = None):
    num_prompts = request.num_prompts if request else 40
    reset_first = request.reset_cache_first if request else True
    return benchmark_service.run_live_mechanism_comparison(
        num_prompts=num_prompts,
        reset_cache_first=reset_first,
    )


@app.get("/benchmark/resources")
def get_benchmark_resources_endpoint(num_entries: int = 100000, vector_dim: int = 384):
    return benchmark_service.calculate_resource_footprint(
        num_entries=num_entries,
        vector_dim=vector_dim,
    )


# --- Baseline Endpoints for Benchmark Comparison ---
@app.post("/process-prompt-no-cache/")
def process_prompt_no_cache(request: PromptRequest):
    """Baseline endpoint that ALWAYS calls the LLM."""
    start_time = time.perf_counter()
    llm_result = llm_provider.generate_llm_answer(request.prompt)
    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
    return {
        "response": llm_result["response"],
        "from_cache": False,
        "latency_ms": latency_ms,
        "latency": round(latency_ms / 1000.0, 4),
        "model": llm_result["model"],
    }


@app.post("/process-prompt-simple-cache/")
def process_prompt_simple_cache(request: PromptRequest):
    """Baseline endpoint with ONLY a simple, exact-match Tier-1 cache."""
    start_time = time.perf_counter()
    prompt = request.prompt

    cached_response = cache_manager.get_from_tier1(prompt)
    if cached_response is not None:
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        return {
            "response": cached_response,
            "from_cache": True,
            "cache_tier": 1,
            "latency_ms": latency_ms,
            "latency": round(latency_ms / 1000.0, 4),
        }

    llm_result = llm_provider.generate_llm_answer(prompt)
    llm_response = llm_result["response"]
    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

    cache_manager.set_in_tier1(prompt, llm_response)

    return {
        "response": llm_response,
        "from_cache": False,
        "cache_tier": None,
        "latency_ms": latency_ms,
        "latency": round(latency_ms / 1000.0, 4),
    }
