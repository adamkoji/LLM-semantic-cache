import os
import time
import redis
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from .services import cache_manager, llm_provider, metrics_manager

app = FastAPI(title="Semantic Cache API")

# --- Redis Connection for Tier-1 Cache ---
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )
    redis_client.ping()
    print("Successfully connected to Redis.")
except Exception as e:
    print(f"Error connecting to Redis: {e}")
    redis_client = None

# --- Function to log cache misses ---
def log_cache_miss(prompt: str):
    """A simple file-based logger for cache misses."""
    try:
        with open("cache_misses.log", "a") as f:
            f.write(prompt + "\n")
    except Exception as e:
        print(f"Error logging cache miss: {e}")

# --- Pydantic Models ---
class PromptRequest(BaseModel):
    prompt: str

class WarmCacheRequest(BaseModel):
    prompt: str
    answer: str

# --- API Endpoints ---
@app.post("/process-prompt/")
def process_prompt(request: PromptRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    prompt = request.prompt
    embedding_time_ms = 0 # Initialize

    # --- TIER 1 CACHE CHECK: Redis (Exact Match) ---
    if redis_client:
        cached_response = redis_client.get(prompt)
        if cached_response:
            latency_ms = (time.time() - start_time) * 1000
            print("DEBUG: T1 EXACT-MATCH CACHE HIT!")
            metrics_manager.update_metrics(is_hit=True, latency_saved=max(0, 3500 - latency_ms))
            return {
                "response": cached_response, "from_cache": True, "cache_tier": 1,
                "latency_ms": latency_ms, "similarity": 1.0,
                "embedding_time_ms": 0 # No embedding was generated
            }

    # --- TIER 2 CACHE CHECK: ChromaDB (Semantic Match) ---
    cached_result, embedding_time_ms = cache_manager.find_in_semantic_cache(prompt)
    
    if cached_result:
        latency_ms = (time.time() - start_time) * 1000
        if redis_client:
            redis_client.set(prompt, cached_result["response"])
            print(f"DEBUG: Promoted prompt to T1 Redis cache.")
        metrics_manager.update_metrics(is_hit=True, latency_saved=max(0, 3500 - latency_ms))
        return {
            "response": cached_result["response"], "from_cache": True, "cache_tier": 2,
            "latency_ms": latency_ms, "similarity": cached_result.get("similarity", 0),
            "embedding_time_ms": embedding_time_ms
        }

    # --- TIER 3: LLM Call (Cache Miss) ---
    print("DEBUG: T1 & T2 Cache Miss. Calling LLM.")
    background_tasks.add_task(log_cache_miss, prompt)
    
    llm_response = llm_provider.get_llm_response(prompt)
    
    if cache_manager.is_response_high_quality(llm_response):
        if redis_client:
            redis_client.set(prompt, llm_response)
        cache_manager.add_to_semantic_cache(prompt, llm_response)
    
    latency_ms = (time.time() - start_time) * 1000
    metrics_manager.update_metrics(is_hit=False)

    return {
        "response": llm_response, "from_cache": False, "cache_tier": None,
        "latency_ms": latency_ms,
        "embedding_time_ms": embedding_time_ms
    }

@app.get("/metrics/")
def get_metrics_endpoint():
    return metrics_manager.get_metrics()

@app.post("/warm-cache/")
def warm_cache_endpoint(request: WarmCacheRequest):
    """Internal endpoint for proactive caching."""
    prompt = request.prompt
    answer = request.answer
    print(f"DEBUG: Received warming request for prompt: '{prompt}'")
    if redis_client:
        redis_client.set(prompt, answer)
    cache_manager.add_to_semantic_cache(prompt, answer)
    return {"status": "success", "message": f"Cache warmed for prompt: '{prompt}'"}

# --- NEW: Baseline Endpoints for Comparison ---

@app.post("/process-prompt-no-cache/")
def process_prompt_no_cache(request: PromptRequest):
    """Baseline endpoint that ALWAYS calls the LLM."""
    start_time = time.time()
    llm_response = llm_provider.get_llm_response(request.prompt)
    latency_ms = (time.time() - start_time) * 1000
    return {"response": llm_response, "from_cache": False, "latency_ms": latency_ms}

@app.post("/process-prompt-simple-cache/")
def process_prompt_simple_cache(request: PromptRequest):
    """Baseline endpoint with ONLY a simple, exact-match cache."""
    start_time = time.time()
    prompt = request.prompt
    
    if redis_client:
        cached_response = redis_client.get(prompt)
        if cached_response:
            latency_ms = (time.time() - start_time) * 1000
            return {"response": cached_response, "from_cache": True, "latency_ms": latency_ms}

    llm_response = llm_provider.get_llm_response(request.prompt)
    latency_ms = (time.time() - start_time) * 1000
    
    if redis_client:
        redis_client.set(prompt, llm_response)
        
    return {"response": llm_response, "from_cache": False, "latency_ms": latency_ms}