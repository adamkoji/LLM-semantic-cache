from fastapi import FastAPI
from pydantic import BaseModel
import time
import os
import redis

from .services import cache_manager, llm_provider, metrics_manager

app = FastAPI(title="Semantic Cache API")

# --- NEW: Redis Connection for Tier-1 Cache ---
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True # Important to get strings back
    )
    redis_client.ping()
    print("Successfully connected to Redis.")
except Exception as e:
    print(f"Error connecting to Redis: {e}")
    redis_client = None

class PromptRequest(BaseModel):
    prompt: str

@app.post("/process-prompt/")
def process_prompt(request: PromptRequest):
    start_time = time.time()
    prompt = request.prompt

    # --- TIER 1 CACHE CHECK: Redis (Exact Match) ---
    if redis_client:
        cached_response = redis_client.get(prompt)
        if cached_response:
            end_time = time.time()
            latency = end_time - start_time
            print("DEBUG: T1 EXACT-MATCH CACHE HIT!")
            metrics_manager.update_metrics(is_hit=True, latency_saved=max(0, 2.5 - latency))
            return {
                "response": cached_response,
                "from_cache": True, "cache_tier": 1,
                "latency": latency, "similarity": 1.0
            }

    # --- TIER 2 CACHE CHECK: ChromaDB (Semantic Match) ---
    cached_result = cache_manager.find_in_semantic_cache(prompt)
    if cached_result:
        end_time = time.time()
        latency = end_time - start_time
        # Promote to Tier 1 cache for faster future access
        if redis_client:
            redis_client.set(prompt, cached_result["response"])
        metrics_manager.update_metrics(is_hit=True, latency_saved=max(0, 2.5 - latency))
        return {
            "response": cached_result["response"],
            "from_cache": True, "cache_tier": 2,
            "latency": latency, "similarity": cached_result.get("similarity", 0)
        }

    # --- TIER 3: LLM Call (Cache Miss) ---
    print("DEBUG: T1 & T2 Cache Miss. Calling LLM.")
    llm_response = llm_provider.get_llm_response(prompt)
    
    # --- Cache Admission & Population ---
    if cache_manager.is_response_high_quality(llm_response):
        # Add to both caches for future requests
        if redis_client:
            redis_client.set(prompt, llm_response)
        cache_manager.add_to_semantic_cache(prompt, llm_response)
    
    end_time = time.time()
    latency = end_time - start_time
    metrics_manager.update_metrics(is_hit=False)

    return {
        "response": llm_response,
        "from_cache": False, "cache_tier": None,
        "latency": latency
    }

@app.get("/metrics/")
def get_metrics_endpoint():
    return metrics_manager.get_metrics()