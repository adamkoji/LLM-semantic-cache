# This dictionary acts as a simple, in-memory database to store our metrics.
# For a real production application, you would use a more robust tool like
# Prometheus, but this is perfect for a self-contained demo.
METRICS = {
    "cache_hits": 0,
    "cache_misses": 0,
    "total_requests": 0,
    "total_latency_saved": 0.0,
}

def update_metrics(is_hit: bool, latency_saved: float = 0.0):
    """
    Updates the global metrics dictionary after each prompt is processed.
    
    Args:
        is_hit (bool): True if the response was a cache hit, False otherwise.
        latency_saved (float): An estimate of the time saved by hitting the cache.
    """
    METRICS["total_requests"] += 1
    if is_hit:
        METRICS["cache_hits"] += 1
        METRICS["total_latency_saved"] += latency_saved
    else:
        METRICS["cache_misses"] += 1

def get_metrics():
    """
    Returns the current state of the metrics dictionary.
    This is the function called by the /metrics/ endpoint in main.py.
    """
    return METRICS